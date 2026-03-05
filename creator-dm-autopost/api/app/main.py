from fastapi import FastAPI

from app.audit.middleware import AuditLogMiddleware
from app.core.config import settings
from app.routers.alerts import router as alerts_router
from app.routers.audit import router as audit_router
from app.routers.approval import router as approval_router
from app.routers.consents import router as consents_router
from app.routers.creators import router as creators_router
from app.routers.dashboard import router as dashboard_router
from app.routers.deliveries import router as deliveries_router
from app.routers.health import router as health_router
from app.routers.metrics import router as metrics_router
from app.routers.posts import router as posts_router
from app.routers.rbac import router as rbac_router

app = FastAPI(title=settings.app_name)
app.add_middleware(AuditLogMiddleware)
app.include_router(health_router)
app.include_router(rbac_router)
app.include_router(alerts_router)
app.include_router(audit_router)
app.include_router(approval_router)
app.include_router(consents_router)
app.include_router(creators_router)
app.include_router(dashboard_router)
app.include_router(deliveries_router)
app.include_router(posts_router)
app.include_router(metrics_router)
