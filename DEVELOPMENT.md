# Four Apps v3.0 — implementation and next development

## What changed
The combined Hospital/Driver selector has been replaced by four independent HTML clients and URLs. Hospital and Driver have distinct presentation, login, navigation and dashboards: a hospital operations workspace and an AmbuSprint driver workspace with online state, trip progression and earnings. Customer v2.2 and Doctor v1.4.1 visual baselines are retained, with their core request/care/report routes connected to the shared API. All four apps now have date/service-filtered PDF/XLSX reports.

This is a runnable local full-stack demo, not another same-browser storage bridge. A Python standard-library ThreadingHTTPServer serves the four clients and a common role-scoped API. SQLite stores canonical hospitals/services/users, actual request/trip/care states, prescription bytes, simulated collections and driver claims. Browser sessionStorage holds the role-specific API token; browser localStorage remains for selected UI preferences and temporary pickup-map state, not the authoritative shared core records.

No third-party Python packages or app.py are required. server.py requires Python 3.10+ as documented. The Windows launchers are source-reviewed; this Linux environment did not execute Windows batch files. Browser/API/server code was exercised on a real local HTTP server in automated tests.

## Independent app identity
- /customer/: dedicated customer onboarding/login, previously approved service tiles/QR/cashback/reports UI.
- /doctor/: dedicated Doctor account gate and existing Doctor workspace; shared hospital master and care submissions.
- /hospital/: dedicated staff account login, hospital overview/inbox/Doctor care/billing/reports. No role selector.
- /driver/: dedicated driver login/registration, online state, eligible requests/trips/claims/reports. No role selector.

Different browser profiles/contexts can interact through the same running server. It is not necessary to share localStorage. A different physical device must reach the same server and use its address. The default server listens only on 127.0.0.1. For an isolated trusted LAN test, run `python server.py --host 0.0.0.0 --port 8765`, then visit the computer's LAN address with each role path. Demo credentials are public and the local database is not encrypted; do not expose this demo to the public Internet. Physical-device testing, firewall/network setup and HTTPS deployment are not performed by this deliverable. Camera/GPS generally require HTTPS or localhost; a phone's localhost is not the desktop server.

There are no native APK/IPA binaries, production push notifications or app-store releases in this package. The deliverable is four app-style web clients plus the shared API/database.

## API/session and access model
Sessions are opaque random tokens with an eight-hour expiry. Seed account passwords are PBKDF2 hashes, not plaintext database passwords. Seed/demo password and customer OTP remain publicly known 1234, so this is not production authentication, real phone verification, KYC or MFA.

The server authenticates each API call and scopes reads/writes:
- Customer owns its requests, receipt/benefit records and prescription uploads.
- Hospital staff access only their hospital's requests/referrals/documents and receipt confirmations.
- Driver sees its eligible nearby queue and own assigned trips; clinical prescription/reason fields and expected OTP codes are withheld. Reports include assigned trips/claims, not the unrelated nearby queue.
- Doctor accesses its own submissions/profile. Admission updates belong to the matching Hospital.

Role checks, server-side OTP comparisons, SQLite BEGIN IMMEDIATE transactions, unique payment/claim constraints and amount validation are implemented for the tested core flows. Client flags cannot set service completion/payment or overwrite an assigned trip through the customer-save endpoint. This is still a demo implementation: real OTP delivery/expiry/rate limits, stronger account verification, abuse protection, session/device management and production review remain necessary.

## Customer/hospital service flow
Customer creates request with canonical hospital/service mapping. Hospital accepts, confirms an online doctor/fee or later reviews a prescription and issues an after-service bill. Customer performs the local dummy checkout. Hospital records actual sample service/delivery and validates the customer-provided completion OTP through the server. Company collection and completion are separate states.

For Pharmacy/Lab/Physician there is no upfront fixed price: prescription + address -> hospital acceptance -> service/delivery -> hospital bill -> cash acknowledgement or hospital-generated payment link -> completion verification. Packages retain example prices and after-service settlement. Customer cannot record staff cash receipt or manufacture a hospital link; it can request one and pay an active link. Mutating a bill after collection is rejected. Actual external clinicians, stock, schedules, fees and MOU rates are not verified.

The existing sample hospital QR/bill and customer benefit screens remain demonstrations. A sample bill payment uses a server-known example amount and records a simulated payment; a real hospital/merchant/gateway is not connected. Direct receipts and benefits remain separate ledger records with confirmation/eligibility rules. Rate cards, healthcare commercial terms, fees/cashback eligibility and actual settlement arrangements still require the previously discussed qualified review; this build grants no legal approval.

## Prescription persistence
The Customer uploads supported JPG/PNG/WebP/PDF bytes to the shared database after the request is created. The server checks declared size/type and basic file signature, stores a BLOB and returns a document ID. The selected Hospital can fetch it via an authenticated endpoint after the Customer tab closes/reloads. Other hospitals and drivers are denied in tests.

This is not a production medical-document repository: malware scanning, encryption at rest, retention/deletion, audited document access, signed/object-storage URLs, consent management and operational privacy controls remain to be implemented. Use invented files only. Receipt-proof uploads in the legacy direct-receipt workflow remain metadata-only; durable prescription storage must not be mistaken for completed receipt document integration.

## Ambulance and hospital updates
Driver registration captures vehicle class/number, opted-in online state and a registered service-base coordinate. A sample BLS account is seeded at the explicit Anantapur demo coordinate. These are demo registrations, not verified driver/vehicle credentials.

The Customer's confirmed pickup and chosen destination hospital are stored on one trip request. Nearby eligibility uses online/opt-in/class and a 10 km straight-line radius from registered base, not live road proximity. Company fare is server-calculated from the manual demo route estimate: INR 1200 + INR 12/km + INR 100 extras. At 10 km, 1420 is derived server-side; a spoofed client amount is ignored.

Driver first acceptance wins under a shared transaction; one active trip per driver; arrival -> customer pickup OTP checked by server -> trip -> hospital drop -> customer handover OTP checked by server -> completed. The expected codes are returned to the owning Customer, not the Driver/Hospital. The selected Hospital receives persisted request/arrival/pickup/drop events; its inbox polls for updates. These are actual internal shared-DB updates, not real SMS/WhatsApp/push delivery.

A driver can share a browser GPS point; it is not continuous background tracking or live navigation. Route graphics and ETA/dispatch are illustrative. Real routing, secure location streaming, freshness/accuracy handling, verified vehicle capabilities, expiring offers, safety escalation and emergency operations remain future integrations.

After completed trip + handover OTP + simulated company collection, the assigned Driver can create one full-fare claim. Payout stays pending company finance. No Hospital/Driver/Customer can authorise a bank payout. Finance review, verified beneficiary, captured/settleable funds, idempotent payout provider callbacks, refunds and disputes remain a future authorised company service.

## Doctor care coordination
Doctor submits to the same canonical hospital master used by Customer. Hospital follow-up/admission records update the Doctor workspace through the API. No professional service, fee, referral commission, post-discharge work, signature or legal approval is inferred from admission. Old seeded patients/claims are not imported. The retained wallet/document UI does not create a bank/clinical entitlement; the new API does not approve referral-linked fees. Any genuine professional-service billing extension must be separately specified and reviewed.

## Reports
One report component queries the shared API with role-scoped rows. From/To are inclusive creation dates in Asia/Kolkata (IST); they are not completion or payment dates. Reports use current record statuses. Driver and Doctor report selectors show relevant record types; Customer/Hospital have service/ledger filters.

PDF and Excel are actual downloadable files, generated offline from authorised rows. Excel is OOXML .xlsx with Summary/Filtered records worksheets and inline strings (formula-like text is not evaluated). PDF is A4, multipage when needed, using rasterised browser text; it is not searchable/tagged PDF. Download-again links are tied to their filter snapshot. Unbilled/unknown values stay blank; Doctor care rows do not generate fees. Request amounts, direct receipts, benefits and claims are separate ledgers, not summed into an invented paid balance.

## Operational next steps
1. Versioned migrations, full relational/typed billing fields and PostgreSQL deployment when required; no external PostgreSQL setup is included.
2. Production auth/OTP/identity verification, credential rotation, roles/hospital staff administration, rate limits, audit/retention and encrypted storage/backups.
3. Provider/clinician/stock/scheduling integrations and approved hospital rate cards, insurance/exclusion and dispute policies.
4. Protected upload lifecycle and actual receipt-evidence storage/reconciliation.
5. Approved gateway/merchant onboarding, signed payment webhooks and ledger reconciliation; linked hospital settlement and authorised company finance/payout role.
6. Verified driver/vehicle onboarding, actual route-distance quotes, secure live GPS, dispatch offer expiry, notifications and safety support.
7. Consent-scoped WhatsApp/push outbox/provider integration. No messages are sent by this code.
8. HTTPS hosting, physical mobile testing, packaging/release/update manifests and deployment hardening.

All 4 apps share the same tables/connection; this is a local functional demo, not production medical, emergency or financial software.

## v3.1 — inbox clarity and consultation schedule confirmation
The screenshot's Sunrise request is scoped to hospital003/HOSP-003, not hospital001/VeloCare. The Hospital inbox now identifies its signed-in hospital/ID with a manual Refresh action, and login help lists the three demo staff accounts. Browser-tab visibility triggers an immediate API refresh. Cross-hospital access remains denied.

The Customer-side legacy provider-confirmation button could remain visible because author CSS overrode the native hidden display rule. A global `[hidden]{display:none!important}` resolves that display issue; the server still independently requires Hospital role for approval.

Hospital consultation acceptance includes confirmed date and start/end time in IST alongside doctor and fee. The original requested date/slot is preserved. The server validates date/time, checks overlapping confirmed intervals for the same demo doctor ID, and stores a schedule revision. Actual provider availability is staff-confirmed; there is no external calendar/doctor-master integration.

Changed appointments require explicit Customer acceptance of the current schedule revision before payment and before consultation completion. Hospital may revise an unfinished confirmed consultation, including after a simulated payment, but may not alter paid fee/doctor through the reschedule action. Paid rescheduling never creates another collection. Stale acceptance revisions are rejected. Existing rows acquire these optional schedule fields when confirmed/rescheduled, without schema or destructive migrations. Keep the existing database when updating.
