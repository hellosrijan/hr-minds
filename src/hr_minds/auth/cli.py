"""
Command-line tools for the auth module.

Usage:
    uv run python -m hr_minds.auth.cli create-superuser \
        --email you@example.com --first-name First --last-name Last
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from hr_minds.auth.models import User
from hr_minds.settings.db import AsyncSessionLocal

MIN_PASSWORD_LENGTH = 8


async def _create_superuser(email: str, first_name: str, last_name: str, password: str) -> int:
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(select(User.id).where(User.email == email.lower()))
        if exists is not None:
            print(f"Error: a user with email {email} already exists.", file=sys.stderr)
            return 1

        user = User(
            email=email.lower(),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_superuser=True,
        )
        user.set_password(password)
        db.add(user)
        await db.commit()

    print(f"Superuser created: {email.lower()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hr_minds.auth.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-superuser", help="Create a superuser account")
    create.add_argument("--email", required=True)
    create.add_argument("--first-name", required=True)
    create.add_argument("--last-name", required=True)

    args = parser.parse_args(argv)

    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Error: password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Password (again): "):
        print("Error: passwords do not match.", file=sys.stderr)
        return 1

    return asyncio.run(
        _create_superuser(args.email, args.first_name, args.last_name, password)
    )


if __name__ == "__main__":
    sys.exit(main())
