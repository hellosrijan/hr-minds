from dataclasses import dataclass
from enum import StrEnum


class FeatureSlug(StrEnum):
    AUTH = "auth"
    MEDIA = "media"
    # RECRUITMENT = "recruitment"
    # ATTENDANCE = "attendance"


@dataclass(frozen=True)
class FeatureInfo:
    name: str
    base_path: str
    description: str


# Source of truth for features. The slug is stored in the database, so changing
# a slug value requires a data migration.
FEATURES: dict[FeatureSlug, FeatureInfo] = {
    FeatureSlug.AUTH: FeatureInfo("Authentication", "/auth", "Users, login and role management"),
    FeatureSlug.MEDIA: FeatureInfo("Media", "/media", "Resume and document uploads"),
    # FeatureSlug.RECRUITMENT: FeatureInfo("Recruitment", "/recruitment", "Candidates and hiring pipeline"),
    # FeatureSlug.ATTENDANCE: FeatureInfo("Attendance", "/attendance", "Employee check-in and check-out"),
}

DEFAULT_ACTIONS: tuple[str, ...] = ("create", "read", "update", "delete")
