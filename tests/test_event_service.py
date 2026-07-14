from app.services import event_service


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


def test_build_event_shape():
    event = event_service.build_event(
        event_type="ticket.uploaded",
        actor_type="driver",
        actor_id="driver_1",
        entity_type="ticket",
        entity_id="ticket_1",
        related_entities=[{"type": "driver", "id": "driver_1"}],
        source="driver_app",
        payload={"filename": "ticket.pdf"},
    )

    assert event["id"].startswith("evt_")
    assert event["event_type"] == "ticket.uploaded"
    assert event["version"] == "1.0"
    assert event["actor_type"] == "driver"
    assert event["actor_id"] == "driver_1"
    assert event["entity_type"] == "ticket"
    assert event["entity_id"] == "ticket_1"
    assert event["related_entities"] == [{"type": "driver", "id": "driver_1"}]
    assert event["source"] == "driver_app"
    assert event["payload"] == {"filename": "ticket.pdf"}
    assert "created_at" in event


def test_write_event_persists_event(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(event_service, "_db", lambda: db)

    event_id = event_service.write_event(
        event_type="ticket.processed",
        actor_type="system",
        actor_id=None,
        entity_type="ticket",
        entity_id="ticket_1",
        payload={"pass_status": "green"},
    )

    assert event_id.startswith("evt_")
    stored = db.collections["events"].docs[event_id].data
    assert stored["id"] == event_id
    assert stored["event_type"] == "ticket.processed"
    assert stored["payload"] == {"pass_status": "green"}


def test_write_event_fails_closed(monkeypatch):
    monkeypatch.setattr(event_service, "_db", lambda: None)

    assert event_service.write_event("ticket.uploaded", "system", None, "ticket", "ticket_1") == ""
