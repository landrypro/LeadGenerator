# Phase 3.4-D — Rapport d’implémentation et de clôture

> Modèle de preuve à compléter pendant la recette. Ne pas remplacer « À exécuter » par « Vert » sans résultat réel.

| Métadonnée | Valeur |
| --- | --- |
| Phase | 3.4-D — Recette et verrou |
| Révision Alembic attendue | `20260910_0020 (head)` |
| Date d’exécution | 11 septembre 2026 |
| Responsable de recette | À renseigner |
| Verdict | Verrou global conforme ; recette fonctionnelle en cours |

## Preuves de migration

| Contrôle | Résultat | Preuve |
| --- | --- | --- |
| Base isolée créée | Conforme | composition Docker du verrou global |
| `upgrade head` | Conforme | journal du verrou global |
| Reconstruction depuis `20260723_0002` | Conforme | étape « Alembic reconstruction » du verrou global |
| `current = 20260910_0020 (head)` | Conforme | contrôle local et `test-results/alembic-current.txt` |
| `alembic check` sans dérive | Conforme | `No new upgrade operations detected.` |

## Preuves fonctionnelles

Reporter ici les verdicts `OPP-01` à `OPP-17` et `REG-31` à `REG-33` du document de recette, les captures et les
anomalies. Toute réserve doit avoir un identifiant, un risque, un responsable et une échéance.

| Scénario | Verdict | Preuve |
| --- | --- | --- |
| OPP-01 — Création et montant exact | OK | Opportunité « Clinique Proximité » : `12 500,5 CAD`, probabilité 40 %, valeur pondérée `5 000,2 CAD`; capture du 10 septembre 2026 |
| OPP-02 — Devises séparées | OK | Agrégats distincts `20 000 CAD` et `6 250 USD`, sans total multidevise ; capture du 10 septembre 2026 |
| OPP-03 — Validations et échéance | Partiellement OK | Messages montant, probabilité et échéance validés. Affichage de l’erreur `ZZZ` à rejouer seule en recette finale ; aucune écriture partielle constatée. |
| OPP-04 — Étapes ouvertes | OK | Transitions voisines et chronologie validées ; saut `discovery` → `proposal` refusé en `422`, étape et version `1` inchangées. |
| OPP-05 — Gagnée | OK | Rejeu du 17 septembre 2026 : payload `version: 3`, `to_stage: won`; réponse en version `4`, étape `won`, probabilité `100`, `closed_at` renseigné, motifs de perte nuls et interface terminale avec action « Réouvrir ». Verrou global après correctif vert. |
| OPP-06 — Perdue et motifs | OK | Motifs affichés en langage métier ; perte à `0 %` et état terminal avec « Réouvrir ». Le motif `other` et sa note ont été persistés et horodatés ; l'absence de note est refusée sans requête ni écriture. |
| OPP-07 — Réouverture | OK avec réserve | Réouverture autorisée constatée : étape ouverte, probabilité `50`, motifs de perte et clôture remis à `null`. L'action est absente pour Sales. Le refus API Sales `403 opportunity_action_forbidden` est reporté à la recette finale. |
| OPP-08 à OPP-17 | À exécuter | — |

## Preuves du verrou global

| Contrôle | Résultat |
| --- | --- |
| Ruff / format Ruff / mypy | Conforme |
| Pytest réel / zéro skip backend | Conforme |
| Audit npm / ESLint | Conforme |
| Vitest avec axe / zéro skip frontend | Conforme — pool `threads` mono-worker, zéro erreur non gérée |
| Build et artefact Vite | Conforme |
| Sources navigateur / diff Git | Conforme |

Artefacts produits : `test-results/quality-summary.md`, `pytest-quality.xml`, `vitest.xml` et
`alembic-current.txt`. Le verrou local a rapporté `Verrou qualité local 3.4 : VERT` le 11 septembre 2026.

### Contrôles du correctif OPP-05 — 17 septembre 2026

| Contrôle | Résultat |
| --- | --- |
| Tests ciblés audit et opportunités | Conforme — 32 tests réussis |
| Régression backend et intégrations réelles | Conforme — 300 tests réussis, zéro skip |
| ESLint, Vitest et build Vite | Conforme — Vitest `4.1.11`, 40 fichiers / 167 tests, build de production réussi ; aucune reprise du worker n’a été requise |
| Verrou global après correctif | Conforme — `Verrou qualité local 3.4 : VERT` le 17 septembre 2026 ; ports isolés alternatifs utilisés car le PostgreSQL de développement occupait `55432` |

## Décision de clôture

3.4 ne peut être déclarée clôturée qu’après verrou global vert, recette acceptée et GO explicite du responsable
produit. Les scénarios reportés vers 3.6 restent listés et ne sont jamais assimilés à des validations.
