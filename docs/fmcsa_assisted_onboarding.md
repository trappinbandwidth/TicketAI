# FMCSA-assisted Carrier onboarding and Driver career history

## What the Pilot implements

The public discovery API searches the locally ingested FMCSA motor-carrier
authority index by USDOT, docket/authority number, legal or DBA name, full
public phone, and city with an optional state filter. Results are capped at 20;
the default is 10. Search results mask the phone except for its final four
digits. Selecting one USDOT returns the whitelisted public record, its local
cache provenance, and carrier-level crash context when available.

The Carrier onboarding client may pass the selected USDOT back during
registration. The Engine reloads the source record and stores an immutable
server-derived snapshot separately from the Carrier profile. The Carrier
workspace and USDOT claim remain `pending_verification`/unverified.

The Driver can select the same public record for a self-reported employment
history entry. The entry is owned only by that Driver principal, retry-safe,
editable without changing its USDOT/start-date identity, deletable, and audited.

## Required labels

- FMCSA values: `authoritative_public` source context with cache date.
- Carrier selection: `applicant_confirmed_record_match`.
- Carrier account control: `pending_verification`.
- Driver employment claim: `driver_self_reported` / `self_reported`.
- Carrier crash context: `carrier_level_public_context`.

Carrier-level authority or crash data must never be labeled as an individual
Driver's MVR, PSP, Clearinghouse, inspection, or safety history.

## What selection does not do

Finding or selecting a public Carrier record does not:

- authenticate the user or prove that they represent the Carrier;
- grant access to an existing TIP workspace;
- merge duplicate USDOT claims;
- attach a named Driver to a Carrier;
- confirm that a Driver worked for that Carrier;
- update the official FMCSA record; or
- create a TIP Score, Carrier Passport, payment account, or private FMCSA login.

Duplicate USDOT claims remain isolated and quarantined for Captain review. The
Pilot records the authority state as pending until a separately approved
business-email, domain, listed-phone, document, existing-administrator, or
Captain verification workflow completes.

## Support response

- Wrong company selected before registration: return to search and select the
  correct USDOT record.
- Wrong USDOT submitted with a selected record: the API rejects the mismatch;
  do not override it manually.
- Official information is outdated: explain that TIP preserves the FMCSA
  snapshot and Carrier-provided correction separately. The Carrier must use the
  applicable FMCSA process to change the official record.
- Applicant disputes control: preserve the claim and audit IDs, keep workspaces
  isolated, and escalate to Captain.
- Driver disputes career data: only that Driver may edit or delete the
  self-reported entry.

## Performance evidence

At the 2026-07-25 local checkpoint, the 55,552-record search index is normalized
once during Engine startup. Exact USDOT lookup is constant-time (approximately
0.1 ms locally); warm name search measured approximately 123 ms. Startup index
construction measured approximately 4.4 seconds and should be revisited during
the release performance audit or replaced with a generated search artifact.
