"""Stripe provider adapter.

This module defines the provider boundary. Real Stripe calls should be added
here, behind the Financial Service, when a route needs checkout/session creation.
"""
from __future__ import annotations


class StripeProvider:
    provider_name = "stripe"

    def create_checkout_session(self, request: dict) -> dict:
        raise NotImplementedError(
            "Stripe checkout session creation is not wired in this abstraction yet."
        )
