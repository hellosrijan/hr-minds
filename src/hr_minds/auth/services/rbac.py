"""
Business logic for features, roles, members and invitations.

Escalation rule used throughout: a non-owner may only grant, edit, delete or
assign permissions they hold themselves, and may only manage members whose
current role they could have granted. Owners pass every check.
"""

import logging
import secrets
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hr_minds.auth.exceptions import (
    AlreadyMember,
    CannotModifyMember,
    InvitationNotFound,
    MemberNotFound,
    PrivilegeEscalation,
    RoleInUse,
    RoleNameTaken,
    RoleNotFound,
    UnknownPermission,
)
from hr_minds.auth.models import Feature, Invitation, Membership, Permission, Role, User
from hr_minds.auth.schemas import InvitationCreate, PermissionGrant, RoleCreate, RoleUpdate
from hr_minds.settings.features import DEFAULT_ACTIONS, FEATURES

logger = logging.getLogger(__name__)

INVITATION_TTL = timedelta(days=7)


# --- Features ---


async def sync_features(db: AsyncSession) -> list[str]:
    """
    Upsert FEATURES and their DEFAULT_ACTIONS into the database. Safe to rerun.
    Features no longer in code are left alone (deleting them would strip role
    grants) and returned so the caller can report them.
    """
    for slug, info in FEATURES.items():
        values = {"name": info.name, "base_path": info.base_path, "description": info.description}
        feature_id = await db.scalar(
            insert(Feature)
            .values(slug=slug, **values)
            .on_conflict_do_update(index_elements=[Feature.slug], set_={**values, "modified": func.now()})
            .returning(Feature.id)
        )
        await db.execute(
            insert(Permission)
            .values([{"feature_id": feature_id, "action": a} for a in DEFAULT_ACTIONS])
            .on_conflict_do_nothing()
        )
    stale = list(await db.scalars(select(Feature.slug).where(Feature.slug.not_in(list(FEATURES)))))
    await db.commit()
    return stale


async def list_features(db: AsyncSession) -> list[Feature]:
    return list(
        await db.scalars(
            select(Feature).options(selectinload(Feature.permissions)).order_by(Feature.slug)
        )
    )


# --- Escalation guard ---


def _keys(permissions: Iterable[Permission]) -> set[tuple[str, str]]:
    return {(p.feature.slug, p.action) for p in permissions}


def check_grantable(membership: Membership, permissions: Iterable[Permission]) -> None:
    """Raise PrivilegeEscalation unless the caller holds every one of `permissions`."""
    if not membership.is_owner and _keys(permissions) - membership.grants():
        raise PrivilegeEscalation()


async def resolve_permissions(db: AsyncSession, grants: list[PermissionGrant]) -> list[Permission]:
    """Turn [{feature, actions}] into Permission rows. Raises UnknownPermission if any is missing."""
    wanted = {(str(g.feature), a) for g in grants for a in g.actions}
    if not wanted:
        return []
    rows = list(
        await db.scalars(
            select(Permission)
            .join(Permission.feature)
            .where(tuple_(Feature.slug, Permission.action).in_(wanted))
        )
    )
    if len(rows) != len(wanted):
        raise UnknownPermission()
    return rows


# --- Roles ---


async def get_role(db: AsyncSession, org_id: int, role_id: int) -> Role:
    role = await Role.get(db, org_id, role_id)
    if role is None:
        raise RoleNotFound()
    return role


async def _commit_role(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise RoleNameTaken from exc


async def create_role(db: AsyncSession, membership: Membership, data: RoleCreate) -> Role:
    permissions = await resolve_permissions(db, data.permissions)
    check_grantable(membership, permissions)
    role = Role(
        org_id=membership.org_id,
        name=data.name,
        description=data.description,
        permissions=permissions,
    )
    db.add(role)
    await _commit_role(db)
    return role


async def update_role(
    db: AsyncSession, membership: Membership, role_id: int, data: RoleUpdate
) -> Role:
    role = await get_role(db, membership.org_id, role_id)
    check_grantable(membership, role.permissions)
    fields = data.model_dump(exclude_unset=True, exclude={"permissions"})
    for name, value in fields.items():
        setattr(role, name, value)
    if data.permissions is not None:
        permissions = await resolve_permissions(db, data.permissions)
        check_grantable(membership, permissions)
        role.permissions = permissions
    await _commit_role(db)
    return role


async def delete_role(db: AsyncSession, membership: Membership, role_id: int) -> None:
    role = await get_role(db, membership.org_id, role_id)
    check_grantable(membership, role.permissions)
    await db.delete(role)
    try:
        await db.commit()
    except IntegrityError as exc:  # membership.role_id is ON DELETE RESTRICT
        await db.rollback()
        raise RoleInUse from exc


# --- Members ---


async def _get_manageable_member(db: AsyncSession, membership: Membership, user_id: int) -> Membership:
    target = await Membership.get(db, membership.org_id, user_id)
    if target is None:
        raise MemberNotFound()
    if target.is_owner or target.user_id == membership.user_id:
        raise CannotModifyMember()
    check_grantable(membership, target.role.permissions if target.role else [])
    return target


async def change_member_role(
    db: AsyncSession, membership: Membership, user_id: int, role_id: int
) -> Membership:
    target = await _get_manageable_member(db, membership, user_id)
    role = await get_role(db, membership.org_id, role_id)
    check_grantable(membership, role.permissions)
    target.role = role
    await db.commit()
    return target


async def remove_member(db: AsyncSession, membership: Membership, user_id: int) -> None:
    target = await _get_manageable_member(db, membership, user_id)
    await db.delete(target)
    await db.commit()


# --- Invitations ---


async def invite(
    db: AsyncSession, membership: Membership, data: InvitationCreate
) -> tuple[Invitation, str]:
    """Create an invitation and return it with the raw token. The token is not stored."""
    role = await get_role(db, membership.org_id, data.role_id)
    check_grantable(membership, role.permissions)

    email = str(data.email).lower()
    already = await db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == membership.org_id, User.email == email)
    )
    if already is not None:
        raise AlreadyMember()

    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        org_id=membership.org_id,
        role=role,
        invited_by_id=membership.user_id,
        email=email,
        token_hash=Invitation.hash_token(token),
        expires_at=datetime.now(timezone.utc) + INVITATION_TTL,
    )
    db.add(invitation)
    await db.commit()
    return invitation, token


async def accept_invitation(db: AsyncSession, user: User, token: str) -> Membership:
    """Join the invitation's organization. The invitation must be for this user's email."""
    invitation = await Invitation.get_pending(db, token)
    if invitation is None or invitation.email != user.email:
        raise InvitationNotFound()

    membership = Membership(org_id=invitation.org_id, user_id=user.id, role_id=invitation.role_id)
    db.add(membership)
    invitation.accepted_at = func.now()
    try:
        await db.commit()
    except IntegrityError as exc:  # unique (org_id, user_id)
        await db.rollback()
        raise AlreadyMember from exc
    await db.refresh(membership, ["organization", "role"])  # async can't lazy-load them later
    return membership
