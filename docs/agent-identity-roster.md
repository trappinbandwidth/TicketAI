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
| `roux` | Ida B. Wells | Roux | Disciplined investigation and truth documentation before a case moves forward. |
| `document_gate` | Granville T. Woods | Document Gate | Transportation engineering and routing fit the pre-classification gate. |
| `photo_analyst` | Gordon Parks | Photo Analyst | Photography as evidence, context, and human truth. |
| `carver` | Harriet Tubman | Carver | Navigation, precision, courage, and risk-aware extraction. |
| `bolin` | Thurgood Marshall | Bolin | Legal judgment, standards, and principled review. |
| `bunche` | Septima Poinsette Clark | Bunche | Civic education and coordinated action from many voices. |
| `ida_wells` | Mary McLeod Bethune | Ida Wells | Institutional readiness, records, and preparation. |
| `charlotte_ray` | Carter G. Woodson | Charlotte Ray | Research discipline, historical context, and knowledge preservation. |
| `jollof` | Rebecca Lee Crumpler | Jollof | Careful professional assessment and service. |
| `mvr_request` | Frederick McKinley Jones | Stagecoach Mary | Transportation engineering and freight innovation. |
| `psp_request` | Bessie Coleman | Bass Reeves | Safety, certification, and transportation trailblazing. |
| `banneker` | Benjamin Banneker | Banneker | Measurement, research, civic knowledge, and practical context. |
| `madam_walker` | Maggie Lena Walker | Madam Walker | Community networks, practical support, and institution building. |
| `tubman` | Sojourner Truth | Tubman | Direct advocacy, urgency, and moral clarity. |
| `statement_of_record` | Frederick Douglass | Douglass | Written testimony, public record, and truth shaped into durable evidence. |

## Implementation Standard

- Source of truth: `app/services/agent_identity.py`
- Staff stats should return both `agent` and `identity`.
- Staff config should return the same identity payload.
- Tests must fail if an agent logs events without identity metadata.
- Historical event keys remain the internal IDs.

