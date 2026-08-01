from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import settings
from backend.app.db.session import engine


router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["connected", "unavailable"]
    mistral: Literal["configured", "not_configured"]
    environment: str


@router.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    database_status: Literal["connected", "unavailable"] = "connected"

    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError:
        database_status = "unavailable"

    mistral_status: Literal["configured", "not_configured"] = (
        "configured" if settings.has_mistral_key else "not_configured"
    )
    overall_status: Literal["ok", "degraded"] = (
        "ok"
        if database_status == "connected" and mistral_status == "configured"
        else "degraded"
    )

    if overall_status == "degraded":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        database=database_status,
        mistral=mistral_status,
        environment=settings.app_env,
    )
