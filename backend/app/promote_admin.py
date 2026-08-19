"""Grants (or revokes) admin access for an existing user. Deliberately not
an API endpoint - rules.md §1.12 treats authorization as server-owned,
deterministic state with no self-serve path; this is an operator-run
script against the database directly, the same trust boundary as running
a migration.

Usage:
    python -m app.promote_admin user@example.com
    python -m app.promote_admin user@example.com --revoke
"""

import sys

from app.core.db import SessionLocal
from app.repositories import user_repository


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage: python -m app.promote_admin <email> [--revoke]")
        sys.exit(1)

    email = args[0]
    revoke = "--revoke" in args[1:]

    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, email)
        if user is None:
            print(f'No user found with email "{email}".')
            sys.exit(1)

        user.is_admin = not revoke
        db.commit()
        print(f'{email} is {"no longer" if revoke else "now"} an admin.')
    finally:
        db.close()


if __name__ == "__main__":
    main()
