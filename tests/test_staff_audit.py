from app.services.staff_audit import write_staff_audit


class FakeDocument:
    def __init__(self):
        self.data = None

    def set(self, data):
        self.data = data


class FakeCollection:
    def __init__(self):
        self.doc = FakeDocument()

    def document(self):
        return self.doc


class FakeDb:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        self.collections.setdefault(name, FakeCollection())
        return self.collections[name]


def test_write_staff_audit_shape():
    db = FakeDb()

    ok = write_staff_audit(
        db,
        actor={"uid": "staff_1", "email": "ops@rigresolve.com", "staff_role": "ops_staff"},
        action="ticket.approved",
        entity_type="ticket",
        entity_id="ticket_1",
        before={"attorney_status": "AI Review"},
        after={"attorney_status": "New"},
        source="admin_dashboard",
    )

    assert ok is True
    entry = db.collections["staff_audit"].doc.data
    assert entry["actor_uid"] == "staff_1"
    assert entry["actor_email"] == "ops@rigresolve.com"
    assert entry["actor_role"] == "ops_staff"
    assert entry["action"] == "ticket.approved"
    assert entry["entity_type"] == "ticket"
    assert entry["entity_id"] == "ticket_1"
    assert entry["before"] == {"attorney_status": "AI Review"}
    assert entry["after"] == {"attorney_status": "New"}
    assert entry["source"] == "admin_dashboard"


def test_write_staff_audit_fails_closed_without_db():
    assert write_staff_audit(None, {}, "ticket.rejected", "ticket", "ticket_1") is False
