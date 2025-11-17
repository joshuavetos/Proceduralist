"""Stripe Checkout session creation for map exports."""
from __future__ import annotations

import os

import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import auditor, clauses
from backend.models.db import DBMap, SessionLocal

router = APIRouter()


class CheckoutRequest(BaseModel):
    map_id: int


class CheckoutResponse(BaseModel):
    url: str


@router.post("/api/store/checkout", response_model=CheckoutResponse)
async def create_checkout_session(request: CheckoutRequest) -> CheckoutResponse:
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=500, detail="Stripe secret key not configured")

    stripe.api_key = secret_key

    session = SessionLocal()
    try:
        map_record = session.get(DBMap, request.map_id)
        if map_record is None:
            raise HTTPException(status_code=404, detail="Map not found")
    finally:
        session.close()

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
            success_url=f"/store/{request.map_id}?success=1",
            cancel_url=f"/store/{request.map_id}?canceled=1",
        )
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        raise HTTPException(status_code=500, detail=f"Stripe checkout creation failed: {exc}") from exc

    if not checkout_session.url:
        raise HTTPException(status_code=502, detail="Stripe session missing redirect URL")

    return CheckoutResponse(url=checkout_session.url)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
