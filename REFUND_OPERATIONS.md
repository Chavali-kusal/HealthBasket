# v4.0 — Company cancellation and refund operations

## Working local flow

1. Customer pays only after ticking versioned cancellation/refund terms. Server stores acceptance timestamp/version, payment reference, discount used and simulated cash collected separately.
2. Customer requests cancellation with a reason. Booking stays at its existing service stage; `cancellationStatus` becomes `Pending approval`. No refund claim exists yet. Company/hospital verification target is 48 hours from request, not a guarantee of bank credit in 48 hours.
3. Selected Hospital opens the booking, records its actual verification and approves or rejects cancellation. Other hospitals and Customer cannot approve. Rejection retains the service stage and allows the service to continue. Approval changes stage to Cancelled and exposes refund eligibility only for recorded money collected. Completed services and published clinical reports are blocked. Actual ambulance safety/trip updates remain possible while review is pending; actual completion wins over a pending cancellation.
4. Customer explicitly claims original-payment refund, optional discount credit, or bank-transfer preference. Changing method or submitting a second claim after submission is blocked; support must reconcile an exceptional correction.
5. Company finance independently verifies the original collection, service status, selected method and bank/gateway reconciliation. Hospital cannot issue credits or approve its own payout.

## Trusted company operator (local demo only)

Run from the project folder. These commands use the same `data/healthbasket.sqlite3` as server.py (or identical HEALTHBASKET_DB override). Restrict operating-system access to authorised staff. This is NOT an authenticated production finance dashboard.

```cmd
python company_finance.py list
python company_finance.py issue-credit REQUEST_ID --reference VERIFIED_CASE_REFERENCE
python company_finance.py queue-refund REQUEST_ID --reference GATEWAY_OR_VERIFICATION_REFERENCE
```

`issue-credit` requires Customer's explicit discount choice and approved cancellation. It creates one immutable-source credit ledger entry, marks simulated issuance, and emits an audit event. Repeats fail. Available credit is shown at next eligible checkout; user may tick Apply discount. Debit and payment are in one transaction. Gross service amount and net simulated collection are separate. If a credit-funded service is cancelled with approval, used credit is restored once; only the actual cash component is eligible for bank/source refund.

`queue-refund` records finance verification/queue status ONLY. It calls no payment provider and cannot mark an actual bank refund complete. Bank option captures sample holder, IFSC, last four digits only; no complete account number is accepted. Full bank/beneficiary onboarding and payout are disabled pending encrypted/hosted provider integration. Never ask for bank PIN, OTP, card CVV or internet banking credentials.

Original-source refund should be the normal route for gateway-paid orders. Bank payouts are a distinct regulated/provider workflow, not an interchangeable implementation of a gateway refund. Discount conversion is voluntary; cancellation terms must not remove statutory rights or mandatory refunds.

## Reports and Records

Customer Records includes actual persisted prescription uploads, Hospital-issued report/prescription/discharge attachments, payment summaries and cancellation/refund history. No medical report is automatically invented. Hospital uploads PDF/photo only after actual service completion. Owner and selected hospital can download; other accounts cannot. Files are local SQLite BLOBs with signature/type/size checks, not malware-scanned encrypted production storage.

Refunds and discount credits appear as separate report records; they are not extra revenue and must not be summed with request amounts as collections. Full request history is retained in the expandable timeline.

## Existing databases

Keep your existing database. Schema additions are additive. Old v3.4 cancellations/refunds without an approval trail must be reconciled manually; this update does not manufacture a historical hospital approval. Back up the old DB before upgrading. Do not erase historical payments to make a new claim eligible.

## Production operations still required

A staffed support contact, overdue-review queue/alerts and escalation; automatic gateway reconciliation; verified refund references (ARN/RRN/UTR where applicable); gateway retry/failure handling; maker-checker finance approval; encrypted bank-beneficiary vault; immutable remote audit log; tested recovery and privacy retention/deletion fulfilment. The 48-hour text is an operational target requiring real staffing and monitoring, not an implemented background refund timer.
