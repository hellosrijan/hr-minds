"""
Command-line tools for the auth module.

Usage:
    uv run python -m hr_minds.auth.cli create-superuser \
        --email you@example.com --first-name First --last-name Last
    uv run python -m hr_minds.auth.cli sync-features
"""

import argparse
import asyncio
import getpass
import sys

from hr_minds.auth.exceptions import EmailAlreadyRegistered
from hr_minds.auth.schemas import UserRegister
from hr_minds.auth.services import register_user
from hr_minds.auth.services.rbac import sync_features
from hr_minds.settings.db import AsyncSessionLocal

MIN_PASSWORD_LENGTH = 8


async def _create_superuser(email: str, first_name: str, last_name: str, password: str) -> int:
    data = UserRegister(email=email, first_name=first_name, last_name=last_name, password=password)
    async with AsyncSessionLocal() as db:
        try:
            user = await register_user(db, data, is_superuser=True)
        except EmailAlreadyRegistered:
            print(f"Error: a user with email {email} already exists.", file=sys.stderr)
            return 1

    print(f"Superuser created: {user.email}")
    return 0


async def _sync_features() -> int:
    async with AsyncSessionLocal() as db:
        stale = await sync_features(db)
    print("Features synced.")
    if stale:
        print(f"Warning: in the database but not in FEATURES: {', '.join(stale)}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hr_minds.auth.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-superuser", help="Create a superuser account")
    create.add_argument("--email", required=True)
    create.add_argument("--first-name", required=True)
    create.add_argument("--last-name", required=True)

    subparsers.add_parser("sync-features", help="Sync FEATURES into the database")

    args = parser.parse_args(argv)
    if args.command == "sync-features":
        return asyncio.run(_sync_features())

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
