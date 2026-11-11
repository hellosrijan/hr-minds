from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import get_current_user, require
from hr_minds.auth.models import Membership, Role, User
from hr_minds.auth.schemas import (
    FeatureRead,
    InvitationCreate,
    InvitationRead,
    MemberRead,
    MemberUpdate,
    OrgRead,
    RoleCreate,
    RoleRead,
    RoleUpdate,
)
from hr_minds.auth.services import rbac
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug

router = APIRouter(tags=["RBAC"])

ROLES = FeatureSlug.ROLES
MEMBERS = FeatureSlug.MEMBERS


def _org_read(membership: Membership) -> OrgRead:
    return OrgRead(
        id=membership.organization.public_id,
        name=membership.organization.name,
        is_owner=membership.is_owner,
        role=membership.role,
    )


# --- Features ---


@router.get("/features", response_model=list[FeatureRead], summary="List Features")
async def list_features(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Features and the actions that can be granted on each, for building roles."""
    return [
        FeatureRead(
            slug=f.slug,
            name=f.name,
            description=f.description,
            actions=[p.action for p in f.permissions],
        )
        for f in await rbac.list_features(db)
    ]


# --- Organizations ---


@router.get("/orgs", response_model=list[OrgRead], summary="List My Organizations")
async def list_orgs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Organizations the current user belongs to, with their role in each."""
    return [_org_read(m) for m in await Membership.list_for_user(db, user.id)]


# --- Roles, members, invitations ---
# These act on the organization in the X-Org-Id header (default: your own), see require().

# --- Roles ---


@router.get("/roles", response_model=list[RoleRead], summary="List Roles")
async def list_roles(
    membership: Membership = Depends(require(ROLES, "read")),
    db: AsyncSession = Depends(get_db),
):
    return await Role.list_for_org(db, membership.org_id)


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Role",
)
async def create_role(
    data: RoleCreate,
    membership: Membership = Depends(require(ROLES, "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a custom role. You can only grant permissions you hold yourself.

    Raises: **403** escalation, **409** duplicate name, **422** unknown feature/action.
    """
    return await rbac.create_role(db, membership, data)


@router.get("/roles/{role_id}", response_model=RoleRead, summary="Get Role")
async def get_role(
    role_id: int,
    membership: Membership = Depends(require(ROLES, "read")),
    db: AsyncSession = Depends(get_db),
):
    return await rbac.get_role(db, membership.org_id, role_id)


@router.patch("/roles/{role_id}", response_model=RoleRead, summary="Update Role")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    membership: Membership = Depends(require(ROLES, "update")),
    db: AsyncSession = Depends(get_db),
):
    """Rename a role or replace its permissions. Omitted fields are unchanged."""
    return await rbac.update_role(db, membership, role_id, data)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Role",
)
async def delete_role(
    role_id: int,
    membership: Membership = Depends(require(ROLES, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a role. Fails with **409** while members still have it; pending invitations are dropped."""
    await rbac.delete_role(db, membership, role_id)


# --- Members ---


@router.get("/members", response_model=list[MemberRead], summary="List Members")
async def list_members(
    membership: Membership = Depends(require(MEMBERS, "read")),
    db: AsyncSession = Depends(get_db),
):
    return await Membership.list_for_org(db, membership.org_id)


@router.patch(
    "/members/{user_id}", response_model=MemberRead, summary="Change Member Role"
)
async def change_member_role(
    user_id: int,
    data: MemberUpdate,
    membership: Membership = Depends(require(MEMBERS, "update")),
    db: AsyncSession = Depends(get_db),
):
    """Assign a different role. The owner and your own membership can't be changed."""
    return await rbac.change_member_role(db, membership, user_id, data.role_id)


@router.delete(
    "/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Member",
)
async def remove_member(
    user_id: int,
    membership: Membership = Depends(require(MEMBERS, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await rbac.remove_member(db, membership, user_id)


# --- Invitations ---


@router.post(
    "/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Invite Member",
)
async def invite(
    data: InvitationCreate,
    request: Request,
    membership: Membership = Depends(require(MEMBERS, "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite someone by email with a role. Works for existing and new users.
    No email is sent yet: share the returned `accept_url` with the invitee.
    It is shown only once and expires in 7 days.
    """
    invitation, token = await rbac.invite(db, membership, data)
    return InvitationRead(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        accept_url=str(request.url_for("accept_invitation", token=token)),
    )


@router.post(
    "/invitations/{token}/accept",
    response_model=OrgRead,
    summary="Accept Invitation",
)
async def accept_invitation(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join the inviting organization. You must be logged in with the invited email."""
    return _org_read(await rbac.accept_invitation(db, user, token))
