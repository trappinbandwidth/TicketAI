# Agent Identity Roster

Rig Resolve keeps each agent's internal ID stable for code, logs, Firestore
events, and dashboards. Display names and historical aliases are governed by
`app/services/agent_identity.py`; this table mirrors that runtime contract.

Use respectful language in product and documentation: "enslaved people,"
"abolitionists," "Black engineers," "researchers," "inventors," "civil rights
leaders," and "institution builders." Internal IDs should not be renamed unless
there is a migration plan for graph nodes, event history, analytics, tests, and
admin filters.

| Internal ID | Display name | Legacy name | Department | Operational role |
| --- | --- | --- | --- | --- |
| `roux` | Roux | Case Intake | Document | Validates submissions before AI spend. |
| `document_gate` | Granville T. Woods | Document Gate | Document | Routes submissions by supported type. |
| `photo_analyst` | Gordon Parks | Photo Analyst | Document | Analyzes photo evidence outside ticket extraction. |
| `carver` | Carver | Lone Ranger | Document | Performs primary and secondary extraction. |
| `bolin` | Bolin | Referee | Document | Scores extraction quality and controls routing. |
| `bunche` | Bunche | Consensus | Document | Merges extraction passes and flags conflicts. |
| `ida_wells` | Ida Wells | Document Completeness | Document | Audits missing fields for preparation. |
| `charlotte_ray` | Charlotte Ray | Book Worm | Compliance | Adds CDL impact and severity context. |
| `jollof` | Jollof | PII Match | Compliance | Compares extracted CDL identity to the Driver profile. |
| `stagecoach_mary` | Stagecoach Mary | MVR Request | Compliance | Prepares Motor Vehicle Record requests. |
| `bass_reeves` | Bass Reeves | PSP Request | Compliance | Prepares FMCSA PSP safety-record requests. |
| `banneker` | Banneker | Research Ron | Legal | Builds jurisdiction, court, Carrier, and violation context. |
| `madam_walker` | Madam Walker | Team Quest | Legal | Prepares attorney coverage matches. |
| `tubman` | Tubman | Urgency Router | Operational | Calculates court-date urgency and priority. |
| `douglass` | Douglass | Statement of Record | Legal | Builds accounts, conflict maps, and evidence indexes. |

## Implementation Standard

- Source of truth: `app/services/agent_identity.py`
- Staff stats should return both `agent` and `identity`.
- Staff config should return the same identity payload.
- Tests must fail if an agent logs events without identity metadata.
- Historical event keys remain the internal IDs.
