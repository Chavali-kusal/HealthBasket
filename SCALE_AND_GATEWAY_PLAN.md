# Production engineering handoff

## Ten million members versus concurrent users

Ten million registered accounts is different from ten million people actively using the app simultaneously. Both require measured workload assumptions. No capacity guarantee follows from a UI update, SQLite index, or successful local tests.

For illustration only, 10,000,000 active clients making one read every 30 seconds generate about 333,333 reads/second BEFORE login, writes, documents, payments and tracking. The demo's 1.8-second snapshot polling would approach 5,555,556 requests/second if used by 10 million active clients. Do not deploy that polling design at this scale.

## Target topology (not deployed)

CDN/static assets -> WAF/rate limit -> multi-zone load balancer -> horizontally scaled stateless API services. Keep booking/care, notifications/tracking, document access, credit ledger and payment/finance services independently bounded. PostgreSQL transactions + unique keys for bookings and money; appropriate regional partitioning/read replicas; Redis for bounded caching/distributed rate limiting (never authoritative money). Queue/outbox workers for notifications and provider retries; persist deduplication and dead-letter cases. Private encrypted object storage/CDN signed downloads for documents. Use event subscriptions/WebSocket/SSE with backoff and fan-out infrastructure, not full-account snapshots per client. Page all lists; use cursor/delta updates and per-user indexes. Centralise observability, trace IDs, audit export, SLOs and cost limits.

Choose a provider region, data-residency policy, recovery targets and availability budget with the company. Design tenant isolation, hospital IDs and actor scopes into every query/event. Use integer minor-unit accounting and double-entry ledgers in the production finance database. Existing SQLite JSON rows need an audited migration; retain original references and reconcile totals before switching traffic.

## Performance acceptance work

1. Measure expected DAU, peak concurrency, geographic distribution, ride tracking frequency, document sizes and write/payment rate. Separate cached/CDN traffic from transactional traffic.
2. Define targets (illustrative, not achieved): booking reads p95 <300 ms; writes p95 <700 ms excluding gateways; availability target agreed by management; zero duplicate money movements. Measure error rate, queue age, DB lock waits, connection saturation and memory.
3. Build staged k6/Locust distributed load suites against isolated synthetic data. Test 1k, 10k, 100k users first; increase only after each bottleneck is understood. A 10-million-concurrent validation needs a funded distributed load fleet and network/provider capacity, not one laptop.
4. Include sustained soak, burst login, same-slot contention, duplicate/reordered webhooks, gateway outage, lost callback, DB failover, queue lag, expired sessions, large documents and regional failure. Prove restore and payment reconciliation, not just homepage throughput.
5. Perform canary releases, live capacity monitoring, circuit breakers/backpressure, rollback drills and peak headroom planning. Sign off measured capacity after production-like tests. The local browser/API tests in this ZIP validate correctness, not million-user performance.

## Gateway integration contract

Live/Test provider APIs are NOT connected in this release. `gateway_security.py` verifies raw-body signatures only and has synthetic tamper tests. It does not parse provider events, verify amounts or deduplicate events. Required next implementation:

- Server creates Razorpay/Cashfree order with immutable internal order ID, amount in paise, INR, merchant/account and idempotency correlation. Customer receives only public checkout/session tokens, never secrets.
- Persist intent before invoking provider. Use provider sandbox keys in secrets manager; keep test/live accounts separate. Use their hosted checkout and official SDK as applicable to native clients.
- Verified callback/webhook intake records provider event ID under a UNIQUE(provider,event_id), retains raw body safely, verifies signature on EXACT raw bytes and then fetches/reconciles provider payment details. Process transactionally; duplicate delivery returns success without double capture/credit/refund. Failed/pending events cannot overwrite a verified successful payment; refund state is a separate ledger.
- Razorpay HMAC-SHA256 uses webhook secret + raw body; Cashfree uses Base64(HMAC-SHA256(timestamp+raw_body, merchant_secret)). Follow current official retry/rotation guidance; do not reject legitimate delayed retries using an invented freshness rule. Persist IDs to prevent replay.
- Captured/verified amount, currency, order and merchant must match server intent before paid status. Refund only approved reconciled amounts, never trust Customer's claim of a captured payment. Original-source refund IDs, pending/failure states and ARN/RRN/UTR must be stored as provided.
- Use a refund idempotency key, reconciliation scheduler and a trusted company maker-checker interface. A bank payout is a separate product/beneficiary flow. Credits need explicit consent, unique source IDs and atomic redemption; they cannot be reported as bank refunds.
- No production webhook endpoint is exposed here. Enable live routes only after provider onboarding, external HTTPS endpoint, credentials, integration tests, monitoring and verified rollback/finance controls exist.
