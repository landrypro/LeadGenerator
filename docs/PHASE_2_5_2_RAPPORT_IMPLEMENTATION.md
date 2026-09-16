# Rapport d’implémentation — Incrément 2.5.2

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.5.2 — Socle prospect et ajout Google |
| Date | 14 août 2026 |
| Statut | Validé avec réserves — preuves des étapes 9 et 10 à consigner |
| Décisions appliquées | Les seize décisions validées de la section 16 |

## 1. Résultat livré

- Ajout du jeton serveur éphémère `selection_token` dans `POST /api/google/places/search`.
- Ajout du port `GoogleSelectionGrantStore` et de l’implémentation mémoire bornée.
- Ajout de `POST /api/prospects`, `POST /api/prospects/from-google`, `GET /api/prospects` et `GET /api/prospects/{id}`.
- Ajout des capacités `prospects:read` et `prospects:create` pour `admin`, `manager` et `sales`.
- Ajout depuis Google sans appel Google supplémentaire, sans pagination et avec conservation durable du seul `place_id`.
- Création d’un alias interne neutre et non réversible pour les prospects issus de Google.
- Déduplication applicative par `google_place_id` actif dans l’organisation.
- Audit transactionnel `prospect.created` minimal : origine uniquement, sans `place_id`, nom, adresse ou donnée Google.
- Interface de recherche enrichie avec sélection individuelle/groupée et ajout au CRM.
- Aucune écriture dans `localStorage`, `sessionStorage`, IndexedDB ou cache applicatif navigateur.

## 2. Fichiers principaux modifiés

- Backend application : `backend/app/application/use_cases/prospects.py`, `backend/app/application/use_cases/search_google_places.py`
- Backend ports/adaptateurs : `backend/app/application/ports/prospect.py`, `backend/app/infrastructure/memory/google_selection_grants.py`
- Backend API : `backend/app/presentation/api/routers/prospects.py`, `backend/app/presentation/api/schemas.py`, `backend/app/presentation/api/mappers.py`
- Composition : `backend/app/bootstrap.py`, `backend/app/container.py`, `backend/app/config.py`
- Frontend : `client/src/features/lead-search/**`, `client/src/styles.css`
- Tests : `tests/test_google_selection_grants.py`, `tests/test_prospect_use_cases.py`, `tests/test_prospect_api.py`, `client/src/features/lead-search/LeadGeneratorPage.test.jsx`

## 3. Contrôles exécutés

- `python -m compileall backend\app ...` : conforme
- `python -m pytest tests/test_google_selection_grants.py tests/test_prospect_use_cases.py tests/test_prospect_api.py tests/test_search_service.py tests/test_lead_generation_response.py tests/test_app_factory.py -q` : 13 passed
- `python -m pytest tests/integration/test_api_workflow.py -q` : 17 passed
- `python -m pytest -q` : 174 passed, 28 skipped
- `python -m ruff check backend\app tests` : conforme
- `python -m mypy backend\app` : conforme
- `npm.cmd run lint` : conforme
- `npm.cmd test -- --run src/features/lead-search/LeadGeneratorPage.test.jsx` : 11 passed
- `npm.cmd run build` : conforme

Note : `npm.cmd test` complet a dépassé le délai local sans produire de détail exploitable. Le test ciblé de l’écran modifié, ESLint et le build sont conformes.

## 4. Points à vérifier en recette locale

1. Se connecter avec un utilisateur d’organisation actif.
2. Lancer une recherche Google limitée à 20 résultats.
3. Ajouter un résultat individuel au CRM.
4. Relancer la même action et vérifier l’état `Déjà au CRM`.
5. Sélectionner plusieurs résultats et utiliser `Ajouter la sélection`.
6. Vérifier que le tableau reste temporaire et que l’export Excel reste désactivé.
7. Vérifier dans l’audit que seuls les événements `prospect.created` avec `origin` sont inscrits.
8. Vérifier dans PostgreSQL que seul `google_place_id` est conservé depuis Google.

## 5. Critique technique

- Le magasin de jetons de sélection est volontairement en mémoire. Il est conforme au mode local et mono-instance, mais devra passer sur Redis avant un déploiement multi-instance.
- La déduplication concurrente s’appuie surtout sur l’unicité PostgreSQL et le pré-check applicatif. Une course extrême peut encore retourner une erreur technique plutôt qu’un `existing`; ce raffinement peut être durci lors de l’industrialisation de la transaction.
- L’interface ajoute au CRM depuis l’écran Google, mais ne fournit pas encore de portefeuille prospects complet. C’est volontairement reporté à 2.5.5.

## 6. Décision de passage

L’implémentation 2.5.2 est prête pour la recette locale regroupée avec 2.5.1.
