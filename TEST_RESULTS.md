# Validation recorded for Four Apps v3.0

## End-to-end browser/server tests
A real local Python HTTP server and one SQLite database were used with FOUR INDEPENDENT Playwright browser contexts (isolated browser storage), proving the core connection is the API/database rather than localStorage events.

Passed:
- Dedicated Customer, Doctor, Hospital and Driver logins. No combined role-selection screen.
- Customer consultation request -> scoped Hospital accept/doctor/fee -> customer simulated company payment -> Hospital completion -> Customer status/recent doctor update.
- Prescription uploaded into SQLite -> Customer reload -> Hospital opens persistent file -> acceptance -> service -> bill -> generated link -> customer mock payment -> wrong completion OTP rejected -> correct server verification.
- Driver online -> matching Customer request -> acceptance -> arrival -> pickup OTP -> hospital trip/drop -> handover OTP -> unpaid claim blocked -> customer mock collection -> one full-fare driver claim.
- Expected pickup/completion codes absent from Driver API state.
- Doctor submission with common hospital ID -> Hospital follow-up/admission -> Doctor status update.
- Reports in ALL FOUR apps with real PDF/XLSX downloads and date/service UI; 320x568, 390x844 and 1440x900 report layout checks.
- Exported XLSX ZIP CRC and all XML parsed successfully for all four roles. Exported PDF recognised as A4 PDF 1.4 and visually inspected in representative cases.
- No uncaught browser JavaScript errors in the tested end-to-end paths.

## Backend/API tests
Passed:
- Unauthenticated write denied; other customer's/hospital's records hidden.
- Wrong-hospital request acceptance denied.
- Two simultaneous driver accept requests produce exactly one winning assignment.
- Server fare derives 1420 at 10 km despite spoofed client amount.
- Customer snapshot cannot spoof completed/paid trip state.
- Server rejects wrong OTP, premature payment/claim, duplicate collection and duplicate claim.
- Protected saved prescription readable by owning Customer/selected Hospital, denied to other Hospital and Driver.
- File-signature/type mismatch rejected; upload size/type constraints apply.
- Role-scoped report rows and invalid date range handling.
- Doctor-to-Hospital follow-up/admission changes.
- SQLite foreign_key_check returns no violations.
- Request/payment/claim/document data survives reinitialisation; seeded accounts do not overwrite records.

## Limits
Windows .bat launchers were source-reviewed but not executed on Windows here. Physical devices, real GPS accuracy, external map/geocoding availability, real OTP/SMS/WhatsApp, live hospital/clinician/driver verification, gateway captures and bank payouts are not tested/implemented as production integrations. Demo credentials are public. No production security or regulatory approval is claimed.

## v3.1 additional validation
- Reproduced a Sunrise customer request across independent browser contexts: hospital003 sees it; hospital001 does not.
- Hospital inbox displays scoped hospital name/ID and Refresh works.
- Customer's legacy 'Demo: hospital confirms doctor & fee' control is not visible.
- Hospital accepts with changed date/time; Customer sees original vs revised slot.
- API rejects payment until revised schedule is accepted.
- Paid appointment rescheduling requires new consent and does not request another payment.
- API rejects overlapping confirmed slots for the same doctor, stale schedule revisions and completion before consent.
- Existing paid amount and original customer preference remain unchanged in the database.
- Small mobile screens and Hospital reports footer remain within the viewport/nav layout.

Slot fix: requested-slot acceptance without editing and with stale editor values passes; revised-slot consent, browser default mode/editor visibility, overlap checks and API regression pass.

v3.3 browser regression: customer payment arrives while hospital schedule input focused; deferred refresh renders on blur, payment received and completion button visible, rescheduling collapsed; paid reschedule and completion pass.

v3.4: Four independent browsers, consultation, stored lab prescription, quote/link/payment/OTP, ambulance/driver claims, Doctor/hospital admission, all four PDF/XLSX and viewport tests pass. Service API tests cover pharmacy/lab/physician/packages/camps; paid cancellation/refund references and role-scoped review; completed cancellation/duplicate refund/payment blocked. Browser refund form, review sync, full expandable timeline and 320x568/390x844/1440x900 fit pass.

v3.5: Shared polish CSS loading verified in all four apps. 129 route/viewport checks: Customer Home/Bookings/Profile/Updates, consultation and prescription forms, ambulance, packages/offers/scan/cashback/details/reports; Doctor Home/patients/submit/details/wallet/offers/shopping/profile/security/documents/QR/notifications/reports; Hospital and Driver main screens. Screens inspected visually. Frames/nav/footers and horizontal overflow checked at 320x568, 390x844, 1440x900.

v4.0: API tests cover terms enforcement, cancellation request/approval/rejection, premature refund denial, role isolation, completed-service/report locks, explicit credit consent, duplicate issuance/debit prevention, credit-only cancellation restoration, bank preference masking and rejection of full-account payloads, private document bytes, scoped deletion requests. Browser terms/approval/refund/credit redemption/Hospital report publication/Records viewer-download/deletion request and viewports pass. Synthetic gateway signature tamper tests pass; no live provider tested. Full four-context booking/payment/OTP/trip/Doctor/report regressions pass. This is correctness QA only, not load certification.

v4.1: 220 route/viewport checks across all four apps (portrait and short landscape). Visual inspection of compact home/form states. Browser test covers Driver login auto-ON, manual OFF/reload persistence, signout OFF; absent Age/manual note; 16px consent; server-generated referral reference; actual QR decoded independently using jsQR; public form submission visible to Doctor and selected Hospital. API tests cover offline matching suppression, all-session signout, scoped token intake, consent and duplicate submissions. Full consultation/prescription/payment/OTP/ambulance/Doctor/report regressions pass. Locked-phone/native/Web Push delivery is not implemented or device-tested.

v4.2: 220 route/viewport checks pass with all app frames constrained to maximum 410px and two-column service layouts. Landscape expansion removed; vertical scrolling remains within each app.

v4.3: 220 app route/viewport checks plus five public intake viewport checks. Visible field grids must compute to one column. Intake width <=410px, viewport containment, no horizontal overflow and actual top-to-bottom field order checked at 320x568/390x844/568x320/844x390/1440x900.

v4.4: Browser confirms automatic reference equals unique request ID, absence of manual input, bill issue without reference, paid bill read-only summary, cash + completion OTP and completed state, compact paid/completed screen fits 390x844 without internal scrolling. Provider-service and API security regressions pass.
