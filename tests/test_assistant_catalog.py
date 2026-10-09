import pytest

from backend.app.domain.assistant import AssistantIntentCode, AssistantScopeKind
from backend.app.domain.assistant_catalog import (
    ASSISTANT_CATALOG,
    ASSISTANT_CATALOG_BY_CODE,
    ASSISTANT_GUIDED_CODES,
    ASSISTANT_SUGGESTION_CODES,
    catalog_entry,
    classify_catalog_intent,
    normalize_assistant_text,
)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("Montre-moi les prospects ouverts", AssistantIntentCode.SCOPE_OPEN_PROSPECTS),
        ("Les prospects d’aujourd’hui", AssistantIntentCode.SCOPE_OPEN_PROSPECTS),
        ("Show my assigned open prospects", AssistantIntentCode.SCOPE_OPEN_PROSPECTS),
        ("Répartis les prospects en cours entre mon équipe", AssistantIntentCode.REBALANCE_OPEN_PROSPECTS),
        ("Review the open prospects workload among my team", AssistantIntentCode.REBALANCE_OPEN_PROSPECTS),
        ("Prépare le suivi des nouveaux prospects", AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP),
        ("Prepare the new prospect follow-up", AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP),
        ("Explique le statut de l’automatisation", AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS),
    ],
)
def test_catalog_classifies_canonical_phrases_and_aliases(phrase: str, expected: AssistantIntentCode) -> None:
    assert classify_catalog_intent(phrase) is expected


def test_catalog_is_closed_and_metadata_is_complete() -> None:
    assert len(ASSISTANT_CATALOG) == len(ASSISTANT_CATALOG_BY_CODE)
    assert set(ASSISTANT_GUIDED_CODES) == {
        AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
        AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
        AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
    }
    assert ASSISTANT_SUGGESTION_CODES == (
        AssistantIntentCode.SCOPE_OPEN_PROSPECTS,
        AssistantIntentCode.REBALANCE_OPEN_PROSPECTS,
        AssistantIntentCode.PREPARE_NEW_PROSPECT_FOLLOWUP,
        AssistantIntentCode.EXPLAIN_AUTOMATION_STATUS,
    )
    assert all(entry.aliases for entry in ASSISTANT_CATALOG)
    assert all(entry.required_capability for entry in ASSISTANT_CATALOG)
    assert (
        catalog_entry(AssistantIntentCode.SCOPE_OPEN_PROSPECTS).scope_kind is AssistantScopeKind.ASSIGNED_OPEN_PROSPECTS
    )


def test_catalog_does_not_guess_unknown_requests() -> None:
    assert classify_catalog_intent("Aide-moi à analyser mon portefeuille") is None
    assert normalize_assistant_text("  Les prospects d’Aujourd’hui  ") == "les prospects d'aujourd'hui"
