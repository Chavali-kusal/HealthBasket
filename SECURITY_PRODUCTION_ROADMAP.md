# Security, store release and production readiness — 25 October 2026

## Release status

This bundle is a runnable four-client LOCAL DEMO, not an APK/IPA, production payment system or store-approved product. Public OTP/password 1234 and a local SQLite medical-data store make it unsuitable for public deployment or real patient/bank information. No provider credentials were supplied. Razorpay/Cashfree checkout, refunds, payouts and webhooks remain disconnected. Signature helpers are unit-tested reusable code, not a live integration. No audit, penetration test, store review or large-scale capacity certification has been performed.

## Controls implemented in this bundle

Role/ownership-scoped actions and documents; parameterised SQL; PBKDF2 password hashes; random expiring bearer sessions; server-side price/status/OTP checks; origin check on browser writes; simple in-process login throttle; size/type/signature upload checks; no-store responses; MIME sniffing protection; same-origin framing; limited camera/location permission policy. Payment terms are versioned and server-enforced. Completion/cancellation/approval/refund transitions are checked on the server. Finance credit issuance and redemption are transactional and duplicate-protected. Full bank account/card credentials are rejected by the refund-preference endpoint; hospital/driver responses exclude bank preference and customer OTPs. SQLite WAL and account request indexes improve local concurrency.

Privacy/export/account-deletion request entry points are available in every profile. Requests persist for company review. This is initiation only: identity verification, actual erasure/anonymisation, legally required retention, backups deletion and public deletion website still need production implementation. Do not tell reviewers that this request form by itself fulfils all deletion obligations.

## Mandatory build/operations gates before real release

- Replace demo identities with verified OTP/OIDC login, MFA for Hospital/company, account recovery, device/session revocation and scoped short-lived tokens. Persist distributed rate limiting and fraud rules. Verify clinicians, hospitals and ambulance partners and their authorisation.
- Serve HTTPS; separate internet edge, app APIs, clinical documents and finance systems. Use hardened production application servers, WAF, secrets manager/KMS, least-privilege service identities, key rotation, dependency scanning and environment separation. Do not expose this Python http.server.
- Store documents in encrypted object storage with private bucket policies, short-lived signed URLs, antivirus scanning and retention rules. Encrypt sensitive fields and backups. PDFs/images require more than a magic-byte check. Never log patient content, OTPs, access tokens or bank data.
- Payment intent/order creation must happen on the server with integer paise and an immutable price snapshot. Use hosted provider checkout; never accept card PAN/CVV. Verify signatures, fetched payment status, amount/currency/order/merchant identity. Return callbacks are not proof of payment. Maintain persistent event deduplication, state precedence, out-of-order handling and daily reconciliation.
- Use real refunds to original source, idempotent refund keys and reconciled refund events. Verified bank payouts require separately authorised product/onboarding, secure beneficiary collection and maker-checker controls. Review closed-loop credit terms/treatment with qualified legal/accounting/provider teams; never force a cash refund into app credit.
- Test actual care/telemedicine consent, privacy notice, support/grievance contact, retention/deletion policy, emergency limitations, cancellation terms and refund eligibility with applicable Indian healthcare/privacy/payment rules. No fabricated service or post-discharge document can justify a fee. Admission/referral status does not create a Doctor fee.
- Add incident response, monitoring, alert ownership, fraud/dispute operations, backup restoration drills, multi-zone failover, disaster recovery objectives and independent penetration testing. Close critical/high findings before any real-data pilot.

## Google Play and Apple release gates

Create Android/iOS native or appropriate secure hybrid builds with signing, bundle IDs, supported OS/device matrix, deep links, permission purpose strings, accessibility/dynamic type, real device tests and crash monitoring. A localhost HTML bundle cannot be submitted as the four finished native apps. Configure secure WebView bridging if used; avoid broad file/network access or a thin broken website wrapper.

Publish accurate privacy and support URLs. Complete Google's Data safety and relevant Health apps/Financial features declarations and Apple's App Privacy details. Inventory every SDK and disclosure. Ask for location/camera only when the user invokes pickup/scan; explain why. No health-data ad targeting. Account deletion needs an in-app path and Google's external web link; backend operations must actually fulfil approved requests subject to lawful retention. Account for physical healthcare services versus any digital goods when selecting payment rails; review exact service/store rules rather than assuming every payment may use an external gateway.

Provide reviewer demo credentials, sample QR, sample prescriptions, clear demo/live separation, test location and instructions for each role. Check content ratings, medical claims, licensed entities, screenshots and metadata. Avoid fake testimonials, fabricated clinical records or guaranteed approval claims. Store/provider approval is their decision and must be rechecked for each release.

## Primary sources reviewed

- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/support/offering-account-deletion-in-your-app/
- https://support.google.com/googleplay/android-developer/answer/10787469
- https://support.google.com/googleplay/android-developer/answer/13327111
- https://support.google.com/googleplay/android-developer/answer/13849271
- https://razorpay.com/docs/payments/refunds/
- https://razorpay.com/docs/webhooks/validate-test/
- https://www.cashfree.com/docs/payments/online/webhooks/signature-verification
- https://www.cashfree.com/docs/payments/quick-guide/refunds

These are implementation/release references, not legal approval or a promise of compliance.
