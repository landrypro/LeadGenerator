"""Validation statique des artefacts S4-0.

Ce script ne démarre aucun service et ne touche à aucune donnée CRM.
Il vérifie uniquement le manifeste synthétique et les garde-fous de conception.
"""

from __future__ import annotations

import json
from pathlib import Path


MANIFEST = Path(__file__).with_name("manifest.json")


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["source"] == "synthetic"
    assert data["contains_pii"] is False
    assert data["contains_provider_secrets"] is False

    tenants = data["tenants"]
    assert len(tenants) >= 2
    tenant_ids = {tenant["id"] for tenant in tenants}
    assert len(tenant_ids) == len(tenants)

    prospect_ids: set[str] = set()
    for tenant in tenants:
        flags = tenant["flags"]
        assert all(value is False for value in flags.values())
        for member in tenant["members"]:
            assert member["id"] not in tenant_ids
        for prospect in tenant["prospects"]:
            assert prospect["id"] not in prospect_ids
            prospect_ids.add(prospect["id"])
            if prospect["assigned_member_id"] is not None:
                member_ids = {member["id"] for member in tenant["members"]}
                assert prospect["assigned_member_id"] in member_ids

    principal = data["system_principal"]
    assert principal["enabled"] is False
    assert principal["max_scope"] == "single_organization"
    assert principal["ttl_seconds"] <= 900
    assert principal["requires_human_actor"] is True
    assert principal["external_send"] is False

    migration = data["migration_plan"]
    assert migration["rls_required"] is True
    assert migration["crm_tables_mutated"] is False
    assert migration["rollback"]

    required_capabilities = {"automation.prepare", "automation.approve_internal"}
    assert required_capabilities <= set(data["capabilities"]["commercial"])
    assert data["capabilities"]["revoked"] == []

    for metric in data["metrics"]:
        assert "organization_id" in metric["labels"]
        assert all("phrase" not in label and "email" not in label for label in metric["labels"])

    print("S4-0 D2 artifact validation: PASS")
    print(f"tenants={len(tenants)} prospects={len(prospect_ids)} metrics={len(data['metrics'])}")
    print("crm_tables_mutated=false flags_default=false system_principal_enabled=false")


if __name__ == "__main__":
    main()
