from dataclasses import dataclass
from enum import StrEnum


class FeatureSlug(StrEnum):
    MEMBERS = "members"
    ROLES = "roles"
    MEDIA = "media"
    # RECRUITMENT = "recruitment"
    # ATTENDANCE = "attendance"


@dataclass(frozen=True)
class FeatureInfo:
    name: str
    base_path: str
    description: str


# Source of truth for features. The slug is stored in the database, so changing
# a slug value requires a data migration. Run `cli sync-features` after editing.
FEATURES: dict[FeatureSlug, FeatureInfo] = {
    FeatureSlug.MEMBERS: FeatureInfo("Members", "/members", "Invite members and manage their roles"),
    FeatureSlug.ROLES: FeatureInfo("Roles", "/roles", "Custom roles and their permissions"),
    FeatureSlug.MEDIA: FeatureInfo("Media", "/media", "Scan local folders of candidate resumes"),
    # FeatureSlug.RECRUITMENT: FeatureInfo("Recruitment", "/recruitment", "Candidates and hiring pipeline"),
    # FeatureSlug.ATTENDANCE: FeatureInfo("Attendance", "/attendance", "Employee check-in and check-out"),
}

DEFAULT_ACTIONS: tuple[str, ...] = ("create", "read", "update", "delete")
