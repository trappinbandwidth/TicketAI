import asyncio

from app.routes import attorneys


class Snapshot:
    def __init__(self, ident, data):
        self.id = ident
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class Document:
    def __init__(self, ident, rows):
        self.ident = ident
        self.rows = rows

    def get(self):
        return Snapshot(self.ident, self.rows.get(self.ident))


class Collection:
    def __init__(self, rows):
        self.rows = rows

    def document(self, ident):
        return Document(ident, self.rows)

    def stream(self):
        return [Snapshot(ident, data) for ident, data in self.rows.items()]


class Db:
    def __init__(self, rows):
        self.rows = rows

    def collection(self, name):
        return Collection(self.rows.setdefault(name, {}))


def test_attorney_detail_includes_contact_case_outcome_and_payout_stats(monkeypatch):
    db = Db({
        "attorneys": {
            "attorney-1": {
                "full_name": "Avery Counsel",
                "firm_name": "Counsel CDL Law",
                "email": "avery@example.test",
                "states_covered": ["TX"],
            },
        },
        "tickets": {
            "case-1": {
                "assigned_attorney_id": "attorney-1",
                "attorney_status": "Ticket Closed",
                "outcome": "dismissed",
                "selected_fee_cents": 45000,
            },
            "case-2": {
                "claimed_by": "attorney-1",
                "attorney_status": "Accepted",
            },
            "other": {"assigned_attorney_id": "attorney-2"},
        },
        "payout_requests": {
            "paid": {
                "attorney_id": "attorney-1",
                "status": "paid",
                "total_amount": 450,
            },
            "pending": {
                "attorney_id": "attorney-1",
                "status": "requested",
                "total_amount": 300,
            },
        },
    })
    monkeypatch.setattr(attorneys, "require_staff", lambda _authorization: {})
    monkeypatch.setattr(attorneys, "_db", lambda: db)

    detail = asyncio.run(attorneys.get_attorney("attorney-1", "Bearer test"))

    assert detail["email"] == "avery@example.test"
    assert detail["captain_stats"] == {
        "total_cases": 2,
        "active_cases": 1,
        "resolved_cases": 1,
        "favorable_outcomes": 1,
        "favorable_rate": 1.0,
        "paid_to_date": 450.0,
        "pending_payout": 300.0,
        "payout_count": 2,
    }
    assert [case["ticket_id"] for case in detail["recent_cases"]] == [
        "case-1", "case-2",
    ]
