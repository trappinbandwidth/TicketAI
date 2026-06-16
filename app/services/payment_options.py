"""
Payment options service.
Calculates installment plan options for a driver based on the attorney fee base
amount and the number of days until the court date.

Rules:
  30+ days until court → 2-payment option unlocked
  60+ days until court → 3-payment option unlocked
  90+ days until court → 4-payment option unlocked
  Pay in Full always available.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.models.response import PaymentOption, PaymentOptions

logger = logging.getLogger(__name__)

_DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
    "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y",
]


def _days_until(court_date_str: str) -> Optional[int]:
    s = (court_date_str or "").strip()
    if not s:
        return None
    try:
        from dateutil import parser as du
        dt = du.parse(s, dayfirst=False)
        return (dt - datetime.now()).days
    except Exception:
        pass
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return (dt - datetime.now()).days
        except ValueError:
            continue
    return None


def _round2(v: float) -> float:
    return round(v, 2)


def calculate_payment_options(
    base_amount: float,
    court_date_str: Optional[str] = None,
) -> Optional[PaymentOptions]:
    """
    Return PaymentOptions for the given base attorney fee amount.
    Returns None if base_amount is 0 or unknown.
    """
    if not base_amount or base_amount <= 0:
        return None

    days = _days_until(court_date_str) if court_date_str else None

    options: list[PaymentOption] = [
        PaymentOption(
            plan="Pay in Full",
            installments=1,
            down_payment=_round2(base_amount),
            monthly_payment=0.0,
            total=_round2(base_amount),
            available=True,
        )
    ]

    if days is None or days >= 30:
        half = _round2(base_amount / 2)
        options.append(PaymentOption(
            plan="2 Payments",
            installments=2,
            down_payment=half,
            monthly_payment=half,
            total=_round2(base_amount),
            available=True,
        ))

    if days is None or days >= 60:
        third = _round2(base_amount / 3)
        remainder = _round2(base_amount - third * 2)
        options.append(PaymentOption(
            plan="3 Payments",
            installments=3,
            down_payment=third,
            monthly_payment=third,
            total=_round2(third * 2 + remainder),
            available=True,
        ))

    if days is None or days >= 90:
        quarter = _round2(base_amount / 4)
        options.append(PaymentOption(
            plan="4 Payments",
            installments=4,
            down_payment=quarter,
            monthly_payment=quarter,
            total=_round2(base_amount),
            available=True,
        ))

    note = ""
    if days is not None and days < 30:
        note = f"Court date is {days} days away — only pay-in-full is available at this time."
    elif days is not None:
        note = f"{days} days until court date."

    return PaymentOptions(
        base_amount=_round2(base_amount),
        days_until_court=days,
        options=options,
        note=note,
    )
