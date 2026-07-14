"""Choice Digital provider adapter.

Do not implement outbound payout calls until Choice Digital API docs,
credentials, auth model, and webhook verification details are available.
"""
from __future__ import annotations


class ChoiceDigitalProvider:
    provider_name = "choice_digital"

    def submit_payout(self, payout_request: dict) -> dict:
        raise NotImplementedError(
            "Choice Digital payouts require provider API docs and credentials before implementation."
        )
