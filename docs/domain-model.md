# Domain Model

Rig Resolve is moving from a ticket-centered product to a Transportation
Intelligence Platform. A ticket is important, but it is one event in the life
of a professional driver, carrier, attorney, vehicle, and case.

## Principle

Entities should support relationships without forcing a single ownership model.
A driver may work for a carrier, leave that carrier, own equipment, lease to
another fleet, and keep the same Rig Resolve identity.

## Core Entities

### Driver

Represents a CDL holder or future professional-driving persona.

Key fields:

```json
{
  "id": "driver_...",
  "firebase_uid": "...",
  "name": "...",
  "phone": "...",
  "email": "...",
  "driver_type": "company_driver|owner_operator|lease_operator|professional_driver",
  "cdl_number": "...",
  "cdl_state": "MO",
  "cdl_class": "A|B|C|none",
  "endorsements": [],
  "medical_card_expiration": "...",
  "subscription_status": "active|lapsed|cancelled",
  "safe_driver_verified": true,
  "created_at": "...",
  "updated_at": "..."
}
```

### Carrier

Represents a fleet, motor carrier, brokerage-connected fleet, or owner-operator
authority.

```json
{
  "id": "carrier_...",
  "company_name": "...",
  "dot_number": "...",
  "mc_number": "...",
  "carrier_type": "small|medium|enterprise|owner_operator_authority",
  "billing_type": "invoice|payroll|card|ach",
  "per_driver_rate": 9.00,
  "status": "prospect|enrolled|active|terminated",
  "created_at": "..."
}
```

### DriverCarrierRelationship

Carriers should not own drivers. They receive permissioned access.

```json
{
  "id": "rel_...",
  "driver_id": "driver_...",
  "carrier_id": "carrier_...",
  "relationship_type": "employee|contractor|lease_operator|owner_operator",
  "status": "invited|active|ended|revoked",
  "permissions": {
    "view_case_status": true,
    "view_full_case_detail": false,
    "view_compliance_profile": true,
    "receive_alerts": true
  },
  "started_at": "...",
  "ended_at": null
}
```

### Attorney

Represents a legal professional in the Rig Resolve network.

```json
{
  "id": "attorney_...",
  "firebase_uid": "...",
  "name": "...",
  "firm_name": "...",
  "states_licensed": [],
  "counties_covered": [],
  "experience_tier": "senior|junior|law_student",
  "performance_level": "bronze|silver|gold|platinum|diamond",
  "win_rate": 0.85,
  "cases_active": 0,
  "max_active_cases": 20,
  "payout_status": "verified|pending|blocked"
}
```

### Vehicle And Trailer

Represents tractors, straight trucks, vans, trailers, or future equipment.

```json
{
  "id": "vehicle_...",
  "driver_id": "driver_...",
  "carrier_id": "carrier_...",
  "vin": "...",
  "unit_number": "...",
  "vehicle_type": "tractor|straight_truck|van|personal_vehicle|trailer",
  "plate_number": "...",
  "plate_state": "...",
  "status": "active|inactive"
}
```

### Ticket / Citation

A legal event, not the center of the platform.

```json
{
  "id": "ticket_...",
  "driver_id": "driver_...",
  "carrier_id": "carrier_...",
  "vehicle_id": "vehicle_...",
  "citation_number": "...",
  "ticket_state": "...",
  "ticket_county": "...",
  "ticket_city": "...",
  "violation_description": "...",
  "court_date": "...",
  "court_date_is_artificial": false,
  "source": "driver_upload|manual|carrier_upload|attorney_self_sourced",
  "attorney_status": "AI Review|New|Accepted|Ticket Closed|Rejected",
  "created_at": "..."
}
```

### Inspection

Represents a roadside inspection, DOT inspection, or compliance event.

```json
{
  "id": "inspection_...",
  "driver_id": "driver_...",
  "carrier_id": "carrier_...",
  "vehicle_id": "vehicle_...",
  "inspection_date": "...",
  "inspection_level": "I|II|III|IV|V|VI|unknown",
  "state": "...",
  "violations": [],
  "out_of_service": false,
  "dataq_eligible": null
}
```

### Violation

Normalized violation object.

```json
{
  "id": "violation_...",
  "source_type": "ticket|inspection|mvr|psp",
  "source_id": "...",
  "driver_id": "driver_...",
  "category": "speeding|hos|logbook|equipment|accident|dui|other",
  "description": "...",
  "fmcsa_basic": "Unsafe Driving|HOS Compliance|Vehicle Maintenance|Crash Indicator|Driver Fitness|Controlled Substances|Hazmat",
  "severity": "low|medium|high|critical",
  "cdl_point_impact": 0,
  "disqualification_risk": "low|medium|high|critical"
}
```

### Court

```json
{
  "id": "court_...",
  "state": "...",
  "county": "...",
  "city": "...",
  "name": "...",
  "phone": "...",
  "payment_url": "...",
  "scheduling_url": "...",
  "cdl_appearance_rules": "..."
}
```

### Case

Legal workflow object created from one or more tickets or violations.

```json
{
  "id": "case_...",
  "driver_id": "driver_...",
  "carrier_id": "carrier_...",
  "ticket_ids": [],
  "assigned_attorney_id": "attorney_...",
  "status": "new|assigned|accepted|active|outcome_logged|payout_sent|closed",
  "urgency_level": "critical|high|standard|low",
  "outcome": "won|dismissed|reduced|lost|transferred|null"
}
```

### Document

All uploaded or generated documents.

```json
{
  "id": "doc_...",
  "owner_type": "driver|carrier|attorney|case|ticket",
  "owner_id": "...",
  "document_type": "ticket|inspection_report|mvr|psp|photo|court_notice|dataq_packet|w9|bar_license",
  "storage_path": "...",
  "hash_sha256": "...",
  "classification": "ticket|photo|unknown|legal_document",
  "created_at": "..."
}
```

## Platform Primitives

- Event: see `event-model.md`.
- Recommendation: see `recommendation-contract.md`.
- Payment / Transaction / Payout: see `financial-service.md`.

## Future Domain Objects

- DataQ opportunity and packet
- MVR request and report
- PSP request and report
- Insurance/risk profile
- Consent grant and relationship permission
