"""Protect customer-facing notification records (Workstream 9 continuation).

Revision ID: 20260721_0050
Revises: 20260721_0049

notifications_notifications has a real customer-facing read route
(app.api.routes.pet_life's "my notifications" listing) and carries
recipient_identity_id directly -- the same identity_id-scoped shape as
catalog_availability_subscriptions (already protected in 20260720_0041).
notifications_attempts (per-channel delivery attempts) has no
customer-facing read path of its own, but reaches the same identity via
notification_id -> notifications_notifications.recipient_identity_id
(two hops); protected as defense in depth for consistency, not because
a route currently exposes it.

notifications_preferences/notifications_templates remain out of scope
for this pass: preferences is keyed by identity_id but has no
confirmed customer-facing read route in this audit, and templates is
operator-authored reference content, not a per-customer row -- both
recorded as explicit follow-up rather than assumed safe.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_0050"
down_revision: str | None = "20260721_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE notifications_notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications_notifications FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY notifications_notifications_isolation ON notifications_notifications "
        "USING (app_is_operator() OR recipient_identity_id = app_identity_id()) "
        "WITH CHECK (app_is_operator() OR recipient_identity_id = app_identity_id())"
    )

    op.execute("ALTER TABLE notifications_attempts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications_attempts FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY notifications_attempts_isolation ON notifications_attempts "
        "USING (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM notifications_notifications n"
        "  WHERE n.id = notifications_attempts.notification_id"
        "   AND n.recipient_identity_id = app_identity_id()"
        ")) "
        "WITH CHECK (app_is_operator() OR EXISTS ("
        "  SELECT 1 FROM notifications_notifications n"
        "  WHERE n.id = notifications_attempts.notification_id"
        "   AND n.recipient_identity_id = app_identity_id()"
        "))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notifications_attempts_isolation ON notifications_attempts")
    op.execute("ALTER TABLE notifications_attempts DISABLE ROW LEVEL SECURITY")

    op.execute(
        "DROP POLICY IF EXISTS notifications_notifications_isolation ON notifications_notifications"
    )
    op.execute("ALTER TABLE notifications_notifications DISABLE ROW LEVEL SECURITY")
