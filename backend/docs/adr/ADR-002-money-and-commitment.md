# ADR-002 — Money and paid-order commitment

**Status:** Approved  
**Date:** 2026-07-16

- Store amounts as integer IRR.
- Convert to toman explicitly at the presentation boundary.
- Start the delivery clock at verified successful payment.
- Delivery is due exactly 366 hours later.
- Crossing the deadline without completed delivery issues 5% of merchandise value as wallet
  credit exactly once.
- Credit expires three months after issuance.
- Wallet usage consumes the earliest-expiring credit first.
