"""user.dao — таблицы SQLAlchemy и запросы модуля пользователей."""

from app.user.dao.repository import (
    insert_user_if_absent,
    select_active_employees,
    select_credentials_by_email,
    select_user_by_id,
    select_user_names,
    select_users_by_ids,
    update_password_hash,
)
from app.user.dao.tables import UserRow

__all__ = [
    "UserRow",
    "insert_user_if_absent",
    "select_active_employees",
    "select_credentials_by_email",
    "select_user_by_id",
    "select_user_names",
    "select_users_by_ids",
    "update_password_hash",
]
