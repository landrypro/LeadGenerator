# Phase 3.4-D — Rapport d’implémentation et de clôture

> Modèle de preuve à compléter pendant la recette. Ne pas remplacer « À exécuter » par « Vert » sans résultat réel.

| Métadonnée | Valeur |
| --- | --- |
| Phase | 3.4-D — Recette et verrou |
| Révision Alembic attendue | `20260922_0021 (head)` |
| Date d’exécution | 11 au 23 septembre 2026 (UTC) |
| Responsable de recette | À renseigner |
| Verdict | Phase 3.4 clôturée avec réserves transférées à la recette finale de la phase 4 ; verrou qualité vert et GO produit reçu le 23 septembre 2026 (UTC) |

## Preuves de migration

| Contrôle | Résultat | Preuve |
| --- | --- | --- |
| Base isolée créée | Conforme | composition Docker du verrou global |
| `upgrade head` | Conforme | journal du verrou global |
| Reconstruction depuis `20260723_0002` | Conforme | verrou isolé du 23 septembre 2026, avec Docker via WSL |
| `current = 20260922_0021 (head)` | Conforme | preuve isolée `test-results/alembic-current.txt` |
| `alembic check` sans dérive | Conforme | inclus dans le verrou isolé complet du 23 septembre 2026 |

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
| OPP-07 — Réouverture | OK | Réouverture autorisée constatée : étape ouverte, probabilité `50`, motifs de perte et clôture remis à `null`. Le 22 septembre 2026, la session `CommercialdemoA`, propriétaire de `OPP-07 Sales refus` (`f7d3f706-41b2-4287-8e86-62287f5d222b`), a reçu `403 opportunity_action_forbidden` sur `POST /reopen`. L’opportunité est restée en `lost`, version `6`, avec les mêmes champs métier et les mêmes six événements ; aucune écriture. |
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
| OPP-17 — Français, anglais et clavier | OK avec réserve | Le 22 septembre 2026, `OPP-17 FR` et `OPP-17 EN` ont validé les décimales localisées, les dates, les transitions, la perte, la réouverture, `Tab`, `Échap`, le focus restauré et la traduction `fr-CA`/`en-CA`. Les vues restent utilisables à 200 %. Le test ciblé `OpportunitySection.test.jsx` est vert : 14 tests, dont axe. La locale initiale `fr-CA` a été restaurée. Réserve `OPP-17-C-R1` : rapports axe exhaustifs par vue et par locale non exportés. |

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

### Contrôles du correctif de locale — 22 septembre 2026

| Contrôle | Résultat |
| --- | --- |
| Ruff / format Ruff / mypy | Conforme — 244 fichiers formatés, 181 fichiers typés sans erreur |
| Pytest local | Partiel — 263 tests réussis et 40 tests d’infrastructure ignorés faute de services Docker |
| ESLint et build Vite | Conforme — aucune erreur ESLint et build de production réussi |
| Vitest OPP-17 ciblé | Conforme — 14 tests réussis, dont axe |
| Vitest mise en page ciblé | Conforme après correction de l’attente localisée — 5 tests réussis |
| Vitest frontend complet | Conforme — 43 fichiers et 186 tests réussis, sans échec |
| Sources navigateur / artefact Vite / diff Git | Conforme — seule la préférence publique `marketteo.public-locale.v1` est autorisée dans `localStorage`; 5 tests du verrou ciblé sont verts |
| Verrou global sur `20260922_0021` | Conforme — Docker via WSL, reconstruction Alembic, 303 tests backend sans skip, tests frontend sans skip, build Vite, sources navigateur, artefact et diff Git verts. Rapport : `test-results/quality-summary.md`, 23 septembre 2026 à 02:46 UTC. |

## Réserves de clôture

| Identifiant | Risque | Responsable | Échéance |
| --- | --- | --- | --- |
| OPP-03-R1 | Présentation isolée de l’erreur de devise invalide non confirmée | QA produit | Recette finale phase 4 — transfert accepté |
| OPP-11-R1 | Requêtes `415` pendant la saisie partielle d’une devise | Frontend | Recette finale phase 4 — transfert accepté |
| OPP-14-R1 | Mutation interdite Sales et absence d’écriture non rejouées dans l’organisation | QA API | Recette finale phase 4 — transfert accepté |
| OPP-17-C-R1 | Rapports axe exhaustifs par vue et par locale non exportés | QA accessibilité | Recette finale phase 4 — transfert accepté |
| REG-31-33-R1 | Régressions Import, Kanban et Chronologie non consignées | QA produit | Recette finale phase 4 — transfert accepté |
| QG-3.4-R1 | Levée — verrou complet sans skip vert sur `20260922_0021` | Dev/QA | 23 septembre 2026 |

## Décision de clôture

Le 23 septembre 2026 (UTC), le verrou global sans skip a validé la tête `20260922_0021`. Le responsable produit a
ensuite donné son GO explicite dans la tâche de recette pour clôturer la phase 3.4 et ouvrir la spécification détaillée
de la phase 4. **La phase 3.4 est clôturée avec réserves transférées.** OPP-03-R1, OPP-11-R1, OPP-14-R1,
OPP-17-C-R1 et REG-31-33-R1 restent dus lors de la recette finale de la phase 4 ; ce transfert ne vaut pas validation
des contrôles. Le périmètre suivant est ouvert dans [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md).
