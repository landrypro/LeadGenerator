"""Catalogue fermé des demandes Assistant et de leurs portées autorisées."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from .assistant import AssistantIntentCode, AssistantScopeKind


@dataclass(frozen=True, slots=True)
class AssistantCatalogEntry:
    """Description stable d’une demande que l’Assistant peut préparer."""

    code: AssistantIntentCode
    label_fr: str
    label_en: str
    prompt_fr: str
    prompt_en: str
    aliases: tuple[str, ...]
    scope_kind: AssistantScopeKind
    required_capability: str
    returns_crm_items: bool
    guided: bool

    def label(self, locale: str) -> str:
        return self.label_en if locale == "en-CA" else self.label_fr

    def prompt(self, locale: str) -> str:
        return self.prompt_en if locale == "en-CA" else self.prompt_fr


# L'ordre est volontaire : un rééquilibrage contient aussi « prospects en cours »,
# il doit donc être reconnu avant la portée simple des prospects ouverts.
ASSISTANT_CATALOG: Final[tuple[AssistantCatalogEntry, ...]] = (
    AssistantCatalogEntry(
        code=AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS,
        label_fr="Statut de l’automatisation",
        label_en="Automation status",
        prompt_fr="Explique le statut de l’automatisation",
        prompt_en="Explain the automation status",
        aliases=(
            "statut automatisation",
            "statut de l'automatisation",
            "etat automatisation",
            "etat de l'automatisation",
            "automation status",
            "prevol",
            "feu",
        ),
        scope_kind=AssistantScopeKind.AUTOMATION_STATUS,
        required_capability="automation:plan:create",
        returns_crm_items=False,
        guided=False,
    ),
    AssistantCatalogEntry(
        code=AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
        label_fr="Rééquilibrer la charge",
        label_en="Review the workload balance",
        prompt_fr="Répartis les prospects en cours entre mon équipe",
        prompt_en="Review the open prospects workload among my team",
        aliases=("repart", "redistrib", "charge", "entre mon equipe", "among my team", "rebalance"),
        scope_kind=AssistantScopeKind.ORGANIZATION_OPEN_PROSPECTS,
        required_capability="automation:read:organization",
        returns_crm_items=True,
        guided=True,
    ),
    AssistantCatalogEntry(
        code=AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
        label_fr="Nouveaux prospects à suivre",
        label_en="New prospects to follow up",
        prompt_fr="Prépare le suivi des nouveaux prospects",
        prompt_en="Prepare the new prospect follow-up",
        aliases=("relance", "suivi", "follow up", "follow-up", "nouveaux prospects", "new prospects"),
        scope_kind=AssistantScopeKind.NEW_PROSPECTS,
        required_capability="automation:plan:create",
        returns_crm_items=True,
        guided=True,
    ),
    AssistantCatalogEntry(
        code=AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
        label_fr="Prospects ouverts",
        label_en="Open prospects",
        prompt_fr="Montre-moi les prospects ouverts",
        prompt_en="Show my assigned open prospects",
        aliases=(
            "prospects en cours",
            "prospects ouverts",
            "prospects du jour",
            "prospects d'aujourd'hui",
            "open prospects",
            "current prospects",
            "today's prospects",
        ),
        scope_kind=AssistantScopeKind.ASSIGNED_OPEN_PROSPECTS,
        required_capability="automation:plan:create",
        returns_crm_items=True,
        guided=True,
    ),
)

ASSISTANT_CATALOG_BY_CODE: Final[Mapping[AssistantIntentCode, AssistantCatalogEntry]] = MappingProxyType(
    {entry.code: entry for entry in ASSISTANT_CATALOG}
)

ASSISTANT_GUIDED_CODES: Final[tuple[AssistantIntentCode, ...]] = (
    AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
    AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
    AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
)

# Ordre stable exposé à l'interface. Il privilégie les demandes CRM les plus
# directement actionnables, puis l'explication de l'état Automation.
ASSISTANT_SUGGESTION_CODES: Final[tuple[AssistantIntentCode, ...]] = (
    AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
    AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
    AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
    AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS,
)


def normalize_assistant_text(value: str) -> str:
    """Normalise les accents, apostrophes et espaces sans conserver le texte."""

    folded = unicodedata.normalize("NFKD", value.casefold().replace("’", "'"))
    without_marks = "".join(character for character in folded if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", without_marks).strip()


def classify_catalog_intent(value: str) -> AssistantIntentCode | None:
    """Retourne uniquement une intention du catalogue, sans heuristique ouverte."""

    normalized = normalize_assistant_text(value)
    for entry in ASSISTANT_CATALOG:
        if any(_alias_matches(normalized, normalize_assistant_text(alias)) for alias in entry.aliases):
            return entry.code
    return None


def _alias_matches(normalized_text: str, normalized_alias: str) -> bool:
    if len(normalized_alias) <= 3 and " " not in normalized_alias:
        return re.search(rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", normalized_text) is not None
    return normalized_alias in normalized_text


def catalog_entry(code: AssistantIntentCode) -> AssistantCatalogEntry:
    return ASSISTANT_CATALOG_BY_CODE[code]
