from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import cast
from uuid import UUID


class InvalidAuditEvent(ValueError):
    pass


class InvalidAuditMetadata(InvalidAuditEvent):
    pass


class AuditScope(StrEnum):
    TENANT = "tenant"
    PLATFORM = "platform"


class AuditActorKind(StrEnum):
    USER = "user"
    SYSTEM = "system"


class AuditSource(StrEnum):
    API = "api"
    CLI = "cli"
    WORKER = "worker"


class AuditAction(StrEnum):
    ORGANIZATION_UPDATED = "organization.updated"
    ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED = "account.organization_preference_changed"
    MEMBERSHIP_ROLE_CHANGED = "membership.role_changed"
    MEMBERSHIP_STATUS_CHANGED = "membership.status_changed"
    INVITATION_CREATED = "invitation.created"
    INVITATION_RESEND_REQUESTED = "invitation.resend_requested"
    INVITATION_DELIVERY_COMPLETED = "invitation.delivery_completed"
    INVITATION_REVOKED = "invitation.revoked"
    INVITATION_ACCEPTED = "invitation.accepted"
    ORGANIZATION_ACTIVATED = "organization.activated"
    ORGANIZATION_PROVISIONED = "organization.provisioned"
    INITIAL_INVITATION_CREATED = "organization.initial_invitation.created"
    INITIAL_INVITATION_RESEND_REQUESTED = "organization.initial_invitation.resend_requested"
    INITIAL_INVITATION_DELIVERY_COMPLETED = "organization.initial_invitation.delivery_completed"
    INITIAL_INVITATION_REVOKED = "organization.initial_invitation.revoked"
    ORGANIZATION_SUSPENDED = "organization.suspended"
    ORGANIZATION_REACTIVATED = "organization.reactivated"
    PROSPECT_CREATED = "prospect.created"
    PROSPECT_UPDATED = "prospect.updated"
    PROSPECT_ARCHIVED = "prospect.archived"
    PROSPECT_STAGE_CHANGED = "prospect.stage_changed"
    PIPELINE_STAGE_SETTINGS_UPDATED = "pipeline.stage_settings_updated"
    CONTACT_CREATED = "contact.created"
    CHANNEL_CREATED = "channel.created"
    PROVENANCE_RECORDED = "provenance.recorded"
    SOURCE_PROVIDER_CREATED = "source_provider.created"
    SOURCE_PROVIDER_UPDATED = "source_provider.updated"
    SOURCE_PROVIDER_STATUS_CHANGED = "source_provider.status_changed"
    ACQUISITION_DECLARED = "acquisition.declared"
    ACQUISITION_QUARANTINED = "acquisition.quarantined"
    ACQUISITION_APPROVED = "acquisition.approved"
    ACQUISITION_REJECTED = "acquisition.rejected"
    CONTACT_PERMISSION_CHANGED = "contact_permission.changed"
    RETENTION_POLICY_CREATED = "retention_policy.created"
    RETENTION_POLICY_ACTIVATED = "retention_policy.activated"
    RETENTION_POLICY_SUPERSEDED = "retention_policy.superseded"
    RETENTION_HOLD_PLACED = "retention_hold.placed"
    RETENTION_HOLD_RELEASED = "retention_hold.released"
    IMPORT_DECLARATION_DECLARED = "import_declaration.declared"
    IMPORT_DECLARATION_QUARANTINED = "import_declaration.quarantined"
    IMPORT_DECLARATION_CANCELLED = "import_declaration.cancelled"
    IMPORT_DECLARATION_ARCHIVED = "import_declaration.archived"
    IMPORT_FILE_UPLOADED = "import.file_uploaded"
    IMPORT_MAPPING_SAVED = "import.mapping_saved"
    IMPORT_VALIDATED = "import.validated"
    IMPORT_CONFIRMED = "import.confirmed"
    IMPORT_RETRY_STARTED = "import.retry_started"
    IMPORT_REPORT_VIEWED = "import.report_viewed"
    EXPORT_REQUESTED = "export.requested"
    EXPORT_READY = "export.ready"
    EXPORT_FAILED = "export.failed"
    EXPORT_DOWNLOADED = "export.downloaded"
    EXPORT_EXPIRED = "export.expired"
    EXPORT_RULE_CHANGED = "export.rule_changed"
    CONTACT_ARCHIVED = "contact.archived"
    CONTACT_CHANNEL_ARCHIVED = "contact_channel.archived"
    PROSPECT_ACTIVITY_CREATED = "prospect.activity_created"
    PROSPECT_ACTIVITY_CORRECTED = "prospect.activity_corrected"
    PROSPECT_TASK_CREATED = "prospect.task_created"
    PROSPECT_TASK_UPDATED = "prospect.task_updated"
    PROSPECT_TASK_COMPLETED = "prospect.task_completed"
    PROSPECT_TASK_CANCELLED = "prospect.task_cancelled"
    PROSPECT_TASK_REOPENED = "prospect.task_reopened"
    PROSPECT_TASK_REMINDER_CHANGED = "prospect.task_reminder_changed"
    OPPORTUNITY_CREATED = "opportunity.created"
    OPPORTUNITY_UPDATED = "opportunity.updated"
    OPPORTUNITY_STAGE_CHANGED = "opportunity.stage_changed"
    OPPORTUNITY_REOPENED = "opportunity.reopened"


_ENTITY_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$", re.ASCII)
_EXTERNAL_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}$", re.ASCII)
_ORGANIZATION_FIELDS = frozenset({"locale", "name", "timezone"})
_MEMBERSHIP_ROLES = frozenset({"admin", "manager", "sales"})
_MEMBERSHIP_STATUSES = frozenset({"active", "disabled"})
_INVITATION_KINDS = frozenset({"initial_administrator", "member"})
_DELIVERY_STATUSES = frozenset({"pending", "sent", "failed"})
_DELIVERY_KINDS = frozenset({"initial", "resend"})
_STATUS_REASON_CODES = frozenset({"administrative", "billing", "compliance", "customer_request", "other", "security"})
_PROSPECT_ORIGINS = frozenset({"connector", "google_place", "import", "manual", "open_data"})
_CONTACT_CHANNEL_TYPES = frozenset({"email", "facebook", "linkedin", "other", "phone"})
_PROVENANCE_SOURCE_KINDS = frozenset(
    {"api", "csv", "facebook", "google_maps", "linkedin", "manual", "open_data", "other"}
)
_SOURCE_PROVIDER_STATUSES = frozenset({"active", "draft", "retired", "suspended"})
_ACQUISITION_STATUSES = frozenset({"approved", "pending_review", "quarantined", "rejected"})
_PERMISSION_STATUSES = frozenset({"allowed", "do_not_contact", "opted_out", "unknown"})
_RETENTION_RESOURCE_TYPES = frozenset(
    {"acquisition_record", "contact", "contact_channel", "import_declaration", "prospect", "provenance_record"}
)
_RETENTION_POLICY_STATUSES = frozenset({"active", "draft", "superseded"})
_RETENTION_HOLD_REASONS = frozenset(
    {"contractual_obligation", "data_subject_request", "investigation", "legal_request", "other", "quality_review"}
)
_RETENTION_RELEASE_REASONS = frozenset({"entered_in_error", "expired", "other", "resolved"})
_IMPORT_DECLARATION_STATUSES = frozenset({"archived", "cancelled", "declared", "quarantined"})
_IMPORT_DECLARATION_REASON_CODES = frozenset(
    {"category_not_acquired", "field_not_allowed", "high_risk_free_text", "provider_history_incomplete"}
)
_EXPORT_DATASETS = frozenset({"prospects", "contacts", "contact_channels", "activities", "tasks", "opportunities"})
_EXPORT_SCOPES = frozenset({"self", "organization"})
_EXPORT_ERRORS = frozenset(
    {
        "authorization_revoked",
        "subject_missing",
        "invalid_contract",
        "limit_exceeded",
        "dependency_unavailable",
        "timeout",
    }
)
_EXPORT_FILTERS = frozenset(
    {
        "created_from",
        "created_to",
        "obtained_from",
        "obtained_to",
        "occurred_from",
        "occurred_to",
        "due_from",
        "due_to",
        "expected_close_from",
        "expected_close_to",
        "stage_code",
        "status",
        "priority",
        "owner_membership_id",
    }
)
_ARCHIVE_REASON_CODES = frozenset(
    {"duplicate", "import_cancelled", "invalid_data", "no_longer_relevant", "other", "relationship_ended"}
)
_QUARANTINE_REASON_CODES = frozenset(
    {
        "contract_expired",
        "contract_not_started",
        "data_category_not_allowed",
        "provider_not_active",
        "purpose_not_allowed",
        "rights_attestation_missing",
        "source_kind_mismatch",
        "territory_not_allowed",
    }
)
_TENANT_ACTIONS = frozenset(
    {
        AuditAction.ORGANIZATION_UPDATED,
        AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED,
        AuditAction.MEMBERSHIP_ROLE_CHANGED,
        AuditAction.MEMBERSHIP_STATUS_CHANGED,
        AuditAction.INVITATION_CREATED,
        AuditAction.INVITATION_RESEND_REQUESTED,
        AuditAction.INVITATION_DELIVERY_COMPLETED,
        AuditAction.INVITATION_REVOKED,
        AuditAction.INVITATION_ACCEPTED,
        AuditAction.ORGANIZATION_ACTIVATED,
        AuditAction.PROSPECT_CREATED,
        AuditAction.PROSPECT_UPDATED,
        AuditAction.PROSPECT_ARCHIVED,
        AuditAction.PROSPECT_STAGE_CHANGED,
        AuditAction.PIPELINE_STAGE_SETTINGS_UPDATED,
        AuditAction.CONTACT_CREATED,
        AuditAction.CHANNEL_CREATED,
        AuditAction.PROVENANCE_RECORDED,
        AuditAction.SOURCE_PROVIDER_CREATED,
        AuditAction.SOURCE_PROVIDER_UPDATED,
        AuditAction.SOURCE_PROVIDER_STATUS_CHANGED,
        AuditAction.ACQUISITION_DECLARED,
        AuditAction.ACQUISITION_QUARANTINED,
        AuditAction.ACQUISITION_APPROVED,
        AuditAction.ACQUISITION_REJECTED,
        AuditAction.CONTACT_PERMISSION_CHANGED,
        AuditAction.RETENTION_POLICY_CREATED,
        AuditAction.RETENTION_POLICY_ACTIVATED,
        AuditAction.RETENTION_POLICY_SUPERSEDED,
        AuditAction.RETENTION_HOLD_PLACED,
        AuditAction.RETENTION_HOLD_RELEASED,
        AuditAction.IMPORT_DECLARATION_DECLARED,
        AuditAction.IMPORT_DECLARATION_QUARANTINED,
        AuditAction.IMPORT_DECLARATION_CANCELLED,
        AuditAction.IMPORT_DECLARATION_ARCHIVED,
        AuditAction.IMPORT_FILE_UPLOADED,
        AuditAction.IMPORT_MAPPING_SAVED,
        AuditAction.IMPORT_VALIDATED,
        AuditAction.IMPORT_CONFIRMED,
        AuditAction.IMPORT_RETRY_STARTED,
        AuditAction.IMPORT_REPORT_VIEWED,
        AuditAction.EXPORT_REQUESTED,
        AuditAction.EXPORT_READY,
        AuditAction.EXPORT_FAILED,
        AuditAction.EXPORT_DOWNLOADED,
        AuditAction.EXPORT_EXPIRED,
        AuditAction.EXPORT_RULE_CHANGED,
        AuditAction.CONTACT_ARCHIVED,
        AuditAction.CONTACT_CHANNEL_ARCHIVED,
        AuditAction.PROSPECT_ACTIVITY_CREATED,
        AuditAction.PROSPECT_ACTIVITY_CORRECTED,
        AuditAction.PROSPECT_TASK_CREATED,
        AuditAction.PROSPECT_TASK_UPDATED,
        AuditAction.PROSPECT_TASK_COMPLETED,
        AuditAction.PROSPECT_TASK_CANCELLED,
        AuditAction.PROSPECT_TASK_REOPENED,
        AuditAction.PROSPECT_TASK_REMINDER_CHANGED,
        AuditAction.OPPORTUNITY_CREATED,
        AuditAction.OPPORTUNITY_UPDATED,
        AuditAction.OPPORTUNITY_STAGE_CHANGED,
        AuditAction.OPPORTUNITY_REOPENED,
    }
)
_PLATFORM_ACTIONS = frozenset(set(AuditAction) - _TENANT_ACTIONS)
_ACTION_ENTITY_TYPES = {
    AuditAction.ORGANIZATION_UPDATED: "organization",
    AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED: "user",
    AuditAction.MEMBERSHIP_ROLE_CHANGED: "membership",
    AuditAction.MEMBERSHIP_STATUS_CHANGED: "membership",
    AuditAction.INVITATION_CREATED: "invitation",
    AuditAction.INVITATION_RESEND_REQUESTED: "invitation",
    AuditAction.INVITATION_DELIVERY_COMPLETED: "invitation",
    AuditAction.INVITATION_REVOKED: "invitation",
    AuditAction.INVITATION_ACCEPTED: "invitation",
    AuditAction.ORGANIZATION_ACTIVATED: "organization",
    AuditAction.ORGANIZATION_PROVISIONED: "organization",
    AuditAction.INITIAL_INVITATION_CREATED: "invitation",
    AuditAction.INITIAL_INVITATION_RESEND_REQUESTED: "invitation",
    AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED: "invitation",
    AuditAction.INITIAL_INVITATION_REVOKED: "invitation",
    AuditAction.ORGANIZATION_SUSPENDED: "organization",
    AuditAction.ORGANIZATION_REACTIVATED: "organization",
    AuditAction.PROSPECT_CREATED: "prospect",
    AuditAction.PROSPECT_UPDATED: "prospect",
    AuditAction.PROSPECT_ARCHIVED: "prospect",
    AuditAction.PROSPECT_STAGE_CHANGED: "prospect",
    AuditAction.PIPELINE_STAGE_SETTINGS_UPDATED: "pipeline_stage_setting",
    AuditAction.CONTACT_CREATED: "contact",
    AuditAction.CHANNEL_CREATED: "contact_channel",
    AuditAction.PROVENANCE_RECORDED: "provenance",
    AuditAction.SOURCE_PROVIDER_CREATED: "source_provider",
    AuditAction.SOURCE_PROVIDER_UPDATED: "source_provider",
    AuditAction.SOURCE_PROVIDER_STATUS_CHANGED: "source_provider",
    AuditAction.ACQUISITION_DECLARED: "acquisition",
    AuditAction.ACQUISITION_QUARANTINED: "acquisition",
    AuditAction.ACQUISITION_APPROVED: "acquisition",
    AuditAction.ACQUISITION_REJECTED: "acquisition",
    AuditAction.CONTACT_PERMISSION_CHANGED: "contact_permission",
    AuditAction.RETENTION_POLICY_CREATED: "retention_policy",
    AuditAction.RETENTION_POLICY_ACTIVATED: "retention_policy",
    AuditAction.RETENTION_POLICY_SUPERSEDED: "retention_policy",
    AuditAction.RETENTION_HOLD_PLACED: "retention_hold",
    AuditAction.RETENTION_HOLD_RELEASED: "retention_hold",
    AuditAction.IMPORT_DECLARATION_DECLARED: "import_declaration",
    AuditAction.IMPORT_DECLARATION_QUARANTINED: "import_declaration",
    AuditAction.IMPORT_DECLARATION_CANCELLED: "import_declaration",
    AuditAction.IMPORT_DECLARATION_ARCHIVED: "import_declaration",
    AuditAction.IMPORT_FILE_UPLOADED: "csv_import_session",
    AuditAction.IMPORT_MAPPING_SAVED: "csv_import_session",
    AuditAction.IMPORT_VALIDATED: "csv_import_session",
    AuditAction.IMPORT_CONFIRMED: "csv_import_session",
    AuditAction.IMPORT_RETRY_STARTED: "csv_import_session",
    AuditAction.IMPORT_REPORT_VIEWED: "csv_import_run",
    AuditAction.EXPORT_REQUESTED: "export_request",
    AuditAction.EXPORT_READY: "export_request",
    AuditAction.EXPORT_FAILED: "export_request",
    AuditAction.EXPORT_DOWNLOADED: "export_request",
    AuditAction.EXPORT_EXPIRED: "export_request",
    AuditAction.EXPORT_RULE_CHANGED: "source_export_rule",
    AuditAction.CONTACT_ARCHIVED: "contact",
    AuditAction.CONTACT_CHANNEL_ARCHIVED: "contact_channel",
    AuditAction.PROSPECT_ACTIVITY_CREATED: "prospect_activity",
    AuditAction.PROSPECT_ACTIVITY_CORRECTED: "prospect_activity",
    AuditAction.PROSPECT_TASK_CREATED: "prospect_task",
    AuditAction.PROSPECT_TASK_UPDATED: "prospect_task",
    AuditAction.PROSPECT_TASK_COMPLETED: "prospect_task",
    AuditAction.PROSPECT_TASK_CANCELLED: "prospect_task",
    AuditAction.PROSPECT_TASK_REOPENED: "prospect_task",
    AuditAction.PROSPECT_TASK_REMINDER_CHANGED: "prospect_task",
    AuditAction.OPPORTUNITY_CREATED: "opportunity",
    AuditAction.OPPORTUNITY_UPDATED: "opportunity",
    AuditAction.OPPORTUNITY_STAGE_CHANGED: "opportunity",
    AuditAction.OPPORTUNITY_REOPENED: "opportunity",
}


def audit_actions_for_scope(scope: AuditScope) -> tuple[AuditAction, ...]:
    actions = _TENANT_ACTIONS if scope is AuditScope.TENANT else _PLATFORM_ACTIONS
    return tuple(sorted(actions, key=lambda action: action.value))


def audit_entity_types_for_scope(scope: AuditScope) -> tuple[str, ...]:
    return tuple(sorted({_ACTION_ENTITY_TYPES[action] for action in audit_actions_for_scope(scope)}))


def audit_entity_type_for_action(action: AuditAction) -> str:
    return _ACTION_ENTITY_TYPES[action]


def audit_action_matches_scope(action: AuditAction, scope: AuditScope) -> bool:
    return action in (_TENANT_ACTIONS if scope is AuditScope.TENANT else _PLATFORM_ACTIONS)


class AuditMetadataPolicy:
    """Valide et normalise les seules métadonnées permises pour une action stable."""

    @classmethod
    def validate(cls, action: AuditAction, metadata: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(metadata, Mapping):
            raise InvalidAuditMetadata("Les métadonnées d’audit doivent être un objet.")

        values = dict(metadata)
        if action is AuditAction.ORGANIZATION_UPDATED:
            cls._require_keys(values, {"changed_fields"})
            changed_fields = values["changed_fields"]
            if (
                isinstance(changed_fields, (str, bytes))
                or not isinstance(changed_fields, Sequence)
                or not changed_fields
                or any(
                    not isinstance(field_name, str) or field_name not in _ORGANIZATION_FIELDS
                    for field_name in changed_fields
                )
                or len(set(changed_fields)) != len(changed_fields)
            ):
                raise InvalidAuditMetadata("changed_fields contient une valeur interdite ou dupliquée.")
            return {"changed_fields": tuple(sorted(changed_fields))}

        if action is AuditAction.ACCOUNT_ORGANIZATION_PREFERENCE_CHANGED:
            cls._require_keys(values, {"previous_membership_id", "new_membership_id"})
            return {
                "previous_membership_id": cls._uuid(values["previous_membership_id"], "previous_membership_id"),
                "new_membership_id": cls._uuid(values["new_membership_id"], "new_membership_id"),
            }

        if action is AuditAction.MEMBERSHIP_ROLE_CHANGED:
            cls._require_keys(values, {"previous_role", "new_role"})
            return {
                "previous_role": cls._choice(values["previous_role"], _MEMBERSHIP_ROLES, "previous_role"),
                "new_role": cls._choice(values["new_role"], _MEMBERSHIP_ROLES, "new_role"),
            }

        if action is AuditAction.MEMBERSHIP_STATUS_CHANGED:
            cls._require_keys(values, {"previous_status", "new_status"})
            return {
                "previous_status": cls._choice(values["previous_status"], _MEMBERSHIP_STATUSES, "previous_status"),
                "new_status": cls._choice(values["new_status"], _MEMBERSHIP_STATUSES, "new_status"),
            }

        if action in {AuditAction.INVITATION_CREATED, AuditAction.INITIAL_INVITATION_CREATED}:
            cls._require_keys(values, {"role", "invitation_kind", "delivery_status"})
            return {
                "role": cls._choice(values["role"], _MEMBERSHIP_ROLES, "role"),
                "invitation_kind": cls._choice(values["invitation_kind"], _INVITATION_KINDS, "invitation_kind"),
                "delivery_status": cls._choice(values["delivery_status"], _DELIVERY_STATUSES, "delivery_status"),
            }

        if action in {
            AuditAction.INVITATION_RESEND_REQUESTED,
            AuditAction.INITIAL_INVITATION_RESEND_REQUESTED,
        }:
            cls._require_keys(values, {"delivery_attempt_id"})
            return {"delivery_attempt_id": cls._uuid(values["delivery_attempt_id"], "delivery_attempt_id")}

        if action in {
            AuditAction.INVITATION_DELIVERY_COMPLETED,
            AuditAction.INITIAL_INVITATION_DELIVERY_COMPLETED,
        }:
            cls._require_keys(values, {"delivery_status", "delivery_kind", "delivery_attempt_id"})
            return {
                "delivery_status": cls._choice(values["delivery_status"], _DELIVERY_STATUSES, "delivery_status"),
                "delivery_kind": cls._choice(values["delivery_kind"], _DELIVERY_KINDS, "delivery_kind"),
                "delivery_attempt_id": cls._uuid(values["delivery_attempt_id"], "delivery_attempt_id"),
            }

        if action is AuditAction.ORGANIZATION_SUSPENDED:
            cls._require_keys(values, {"reason_code", "operation_id"}, {"external_reference"})
            result = cls._status_operation(values)
            external_reference = values.get("external_reference")
            if external_reference is not None:
                if not isinstance(external_reference, str) or not _EXTERNAL_REFERENCE_PATTERN.fullmatch(
                    external_reference
                ):
                    raise InvalidAuditMetadata("external_reference ne respecte pas le format autorisé.")
                result["external_reference"] = external_reference
            return result

        if action is AuditAction.ORGANIZATION_REACTIVATED:
            cls._require_keys(values, {"reason_code", "operation_id"})
            return cls._status_operation(values)

        if action is AuditAction.PROSPECT_CREATED:
            cls._require_keys(values, {"origin"})
            return {"origin": cls._choice(values["origin"], _PROSPECT_ORIGINS, "origin")}

        if action is AuditAction.PROSPECT_UPDATED:
            cls._require_keys(values, {"changed_fields"})
            changed_fields = values["changed_fields"]
            allowed_fields = frozenset(
                {
                    "internal_alias",
                    "owner_id",
                    "priority",
                    "retention_review_at",
                    "stage_code",
                    "industry_label",
                    "segment_code",
                    "size_band",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "region",
                    "postal_code",
                    "country_code",
                    "tags",
                }
            )
            if (
                isinstance(changed_fields, (str, bytes))
                or not isinstance(changed_fields, Sequence)
                or not changed_fields
                or any(
                    not isinstance(field_name, str) or field_name not in allowed_fields for field_name in changed_fields
                )
                or len(set(changed_fields)) != len(changed_fields)
            ):
                raise InvalidAuditMetadata("changed_fields contient une valeur prospect interdite ou dupliquee.")
            return {"changed_fields": tuple(sorted(changed_fields))}

        if action is AuditAction.PROSPECT_STAGE_CHANGED:
            cls._require_keys(values, {"from_stage", "to_stage", "from_version", "resulting_version"}, {"reason_code"})
            allowed_stages = frozenset(
                {
                    "new",
                    "qualifying",
                    "qualified",
                    "contacted",
                    "opportunity",
                    "proposal_sent",
                    "negotiation",
                    "won",
                    "lost",
                }
            )
            from_version, resulting_version = values["from_version"], values["resulting_version"]
            if (
                not isinstance(from_version, int)
                or not isinstance(resulting_version, int)
                or from_version <= 0
                or resulting_version <= from_version
            ):
                raise InvalidAuditMetadata("Les versions de transition sont invalides.")
            result = {
                "from_stage": cls._choice(values["from_stage"], allowed_stages, "from_stage"),
                "to_stage": cls._choice(values["to_stage"], allowed_stages, "to_stage"),
                "from_version": from_version,
                "resulting_version": resulting_version,
            }
            if "reason_code" in values:
                reason_code = values["reason_code"]
                if not isinstance(reason_code, str) or not 1 <= len(reason_code) <= 64:
                    raise InvalidAuditMetadata("reason_code est invalide.")
                result["reason_code"] = reason_code
            return result

        if action in {AuditAction.PROSPECT_ACTIVITY_CREATED, AuditAction.PROSPECT_ACTIVITY_CORRECTED}:
            cls._require_keys(values, {"activity_type"}, {"direction", "correction"})
            result = {
                "activity_type": cls._choice(
                    values["activity_type"], frozenset({"note", "call", "email", "meeting"}), "activity_type"
                )
            }
            if "direction" in values:
                result["direction"] = cls._choice(
                    values["direction"], frozenset({"internal", "inbound", "outbound"}), "direction"
                )
            if "correction" in values:
                if not isinstance(values["correction"], bool):
                    raise InvalidAuditMetadata("correction doit être booléen.")
                result["correction"] = values["correction"]
            return result

        if action in {
            AuditAction.PROSPECT_TASK_CREATED,
            AuditAction.PROSPECT_TASK_UPDATED,
            AuditAction.PROSPECT_TASK_COMPLETED,
            AuditAction.PROSPECT_TASK_CANCELLED,
            AuditAction.PROSPECT_TASK_REOPENED,
            AuditAction.PROSPECT_TASK_REMINDER_CHANGED,
        }:
            cls._require_keys(values, {"resulting_status", "resulting_version"}, {"changed_fields"})
            version = values["resulting_version"]
            if not isinstance(version, int) or version <= 0:
                raise InvalidAuditMetadata("resulting_version est invalide.")
            result = {
                "resulting_status": cls._choice(
                    values["resulting_status"], frozenset({"open", "completed", "cancelled"}), "resulting_status"
                ),
                "resulting_version": version,
            }
            if "changed_fields" in values:
                result["changed_fields"] = cls._field_names(
                    values["changed_fields"],
                    frozenset(
                        {
                            "assigned_membership_id",
                            "cancelled_at",
                            "cancelled_reason",
                            "completed_at",
                            "description",
                            "due_at",
                            "priority",
                            "reminder_acknowledged_at",
                            "reminder_at",
                            "reminder_snoozed_until",
                            "status",
                            "title",
                        }
                    ),
                )
            return result

        if action in {
            AuditAction.OPPORTUNITY_CREATED,
            AuditAction.OPPORTUNITY_UPDATED,
            AuditAction.OPPORTUNITY_STAGE_CHANGED,
            AuditAction.OPPORTUNITY_REOPENED,
        }:
            cls._require_keys(
                values,
                {"resulting_version", "stage_code"},
                {"changed_fields", "from_stage", "reason_code", "currency_code"},
            )
            version = values["resulting_version"]
            if not isinstance(version, int) or version <= 0:
                raise InvalidAuditMetadata("resulting_version est invalide.")
            stages = frozenset({"discovery", "qualification", "proposal", "negotiation", "won", "lost"})
            result = {
                "resulting_version": version,
                "stage_code": cls._choice(values["stage_code"], stages, "stage_code"),
            }
            if "from_stage" in values:
                result["from_stage"] = cls._choice(values["from_stage"], stages, "from_stage")
            if "reason_code" in values:
                result["reason_code"] = cls._short_text(values["reason_code"], "reason_code", 64)
            if "currency_code" in values:
                result["currency_code"] = cls._short_text(values["currency_code"], "currency_code", 3)
            if "changed_fields" in values:
                result["changed_fields"] = cls._field_names(
                    values["changed_fields"],
                    frozenset(
                        {
                            "amount",
                            "closed_at",
                            "currency_code",
                            "expected_close_on",
                            "loss_reason_code",
                            "loss_reason_note",
                            "name",
                            "owner_membership_id",
                            "probability",
                            "stage_code",
                        }
                    ),
                )
            return result

        if action is AuditAction.PIPELINE_STAGE_SETTINGS_UPDATED:
            cls._require_keys(values, {"stage_code", "changed_fields"})
            allowed_stages = frozenset(
                {
                    "new",
                    "qualifying",
                    "qualified",
                    "contacted",
                    "opportunity",
                    "proposal_sent",
                    "negotiation",
                    "won",
                    "lost",
                }
            )
            changed_fields = values["changed_fields"]
            if (
                isinstance(changed_fields, (str, bytes))
                or not isinstance(changed_fields, Sequence)
                or set(changed_fields) - {"color_token", "labels"}
            ):
                raise InvalidAuditMetadata("changed_fields de pipeline est invalide.")
            return {
                "stage_code": cls._choice(values["stage_code"], allowed_stages, "stage_code"),
                "changed_fields": tuple(sorted(changed_fields)),
            }

        if action is AuditAction.PROSPECT_ARCHIVED:
            cls._require_keys(
                values, {"previous_version"}, {"archive_reason_code", "contacts_archived", "channels_archived"}
            )
            previous_version = values["previous_version"]
            if not isinstance(previous_version, int) or previous_version <= 0:
                raise InvalidAuditMetadata("previous_version doit etre strictement positif.")
            prospect_archive_result: dict[str, object] = {"previous_version": previous_version}
            if "archive_reason_code" in values:
                prospect_archive_result["archive_reason_code"] = cls._choice(
                    values["archive_reason_code"], _ARCHIVE_REASON_CODES, "archive_reason_code"
                )
            for count_field in ("contacts_archived", "channels_archived"):
                if count_field in values:
                    count = values[count_field]
                    if not isinstance(count, int) or count < 0:
                        raise InvalidAuditMetadata(f"{count_field} doit etre un entier positif.")
                    prospect_archive_result[count_field] = count
            return prospect_archive_result

        if action is AuditAction.CONTACT_CREATED:
            cls._require_keys(values, {"prospect_id"})
            return {"prospect_id": cls._uuid(values["prospect_id"], "prospect_id")}

        if action is AuditAction.CHANNEL_CREATED:
            cls._require_keys(values, {"channel_type", "target_type"})
            target_type = cls._choice(values["target_type"], frozenset({"contact", "prospect"}), "target_type")
            return {
                "channel_type": cls._choice(values["channel_type"], _CONTACT_CHANNEL_TYPES, "channel_type"),
                "target_type": target_type,
            }

        if action is AuditAction.PROVENANCE_RECORDED:
            cls._require_keys(values, {"source_kind"})
            return {
                "source_kind": cls._choice(values["source_kind"], _PROVENANCE_SOURCE_KINDS, "source_kind"),
            }

        if action is AuditAction.SOURCE_PROVIDER_CREATED:
            cls._require_keys(values, {"source_kind", "status"})
            return {
                "source_kind": cls._choice(values["source_kind"], _PROVENANCE_SOURCE_KINDS, "source_kind"),
                "status": cls._choice(values["status"], _SOURCE_PROVIDER_STATUSES, "status"),
            }

        if action is AuditAction.SOURCE_PROVIDER_UPDATED:
            cls._require_keys(values, {"changed_fields"})
            allowed_fields = frozenset(
                {
                    "allowed_data_categories",
                    "allowed_purposes",
                    "allowed_territories",
                    "label",
                    "terms_reference",
                    "terms_url",
                    "valid_from",
                    "valid_until",
                }
            )
            return {"changed_fields": cls._field_names(values["changed_fields"], allowed_fields)}

        if action is AuditAction.SOURCE_PROVIDER_STATUS_CHANGED:
            cls._require_keys(values, {"previous_status", "new_status"})
            return {
                "previous_status": cls._choice(values["previous_status"], _SOURCE_PROVIDER_STATUSES, "previous_status"),
                "new_status": cls._choice(values["new_status"], _SOURCE_PROVIDER_STATUSES, "new_status"),
            }

        if action is AuditAction.ACQUISITION_DECLARED:
            cls._require_keys(values, {"source_kind", "status"})
            return {
                "source_kind": cls._choice(values["source_kind"], _PROVENANCE_SOURCE_KINDS, "source_kind"),
                "status": cls._choice(values["status"], _ACQUISITION_STATUSES, "status"),
            }

        if action is AuditAction.ACQUISITION_QUARANTINED:
            cls._require_keys(values, {"source_kind", "reason_code"})
            return {
                "source_kind": cls._choice(values["source_kind"], _PROVENANCE_SOURCE_KINDS, "source_kind"),
                "reason_code": cls._choice(values["reason_code"], _QUARANTINE_REASON_CODES, "reason_code"),
            }

        if action in {AuditAction.ACQUISITION_APPROVED, AuditAction.ACQUISITION_REJECTED}:
            cls._require_keys(values, {"previous_status", "new_status"})
            return {
                "previous_status": cls._choice(values["previous_status"], _ACQUISITION_STATUSES, "previous_status"),
                "new_status": cls._choice(values["new_status"], _ACQUISITION_STATUSES, "new_status"),
            }

        if action is AuditAction.CONTACT_PERMISSION_CHANGED:
            cls._require_keys(values, {"previous_status", "new_status", "propagated_count"})
            propagated_count = values["propagated_count"]
            if not isinstance(propagated_count, int) or propagated_count < 0:
                raise InvalidAuditMetadata("propagated_count doit etre un entier positif.")
            return {
                "previous_status": cls._choice(values["previous_status"], _PERMISSION_STATUSES, "previous_status"),
                "new_status": cls._choice(values["new_status"], _PERMISSION_STATUSES, "new_status"),
                "propagated_count": propagated_count,
            }

        if action is AuditAction.RETENTION_POLICY_CREATED:
            cls._require_keys(values, {"resource_type", "status"})
            return {
                "resource_type": cls._choice(values["resource_type"], _RETENTION_RESOURCE_TYPES, "resource_type"),
                "status": cls._choice(values["status"], _RETENTION_POLICY_STATUSES, "status"),
            }

        if action in {AuditAction.RETENTION_POLICY_ACTIVATED, AuditAction.RETENTION_POLICY_SUPERSEDED}:
            cls._require_keys(values, {"resource_type", "previous_status", "new_status"})
            return {
                "resource_type": cls._choice(values["resource_type"], _RETENTION_RESOURCE_TYPES, "resource_type"),
                "previous_status": cls._choice(
                    values["previous_status"], _RETENTION_POLICY_STATUSES, "previous_status"
                ),
                "new_status": cls._choice(values["new_status"], _RETENTION_POLICY_STATUSES, "new_status"),
            }

        if action is AuditAction.RETENTION_HOLD_PLACED:
            cls._require_keys(values, {"resource_type", "reason_code"})
            return {
                "resource_type": cls._choice(values["resource_type"], _RETENTION_RESOURCE_TYPES, "resource_type"),
                "reason_code": cls._choice(values["reason_code"], _RETENTION_HOLD_REASONS, "reason_code"),
            }

        if action is AuditAction.RETENTION_HOLD_RELEASED:
            cls._require_keys(values, {"resource_type", "release_reason_code"})
            return {
                "resource_type": cls._choice(values["resource_type"], _RETENTION_RESOURCE_TYPES, "resource_type"),
                "release_reason_code": cls._choice(
                    values["release_reason_code"], _RETENTION_RELEASE_REASONS, "release_reason_code"
                ),
            }

        if action in {
            AuditAction.IMPORT_DECLARATION_DECLARED,
            AuditAction.IMPORT_DECLARATION_QUARANTINED,
            AuditAction.IMPORT_DECLARATION_CANCELLED,
        }:
            optional = {"decision_reason_codes"} if action is AuditAction.IMPORT_DECLARATION_QUARANTINED else None
            cls._require_keys(values, {"status"}, optional)
            result = {"status": cls._choice(values["status"], _IMPORT_DECLARATION_STATUSES, "status")}
            if "decision_reason_codes" in values:
                result["decision_reason_codes"] = cls._field_names(
                    values["decision_reason_codes"], _IMPORT_DECLARATION_REASON_CODES
                )
            return result

        if action is AuditAction.IMPORT_DECLARATION_ARCHIVED:
            cls._require_keys(values, {"previous_status", "archive_reason_code"})
            return {
                "previous_status": cls._choice(
                    values["previous_status"], _IMPORT_DECLARATION_STATUSES, "previous_status"
                ),
                "archive_reason_code": cls._choice(
                    values["archive_reason_code"], _ARCHIVE_REASON_CODES, "archive_reason_code"
                ),
            }

        if action is AuditAction.IMPORT_FILE_UPLOADED:
            cls._require_keys(values, {"byte_size", "header_count"})
            if not all(
                isinstance(values[key], int) and cast(int, values[key]) >= 0 for key in ("byte_size", "header_count")
            ):
                raise InvalidAuditMetadata("Les métadonnées du fichier importé sont invalides.")
            return {"byte_size": values["byte_size"], "header_count": values["header_count"]}

        if action is AuditAction.IMPORT_MAPPING_SAVED:
            cls._require_keys(values, {"mapped_field_count"})
            count = values["mapped_field_count"]
            if not isinstance(count, int) or not 1 <= count <= 9:
                raise InvalidAuditMetadata("mapped_field_count est invalide.")
            return {"mapped_field_count": count}

        if action in {AuditAction.IMPORT_VALIDATED, AuditAction.IMPORT_CONFIRMED}:
            allowed = {"created_count", "duplicate_count", "ready_count", "review_count", "quarantined_count"}
            cls._require_keys(values, set(values), None)
            if not values or set(values) - allowed:
                raise InvalidAuditMetadata("Les compteurs d’import sont invalides.")
            if not all(isinstance(value, int) and value >= 0 for value in values.values()):
                raise InvalidAuditMetadata("Les compteurs d’import sont invalides.")
            return dict(values)

        if action is AuditAction.IMPORT_RETRY_STARTED:
            cls._require_keys(values, {"retry_of_run_id"})
            return {"retry_of_run_id": cls._uuid(values["retry_of_run_id"], "retry_of_run_id")}

        if action is AuditAction.IMPORT_REPORT_VIEWED:
            cls._require_keys(values, set(), {"kind"})
            return {"kind": cls._choice(values["kind"], frozenset({"quarantine"}), "kind")} if values else {}

        if action is AuditAction.EXPORT_REQUESTED:
            cls._require_keys(values, {"dataset", "scope", "filters", "column_count"})
            filters = values["filters"]
            if (
                not isinstance(filters, Mapping)
                or len(filters) > 8
                or any(
                    key not in _EXPORT_FILTERS
                    or not isinstance(value, str)
                    or len(value) > 64
                    or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None
                    for key, value in filters.items()
                )
            ):
                raise InvalidAuditMetadata("Filtres d’export invalides.")
            count = values["column_count"]
            if not isinstance(count, int) or not 1 <= count <= 32:
                raise InvalidAuditMetadata("Nombre de colonnes d’export invalide.")
            return {
                "dataset": cls._choice(values["dataset"], _EXPORT_DATASETS, "dataset"),
                "scope": cls._choice(values["scope"], _EXPORT_SCOPES, "scope"),
                "filters": dict(sorted(filters.items())),
                "column_count": count,
            }

        if action in {AuditAction.EXPORT_READY, AuditAction.EXPORT_DOWNLOADED}:
            required = (
                {"row_count", "byte_size", "omitted_count"}
                if action is AuditAction.EXPORT_READY
                else {"dataset", "byte_size"}
            )
            cls._require_keys(values, required)
            counts = required - {"dataset"}
            if any(not isinstance(value, int) or value < 0 for key, value in values.items() if key in counts):
                raise InvalidAuditMetadata("Compteurs d’export invalides.")
            result = {key: values[key] for key in counts}
            if "dataset" in required:
                result["dataset"] = cls._choice(values["dataset"], _EXPORT_DATASETS, "dataset")
            return result

        if action is AuditAction.EXPORT_FAILED:
            cls._require_keys(values, {"dataset", "error_code"})
            return {
                "dataset": cls._choice(values["dataset"], _EXPORT_DATASETS, "dataset"),
                "error_code": cls._choice(values["error_code"], _EXPORT_ERRORS, "error_code"),
            }

        if action is AuditAction.EXPORT_EXPIRED:
            cls._require_keys(values, {"dataset"})
            return {"dataset": cls._choice(values["dataset"], _EXPORT_DATASETS, "dataset")}

        if action is AuditAction.EXPORT_RULE_CHANGED:
            cls._require_keys(values, {"category", "status", "field_count"})
            count = values["field_count"]
            if not isinstance(count, int) or not 0 <= count <= 32:
                raise InvalidAuditMetadata("Nombre de champs invalide.")
            return {
                "category": cls._choice(
                    values["category"], frozenset({"prospect_profile", "person_identity", "channel"}), "category"
                ),
                "status": cls._choice(values["status"], frozenset({"allowed", "denied", "unknown"}), "status"),
                "field_count": count,
            }

        if action in {AuditAction.CONTACT_ARCHIVED, AuditAction.CONTACT_CHANNEL_ARCHIVED}:
            cls._require_keys(values, {"previous_version", "archive_reason_code"}, {"channels_archived"})
            previous_version = values["previous_version"]
            if not isinstance(previous_version, int) or previous_version <= 0:
                raise InvalidAuditMetadata("previous_version doit etre strictement positif.")
            archive_result = {
                "previous_version": previous_version,
                "archive_reason_code": cls._choice(
                    values["archive_reason_code"], _ARCHIVE_REASON_CODES, "archive_reason_code"
                ),
            }
            if "channels_archived" in values:
                count = values["channels_archived"]
                if not isinstance(count, int) or count < 0:
                    raise InvalidAuditMetadata("channels_archived doit etre un entier positif.")
                archive_result["channels_archived"] = count
            return archive_result

        cls._require_keys(values, set())
        return {}

    @staticmethod
    def _require_keys(
        values: Mapping[str, object],
        required: set[str],
        optional: set[str] | None = None,
    ) -> None:
        allowed = required | (optional or set())
        if set(values) != required and not (required <= set(values) <= allowed):
            raise InvalidAuditMetadata("Les clés de métadonnées ne correspondent pas à la politique de l’action.")

    @staticmethod
    def _uuid(value: object, field_name: str) -> str:
        if not isinstance(value, UUID):
            raise InvalidAuditMetadata(f"{field_name} doit être un UUID interne.")
        return str(value)

    @staticmethod
    def _choice(value: object, choices: frozenset[str], field_name: str) -> str:
        if not isinstance(value, str) or value not in choices:
            raise InvalidAuditMetadata(f"{field_name} contient un code non autorisé.")
        return value

    @staticmethod
    def _short_text(value: object, field_name: str, maximum: int) -> str:
        if not isinstance(value, str) or not 1 <= len(value) <= maximum:
            raise InvalidAuditMetadata(f"{field_name} est invalide.")
        return value

    @classmethod
    def _field_names(cls, value: object, allowed_fields: frozenset[str]) -> tuple[str, ...]:
        if (
            isinstance(value, (str, bytes))
            or not isinstance(value, Sequence)
            or not value
            or any(not isinstance(field_name, str) or field_name not in allowed_fields for field_name in value)
            or len(set(value)) != len(value)
        ):
            raise InvalidAuditMetadata("changed_fields contient une valeur interdite ou dupliquee.")
        return tuple(sorted(value))

    @classmethod
    def _status_operation(cls, values: Mapping[str, object]) -> dict[str, object]:
        return {
            "reason_code": cls._choice(values["reason_code"], _STATUS_REASON_CODES, "reason_code"),
            "operation_id": cls._uuid(values["operation_id"], "operation_id"),
        }


@dataclass(frozen=True, slots=True)
class AuditEventDraft:
    id: UUID
    scope: AuditScope
    action: AuditAction
    entity_type: str
    entity_id: UUID | None
    actor_kind: AuditActorKind
    actor_id: UUID | None
    organization_id: UUID | None
    request_id: str
    correlation_id: str
    source: AuditSource
    metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.scope, AuditScope):
            raise InvalidAuditEvent("La portée d’audit est invalide.")
        if not isinstance(self.action, AuditAction):
            raise InvalidAuditEvent("Le code d’action d’audit est inconnu.")
        if not isinstance(self.actor_kind, AuditActorKind):
            raise InvalidAuditEvent("Le type d’acteur d’audit est invalide.")
        if not isinstance(self.source, AuditSource):
            raise InvalidAuditEvent("La source d’audit est invalide.")
        if self.scope is AuditScope.TENANT and self.organization_id is None:
            raise InvalidAuditEvent("Une organisation est obligatoire pour un événement locataire.")
        if (self.scope is AuditScope.TENANT and self.action not in _TENANT_ACTIONS) or (
            self.scope is AuditScope.PLATFORM and self.action not in _PLATFORM_ACTIONS
        ):
            raise InvalidAuditEvent("L’action d’audit n’est pas autorisée dans cette portée.")
        if self.actor_kind is AuditActorKind.USER and self.actor_id is None:
            raise InvalidAuditEvent("Un identifiant d’acteur est obligatoire pour un acteur utilisateur.")
        if self.actor_kind is AuditActorKind.SYSTEM and self.actor_id is not None:
            raise InvalidAuditEvent("Un événement système ne porte pas d’identifiant utilisateur.")
        if not _ENTITY_TYPE_PATTERN.fullmatch(self.entity_type):
            raise InvalidAuditEvent("Le type d’entité d’audit est invalide.")
        if self.entity_type != _ACTION_ENTITY_TYPES[self.action]:
            raise InvalidAuditEvent("Le type d’entité ne correspond pas à l’action d’audit.")
        _validate_context_identifier(self.request_id, "request_id")
        _validate_context_identifier(self.correlation_id, "correlation_id")
        if self.schema_version <= 0:
            raise InvalidAuditEvent("schema_version doit être strictement positif.")
        normalized = AuditMetadataPolicy.validate(self.action, self.metadata)
        serialized_metadata = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
        if len(serialized_metadata.encode("utf-8")) > 8192:
            raise InvalidAuditMetadata("Les métadonnées d’audit dépassent 8 Kio.")
        object.__setattr__(self, "metadata", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class AuditEventFilter:
    occurred_from: datetime
    occurred_to: datetime
    action: AuditAction | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuditActorView:
    kind: AuditActorKind
    id: UUID | None
    display_name: str | None


@dataclass(frozen=True, slots=True)
class AuditEventView:
    id: UUID
    occurred_at: datetime
    action: str
    entity_type: str
    entity_id: UUID | None
    actor: AuditActorView
    request_id: str
    correlation_id: str
    source: AuditSource
    metadata: Mapping[str, object]
    schema_version: int


def _validate_context_identifier(value: str, field_name: str) -> None:
    if not 1 <= len(value) <= 128 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise InvalidAuditEvent(f"{field_name} doit contenir entre 1 et 128 caractères sans contrôle.")
