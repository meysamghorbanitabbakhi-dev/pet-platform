# ADR-001 — Filesystem media storage

**Status:** Approved  
**Date:** 2026-07-16

Use normal filesystem directories mounted from a persistent Docker volume. Do not run S3 or
MinIO initially. Domain and application code depend on `ObjectStorage`, and only the adapter
knows filesystem paths.

Private trust evidence, pet media, and diary attachments must never be exposed as public
static paths. Production approval still requires backup, restore, capacity-alert, and host-loss
decisions.

