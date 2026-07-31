from app.services import carrier_lookup


def _records():
    return {
        "1234567": {
            "usdot_number": "1234567",
            "docket_number": "MC-101",
            "legal_name": "OPEN ROAD FREIGHT LLC",
            "dba_name": "OPEN ROAD",
            "status": "Active",
            "auth_type": "Common carrier",
            "state": "TX",
            "city": "AUSTIN",
            "zip": "78701",
            "phone": "5125550100",
            "min_coverage": "750000",
        },
        "7654321": {
            "usdot_number": "7654321",
            "docket_number": "MC-202",
            "legal_name": "OPEN HIGHWAY LOGISTICS",
            "dba_name": "",
            "status": "Inactive",
            "auth_type": "Contract carrier",
            "state": "OK",
            "city": "TULSA",
            "zip": "74103",
            "phone": "9185550199",
            "min_coverage": "750000",
        },
    }


def test_public_carrier_search_supports_identifiers_and_never_returns_full_phone(
    monkeypatch,
):
    monkeypatch.setattr(carrier_lookup, "_CARRIERS", _records())
    monkeypatch.setattr(carrier_lookup, "_LOADED", True)

    by_name = carrier_lookup.search_carriers("open road")
    assert [item["dot_number"] for item in by_name] == ["1234567"]
    assert "phone" not in by_name[0]
    assert by_name[0]["phone_last4"] == "0100"

    assert carrier_lookup.search_carriers("MC-202")[0]["dot_number"] == "7654321"
    assert carrier_lookup.search_carriers("5125550100")[0]["dot_number"] == "1234567"
    assert carrier_lookup.search_carriers("open", state="OK")[0]["dot_number"] == "7654321"


def test_discovery_detail_labels_carrier_context_and_provenance(monkeypatch):
    monkeypatch.setattr(carrier_lookup, "_CARRIERS", _records())
    monkeypatch.setattr(carrier_lookup, "_CRASH_DOT", {
        "1234567": {"crash_count": 4, "fatal_count": 1, "most_recent_year": 2025}
    })
    monkeypatch.setattr(carrier_lookup, "_LOADED", True)

    detail = carrier_lookup.carrier_discovery_detail("USDOT 1234567")

    assert detail["legal_name"] == "OPEN ROAD FREIGHT LLC"
    assert detail["phone"] == "5125550100"
    assert detail["carrier_level_crash_context"]["crash_count"] == 4
    assert "not an individual Driver safety record" in (
        detail["carrier_level_crash_context"]["scope_note"]
    )
    assert detail["provenance"]["source_kind"] == "authoritative_public"
