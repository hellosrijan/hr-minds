from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from hr_minds.settings.db import Base, TimestampMixin


# class User(Base, TimestampMixin):
#     email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
