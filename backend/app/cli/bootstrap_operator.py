from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.common.phone import normalize_iranian_mobile
from app.db.session import SessionFactory, close_database
from app.modules.identity.models import AuthIdentity


async def bootstrap(mobile: str) -> AuthIdentity:
    normalized = normalize_iranian_mobile(mobile)
    async with SessionFactory() as session:
        existing_operator = await session.scalar(
            select(AuthIdentity).where(AuthIdentity.identity_type == "operator").limit(1)
        )
        if existing_operator is not None:
            if existing_operator.mobile_e164 != normalized:
                raise RuntimeError("operator_already_exists")
            return existing_operator
        identity = await session.scalar(
            select(AuthIdentity).where(AuthIdentity.mobile_e164 == normalized).with_for_update()
        )
        if identity is None:
            identity = AuthIdentity(
                identity_type="operator", mobile_e164=normalized, status="active"
            )
            session.add(identity)
        else:
            identity.identity_type = "operator"
            identity.status = "active"
        await session.commit()
        return identity


async def _run(mobile: str) -> None:
    try:
        identity = await bootstrap(mobile)
        print(f"operator_ready id={identity.id} mobile={identity.mobile_e164}")
    finally:
        await close_database()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the platform's single operator identity")
    parser.add_argument("--mobile", required=True, help="Iranian mobile number")
    args = parser.parse_args()
    asyncio.run(_run(args.mobile))


if __name__ == "__main__":
    main()
