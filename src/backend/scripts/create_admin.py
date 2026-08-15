"""One-off CLI to bootstrap the first `authorized` account.

Every other role is provisioned through the API (`POST /users` for
regular users, `POST /users/waste-bank-admins` for waste_bank admins —
the latter requires an existing `authorized` caller). That's a chicken-
and-egg problem for the very first `authorized` account, so it's seeded
directly against the DB instead.

Usage (from src/backend):
    python -m scripts.create_admin --email admin@pilahin.id --name "Ops Admin"
"""

from __future__ import annotations

import argparse
import getpass

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db import get_engine, init_db, users


def create_authorized_user(email: str, name: str, password: str) -> int:
    init_db()
    password_hash, password_salt = hash_password(password)
    try:
        with get_engine().begin() as conn:
            row = conn.execute(
                insert(users)
                .values(
                    email=email,
                    name=name,
                    password_hash=password_hash,
                    password_salt=password_salt,
                    role="authorized",
                )
                .returning(users.c.id)
            ).first()
    except IntegrityError as exc:
        raise SystemExit(f"A user with email {email!r} already exists") from exc
    return row[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", help="Omit to be prompted (not echoed to the terminal).")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    user_id = create_authorized_user(args.email, args.name, password)
    print(f"Created authorized user id={user_id} email={args.email}")


if __name__ == "__main__":
    main()
