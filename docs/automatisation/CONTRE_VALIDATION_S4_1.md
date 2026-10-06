# Contre-validation S4-1 — Noyau déterministe et Prévol

> **Verdict : `GO` pour le noyau runtime isolé sans effet**  
> **Intégration API / persistance / worker : `NO-GO` à ce stade**  
> **Production et effets CRM : `NO-GO`**  
> **Date :** 1er octobre 2026

## 1. Objet

Cette contre-validation vérifie la réalisation runtime de S4-1 dans son périmètre autorisé : moteur déterministe, Feu
relationnel, Prévol immuable et invalidation. Elle ne valide pas encore les routes HTTP, la persistance, le worker ou la
garde juste avant effet.

## 2. Artefacts contrôlés

- [`S4-1 — Noyau déterministe et Prévol`](./S4_1_NOYAU_DETERMINISTE_PREVOL.md) ;
- [`backend/app/domain/automation.py`](../../backend/app/domain/automation.py) ;
- [`tests/test_automation_deterministic.py`](../../tests/test_automation_deterministic.py) ;
- [`RF-AUT-2.1`](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) ;
- [preuves Étape 4](./PREUVES_VALIDATION_ETAPE_4.md).

## 3. Vérifications fonctionnelles

| Contrôle | Résultat |
|---|---|
| Version de Playbook immuable | PASS — dataclass gelée et empreinte stable |
| Contexte canonique | PASS — organisation, acteur, capacité, sujet, canal, permission, version CRM et suspension requis |
| Priorité Rouge > Jaune > Vert | PASS — blocage flag/permission prioritaire |
| Permission inconnue jamais Verte | PASS — décision Jaune / vérification |
| Identité absente ou données obsolètes | PASS — décision `TO_VERIFY` |
| Prévol sans effet | PASS — plan immuable, `effect_free=true`, mutations CRM = 0 |
| Fidélité et invalidation | PASS — changement de snapshot ou expiration rend le Prévol obsolète |
| Raisons et prochaines actions fermées | PASS — codes et actions typés, aucune commande libre |
| Repli sans IA | PASS — le moteur ne dépend d’aucun fournisseur |

## 4. Preuves exécutées

| Commande | Résultat |
|---|---|
| `pytest tests/test_automation_deterministic.py -q` | **8 passed** |
| Tests ciblés socle + S4-1 | **36 passed** |
| `ruff check` sur le dépôt | **All checks passed** |
| `ruff format --check` | **291 fichiers déjà formatés** |
| `mypy` | **Success: no issues found in 214 source files** |
| `pytest -q` | **309 passed, 44 skipped** |
| `quality_gate.py junit-no-skips` sur le rapport S4-1 | **Verrou qualité ciblé : conforme** |

## 5. Réserve d’intégration

Les 44 tests ignorés par la suite complète nécessitent des services externes non disponibles dans l’environnement courant :

- PostgreSQL réel et rôles applicatif/propriétaire ;
- Redis de test ;
- Mailpit ;
- URLs de bases de test.

Cette réserve n’affecte pas le noyau pur S4-1, mais empêche de prétendre que l’intégration runtime complète est validée.
Elle doit être levée avant toute intégration API, persistance, worker ou Porte 4.

## 6. Décision

La contre-validation donne un **GO limité** au noyau déterministe et au Prévol exécutés en isolation. Elle confirme :

- l’absence d’effet CRM ;
- l’absence d’appel IA ;
- la déterminisme des décisions ;
- l’invalidation explicite du Prévol ;
- la compatibilité avec les règles `RF-AUT-2.1`.

Elle ne donne pas l’autorisation de :

- créer une route API Automation ;
- persister un Prévol en base client ;
- brancher le worker ;
- préparer une tâche CRM réelle ;
- lancer une communication externe ;
- déclarer la Porte 4 ouverte.

## 7. Suite autorisée

La prochaine tranche peut préparer les contrats d’intégration à partir de ce noyau, mais toute intégration devra être
réalisée sur environnement isolé avec PostgreSQL/RLS, Redis et preuves D2/D3. La Porte 4 restera la décision de
construction.
