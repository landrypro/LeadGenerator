# Phase 4.6 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 4.6 — Recette de phase et tests de bout en bout |
| Date | 30 septembre 2026 (UTC) |
| Statut | GO de clôture locale reçu ; verrou qualité local VERT sur la tête Alembic `20260929_0030`. La preuve Azure sur le commit de clôture reste requise avant l'entrée en phase 5. |
| Spécification | [`PHASE_4_6_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_6_SPECIFICATIONS_DETAILLEES.md) |

## 1. Réalisations

- Ajout de la migration Alembic `20260925_0026` pour enregistrer les cinq codes d’usage du pilote Meta Lead Ads,
  l’issue `quarantined` et la mise à jour symétrique de `app_private.record_usage_event`.
- Émission idempotente des événements `webhook_accepted`, `fetch_attempted`, `imported`, `quarantined` et `failed`
  depuis l’admission webhook et le worker du connecteur.
- Ajout du bloc `connectors.meta_lead_ads` au rapport d’usage, avec conservation des agrégats tenant et utilisateur.
- Extension du test d’intégration d’usage aux cinq codes Meta et à leur rapprochement dans le rapport.
- Ajout du harnais navigateur sans dépendance supplémentaire [`phase4_6_browser_gate.mjs`](../scripts/phase4_6_browser_gate.mjs).
  Il démarre Vite preview et Chrome/Chromium via CDP, parcourt 22 routes dans `fr-CA` et `en-CA`, exécute axe-core,
  capture les erreurs navigateur et écrit `test-results/phase-4-6/browser-axe.json`.
- Branchement du harnais au verrou local et au pipeline Azure après le build Vite.
- Mise à jour du parent Phase 4 et des réserves documentaires pour distinguer la recette interne de l’activation Meta
  externe.

## 2. Vérifications exécutées

| Contrôle | Résultat | Preuve ou limite |
| --- | --- | --- |
| Ruff ciblé | PASS | Modules usage, connecteur, modèle, migration et tests |
| mypy ciblé | PASS | Trois modules backend concernés |
| Tests ciblés | PASS | `13 passed` : connecteur, API, usage, qualité |
| Build Vite | PASS | `npm run build` |
| Recette navigateur locale | PASS | 44 parcours, axe sans violation critique/sérieuse ; `test-results/phase-4-6/browser-axe.json` |
| Test d’intégration usage | PASS | Inclus dans les 345 tests backend du verrou réel ; réconciliation et codes Meta validés |
| Verrou qualité complet | PASS | 30 septembre 2026, WSL `Ubuntu-24.04`, tête `20260929_0030`, 345 backend, 216 frontend, 44 parcours navigateur Axe, zéro échec et zéro skip ; audit npm sans vulnérabilité |

## 3. Clôture de la recette interactive

Le 30 septembre 2026, la vérification humaine `E2E-11-MANUAL` a été clôturée avec le verdict **PASS**.

| Passage | Résultat |
| --- | --- |
| Parcours français et anglais | Les huit vues prévues sont lisibles et leurs actions principales sont accessibles dans les deux langues. |
| Clavier et focus | Lien d'évitement, ordre de tabulation, focus visible et activation des commandes validés. |
| Petit écran et zoom à 200 % | Navigation mobile, Dashboard, Exports, Fournisseurs et acquisitions et Pipeline restent utilisables sans chevauchement bloquant. |
| État vide et erreur réversible | L'état vide est explicite et le retour en ligne permet de reprendre le parcours. |

La preuve détaillée et le registre d'exécution sont mis à jour dans
[`RECETTE_PHASE4.6_INTERACTIVE.md`](RECETTE_PHASE4.6_INTERACTIVE.md) et
[`RECETTE_PHASE4.6_REGISTRE.csv`](RECETTE_PHASE4.6_REGISTRE.csv).

Le rejeu CSV `E2E-03` est également **PASS** depuis le 30 septembre 2026 : le lot
`89b1cdab-2221-4435-a99b-c446da58c495` confirme `0` création et `2` doublons exacts.
Le premier import et la quarantaine étaient déjà rapprochés ; aucun prospect supplémentaire n'a été créé.

Le scénario `E2E-07` est **PASS** depuis le 30 septembre 2026 : `28` tests ciblés verts, refus du quota synthétique
en HTTP `429 google_quota_exceeded`, blocage réel du registre durable en HTTP `503 usage_tracking_unavailable`,
puis pause Redis en HTTP `503 authentication_unavailable`. Après restauration, PostgreSQL et Redis sont `ok`, l'API
est `ready`, Google est revenu en mode `live` et la page Usage affiche le quota courant de l'organisation (`12/100`).

## 4. Décision de clôture et suite

Le 30 septembre 2026, le responsable produit a donné le **GO de clôture locale de la phase 4.6**. Les parcours
`E2E-01` à `E2E-12`, le verrou sans skip et les contrôles d'accessibilité sont `PASS`. Le pilote Meta technique est
validé uniquement avec les doubles locaux ; l'activation Meta réelle demeure `BLOCKED/EXTERNAL`.

Avant l'entrée en phase 5, le commit de clôture doit exécuter le pipeline Azure sur cette même révision et publier les
rapports JUnit ainsi que le dossier de preuves 4.6. Cette preuve CI complète le verdict global prévu par la
spécification ; elle ne modifie ni la décision locale ni le statut externe de Meta.
