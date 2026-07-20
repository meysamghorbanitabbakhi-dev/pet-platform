# Load testing

## Running it

`scripts/load_test.py` issues real, concurrent HTTP requests against a live `uvicorn app.main:app`
instance -- not an in-process test client -- and reports throughput, error rate, and p50/p95/p99
latency from what actually came back.

```
python -m scripts.load_test --base-url http://<host>:<port> --concurrency 20 --duration 30
```

Point it at a disposable environment with a realistic (not empty, not artificially huge) amount of
seeded data. An empty catalog under-represents real query cost; a dev database that has accumulated
years of unrelated test fixtures over-represents it just as dishonestly in the other direction --
see the first rehearsal below, which hit exactly that problem.

## Scope

`GET /api/v1/catalog/offers` (public, unauthenticated, read-only) only, for this first pass -- the
one endpoint every anonymous visitor's browsing traffic exercises regardless of login state, and
the only high-volume path that needs no seeded per-user state (households, sessions, carts) to
exercise meaningfully. **Not covered**: authenticated read paths (`/me/context`, `/orders`,
`/today`), the write/checkout path, and payment initiation. Each needs seeded households, addresses,
and real bearer tokens per virtual user, which is a materially larger harness than this pass
attempted -- open follow-on work, not silently assumed equivalent to what was actually run.

## Rehearsal evidence (2026-07-20, gap-closure program Workstream 12)

**First attempt, discarded as unrepresentative**: run against the shared, long-lived development
database this whole gap-closure session had been using. `catalog_offers` had accumulated 18,745
rows (15,292 `status='active'`) from hundreds of unrelated test-fixture inserts across the session's
own work, none of it cleaned up between workstreams. Even 5 concurrent requests to the unpaginated
listing endpoint returned in ~4.8 seconds each, and 30 concurrent requests over 20 seconds produced
zero successful responses at all (every request hit the 10-second client timeout). This is a data-
volume artifact of one dev database's incidental history, not a finding about the application's real
behavior, and is recorded here specifically so it is not mistaken for one.

**Second attempt, the actual result**: a fresh, disposable Postgres (ephemeral container, `alembic
upgrade head` from empty) seeded with 150 realistic catalog offers -- representative of an
early-stage marketplace's actual scale, not an empty fixture and not an accumulated decade of test
noise.

| concurrency | duration | requests | throughput | p50 | p95 | p99 | errors |
|---|---|---|---|---|---|---|---|
| 20 | 20s | 1,808 | 90.4 req/s | 196 ms | 334 ms | 833 ms | 0 |
| 50 | 20s | 1,719 | 86.0 req/s | 429 ms | 1,415 ms | 2,040 ms | 0 |

Zero connection-level errors at either concurrency; every request completed with `200`. Throughput
plateaus (does not increase) from 20 to 50 concurrent requests while p95/p99 latency roughly
quadruples -- consistent with a single `uvicorn` process (this rehearsal used no `--workers` flag)
and SQLAlchemy's default connection pool (5 base + 10 overflow = 15 concurrent DB connections)
becoming the binding constraint before the application code itself does. This is the expected
single-instance ceiling for this configuration, not a defect; a production deployment intending to
sustain materially more than roughly this environment's ~90 req/s on this endpoint needs either
multiple `uvicorn`/`gunicorn` workers, a larger connection pool sized to match, or horizontal
scaling across instances -- a capacity-planning decision this rehearsal establishes the baseline
for, not one it makes.

## Not rehearsed

Authenticated and write-path load (see Scope above), sustained soak testing beyond 20-second
windows, and behavior under realistic production data volume (this rehearsal's 150 offers is
representative of an early-stage catalog, not a mature one) -- genuine confidence in production
capacity still requires each of these, ideally against a copy of real production-scale data.
