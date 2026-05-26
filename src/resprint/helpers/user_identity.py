from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from resprint.models import UserIdentity

UNKNOWN_USER = "Auteur inconnu"


def user_identity_from_mapping(raw: Mapping[str, Any] | None) -> UserIdentity:
    if not raw:
        return UserIdentity()
    return UserIdentity(
        name=_optional_str(raw.get("name") or raw.get("username")),
        display_name=_optional_str(raw.get("displayName") or raw.get("fullName")),
        key=_optional_str(raw.get("key") or raw.get("userKey")),
        account_id=_optional_str(raw.get("accountId")),
    )


def user_identity_from_value(value: Any) -> UserIdentity:
    if isinstance(value, dict):
        return user_identity_from_mapping(value)
    if isinstance(value, str):
        return UserIdentity(key=value)
    return UserIdentity()


def user_label(identity: UserIdentity) -> str | None:
    return identity.label


def user_key(identity: UserIdentity) -> str | None:
    return identity.key or identity.account_id or identity.name


def user_label_or_unknown(identity: UserIdentity) -> str:
    return identity.label or UNKNOWN_USER


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
