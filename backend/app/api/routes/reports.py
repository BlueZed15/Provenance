import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.api import DecisionReportResponse
from backend.app.services.reports import get_decision_report


router = APIRouter()


@router.get("/reports/{decision_id}", response_model=DecisionReportResponse)
def get_report(
    decision_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> DecisionReportResponse:
    report = get_decision_report(session, decision_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decision report not found")
    return report
