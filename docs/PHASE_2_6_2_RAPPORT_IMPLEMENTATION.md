# Rapport d’implémentation — 2.6.2 Quotas et droits préparatoires

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.6 — Redis partagé, quotas et durcissement |
| Incrément | 2.6.2 — Quotas et droits préparatoires |
| Date | 25 août 2026 |
| Statut | Implémenté ; recette fonctionnelle regroupée à la clôture de 2.6 |
| Migration Alembic | Aucune ; tête inchangée `20260815_0013` |

## Résultat livré

La recherche Google possède maintenant une borne quotidienne opérationnelle, décidée côté serveur avant tout appel
facturable :

- 20 recherches par utilisateur dans son organisation active et par journée UTC ;
- 100 recherches partagées par organisation et par journée UTC ;
- politique serveur immuable `server_default_v1`, remplaçable plus tard par un résolveur de droits de plan ;
- réservation Redis atomique des deux compteurs ; un refus ne modifie aucun compteur ;
- opération UUID interne mémorisée jusqu'à minuit UTC afin qu'un rejeu technique ne débite pas deux fois ;
- refus `429 google_quota_exceeded` avec `Retry-After`, `Cache-Control: no-store` et une portée minimale ;
- sentinelle Redis unique au seuil de 80 %, sans courriel, bannière ou promesse commerciale ;
- comportement fermé `503` en cas d'incertitude Redis, sans repli mémoire ni appel Google.

Une réservation acceptée n'est jamais remboursée après une erreur Google ou l'échec ultérieur d'un jeton. Ce choix
conservateur protège le coût ; ces clés Redis temporaires ne constituent ni une facture ni un registre de
consommation client.

## Fichiers principaux

- `backend/app/application/ports/google_quota.py` : contrats de politique et de réservation ;
- `backend/app/application/models.py` : politique et résultat immuables ;
- `backend/app/infrastructure/google/quota_policy.py` : politique issue des paramètres serveur ;
- `backend/app/infrastructure/redis/google_quota.py` : script Lua atomique, idempotence, TTL UTC et rechargement
  `NOSCRIPT` ;
- `backend/app/application/use_cases/search_google_places.py` : ordre verrou, quota, Places et jetons ;
- `backend/app/presentation/api/routers/google_places.py` : traduction `429` et `Retry-After` ;
- `tests/integration/test_redis_google_state.py` : Redis réel, concurrence et deux applications FastAPI.

## Preuves automatisées exécutées

| Contrôle | Résultat |
| --- | --- |
| Ruff format et lint backend | Vert |
| mypy strict | Vert — 148 fichiers source |
| Régression backend ciblée | Vert — 53 tests |
| Suite backend locale | Vert — 210 tests ; 31 intégrations PostgreSQL/Mailpit ignorées faute de services de test configurés |
| Redis réel `127.0.0.1:6379` | Vert — 4 tests : état partagé, 20/100 sous concurrence, deux applications et `429` |
| ESLint | Vert |
| Vitest et axe | Vert — rapport JUnit sans test ignoré |
| Build Vite | Vert |

Le verrou complet Docker/WSL, incluant PostgreSQL, Mailpit, Alembic et l'interdiction de tout `skip`, reste à
exécuter lorsque l'environnement Docker/WSL est disponible. La recette fonctionnelle utilisateur reste
volontairement différée à la clôture de 2.6.3. Le verrou local isolé `Test-QualityGateLocal.ps1` reste la preuve
attendue pour cet ensemble complet.

## Revue technique

1. Les cinq clés d'une réservation partagent le hash tag de l'organisation : le script reste atomique sur Redis
   Cluster et n'expose aucune donnée personnelle ou contenu Google.
2. L'opération idempotente est générée uniquement par le serveur. Après une erreur Redis incertaine, seule sa lecture
   est tentée ; le script n'est pas rejoué à l'aveugle.
3. Le verrou précède le quota. Une double soumission concurrente retourne `409` sans dépenser de quota ; une limite
   atteinte retourne `429` sans appeler Places, Maps ou émettre un jeton.
4. Le champ HTTP `scope` est fermé à `user` ou `organization` et ne divulgue ni compteur brut, ni politique de plan,
   ni activité d'un autre membre.

## Suite

Le prochain incrément est **2.6.3 — Observabilité et verrou final**. Il consolidera les métriques, journaux JSON,
preuve Azure et le verrou qualité complet. Les plans commerciaux, les prix et la facturation restent hors périmètre.
