# Audit technique — LeadGenerator (Prospect CRM)

**Dépôt audité :** `landrypro/LeadGenerator`
**Stack :** FastAPI (Python 3.12) + PostgreSQL (RLS) + Redis · React/Vite (client) · Docker · Azure Pipelines
**Date :** 14 août 2026

---

## Résumé exécutif

C'est un des codebases les plus rigoureux que j'aie audités pour ce niveau de maturité de produit : architecture hexagonale/Clean réellement respectée (et **testée automatiquement**), authentification par argon2id + sessions Redis + CSRF + rate limiting, multi-tenancy imposée au niveau PostgreSQL via **Row Level Security**, `mypy --strict`, pipeline CI qui refuse les tests skippés et vérifie la cohérence des migrations Alembic dans les deux sens (upgrade/downgrade).

Les points faibles identifiés sont **ciblés et peu nombreux** — une vulnérabilité de dépendance réelle et exploitable, une lacune de supply-chain security en CI, et de l'hygiène de dépôt (fichiers parasites). Rien de structurel.

| Domaine | Note | Commentaire |
|---|---|---|
| Architecture | ★★★★★ | Clean Architecture réelle, frontières testées par AST |
| Sécurité applicative | ★★★★☆ | Excellent sur l'essentiel, une CVE de dépendance à corriger |
| Qualité de code | ★★★★★ | Typage strict, lint strict, tests d'intégration |
| Infra / CI-CD | ★★★★☆ | Très bon, manque un scan de dépendances Python |
| Hygiène du dépôt | ★★☆☆☆ | Fichiers parasites à nettoyer |

---

## 1. Architecture

Structure en 4 couches strictement séparées, conforme à la Clean/Hexagonal Architecture :

```
backend/app/
├── domain/          # entités métier pures, zéro dépendance externe
├── application/     # use cases, ports (interfaces)
├── infrastructure/  # Postgres, Redis, Google APIs, sécurité — implémente les ports
└── presentation/    # routers FastAPI, schémas Pydantic, mapping HTTP
```

**Ce qui sort du lot :** `tests/test_architecture_boundaries.py` parse l'AST du code et vérifie automatiquement, à chaque run CI, que `domain/` n'importe ni `fastapi`, ni `application`, ni `infrastructure`, et que `application/` n'importe pas les adaptateurs. C'est une garde-fou anti-dérive architecturale que très peu d'équipes mettent en place — la plupart des projets qui *disent* faire du Clean Architecture ne le vérifient jamais mécaniquement.

Le pattern d'injection de dépendances (`AppContainer` + `build_container()`) est explicite et centralisé dans `bootstrap.py`, sans framework DI magique — lisible et debuggable.

La multi-tenancy est gérée à deux niveaux : `TenantContext` côté application, et **Row Level Security PostgreSQL** (`set_config('app.audit_scope', ...)`) côté base — donc même un bug applicatif qui oublierait un filtre `WHERE organization_id = ...` ne peut pas faire fuiter les données d'un tenant vers un autre. C'est l'approche recommandée pour du SaaS multi-tenant et elle est rarement implémentée correctement.

---

## 2. Sécurité

### 2.1 Ce qui est bien fait

- **Mots de passe** : Argon2id (`time_cost=3, memory_cost=64MB, parallelism=4`), paramètres conformes aux recommandations OWASP 2024+. Un hash factice (`verify_dummy`) est utilisé pour égaliser le temps de réponse entre "utilisateur inexistant" et "mauvais mot de passe" — protection anti-timing-attack / anti-énumération d'utilisateurs que peu de projets implémentent.
- **Sessions** : cookies `httpOnly`, `Secure` forcé en production, préfixe `__Host-` imposé en production (empêche l'écrasement de cookie depuis un sous-domaine hostile), durées idle/absolute distinctes.
- **CSRF** : double protection — vérification d'origine (`Origin`/`Referer`) + token CSRF comparé avec `hmac.compare_digest` (résistant au timing attack) + exigence de `Content-Type: application/json` (bloque les soumissions de formulaire HTML classiques).
- **Rate limiting** : login limité par paire email/IP *et* par adresse IP seule, avec backend Redis + clé HMAC — protège contre le brute-force et le credential stuffing.
- **Validation de config** : `Settings.__post_init__` refuse de démarrer en production si Redis/Postgres/clé HMAC/cookie sécurisé manquent — empêche un déploiement production mal configuré de façon silencieuse. C'est du "secure by default" bien pensé.
- **Pas de secrets en dur** : recherche exhaustive négative, uniquement des `.env.example`.
- **Pas d'injection SQL** : usage systématique de SQLAlchemy paramétré ; les seules requêtes `text()` brutes sont des constantes sans entrée utilisateur.
- **Frontend** : aucun `dangerouslySetInnerHTML`, aucun `eval`, aucun stockage de token en `localStorage`/`sessionStorage` (cohérent avec l'usage de cookies httpOnly — bon réflexe anti-XSS-token-theft).
- **Gestion d'erreurs** : les erreurs de validation Pydantic sur les routes sensibles (`/api/auth/`, `/api/google/`, etc.) sont volontairement assainies pour ne pas fuiter de détails internes.

### 2.2 Vulnérabilité identifiée — dépendance `starlette` (CVE-2026-48710 / "BadHost")

`pip-audit` sur `backend/requirements.txt` remonte 8 avisos, tous liés à `starlette`. Le pin `fastapi==0.116.1` contraint `starlette<0.48.0,>=0.40.0`, ce qui résout vers **starlette 0.47.3** — vulnérable à plusieurs failles, dont une critique :

> **PYSEC-2026-161 / CVE-2026-48710 ("BadHost")** — Starlette ne valide pas l'en-tête `Host` avant de reconstruire `request.url`. Un attaquant peut manipuler cet en-tête pour faire diverger `request.url.path` du chemin réellement routé, ce qui peut **contourner des contrôles de sécurité basés sur l'URL reconstruite** (CVSS 6.5, CWE-444 — HTTP Request Smuggling). Corrigé en starlette 1.0.1.

**Pourquoi c'est plus préoccupant que la moyenne ici précisément** : le `Dockerfile` lance uvicorn avec `--forwarded-allow-ips "*"`, ce qui fait confiance aux en-têtes `X-Forwarded-*` (dont potentiellement `X-Forwarded-Host`) venant de **n'importe quelle IP**, pas seulement du reverse proxy. Ces deux éléments combinés élargissent la surface d'exploitation de BadHost si un composant de l'application (logique de sécurité, génération de liens d'invitation via `PUBLIC_APP_URL`, etc.) se base un jour sur `request.url` plutôt que sur `scope["path"]`/la config explicite.

**Recommandation :**
1. Retirer la contrainte haute sur `starlette` (ou bumper `fastapi` vers une version qui autorise `starlette>=1.0.1`) et re-verrouiller `requirements.txt` avec un pin explicite sur `starlette`.
2. Restreindre `--forwarded-allow-ips` aux IP réelles du reverse proxy/load balancer plutôt que `*`.
3. Ajouter `pip-audit` (ou `safety`) comme étape CI — voir §3.

### 2.3 Points mineurs à vérifier

- `allow_headers=["*"]` dans `CORSMiddleware` est large ; sans risque majeur vu que `allow_origins` est une liste explicite et validée en production, mais autant le restreindre à la liste réelle des headers utilisés (`Content-Type`, `X-CSRF-Token`) par défense en profondeur.
- Le Dockerfile ne définit pas de `HEALTHCHECK` — mineur, dépend de l'orchestrateur cible.

---

## 3. CI/CD (Azure Pipelines)

Pipeline très complet : lint (`ruff check` + `ruff format --check`), typage strict (`mypy`), migrations Alembic testées **dans les deux sens** (upgrade puis downgrade puis re-upgrade) avec vérification de synchronisation modèle/migration (`alembic check`), interdiction des tests skippés côté Python **et** côté frontend via un script `quality_gate.py` maison, `npm audit --audit-level=high` côté client.

**Lacune identifiée** : aucune étape n'exécute `pip-audit` (ou équivalent) sur les dépendances Python — c'est exactement ce qui aurait détecté la vulnérabilité `starlette` avant un déploiement. Le réflexe existe déjà côté npm ; il manque son pendant Python.

---

## 4. Qualité du code

- `mypy.ini` en `strict = True` sur tout `backend/app` — rare à ce niveau de rigueur.
- `ruff.toml` avec un set de règles pertinent (bugbear, async, simplify, upgrade).
- Tests : 37 fichiers de tests, incluant des tests d'intégration HTTP avec adaptateurs fake, tests de domaine, tests de contrat de gateway (`test_provisioning_gateway_contract.py`) — signe d'une équipe qui teste les *contrats* d'interface, pas seulement les implémentations.
- Gestion d'erreurs métier via des exceptions typées dédiées (`InvalidCredentials`, `LoginRateLimited`, `OrganizationSwitchForbidden`, etc.) mappées explicitement vers des codes HTTP — pas de fourre-tout `except Exception`.
- Autorisation basée sur des capacités (`capabilities_for(role)`) plutôt que des checks de rôle épars dans les routers — plus facile à auditer et à faire évoluer.

Aucun point de qualité de code majeur à signaler ; c'est du niveau senior/staff.

---

## 5. Hygiène du dépôt

Quelques fichiers parasites committés à la racine, à nettoyer et ajouter au `.gitignore` :

| Fichier | Problème |
|---|---|
| `Linux Windows PowerShell.docx` et `~$nux Windows PowerShell.docx` | Document Word personnel + son **fichier de verrou temporaire Office** (`~$...`) — ne devrait jamais être versionné |
| `test1.bat`, `test2.bat`, `test3.bat` | Scripts de dev locaux (en réalité du PowerShell dans un `.bat`) au nommage non descriptif, à la racine plutôt que dans `scripts/` |
| `"actional audit consultation\357\200\242"` et `"\357\200\272MIGRATION_DATABASE_URL"` | Noms de fichiers contenant des caractères Unicode de zone privée (probablement collés depuis un éditeur riche) — fichiers illisibles/inutilisables tels quels, à supprimer |

Le `.gitignore` actuel est correct pour le code (`__pycache__`, `.venv`, `node_modules`, `.env`...) mais ne couvre pas ce type de fichiers bureautiques/temporaires. Ajouter `*.docx`, `~$*`, `*.bat` (ou déplacer les scripts PowerShell utiles vers `scripts/` avec l'extension `.ps1`) réglerait le problème à la racine.

---

## Recommandations priorisées

1. **[Sécurité — Élevé]** Corriger le pin `starlette` (CVE-2026-48710) et restreindre `--forwarded-allow-ips` aux IP du reverse proxy réel.
2. **[CI/CD — Moyen]** Ajouter `pip-audit` au pipeline Azure, au même titre que `npm audit`.
3. **[Hygiène — Faible]** Supprimer les fichiers parasites de la racine (`.docx`, `.bat`, noms Unicode corrompus) et compléter `.gitignore`.
4. **[Défense en profondeur — Faible]** Restreindre `allow_headers` du CORS à la liste réelle utilisée plutôt que `"*"`.

Aucune recommandation structurelle : l'architecture, le modèle de sécurité applicatif et la discipline de tests sont solides et n'ont pas besoin d'être repensés.
