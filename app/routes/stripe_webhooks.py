"""
Stripe webhook receiver — processes payment and subscription events.

Events handled:
  payment_intent.succeeded        → mark ticket payment complete in Firestore
  checkout.session.completed      → record Stripe customer_id on carrier/driver doc
  customer.subscription.updated   → update carriers/{uid}/subscription in Firestore
  customer.subscription.deleted   → set subscription status to 'canceled'
  invoice.payment_failed          → set subscription status to 'past_due', log alert

Webhook secret is read from STRIPE_WEBHOOK_SECRET env var.
Without it the route still accepts events but skips signature verification
(dev / local mode).
"""

import logging
import os
from typing import Optional

import stripe
from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _firestore():
    from app.services.firebase_service import _firestore_client, _init
    _init()
    return _firestore_client


def _update_subscription(customer_id: str, fields: dict) -> None:
    """Write subscription fields to any carrier doc that owns this Stripe customer."""
    db = _firestore()
    if not db:
        return
    # Look up carrier by email matching the Stripe customer email
    try:
        customer = stripe.Customer.retrieve(customer_id)
        email = customer.get("email", "")
        if not email:
            return
        # Find Firebase Auth user by email → uid → carriers/{uid}
        import firebase_admin.auth as auth_sdk
        user = auth_sdk.get_user_by_email(email)
        db.collection("carriers").document(user.uid).set(
            {"subscription": {**fields, "stripe_customer_id": customer_id}},
            merge=True
        )
        logger.info("[stripe] updated subscription for uid=%s customer=%s", user.uid, customer_id)
    except Exception as exc:
        logger.warning("[stripe] _update_subscription failed customer=%s: %s", customer_id, exc)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
):
    payload = await request.body()

    # Verify signature if secret is configured
    if WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("[stripe] webhook signature invalid: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    else:
        import json
        try:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Malformed event: {exc}")

    etype = event["type"]
    data  = event["data"]["object"]
    logger.info("[stripe] received event=%s id=%s", etype, event.get("id"))

    try:
        if etype == "checkout.session.completed":
            _handle_checkout_completed(data)

        elif etype == "payment_intent.succeeded":
            _handle_payment_succeeded(data)

        elif etype == "customer.subscription.updated":
            _handle_subscription_updated(data)

        elif etype == "customer.subscription.deleted":
            _handle_subscription_deleted(data)

        elif etype == "invoice.payment_failed":
            _handle_payment_failed(data)

        else:
            logger.debug("[stripe] unhandled event type=%s", etype)

    except Exception as exc:
        logger.error("[stripe] event handler failed type=%s: %s", etype, exc)
        # Return 200 so Stripe doesn't retry indefinitely
        return {"received": True, "handled": False, "error": str(exc)}

    return {"received": True, "handled": True}


def _handle_checkout_completed(session: dict) -> None:
    """Record Stripe customer_id and initial subscription data."""
    customer_id = session.get("customer")
    if not customer_id:
        return

    fields: dict = {"stripe_customer_id": customer_id}

    # If session has subscription, read plan info
    sub_id = session.get("subscription")
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            item = sub["items"]["data"][0] if sub["items"]["data"] else None
            if item:
                price = stripe.Price.retrieve(item["price"]["id"])
                fields.update({
                    "plan_price": (price.get("unit_amount") or 0) / 100,
                    "billing_cycle": price.get("recurring", {}).get("interval", "monthly"),
                    "status": sub.get("status", "active"),
                    "next_billing_date": _ts_to_date(sub.get("current_period_end")),
                    "stripe_subscription_id": sub_id,
                })
        except Exception as exc:
            logger.warning("[stripe] could not enrich checkout session: %s", exc)

    _update_subscription(customer_id, fields)


def _handle_payment_succeeded(intent: dict) -> None:
    """Mark ticket as paid in Firestore if metadata includes ticket_id."""
    ticket_id = (intent.get("metadata") or {}).get("ticket_id")
    if not ticket_id:
        return
    db = _firestore()
    if not db:
        return
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    db.collection("tickets").document(ticket_id).set(
        {"payment_status": "paid", "payment_intent_id": intent.get("id"), "paid_at": SERVER_TIMESTAMP},
        merge=True
    )
    logger.info("[stripe] marked ticket=%s as paid", ticket_id)


def _handle_subscription_updated(sub: dict) -> None:
    customer_id = sub.get("customer")
    if not customer_id:
        return
    item = sub["items"]["data"][0] if sub.get("items", {}).get("data") else None
    fields: dict = {
        "status": sub.get("status", "active"),
        "next_billing_date": _ts_to_date(sub.get("current_period_end")),
        "stripe_subscription_id": sub.get("id"),
    }
    if item:
        try:
            price = stripe.Price.retrieve(item["price"]["id"])
            fields.update({
                "plan_price": (price.get("unit_amount") or 0) / 100,
                "billing_cycle": price.get("recurring", {}).get("interval", "monthly"),
            })
        except Exception as exc:
            logger.warning("[stripe] could not retrieve price: %s", exc)
    _update_subscription(customer_id, fields)


def _handle_subscription_deleted(sub: dict) -> None:
    customer_id = sub.get("customer")
    if not customer_id:
        return
    _update_subscription(customer_id, {"status": "canceled"})


def _handle_payment_failed(invoice: dict) -> None:
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    _update_subscription(customer_id, {"status": "past_due"})


def _ts_to_date(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
