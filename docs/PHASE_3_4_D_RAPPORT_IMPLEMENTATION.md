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
| Pré-OPP-08 — Éditeur et garde-fous | OK | Modification des champs commerciaux validée. Devise modifiée uniquement après confirmation explicite du montant ; montant `10000.0000 USD`, pondéré `4900.0000`, version `5` → `6` et responsable actif remplacé. |
| OPP-08 — Modification et responsable | OK | Responsable Gestionnaire désactivé : lecture conservée, actions métier bloquées et réaffectation isolée vers `CommercialdemoA` validée. Désactivation = perte d’accès CRM ; réactivation suivie d’une reconnexion = accès et menu restaurés. Captures du 17 septembre 2026. |
| OPP-09 — Concurrence | OK | Affaire `OPP-09 Concurrence` lue en version `1` dans deux fenêtres. La modification A a produit la version `2`; la soumission obsolète B a affiché « L’opportunité a changé depuis sa lecture. ». Une modification ultérieure après reprise a produit la version `3`. Captures du 18 septembre 2026. |
| OPP-10 — Idempotence | OK | Deux créations identiques avec la même clé ont retourné le même id `cd6a0c34-a237-4ac2-beeb-faea595d046a`, version `1`. La même clé avec un nom différent a été refusée en `409`. Lecture finale : une seule affaire et un seul événement `created` (`1` → `1`). 18 septembre 2026. |
| OPP-11 — Portefeuille et pagination | OK avec réserve | Lot `OPP-11-20260918-104723` : 26 affaires, première page de 25, « Charger plus », puis 26e carte sans doublon. Filtres texte, étape, CAD, USD et retard fonctionnels. Réserve OPP-11-A : la saisie intermédiaire d’une devise (`U`, `US`, `C`, `CA`) lance une requête refusée en `415`; le code complet est accepté en `200`. Corriger le déclenchement de requête sur valeur incomplète. 19 septembre 2026. |
| OPP-12 — Chronologie et synthèses | OK | `OPP-12 Chronologie2` (`2b1f408d-060d-4c9d-8a5c-6013ed8ee37b`) : création en version `1` à `3 000 CAD` pondérés `750`, modification en version `2` à `3 500 CAD` pondérés `875`, puis transition vers `qualification` en version `3`. Chronologie, fiche et portefeuille cohérents ; le prospect est resté dans `Nouveau`, conformément à l’indépendance opportunité/prospect. 19 septembre 2026. |
| OPP-13 — Alignement pipeline | OK | OPP-13-A a refusé le saut direct `Nouveau → Qualifié`. OPP-13-B a aligné explicitement le prospect d’un cran (`qualifying → qualified`) en `200`, version `2` → `3`, tandis que l’opportunité `OPP-13 Alignement` est restée indépendante en `qualification`. Kanban final : prospect dans `Qualifié`. 19 septembre 2026. |
| OPP-14 — Rôles | OK avec réserve | Responsable : deux affaires, total pondéré `1 500 CAD`. Sales : seule `Test OPP-14`, total pondéré `500 CAD`. Lecture directe de `Test OPP-15` refusée en `403 opportunity_action_forbidden`. Réserve OPP-14-A : mutation interdite et preuve d’absence d’écriture non rejouées, faute de fonction « Edit and resend » dans le navigateur ; à rejouer avant recette finale. 20 septembre 2026. |
| OPP-15 — Isolation | OK | Organisations A et B : lectures, `PATCH`, transitions et événements croisés refusés en `404 opportunity_not_found`. `OPP-15-A` (`7b01f628-0fdd-44b1-88bb-c6388f958166`) et `OPP-15-B` (`a2eee394-3541-4094-9491-6c846d972143`) sont restées en `discovery`, version `1`, avec l’unique événement `created` (`1` → `1`) ; aucune écriture inter-organisation. 21 septembre 2026. |
| OPP-16 — Sécurité et navigateur | OK | Six lectures ont répondu `200` avec `Cache-Control: no-store, max-age=0`. Avec une nouvelle session authentifiée sans en-tête CSRF, le `PATCH` a été refusé en `400 csrf_failed` et l’état est resté strictement identique : version `2`, même nom, même étape et deux événements. Un premier essai avait légitimement réussi parce que la session de test conservait encore le jeton ; `OPP-15-A` a été restaurée par une commande autorisée en version `3`. Stockages navigateur : Session Storage vide, aucune donnée 3.4 dans IndexedDB ou Cache Storage, aucun service worker ; seul le marqueur technique `ecodis-offline-v2-migrated=true` était présent dans Local Storage. 21 septembre 2026. |
| OPP-17 | À exécuter | — |

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
