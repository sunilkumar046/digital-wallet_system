from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardSummary,
    DashboardTransactions,
    DashboardSuspiciousSummary,
)
from app.services.dashboard_service import DashboardService


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DashboardService.summary(db, current_user)


@router.get(
    "/transactions",
    response_model=DashboardTransactions,
)
def dashboard_transactions(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = DashboardService.recent_transactions(
        db=db,
        user=current_user,
        limit=limit,
    )

    return {
        "items": transactions,
        "limit": limit,
    }


@router.get(
    "/suspicious-activities",
    response_model=DashboardSuspiciousSummary,
)
def dashboard_suspicious_activities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DashboardService.suspicious_summary(db, current_user)