from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings

ALLOWED_ROLES = {"admin", "reviewer"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db_connection() -> sqlite3.Connection:
    settings.user_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(settings.user_db_path))
    connection.row_factory = sqlite3.Row
    return connection


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, settings.password_hash_iterations)
    return f"pbkdf2_sha256${settings.password_hash_iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_hex, digest_hex = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    test_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iteration_text),
    )
    return secrets.compare_digest(test_digest.hex(), digest_hex)


def create_user_record(username: str, password: str, role: str, is_active: bool = True) -> None:
    if role not in ALLOWED_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, hash_password(password), role, int(is_active), _utc_now_iso()),
        )
        connection.commit()


def get_user(username: str) -> Optional[sqlite3.Row]:
    with get_db_connection() as connection:
        return connection.execute(
            "SELECT username, password_hash, role, is_active, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def list_users() -> list[sqlite3.Row]:
    with get_db_connection() as connection:
        return connection.execute(
            "SELECT username, role, is_active, created_at FROM users ORDER BY username"
        ).fetchall()


def update_password(username: str, new_password: str) -> None:
    with get_db_connection() as connection:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(new_password), username),
        )
        connection.commit()


def ensure_default_user(username: str, password: str, role: str) -> None:
    if username and password and get_user(username) is None:
        create_user_record(username, password, role, True)


def backup_broken_user_db() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in [settings.user_db_path, Path(f"{settings.user_db_path}-journal")]:
        if path.exists():
            try:
                path.replace(path.with_name(f"{path.name}.broken_{timestamp}"))
            except PermissionError:
                continue


def init_user_db() -> None:
    try:
        with get_db_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
    except sqlite3.Error:
        backup_broken_user_db()
        with get_db_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    ensure_default_user(settings.admin_username, settings.admin_password, "admin")
    ensure_default_user(settings.reviewer_username, settings.reviewer_password, "reviewer")
