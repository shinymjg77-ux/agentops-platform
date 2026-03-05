from collections.abc import Callable
from enum import StrEnum

from fastapi import Depends, Header, HTTPException, status


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


def get_current_role(x_role: str | None = Header(default=None, alias="X-Role")) -> Role:
    if x_role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_role_header",
        )

    normalized = x_role.strip().lower()
    try:
        return Role(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_role",
        ) from exc


def require_roles(*allowed_roles: Role) -> Callable[[Role], Role]:
    allowed = set(allowed_roles)

    def checker(role: Role = Depends(get_current_role)) -> Role:
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden",
            )
        return role

    return checker
