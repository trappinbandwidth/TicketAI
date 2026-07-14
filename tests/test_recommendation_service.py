from app.models.response import AttorneyMatch
from app.services import recommendation_service


class FakeDocument:
    def __init__(self):
        self.data = None

    def set(self, data):
        self.data = data


class FakeCollection:
    def __init__(self):
        self.docs = {}

    def document(self, doc_id):
        self.docs.setdefault(doc_id, FakeDocument())
        return self.docs[doc_id]


class FakeDb:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        self.collections.setdefault(name, FakeCollection())
        return self.collections[name]


def test_build_recommendation_shape():
    rec = recommendation_service.build_recommendation(
        rec_type="court_deadline_warning",
        subject_type="ticket",
        subject_id="ticket_1",
        audience="staff",
        summary="Court date is near.",
        why_it_matters="Deadline risk.",
        recommended_action="Assign attorney.",
        confidence=0.9,
        severity="high",
        requires_human_approval=True,
        evidence=[{"source_type": "ai_extraction", "field": "Court_Date__c", "quote": "01/01/2027"}],
        reasoning_summary="Court date is within the high urgency window.",
        created_by="legal_intelligence",
    )

    assert rec.id.startswith("rec_")
    assert rec.version == "1.0"
    assert rec.type == "court_deadline_warning"
    assert rec.status == "pending_review"
    assert rec.evidence[0].field == "Court_Date__c"


def test_create_recommendation_persists_and_emits_event(monkeypatch):
    db = FakeDb()
    emitted = []
    monkeypatch.setattr(recommendation_service, "_db", lambda: db)
    monkeypatch.setattr(recommendation_service, "write_event", lambda **kwargs: emitted.append(kwargs) or "evt_1")

    rec = recommendation_service.build_recommendation(
        rec_type="attorney_match_recommendation",
        subject_type="ticket",
        subject_id="ticket_1",
        audience="staff",
        summary="Attorney match.",
        why_it_matters="Coverage.",
        recommended_action="Review assignment.",
        confidence=0.8,
        severity="medium",
        requires_human_approval=True,
        reasoning_summary="Best profile match.",
        created_by="legal_intelligence",
    )

    rec_id = recommendation_service.create_recommendation(rec)

    assert rec_id == rec.id
    assert db.collections["recommendations"].docs[rec.id].data["id"] == rec.id
    assert emitted[0]["event_type"] == "recommendation.created"


def test_court_deadline_recommendation_only_for_high_urgency(monkeypatch):
    created = []
    monkeypatch.setattr(recommendation_service, "create_recommendation", lambda rec: created.append(rec) or rec.id)

    assert recommendation_service.create_court_deadline_recommendation("ticket_1", "LOW", "", "") == ""

    rec_id = recommendation_service.create_court_deadline_recommendation(
        "ticket_1",
        "HIGH",
        "Court date is 10 days away.",
        "01/01/2027",
    )

    assert rec_id.startswith("rec_")
    assert created[0].type == "court_deadline_warning"
    assert created[0].severity == "high"


def test_attorney_match_recommendation_uses_match_evidence(monkeypatch):
    created = []
    monkeypatch.setattr(recommendation_service, "create_recommendation", lambda rec: created.append(rec) or rec.id)

    match = AttorneyMatch(
        attorney_id="attorney_1",
        name="Jane Lawyer",
        email="jane@example.com",
        phone="555-0100",
        rating=4.8,
        win_rate=0.84,
        total_tickets=100,
        match_type="county",
    )

    rec_id = recommendation_service.create_attorney_match_recommendation("ticket_1", match)

    assert rec_id.startswith("rec_")
    assert created[0].type == "attorney_match_recommendation"
    assert created[0].evidence[0].source_id == "attorney_1"
