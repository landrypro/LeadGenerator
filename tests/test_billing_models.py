from backend.app.infrastructure.postgres.models import Base


def test_billing_schema_is_registered_in_alembic_target_metadata() -> None:
    """Prevent Alembic from proposing removal of the P53-02 persistence tables."""

    expected_tables = {
        "billing_commands",
        "billing_customers",
        "billing_event_inbox",
        "billing_events",
        "billing_reconciliation_differences",
        "billing_reconciliation_runs",
        "billing_refunds",
        "subscription_transitions",
        "subscriptions",
    }

    assert expected_tables <= set(Base.metadata.tables)

    assert {index.name for index in Base.metadata.tables["subscriptions"].indexes} == {
        "ix_subscriptions_org_state",
        "uq_subscriptions_current_org",
    }
    assert {index.name for index in Base.metadata.tables["billing_events"].indexes} == {
        "ix_billing_events_org_occurred",
    }
    assert {index.name for index in Base.metadata.tables["subscription_transitions"].indexes} == {
        "ix_subscription_transitions_org_subscription",
    }
    assert {index.name for index in Base.metadata.tables["billing_reconciliation_differences"].indexes} == {
        "ix_billing_reconciliation_differences_org_run",
    }
