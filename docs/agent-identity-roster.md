# Agent Identity Roster

Rig Resolve keeps each agent's internal ID stable for code, logs, Firestore
events, and dashboards. Display names and historical aliases are governed by
`app/services/agent_identity.py`; this table mirrors that runtime contract.

Use respectful language in product and documentation: "enslaved people,"
"abolitionists," "Black engineers," "researchers," "inventors," "civil rights
leaders," and "institution builders." Internal IDs should not be renamed unless
there is a migration plan for graph nodes, event history, analytics, tests, and
admin filters.

| Internal ID | Display name | Legacy name | Operational role |
| --- | --- | --- | --- |
| `roux` | Roux | Case Intake | Validates submissions before AI spend. |
| `document_gate` | Granville T. Woods | Document Gate | Transportation engineering and routing fit the pre-classification gate. |
| `photo_analyst` | Gordon Parks | Photo Analyst | Photography as evidence, context, and human truth. |
| `carver` | Carver | Lone Ranger | Performs the primary and secondary extraction passes. |
| `bolin` | Bolin | Referee | Scores extraction quality and controls review routing. |
| `bunche` | Bunche | Consensus | Merges two extraction passes and flags conflicts. |
| `ida_wells` | Ida Wells | Document Completeness | Audits missing fields for attorney preparation. |
| `charlotte_ray` | Charlotte Ray | Book Worm | Adds CDL point, severity, and disqualification context. |
| `jollof` | Jollof | PII Match | Verifies CDL identity against the Driver profile. |
| `stagecoach_mary` | Stagecoach Mary | MVR Request | Queues Motor Vehicle Record pulls. |
| `bass_reeves` | Bass Reeves | PSP Request | Queues FMCSA PSP safety-record pulls. |
| `banneker` | Banneker | Research Ron | Builds jurisdiction, court, Carrier, and violation context. |
| `madam_walker` | Madam Walker | Team Quest | Matches cases to available CDL attorneys. |
| `tubman` | Tubman | Urgency Router | Calculates court-date urgency and priority. |
| `douglass` | Douglass | Statement of Record | Builds accounts, conflict maps, and evidence indexes. |

## Implementation Standard

- Source of truth: `app/services/agent_identity.py`
- Staff stats should return both `agent` and `identity`.
- Staff config should return the same identity payload.
- Tests must fail if an agent logs events without identity metadata.
- Historical event keys remain the internal IDs.
