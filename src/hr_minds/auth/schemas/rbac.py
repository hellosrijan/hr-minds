from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from hr_minds.auth.schemas.auth import UserRead
from hr_minds.settings.features import FeatureSlug


class FeatureRead(BaseModel):
    """A feature and the actions a role can be granted on it."""

    slug: str
    name: str
    description: str | None
    actions: list[str]


class PermissionGrant(BaseModel):
    """Actions granted on one feature, e.g. {"feature": "media", "actions": ["read"]}."""

    feature: FeatureSlug
    actions: list[str] = Field(min_length=1)


class RoleCreate(BaseModel):
    """Request body for POST /roles."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[PermissionGrant] = []


class RoleUpdate(BaseModel):
    """Request body for PATCH /roles/{role_id}. Omitted fields are unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[PermissionGrant] | None = None


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class RoleRead(RoleSummary):
    description: str | None
    permissions: list[PermissionGrant]

    @field_validator("permissions", mode="before")
    @classmethod
    def group_by_feature(cls, permissions: list) -> list[dict]:
        """Turn the role's Permission rows into one entry per feature."""
        grouped: dict[str, list[str]] = {}
        for p in permissions:
            grouped.setdefault(p.feature.slug, []).append(p.action)
        return [{"feature": f, "actions": a} for f, a in grouped.items()]


class OrgRead(BaseModel):
    """An organization the current user belongs to, and their place in it."""

    id: str  # public id, e.g. org_srijan_k3x9p2m7qa; send it as the X-Org-Id header
    name: str
    is_owner: bool
    role: RoleSummary | None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserRead
    role: RoleSummary | None
    is_owner: bool
    created: datetime


class MemberUpdate(BaseModel):
    role_id: int


class InvitationCreate(BaseModel):
    email: EmailStr
    role_id: int


class InvitationRead(BaseModel):
    """Returned once, when the invitation is created. Share `accept_url` with the invitee."""

    id: int
    email: str
    role: RoleSummary
    expires_at: datetime
    accept_url: str
