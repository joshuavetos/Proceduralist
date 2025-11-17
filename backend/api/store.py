"""Stripe Checkout session creation for map exports."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Tuple

import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import auditor, clauses
from backend.models.db import DBMap, SessionLocal

router = APIRouter()


Environment = Literal["DOCKER_COMPOSE", "LOCAL_DEV"]


def _detect_environment() -> Environment:
    """Detect runtime environment to build accurate callback URLs."""

    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if compose_path.exists():
        compose_text = compose_path.read_text(encoding="utf-8")
        if "frontend:" in compose_text and "backend:" in compose_text:
            return "DOCKER_COMPOSE"

    frontend_pages = Path(__file__).resolve().parents[2] / "frontend" / "pages"
    if frontend_pages.exists():
        return "LOCAL_DEV"

    return "LOCAL_DEV"


def _resolve_checkout_urls(map_id: int) -> Tuple[str, str]:
    environment = _detect_environment()
    base = (
        "http://frontend:3000"
        if environment == "DOCKER_COMPOSE"
        else "http://localhost:3000"
    )
    success_url = f"{base}/store/{map_id}?success=1"
    cancel_url = f"{base}/store/{map_id}?canceled=1"
    return success_url, cancel_url


class CheckoutRequest(BaseModel):
    map_id: int


class CheckoutResponse(BaseModel):
    url: str


@router.post("/api/store/checkout", response_model=CheckoutResponse)
async def create_checkout_session(request: CheckoutRequest) -> CheckoutResponse:
    if request.map_id <= 0:
        raise HTTPException(status_code=400, detail="Map id must be positive")

    secret_key = os.getenv("STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=500, detail="Stripe secret key not configured")
    if not secret_key.startswith("sk_"):
        raise HTTPException(status_code=500, detail="Invalid Stripe secret key format")

    stripe.api_key = secret_key

    session = SessionLocal()
    try:
        map_record = session.get(DBMap, request.map_id)
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")
        if map_record.status != "published":
            raise HTTPException(status_code=403, detail="Map is not published")
    finally:
        session.close()

    success_url, cancel_url = _resolve_checkout_urls(request.map_id)

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": 500,
                        "product_data": {"name": "Proceduralist Audit Export"},
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        raise HTTPException(status_code=500, detail=f"Stripe checkout creation failed: {exc}") from exc

    if not checkout_session.url:
        raise HTTPException(status_code=502, detail="Stripe session missing redirect URL")

    return CheckoutResponse(url=checkout_session.url)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
