from fastapi import APIRouter, Depends

from app.security.rbac import Role, get_current_role, require_roles

router = APIRouter(prefix="/rbac", tags=["rbac"])


@router.get("/me", summary="Return current role")
def rbac_me(role: Role = Depends(get_current_role)) -> dict[str, str]:
    return {"role": role}


@router.get("/viewer", summary="Viewer+ access")
def viewer_endpoint(
    role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> dict[str, str]:
    return {"scope": "viewer", "role": role}


@router.post("/operator", summary="Operator+ access")
def operator_endpoint(
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> dict[str, str]:
    return {"scope": "operator", "role": role}


@router.delete("/admin", summary="Admin-only access")
def admin_endpoint(role: Role = Depends(require_roles(Role.ADMIN))) -> dict[str, str]:
    return {"scope": "admin", "role": role}
