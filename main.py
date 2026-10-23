from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.auth import router as auth_router
from app.api.routes.suspicious_activities import (
    router as suspicious_activities_router,
)
from app.api.routes.transactions import router as transactions_router
from app.api.routes.wallets import router as wallets_router
from app.core.config import settings
from app.database.database import SessionLocal
from app.models.role import Role
from app.api.routes.notifications import router as notifications_router
from app.api.routes.dashboard import router as dashboard_router

ROLE_DEFINITIONS = [
    ("Super Admin", "Full system access"),
    ("Admin", "Administrative access"),
    ("Support Agent", "Customer support and transaction review"),
    ("Customer", "Personal wallet and transaction access"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()

    try:
        for role_name, description in ROLE_DEFINITIONS:
            role = db.scalar(
                select(Role).where(Role.name == role_name)
            )

            if role is None:
                db.add(
                    Role(
                        name=role_name,
                        description=description,
                        is_active=True,
                    )
                )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(wallets_router)
app.include_router(transactions_router)
app.include_router(suspicious_activities_router)
app.include_router(audit_logs_router)
app.include_router(notifications_router)
app.include_router(dashboard_router)

@app.get("/", tags=["Health"])
def health_check():
    return {
        "success": True,
        "message": "Digital Wallet API is running",
    }