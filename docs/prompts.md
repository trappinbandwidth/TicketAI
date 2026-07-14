# Rig Resolve — Master Prompt Reference
## How to Read, Modify, and Version Prompts

**Last updated:** 2026-07-04  
**Prompt files:** `prompts/v2.md` (main extraction) · `prompts/photo_v1.md` (photo analysis)  
**Who uses each:** Carver uses `v2.md`. Photo Analyst uses `photo_v1.md`. Document Gate uses an inline prompt in `agents/document_gate.py`.

---

## How Prompts Are Loaded

```python
# agents/carver.py calls:
process_document(images_b64=..., prompt_version="v2")

# claude_client.py loads it:
system_prompt = Path("prompts/v2.md").read_text()

# Sent to Claude with caching:
system = [{
    "type": "text",
    "text": system_prompt,
    "cache_control": {"type": "ephemeral"}  # ← 75% cost reduction on repeat calls
}]
```

**To change the active prompt version:** Update `PROMPT_VERSION=v2` in `.env` (local) or in the Cloud Run deploy command's `--set-env-vars`.

**To create a new version:** Copy `prompts/v2.md` → `prompts/v3.md`, make changes, redeploy with `PROMPT_VERSION=v3`. The old version stays on disk for rollback.

---

## Prompt 1: `prompts/v2.md` — Main Extraction Prompt

Used by: **Carver** (Pass 1 and Pass 2)  
Purpose: Extract all structured data from a traffic citation, inspection report, crash report, CDL license, MVR, civil penalty, warning, or photograph.  
Model: `claude-sonnet-4-6`  
Tokens: ~18,107 tokens (18K)

---

### Section Map — Where Everything Lives

```
v2.md
├── PERSONA + ZERO-TOLERANCE POLICY         (lines 1–10)
├── MULTIMODAL ANALYSIS REQUIREMENT         (lines 11–14)
├── DOCUMENT TEXT FORMAT DETECTION          (lines 15–73)
│   ├── Digital vs. Handwritten rules
│   ├── Percentage threshold logic
│   └── Classification: "digital" | "handwritten" | "mixed"
├── AI REASONING REQUIREMENT                (lines 74–80)
│   └── Every field must have ai_reason + raw_evidence
├── CORE LOGIC: CHAIN OF THOUGHT           (lines 81–148)
│   ├── STEP 1: Identify all document types
│   │   └── Keyword groups for each type + thresholds
│   ├── STEP 2: Determine primary file_type (hierarchy)
│   │   └── Ticket > Crash > Civil Penalty > Inspection > Warning > MVR > CDL > Photo > Unknown
│   ├── STEP 3: Conditional extraction per type
│   └── STEP 4: Populate metadata
├── TICKET EXTRACTION LOGIC                 (~lines 149–230)
│   ├── Violation identification rules
│   ├── Verbatim extraction rules
│   ├── Speeding format exception
│   └── Multi-violation list format
├── INSPECTION REPORT EXTRACTION LOGIC      (~lines 231–290)
├── CRASH REPORT EXTRACTION LOGIC           (~lines 291–340)
├── WARNING EXTRACTION LOGIC                (~lines 341–360)
├── CIVIL PENALTY EXTRACTION LOGIC          (~lines 361–390)
├── CDL LICENSE EXTRACTION LOGIC            (~lines 391–420)
├── MVR EXTRACTION LOGIC                    (~lines 421–450)
├── NORMALIZATION & MAPPING RULES           (~lines 451–510)
│   ├── Violation Category picklist (18 values)
│   ├── Date normalization rules
│   ├── Phone number format
│   └── Yes/No field rules
├── EXTRACTION FIELDS & LOGIC              (~lines 511–540)
│   └── Field-by-field extraction instructions
├── JSON OUTPUT STRUCTURE                   (~lines 541–590)
│   ├── Shared fields (always present)
│   ├── Ticket tier 1 defense fields
│   ├── Ticket tier 2 defense fields
│   ├── Inspection Report fields
│   ├── Crash Report fields
│   ├── Civil Penalty fields
│   ├── Driver / CDL fields
│   └── MVR fields
├── STATE-SPECIFIC FIELD AVAILABILITY      (~lines 591–644)
│   ├── States where Citation_Number is absent
│   ├── States where County is absent
│   ├── States where Fine IS printed
│   ├── States where Fine is NOT printed
│   ├── Florida special rules (court date calculation)
│   └── Washington special rules (court date calculation)
└── FINAL OUTPUT RULE                       (line 645+)
    └── ONLY output JSON. Start with {. End with }.
```

---

### How to Modify — Common Changes

#### Add a new Violation Category
Two places must match exactly:

**1. In `prompts/v2.md` — find the violation category picklist:**
```
The accepted values for Violation_Category__c are strictly:
- "Driver license violation"
- "Alcohol / Drug related violation"
...add your new category here...
```

**2. In `agents/charlotte_ray.py` — add to `CDL_POINT_MAP`:**
```python
CDL_POINT_MAP = {
    ...
    "Your New Category": {"points": X, "severity": "standard", "csa_category": "Unsafe Driving"},
}
```

**3. In `agents/bolin.py` — add to `_VALID_VIOLATION_CATEGORIES`:**
```python
_VALID_VIOLATION_CATEGORIES = {
    ...
    "Your New Category",
}
```

If you skip step 2 or 3, the system will log a warning and handle it gracefully, but the new category won't have a point value or pass Bolin validation.

---

#### Add a state-specific rule (e.g., a new state that doesn't print court dates)

In `prompts/v2.md`, find the `--- STATE-SPECIFIC FIELD AVAILABILITY ---` section near the bottom. Add a new block following the Florida or Washington pattern:

```markdown
**[State Name] — Special [Field]__c Rules:**

[State] does not print [field] on citations. [Explanation of state law / process].

**Apply this rule:**
- Set `[Field]__c` to [value or calculation].
- Set `confidence_score` to 0.95 and `ai_reason` to: "[State] — [field explanation]."
```

Also update the state-exception sets in `agents/bolin.py` so the Bolin doesn't incorrectly penalize the score:
```python
_NO_CITATION_STATES = {
    ..., "YourState",
}
```

---

#### Change the extraction model

In `app/services/claude_client.py`:
```python
create_kwargs: dict = dict(
    model="claude-sonnet-4-6",  # ← change this
    ...
)
```

Current options and relative cost:
| Model | Speed | Cost | Use For |
|-------|-------|------|---------|
| `claude-haiku-4-5-20251001` | Fastest | Cheapest | Document Gate (classification only) |
| `claude-sonnet-4-6` | Fast | Mid | Carver (current — recommended) |
| `claude-opus-4-8` | Slower | Most expensive | Photo Analyst, complex extractions |

---

#### Adjust confidence thresholds (GREEN / YELLOW / RED)

In `agents/bolin.py`:
```python
GREEN_THRESHOLD = 0.85   # ← lower this to accept more as GREEN
YELLOW_THRESHOLD = 0.60  # ← lower this to accept more as YELLOW
CRITICAL_FLOOR = 0.70    # ← lower this to be less strict on critical fields
```

Lowering thresholds → fewer human reviews, more automation risk  
Raising thresholds → more human reviews, higher confidence in automation

---

#### Add a new extraction field to the output

1. Add the field to the `--- JSON OUTPUT STRUCTURE ---` section in `prompts/v2.md`, listed under the appropriate tier
2. Add extraction instructions for the new field to the relevant extraction logic section
3. If it's a critical field (humans need it to work the case), add it to `_CRITICAL_FIELDS` in `agents/ida_wells.py`
4. If the Bolin should validate its format, add format-check logic to `agents/bolin.py` → `_calibrate_scores()`
5. Add the field key to `_FIELD_KEYS` in `agents/bunche.py` so it's merged correctly on Pass 2

---

### Violation Category Picklist (18 values — must match exactly)

These are the only valid values for `Violation_Category__c`. The string must match character for character including spacing and capitalization.

```
1.  Driver license violation
2.  Alcohol / Drug related violation
3.  Reckless Driving
4.  Speeding (15+)
5.  Cell Phone
6.  Failure to yield to emergency vehicle
7.  Following too close
8.  Careless Driving
9.  Lane Violation
10. Failure to Obey Traffic Control Device
11. Too Fast for Conditions
12. Speeding (1-14)
13. Seatbelt
14. ELD/Logs
15. Equipment/Maintenance
16. Registration Violations
17. Overweight/Overlength
18. Parking
```

**Mapping guidance** — when to use which:
- Officer writes "SPEEDING 75 IN 55" → `Speeding (15+)` (20 over)
- Officer writes "SPEEDING 62 IN 55" → `Speeding (1-14)` (7 over)
- Officer writes "FOLLOWING TOO CLOSELY" → `Following too close`
- Officer writes "IMPROPER LANE CHANGE" → `Lane Violation`
- Officer writes "FAILURE TO YIELD ROW" → `Failure to Obey Traffic Control Device`
- Officer writes "NO SEAT BELT" → `Seatbelt`
- Officer writes "HOS VIOLATION" → `ELD/Logs`

---

### Date Normalization Rules (from prompt)

All date fields are normalized to `MM/DD/YYYY`:
- `01/15/2025` ← correct
- `1/5/25` → normalize to `01/05/2025`
- `January 15, 2025` → normalize to `01/15/2025`
- `2025-01-15` → normalize to `01/15/2025`

Court time normalized to `H:MM AM/PM`:
- `9:00 AM` ← correct
- `14:30` → `2:30 PM`

---

### State-Specific Citation Number Exceptions

These states do **not** print citation numbers on their tickets. Bolin expects an empty value for these states with confidence 0.95, not 0.0:

Alabama · Alaska · California · Connecticut · Kentucky · Maryland · Massachusetts · Minnesota · Montana · Nebraska · Nevada · New Mexico · New York · South Carolina · Utah · Vermont · Virginia · West Virginia

---

### State-Specific County Exceptions

These states do **not** print county on their tickets:
Colorado · Virginia

---

### Fine Amount — State Rules

**Fine IS printed on ticket** (set `Fine_Printed_On_Ticket__c = "Yes"`):  
Texas · Florida · Georgia · Ohio · Pennsylvania · Illinois · Michigan · Indiana · Tennessee · Missouri · North Carolina · Virginia · Arizona · Colorado · Kentucky · Louisiana · Arkansas · Mississippi · Oklahoma · Kansas · Iowa · Nebraska · South Dakota · North Dakota · Wyoming · Montana · Idaho · Utah · Nevada · New Mexico

**Fine is NOT printed at issuance** (set `Fine_Printed_On_Ticket__c = "No"` — court sets it later):  
California · New York · New Jersey · Massachusetts · Connecticut · Maryland · Washington · Oregon · Minnesota · Wisconsin · Alabama · South Carolina · West Virginia · Vermont · New Hampshire · Maine · Rhode Island · Delaware · Hawaii · Alaska

---

### Florida Special Rules

Florida separates violations into civil infractions and criminal offenses.

**Civil infraction** (everything except DUI, suspended license, reckless driving):  
→ No court date printed. Calculate `Court_Date__c` as **30 days after `Date_of_Ticket__c`**.  
→ Set confidence 0.95, reason: "Florida civil infraction — payment due 30 days from issue date per Florida Statute."

**Criminal offense** (DUI, suspended license, reckless driving):  
→ Court date IS printed. Extract verbatim.

**Florida Citation Number:** The citation number doubles as the inspection report number. Copy the same value to both `Citation_Number__c` AND `Insp_Report_Num__c`.

---

### Washington Special Rules

Washington does not print a specific court date at issuance. The court mails a hearing date after the driver responds.

**All non-criminal violations:**  
→ Set `Court_Date__c` = **30 days after `Date_of_Ticket__c`** (response deadline).  
→ Confidence 0.92, reason: "Washington State — no court date printed. Calculated 30-day response deadline."

**Criminal offenses** (DUI, reckless, driving while suspended):  
→ Court date IS printed. Extract verbatim.

---

## Prompt 2: `prompts/photo_v1.md` — Photo Analysis Prompt

Used by: **Photo Analyst**  
Purpose: Analyze a photograph submitted with a CDL driver case and produce an attorney-ready brief.  
Model: `claude-opus-4-5`  
Tokens: ~500 tokens (very lightweight)

---

### Full Prompt

```
You are a visual analyst for Rig Resolve, a legal benefits platform for commercial truck drivers.

You are examining a photograph submitted alongside a CDL driver's case. Your job is to produce a 
precise, attorney-ready description of what the image shows. Attorneys use your analysis to understand 
evidence without always having access to the original image.

--- STRICT RULES ---
- Describe only what is visibly present. Never invent or speculate beyond what you can see.
- Be specific: note vehicle parts, damage locations, road conditions, signage, unit numbers, and 
  license plates when visible.
- Write your summary as if briefing an attorney who cannot see the image.
- Set confidence_score based on image clarity and your certainty about each observation.
- Your output must be ONLY the JSON object below — no preamble, no explanation.

--- PHOTO TYPE DEFINITIONS ---
Classify the image as exactly one of these types:
- "Vehicle Damage"       — shows damage to a commercial truck, trailer, or vehicle components 
                           (tires, wheels, body panels, frame)
- "Accident Scene"       — shows the crash/accident location, road, vehicle positions, skid marks, 
                           debris field
- "Person/Injury"        — shows a person (driver, other party) possibly injured or involved
- "Equipment Damage"     — shows damaged cargo, load securement equipment, or non-vehicle equipment
- "Road/Environment"     — shows road conditions, weather, signage, or environment relevant to incident
- "Driver Documentation" — shows the driver holding or displaying a document (license, logbook) 
                           for verification
- "Repair Documentation" — shows a vehicle at a repair facility, or work being performed
- "Other"                — does not fit any category above

--- ATTORNEY NOTES GUIDANCE ---
In Attorney_Notes__c, flag things that have legal/defense value:
- Tire condition (tread, sidewall, inflation) → equipment maintenance defense
- Skid mark length and pattern → speed and reaction time
- Road signage, lighting, lane markings → visibility and infrastructure defense
- Weather/road surface (wet, ice, gravel) → road hazard defense
- Other vehicles' positions or damage → comparative fault
- Visible truck unit number, DOT number, carrier name → carrier identification
- Any evidence that contradicts the citation

--- OUTPUT FORMAT ---
Return exactly this JSON structure:

{
  "file_type": "Photo",
  "photo_type": "<one of the 8 types above>",
  "file_name": "<filename passed in>",
  "document_text_format": "photo",
  "file_type_analysis": {
    "confidence_score": <0.0–1.0>,
    "ai_reason": "<brief explanation of photo type classification>"
  },
  "other_document_types": [],
  "Photo_Type__c": {
    "value": "<same as photo_type>",
    "confidence_score": <0.0–1.0>,
    "ai_reason": "<why you classified it this way>"
  },
  "Photo_Summary__c": {
    "value": "<2–5 sentence visual description of the photograph for an attorney who cannot 
               see it. Describe subject matter, angle, lighting, and any text or numbers visible>",
    "confidence_score": <0.0–1.0>,
    "ai_reason": "<key visual elements you relied on>"
  },
  "Damage_Assessment__c": {
    "value": "<specific description of damage: location on vehicle, severity (minor/moderate/
               severe/totaled), type of damage (crush, tear, puncture, burn), and whether it 
               appears fresh or pre-existing. Return empty string if no damage visible>",
    "confidence_score": <0.0–1.0>,
    "ai_reason": "<visual basis for damage assessment>"
  },
  "Attorney_Notes__c": {
    "value": "<1–4 specific observations with legal/defense relevance. Each observation should 
               reference a visible detail and explain its potential significance. Return empty 
               string if no defense-relevant details found>",
    "confidence_score": <0.0–1.0>,
    "ai_reason": "<why these observations are legally relevant>"
  }
}
```

---

### How to Modify Photo Prompt

**Add a new photo type:**  
Add to the `--- PHOTO TYPE DEFINITIONS ---` section and update `_KNOWN_PHOTO_TYPES` in `agents/photo_analyst.py`:
```python
_KNOWN_PHOTO_TYPES = {
    "Vehicle Damage", "Accident Scene", ..., "Your New Type",
}
```

**Add a new output field:**  
1. Add the field to the JSON structure in `prompts/photo_v1.md`
2. Add a default value to `_MOCK_RESULT` in `agents/photo_analyst.py` so mock mode works
3. Add an empty fallback to `_EMPTY_FIELD` if applicable

**Change the photo analysis model:**  
In `agents/photo_analyst.py`:
```python
response = client.messages.create(
    model="claude-opus-4-5",  # ← change this
    max_tokens=1200,
    ...
)
```

---

## Prompt 3: Document Gate (Inline)

Used by: **Document Gate**  
Location: hardcoded in `agents/document_gate.py` → `_GATE_PROMPT`  
Model: `claude-haiku-4-5`  
Tokens: ~100 input, 1–2 output

```
Look at this image. Classify it as exactly one of three types:
- 'photo': a photograph of a scene, vehicle, person, accident, damage, or environment 
           — NOT a document
- 'document': a legal or government document with structured text fields (citation, ticket, 
              inspection report, crash report, CDL license, motor vehicle record, civil 
              penalty notice, or similar form)
- 'unknown': anything else — blank page, illegible scan, personal document unrelated to a 
             CDL case

Reply with ONLY the single word: photo, document, or unknown. No explanation.
```

**How to modify:**  
Edit `_GATE_PROMPT` string in `agents/document_gate.py`. Keep it under 200 words — this is a haiku call and cost is the priority. If you want to route a new category (e.g., separate "medical records" from "unknown"), update both the prompt and the `route_after_document_gate()` function in `orchestrator/graph.py`.

---

## Versioning Convention

| Version | Status | Notes |
|---------|--------|-------|
| `v1.md` | Archived | Original extraction prompt — no CDL-specific rules, no multi-type support |
| `v2.md` | **Active** | Full multi-type extraction, state-specific rules, CDL enrichment context |
| `v3.md` | Not yet created | Create when making substantial changes to v2 |

**Rule:** Never edit an active prompt in place without creating a new version file first. The old version is the rollback.

To test a new prompt version locally without affecting production:
```bash
# .env
PROMPT_VERSION=v3
USE_MOCK=false
```

Then run the local server and test against sample images. Only change `PROMPT_VERSION` in Cloud Run deploy when the new version passes batch testing.

---

## Batch Testing After Prompt Changes

After any prompt modification, run the batch scanner against the sample ticket library:

```bash
python3 scripts/batch_scan.py \
  --dir "/Users/digitalmercenary/CDL_Defense/ai tickets samples/20260627 - Batch 1" \
  --api http://localhost:8080 \
  --out scripts/batch_results_v3.json \
  --delay 1
```

Compare results:
- Did GREEN rate improve?
- Did any previously-extracted fields go blank?
- Did violation category accuracy improve?
- Are state-specific rules being applied?

Use `scripts/batch_results.json` (v2 baseline) as the comparison.
