# Rapport d’implémentation — 2.6.1 État Google partagé

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.6 — Redis partagé, quotas et durcissement |
| Incrément | 2.6.1 — État Google partagé |
| Date | 25 août 2026 |
| Statut | Implémenté ; recette fonctionnelle regroupée à la clôture de 2.6 |
| Migration Alembic | Aucune ; tête inchangée `20260815_0013` |

## Résultat livré

Les protections Google auparavant limitées à un processus sont maintenant partagées par Redis :

- `RedisGenerationGuard` protège une recherche par couple utilisateur/organisation avec `SET NX PX` et libération
  compare-and-delete ;
- `RedisMapSnapshotGrantStore` émet une concession de carte opaque indexée par SHA-256, la réclame atomiquement et la
  rend terminale après la première tentative Maps ;
- `RedisGoogleSelectionGrantStore` porte jusqu’à vingt `place_id`, reste non destructif et vérifie le propriétaire dans
  Redis avant de retourner la sélection ;
- les adaptateurs mémoire ne sont plus choisis par `build_container()` ; ils restent uniquement des doublures de tests
  injectées explicitement ;
- sans Redis en développement, les adaptateurs fermés retournent `503 google_protection_unavailable` avant tout appel
  Google ; staging et production refusent une configuration sans `REDIS_URL`.

Les scripts Redis sont chargés et appelés par SHA. Un unique rechargement est autorisé après `NOSCRIPT`; aucune
opération dont le résultat réseau est incertain n’est rejouée automatiquement.

## Fichiers principaux

- `backend/app/infrastructure/redis/google_state.py` : verrou, jetons, scripts et validation stricte des charges ;
- `backend/app/infrastructure/redis/unavailable_google_state.py` : comportement fermé sans Redis ;
- `backend/app/bootstrap.py` : câblage Redis par profil ;
- `backend/app/config.py` : TTL du verrou et contraintes staging/production ;
- `tests/integration/test_redis_google_state.py` : deux pools Redis et deux applications FastAPI.

## Preuves automatisées exécutées

| Contrôle | Résultat |
| --- | --- |
| Ruff format et lint backend | Vert |
| mypy strict | Vert — 145 fichiers source |
| Régression backend ciblée | Vert — 36 tests |
| Redis réel local `127.0.0.1:6379` | Vert — 2 tests : deux pools et deux applications FastAPI |
| ESLint | Vert |
| Build Vite | Vert |

Le contrôle de recette complet avec PostgreSQL, Redis, Mailpit et zéro test ignoré reste à exécuter via
`scripts/Test-QualityGateLocal.ps1` lorsque le moteur Docker/WSL est de nouveau disponible. La recette fonctionnelle
reste volontairement différée à la clôture de 2.6, conformément à la décision produit.

## Revue technique

1. Le verrou ne peut pas être supprimé par une instance qui ne possède plus la valeur aléatoire attendue.
2. Une carte ne peut provoquer qu’un appel facturable : l’état `claimed` n’est jamais rouvert, même si Redis échoue
   pendant la finalisation.
3. Un jeton et un `place_id` ne sont jamais exposés dans une clé Redis ; seul le hash SHA-256 du jeton est utilisé.
4. Une panne Redis bloque le parcours avant Google, sans repli mémoire ni nouvelle tentative fournisseur.

## Suite

La prochaine étape technique est **2.6.2 — Quotas et droits préparatoires**. Elle ne doit commencer qu’après la
revue de cette implémentation et la décision de poursuivre ; la recette utilisateur complète reste une activité de
clôture 2.6.
