"""Deferred customer price-intelligence routes.

Customer-visible competitor pricing is intentionally unregistered for PI-R1.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/price-intelligence", tags=["customers", "price-intelligence"])
