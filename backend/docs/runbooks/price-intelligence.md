# Price intelligence runbook

PI-R1 is an internal operator-only subsystem. Collection is disabled by default and customer
competitor-price presentation is not registered.

Activation requires all of the following:

- `PRICE_INTELLIGENCE_COLLECTION_ENABLED=true`;
- source `robots_status=allowed`;
- source `terms_status=accepted`;
- explicit operator reason and evidence URL for terms approval.

If robots or terms are unchecked, failed, rejected or disallowed, collection remains blocked.
Collectors must use deterministic fixtures in tests and must not make live Petmall requests.

Rollback: set `PRICE_INTELLIGENCE_COLLECTION_ENABLED=false` and set the source
`collection_enabled=false`. Historical observations are append-only; corrections are operator
match decisions/audit records, never deletes.

Monitoring: review collection-run status, error summaries, stale running jobs, pending matches and
latest observations from `/api/v1/operator/price-intelligence/*`.

Unresolved policy:

- FX freshness threshold for cross-currency comparison is not approved.
- Customer presentation of competitor pricing is deferred.
- Legal/terms approval must be recorded per source; it is never hard-coded.
