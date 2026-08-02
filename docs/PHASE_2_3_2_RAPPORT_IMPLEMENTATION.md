# Incrément 2.3.2 — Rapport d’implémentation

Version : 1.0  
Date : 24 juillet 2026  
Statut technique : implémenté et validé automatiquement  
Validation restante : protocole produit local

## 1. Résultat

L’incrément 2.3.2 livre le provisioning idempotent d’une organisation et de sa première invitation Admin, le renvoi et
la révocation contrôlés, l’acceptation par un nouveau compte ou un compte existant, ainsi que la page React minimale
d’acceptation. Il conserve les garanties de 2.3.1, 2.2 et de la recherche Google transitoire.

Les seize décisions de la section 25 de la spécification ont été implémentées sans dérogation fonctionnelle. Mailpit
reste volontairement limité au développement et aux tests. Aucun transport de courriel de production n’est introduit.

## 2. Architecture livrée

### 2.1 Domaine et application

- états `provisioning`, `active`, invitation active, expirée, acceptée ou révoquée ;
- validation canonique du nom, de la langue, du fuseau IANA et du courriel internationalisé ;
- empreinte SHA-256 canonique de la commande d’idempotence ;
- jeton base64url de 256 bits et conservation du seul hash ;
- cas d’utilisation de création, liste, renvoi, révocation, prévisualisation et acceptation ;
- ports dédiés au provisioning, à la livraison, aux limites, aux sessions et au contexte acteur ;
- aucune dépendance FastAPI, SQLAlchemy, Redis ou SMTP dans le domaine.

### 2.2 PostgreSQL et RLS

La migration `20260723_0004` ajoute :

- les métadonnées de création et d’activation des organisations ;
- la version, l’état de livraison et la filiation des invitations ;
- `invitation_delivery_attempts`, sans courriel ni jeton ;
- les contraintes d’état, clés uniques, index opérationnels et clés étrangères ;
- `ENABLE` et `FORCE ROW LEVEL SECURITY` sur la nouvelle table ;
- des fonctions `SECURITY DEFINER` étroites avec `search_path` fixé ;
- une révocation systématique à `PUBLIC` et des droits `EXECUTE` limités aux signatures nécessaires.

Le rôle Web reste non propriétaire, sans `BYPASSRLS` et sans permission `DELETE`. Les opérations plateforme posent
`app.actor_id` et `app.request_id` dans la transaction, sans fabriquer de contexte depuis le corps HTTP.

### 2.3 Redis, session et anti-abus

- rotation atomique de la session : l’ancien secret disparaît dans la même opération Lua qui crée le nouveau ;
- incrément de `users.version` avant la rotation d’un compte existant ;
- limite invitation atomique par HMAC d’adresse et HMAC du hash global du jeton ;
- limite de connexion migrée vers la même clé HMAC ;
- indisponibilité Redis traduite en indisponibilité contrôlée avant l’acceptation ;
- aucune adresse, aucun courriel et aucun jeton brut dans une clé Redis.

### 2.4 Livraison locale

- adaptateur SMTP Mailpit asynchrone vis-à-vis de la boucle d’événements ;
- validation PostgreSQL et commit avant l’envoi ;
- finalisation versionnée de la tentative après le résultat SMTP ;
- échec conservant l’organisation en `provisioning` avec renvoi explicite ;
- image Mailpit figée à `v1.30.5`, ports liés à `127.0.0.1` ;
- configuration Mailpit refusée en staging et production.

### 2.5 API et frontend

Routes ajoutées :

- `GET /api/platform/organizations` ;
- `POST /api/platform/organizations` ;
- `POST /api/platform/organizations/{id}/first-invitation/resend` ;
- `POST /api/platform/organizations/{id}/first-invitation/revoke` ;
- `POST /api/auth/invitations/preview` ;
- `POST /api/auth/invitations/accept`.

Les routes imposent JSON strict, origine fiable, capacité plateforme ou session correspondante, CSRF lorsque requis,
erreurs bornées et `no-store`. Les erreurs de jeton mal formé, inconnu, expiré, révoqué ou consommé sont
indiscernables publiquement.

Le frontend :

- retire le fragment avant `createRoot().render()` ;
- conserve le jeton dans une référence mémoire ;
- empêche la double prévisualisation sous React Strict Mode ;
- ne charge aucune ressource tierce sur la page ;
- gère le compte nouveau et la connexion intégrée du compte existant ;
- installe la session retournée sans navigation intermédiaire ;
- isole un compte sans organisation dans une page contrôlée sans capacité.

## 3. Preuves de validation

| Contrôle | Résultat |
| --- | --- |
| Ruff lint | vert |
| Ruff format | vert |
| mypy | vert sur 101 fichiers source |
| Alembic `check` | aucune opération manquante |
| Migration vide vers `head` | verte |
| Downgrade 0004 sans donnée puis ré-upgrade | vert |
| pytest avec PostgreSQL, Redis et Mailpit réels | 109 tests réussis, aucun ignoré |
| ESLint | vert, zéro avertissement |
| Vitest | 22 tests dans 9 fichiers |
| Vite build | vert, 49 modules transformés |
| Syntaxe du script PowerShell local | verte |
| `git diff --check` | vert |

Note d’environnement local : le `.venv` actuellement présent exécute Python 3.14 mais contient quatre extensions
binaires étiquetées CPython 3.12 (`httptools`, `PyYAML`, `watchfiles`, `websockets`). Les contrôles obligatoires sont
verts, mais `pip check` signale logiquement cette incohérence de plateforme. Avant la validation manuelle, recréer le
venv avec Python 3.12, version de référence de la CI, puis réinstaller `backend/requirements-dev.txt`.

Les scénarios d’intégration prouvent notamment :

- une seule organisation pour deux créations concurrentes partageant le même UUID ;
- une seule appartenance pour deux acceptations concurrentes ;
- l’invalidation de l’ancien hash après renvoi ;
- l’impossibilité pour un résultat SMTP tardif d’écraser une version plus récente ;
- la persistance du plafond de renvoi dans PostgreSQL ;
- l’absence de visibilité directe sans contexte RLS ;
- les ACL et propriétés des fonctions et du rôle Web ;
- un seul message réel dans Mailpit pour une création ;
- la rotation effective du secret Redis et la pseudonymisation des clés ;
- les non-régressions de l’authentification, de la recherche Google et de la carte facturable.

## 4. Critique 1 — Sécurité offensive et confidentialité

### Conclusion

Le parcours résiste correctement à l’énumération, au vol passif par référent, au rejeu simple, au brute force distribué
par jeton et à l’escalade d’un compte sans organisation. Aucun bloqueur de sécurité n’a été conservé dans le périmètre
2.3.2.

### Points examinés et corrections issues de la critique

- Les validations Pydantic d’un jeton vide, trop long ou mal typé produisaient initialement un `422` distinct. Elles
  sont maintenant ramenées au même `400 invitation_invalid` que toutes les autres invalidités.
- La dimension Redis du jeton dépendait initialement de l’adresse. Elle est désormais globale au hash du jeton, ce
  qui empêche un attaquant de contourner le plafond avec plusieurs adresses.
- L’import d’une police Google créait une requête tierce sur la page d’invitation. Il a été retiré.
- L’image Mailpit a été actualisée vers la version corrective actuelle retenue pour éviter d’intégrer une version
  locale connue comme antérieure au correctif SMTP.
- Les recherches de code ne montrent aucune journalisation du jeton, du mot de passe, du cookie, du CSRF ou du corps
  du courriel.

### Risques résiduels acceptés

- Mailpit contient nécessairement le lien brut dans une boîte locale. Il reste lié à la boucle locale et interdit hors
  développement/test.
- Un Administrateur de plateforme compromis pourrait créer plusieurs organisations avec plusieurs UUID. Avant
  d’activer un fournisseur de production, il faudra ajouter quotas opérateur, alertes et éventuellement approbation.
- Le fragment est protégé contre la fuite applicative, mais sa confidentialité dépend encore de la sécurité de la boîte
  courriel et du poste destinataire.

## 5. Critique 2 — Cohérence transactionnelle et résilience distribuée

### Conclusion

Les invariants critiques sont portés par PostgreSQL, non par un enchaînement fragile de lectures applicatives. Les
échecs entre base, SMTP et Redis ont un état de reprise explicite. Aucun double compte, double organisation ou double
appartenance n’a été observé sous concurrence.

### Points examinés et corrections issues de la critique

- Les créations de fonctions Alembic contenant plusieurs commandes dans une exécution échouaient avec `asyncpg`.
  Création, changement de propriétaire, révocation et droits sont maintenant exécutés séparément.
- Un calcul SQL de délai employait une syntaxe `EXTRACT` incorrecte ; le test PostgreSQL réel l’a détectée et la
  migration a été corrigée.
- La révocation relisait d’abord la seule invitation active et pouvait masquer une invitation déjà acceptée. L’ordre
  de décision retourne désormais explicitement `already_accepted`.
- La rotation Redis est atomique et refuse une ancienne session absente ou appartenant à un autre utilisateur.
- Un contrat JSON interne PostgreSQL invalide est maintenant traduit en `ProvisioningServiceUnavailable` au niveau de
  l’adaptateur, sans faire remonter une erreur de parsing hors du vocabulaire applicatif.
- La readiness journalise seulement la classe d’échec, jamais l’URL ou les secrets de connexion.

### Risques résiduels acceptés

- Une tentative de livraison restée `pending` après perte de réponse n’est pas réconciliée par un worker. Le replay du
  même UUID et l’inspection opérationnelle évitent le double envoi ; un job de réconciliation sera nécessaire avant
  une exploitation de production.
- SMTP reste dans la requête HTTP, borné par un timeout. Un fournisseur de production devra passer par une file et une
  boîte d’envoi transactionnelle.
- La création d’un nouveau compte suivie d’une panne Redis conserve correctement l’acceptation, mais oblige ensuite à
  se reconnecter ; ce compromis est explicitement exposé par l’API.

## 6. Critique 3 — Exploitabilité, UX et préparation produit

### Conclusion

L’incrément est testable de bout en bout sans introduire prématurément l’interface d’administration 2.3.5. Le parcours
d’invitation est accessible et cohérent avec les états métier. La validation manuelle produit reste indispensable.

### Points examinés et corrections issues de la critique

- Un script PowerShell passe par la vraie authentification, le cookie, le CSRF et la vraie API ; il ne contourne pas
  RLS et n’affiche jamais le jeton.
- Le routeur possède un test dédié garantissant qu’un compte sans organisation n’atteint pas la recherche.
- Les boutons en cours d’exécution sont désactivés, les erreurs utilisent `role=alert` et le chargement `role=status`.
- Le script est compatible avec Windows PowerShell en restant ASCII ; sa syntaxe est vérifiée sans exécuter de secret.
- Les pages légales et la recherche Google existantes ne sont pas modifiées visuellement.

### Risques résiduels acceptés

- L’absence de page plateforme rend création, renvoi et révocation moins ergonomiques jusqu’à 2.3.5.
- Le courriel local est en texte brut uniquement. Le gabarit HTML, l’identité visuelle et la traduction complète seront
  définis avec le fournisseur de production.
- La page d’état sans organisation demande de rouvrir le lien depuis le courriel, car le jeton a volontairement été
  effacé de l’URL et n’est pas persisté.

## 7. Revue de code 1 — Clean Architecture, SOLID et testabilité

Angle : architecte logiciel / maintenabilité.

### Vérifications

- dépendances orientées présentation → application → domaine ;
- ports possédés par l’application et adaptateurs remplaçables ;
- routes limitées à la sécurité HTTP, au mapping et aux codes de réponse ;
- use cases responsables de l’orchestration, domaine responsable des invariants purs ;
- contextes acteur et locataire distincts ;
- livraison Mailpit, Redis et SQL injectés dans le conteneur ;
- erreurs stables indépendantes des bibliothèques externes ;
- tests unitaires avec doublures et tests d’intégration sur adaptateurs réels.

### Avis

Le découpage respecte l’inversion de dépendances et la responsabilité unique. L’ajout d’un fournisseur de courriel de
production ne demandera pas de modifier le domaine ni les routes. Le durcissement du décodage des contrats SQL ferme
le seul écart relevé pendant cette revue. Aucun commentaire bloquant ne reste ouvert.

## 8. Revue de code 2 — PostgreSQL, sécurité multi-tenant et performance

Angle : expert PostgreSQL / sécurité des données.

### Vérifications

- contraintes et transitions protégées en base ;
- verrou advisory sur l’idempotence de création et verrou de ligne sur l’invitation ;
- clés uniques globales pour requêtes, courriel et hash de jeton ;
- RLS forcée et contexte transactionnel `set_config(..., true)` ;
- propriétaires et ACL vérifiés depuis les catalogues PostgreSQL ;
- aucun SQL dynamique dans les fonctions privilégiées ;
- index du parcours de renvoi et pagination stable par date/UUID ;
- transactions courtes, sans appel SMTP ni Redis sous verrou PostgreSQL ;
- absence de droit `DELETE` et de lecture transversale directe.

### Avis

Le modèle est robuste pour le volume d’une V1 et évite les principaux pièges RLS. Les fonctions privilégiées sont
étroites, auditées et testées par le rôle applicatif réel. Les limites connues concernent l’exploitation asynchrone de
la livraison, pas l’intégrité du modèle. Aucun bloqueur SQL ou multi-tenant ne reste ouvert.

## 9. Protocole local de validation produit

1. Copier `.env.example` vers `.env`, générer `RATE_LIMIT_HMAC_KEY` et conserver les secrets hors Git.
2. Exécuter `docker compose up -d --wait` puis `docker compose run --rm database-role-provisioner`.
3. Appliquer `alembic upgrade head` avec `MIGRATION_DATABASE_URL`.
4. Démarrer FastAPI avec `.env`, puis Vite.
5. Exécuter :

```powershell
.\scripts\Test-ProvisioningLocal.ps1 `
  -AdministratorEmail "admin@example.ca" `
  -OrganizationName "Entreprise Démonstration" `
  -InviteeEmail "nouvel-admin@example.ca"
```

6. Ouvrir `http://127.0.0.1:8025`, vérifier qu’un seul message existe et suivre son lien.
7. Créer le compte, confirmer la connexion et l’organisation active.
8. Refaire le scénario avec le même courriel pour valider le parcours du compte existant.
9. Tester un renvoi après le délai, confirmer l’invalidité de l’ancien lien, puis tester une révocation.
10. Confirmer le protocole produit avant d’autoriser 2.3.3.

## 10. Décision de sortie

L’incrément 2.3.2 est techniquement prêt pour la validation locale du responsable produit. Il ne doit être déclaré
fonctionnellement accepté ni servir de base au démarrage de 2.3.3 avant la réussite du protocole de la section 9.
