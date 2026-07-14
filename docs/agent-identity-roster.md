# Agent Identity Roster

Rig Resolve keeps each agent's internal ID stable for code, logs, Firestore
events, and dashboards. The public display name honors Black historical figures
whose work reflects the agent's job.

Use respectful language in product and documentation: "enslaved people,"
"abolitionists," "Black engineers," "researchers," "inventors," "civil rights
leaders," and "institution builders." Internal IDs should not be renamed unless
there is a migration plan for graph nodes, event history, analytics, tests, and
admin filters.

| Internal ID | Display name | Legacy name | Why this fit was chosen |
| --- | --- | --- | --- |
| `case_intake` | Ida B. Wells | Case Intake | Disciplined investigation and truth documentation before a case moves forward. |
| `document_gate` | Granville T. Woods | Document Gate | Transportation engineering and routing fit the pre-classification gate. |
| `photo_analyst` | Gordon Parks | Photo Analyst | Photography as evidence, context, and human truth. |
| `lone_ranger` | Harriet Tubman | Lone Ranger | Navigation, precision, courage, and risk-aware extraction. |
| `referee` | Thurgood Marshall | Referee | Legal judgment, standards, and principled review. |
| `consensus` | Septima Poinsette Clark | Consensus | Civic education and coordinated action from many voices. |
| `document_completeness` | Mary McLeod Bethune | Document Completeness | Institutional readiness, records, and preparation. |
| `book_worm` | Carter G. Woodson | Book Worm | Research discipline, historical context, and knowledge preservation. |
| `pii_match` | Rebecca Lee Crumpler | PII Match | Careful professional assessment and service. |
| `mvr_request` | Frederick McKinley Jones | MVR Request | Transportation engineering and freight innovation. |
| `psp_request` | Bessie Coleman | PSP Request | Safety, certification, and transportation trailblazing. |
| `research_ron` | Benjamin Banneker | Research Ron | Measurement, research, civic knowledge, and practical context. |
| `team_quest` | Maggie Lena Walker | Team Quest | Community networks, practical support, and institution building. |
| `urgency_router` | Sojourner Truth | Urgency Router | Direct advocacy, urgency, and moral clarity. |
| `statement_of_record` | Frederick Douglass | Statement of Record | Written testimony, public record, and truth shaped into durable evidence. |

## Implementation Standard

- Source of truth: `app/services/agent_identity.py`
- Staff stats should return both `agent` and `identity`.
- Staff config should return the same identity payload.
- Tests must fail if an agent logs events without identity metadata.
- Historical event keys remain the internal IDs.

