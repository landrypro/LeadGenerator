# Phase 2.3.3 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Incrément | 2.3.3 — Membres, capacités et changement d’organisation |
| Date | 2 août 2026 |
| Statut | Implémenté, contrôlé automatiquement et validé localement par le responsable produit |
| Migration | `20260802_0005` |
| Version API | `1.5.0` |
| Contrat | `PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md` version 1.0 |

## 1. Résultat

Les seize décisions validées sont implémentées sans changement visuel de l’écran principal. L’incrément livre les
API et invariants d’organisation, de membres, d’invitations et de changement d’organisation. Les écrans
d’administration et le sélecteur visuel restent volontairement réservés à 2.3.5.

Le résultat protège notamment :

- l’isolation locataire par double autorisation application/RLS ;
- la matrice exacte Administrateur, Gestionnaire et Commercial ;
- le dernier Administrateur actif sous verrou transactionnel ;
- les modifications optimistes de l’organisation et des appartenances ;
- les invitations de membre idempotentes et à usage unique ;
- l’invalidation immédiate des sessions après un changement de privilège ;
- la rotation de la seule session courante lors d’un changement d’organisation ;
- la survie d’une session récente à une purge Redis tardive ;
- l’absence de jeton, cookie, CSRF ou secret dans les réponses et scripts.

## 2. Éléments livrés

### 2.1 Domaine et application

- `domain/organization.py` contient les vues immuables et les commandes validées de l’organisation, des membres et
  des invitations.
- `domain/identity.py` expose les capacités `invitations:read` et `invitations:manage` uniquement pour le rôle Admin.
- `application/ports/organization.py` définit le port orienté cas d’utilisation et ses résultats métier explicites.
- `application/ports/sessions.py` ajoute `revoke_user_before_version`.
- `application/ports/pagination.py` abstrait l’encodage des curseurs.
- `application/use_cases/organization.py` sépare neuf cas d’utilisation : lecture/modification de l’organisation,
  liste/modification des membres, liste/création/renvoi/révocation d’invitations et changement d’organisation.
- l’acceptation existante purge, après rotation, uniquement les sessions portant une ancienne version.

### 2.2 PostgreSQL et migration 0005

La migration :

- ajoute `memberships.updated_by` non nul et `memberships.version` strictement positif ;
- rétroalimente les lignes existantes par `updated_by=created_by` et `version=1` ;
- ajoute les fonctions étroites d’administration locataire et de changement d’organisation ;
- étend l’acceptation aux invitations `member` sans changer l’état de l’organisation ;
- conserve `SECURITY DEFINER`, un `search_path` explicite, la révocation à `PUBLIC` et les droits par signature ;
- refuse un downgrade qui perdrait une modification de membre ou une invitation 2.3.3.

Les modifications susceptibles de retirer un Administrateur verrouillent toujours l’organisation avant
l’appartenance. Le test concurrent exécute deux retraits réels en parallèle et prouve qu’un seul réussit.

### 2.3 Redis et sessions

Le script Lua de purge parcourt l’index des sessions d’un utilisateur et supprime seulement les enregistrements dont
`user_version` est strictement inférieure à la version minimale. Une session créée concurremment avec la nouvelle
version est conservée.

Le changement d’organisation :

1. valide l’appartenance dans PostgreSQL et enregistre la préférence ;
2. recharge l’identité ;
3. remplace atomiquement dans Redis le cookie courant par un nouveau cookie et un nouveau CSRF ;
4. laisse toutes les autres sessions intactes.

La rotation conserve l’échéance absolue de la session d’origine : renouveler le cookie ne permet donc pas de
repousser indéfiniment la limite de 12 heures.

Une panne de rotation retourne `503`. L’ancien cookie conserve son ancien contexte et n’obtient jamais les capacités
de la nouvelle organisation.

### 2.4 API

| Route | Autorisation |
| --- | --- |
| `GET /api/organization` | `organization:read` |
| `PATCH /api/organization` | `organization:update` |
| `GET /api/organization/members` | `members:read` |
| `PATCH /api/organization/members/{membership_id}` | `members:manage` |
| `GET /api/organization/invitations` | `invitations:read` |
| `POST /api/organization/invitations` | `invitations:manage` |
| `POST /api/organization/invitations/{id}/resend` | `invitations:manage` |
| `DELETE /api/organization/invitations/{id}` | `invitations:manage` |
| `POST /api/auth/switch-organization` | session active, origine et CSRF |

Les commandes sont strictes et ne prennent jamais `organization_id`. Les ressources absentes et croisées sont
uniformisées en `404`. Toutes les réponses sensibles utilisent le contrat commun
`Cache-Control: no-store, max-age=0`, qui interdit leur conservation par un cache privé ou partagé.

Les curseurs 2.3.3 sont opaques, signés par HMAC avec séparation de domaine cryptographique et comparés en temps
constant. Une altération est rejetée avant l’appel à la passerelle.

### 2.5 Frontend et protocole local

La page d’invitation :

- parle désormais de rejoindre l’organisation ;
- affiche le rôle réellement proposé : Administrateur, Gestionnaire ou Commercial ;
- conserve le jeton uniquement en mémoire et maintient un seul appel de prévisualisation sous StrictMode ;
- adopte la session retournée après acceptation.

Le script `scripts/Test-OrganizationAdministrationLocal.ps1` permet de lister, inviter, modifier un membre et changer
d’organisation via les routes HTTP réelles. Il n’interroge jamais la base et n’affiche aucun secret.

Le bootstrap affiche maintenant une erreur métier concise pour un mot de passe hors limite au lieu d’une trace Python.

## 3. Preuves de migration et qualité

### 3.1 Base temporaire vierge

Une base PostgreSQL temporaire dédiée a été créée, migrée de zéro vers `20260802_0005`, soumise à `alembic check`,
puis supprimée. Résultats :

- migrations 0001, 0002, 0003, 0004 et 0005 appliquées ;
- `alembic check` : aucune opération nouvelle détectée ;
- 21 tests d’intégration réels passés, aucun ignoré ;
- PostgreSQL, Redis et Mailpit réellement utilisés.

La migration 0004→0005 sur la base de développement peuplée a également été exécutée. Un cycle de downgrade contrôlé
0005→0004→0005 a réussi avant la création de données propres à 2.3.3, sans perte des données antérieures.

### 3.2 Résultats automatisés

| Contrôle | Résultat |
| --- | --- |
| Tests backend hors infrastructure | 111 réussis |
| Tests d’intégration, dont PostgreSQL/Redis/Mailpit réels | 21 réussis |
| Total backend unique | 132 réussis, 0 ignoré |
| Ruff | vert |
| Ruff format | vert, 141 fichiers conformes |
| mypy | vert, 109 fichiers source |
| ESLint | vert |
| Vitest | 22 réussis dans 9 fichiers |
| Vite build | vert |
| Alembic upgrade/check | vert |
| Script PowerShell | syntaxe validée |

Les tests Google historiques restent inclus : un seul Text Search, aucun `nextPageToken`, vingt résultats maximum,
aucun contact, aucune route d’export historique et aucun stockage navigateur.

## 4. Critique experte 1 — sécurité et isolation

### Constats

- Les fonctions privilégiées ne font confiance ni aux capacités du navigateur ni à un `organization_id` client.
- Les lectures de membres partent de `memberships`, filtrée par RLS, avant de joindre `users`.
- Les identifiants croisés sont minimisés en `404`.
- Une première version des curseurs était seulement encodée en Base64 et ne respectait donc pas pleinement le contrat
  de curseur signé.

### Corrections et verdict

Le défaut de curseur a été corrigé par un codec HMAC injecté. Les ACL, propriétaires, `search_path`, absence de
`BYPASSRLS`, absence de `DELETE` et politiques `FORCE RLS` sont vérifiés sur PostgreSQL réel. Aucun problème bloquant
ne subsiste pour le périmètre 2.3.3.

Risque résiduel : les traces structurées restent techniques. Les mutations administratives ne doivent pas être
ouvertes en production avant l’audit append-only de 2.4, conformément à la spécification.

## 5. Critique experte 2 — concurrence et cohérence distribuée

### Constats

- PostgreSQL et Redis ne partagent pas de transaction globale.
- Une purge Redis globale tardive pourrait supprimer une nouvelle session valide.
- Une rotation qui recréerait une fenêtre absolue complète permettrait de prolonger une session par changements
  d’organisation successifs.
- Deux rétrogradations concurrentes pourraient théoriquement retirer tous les Admins sans ordre de verrou commun.
- La livraison SMTP dans une transaction prolongerait inutilement les verrous.
- Un premier calcul des limites de renvoi agrégeait toute l’organisation et pouvait faire bloquer l’invitation B par
  les renvois de l’invitation A ; il omettait aussi le délai après l’envoi initial.

### Corrections et verdict

PostgreSQL reste l’autorité au moyen de `users.version`. La purge Redis est strictement antérieure à cette version ;
le test réel prouve qu’une session récente survit. La rotation Redis conserve atomiquement l’échéance absolue
d’origine. L’organisation est verrouillée avant l’appartenance dans toutes les mutations sensibles. SMTP intervient
après commit. Le calcul de renvoi suit désormais par CTE récursive la chaîne de
versions de l’invitation concernée, inclut l’envoi initial pour le délai minimal et isole le quota des autres
invitations. La préférence PostgreSQL éventuellement enregistrée avant une panne Redis n’accorde aucun privilège à
l’ancien cookie.

Le compromis distribué est cohérent et échoue de manière fermée. Une boîte transactionnelle pourrait améliorer la
reprise automatique de livraison dans une phase ultérieure, mais n’est pas requise pour la sécurité actuelle.

## 6. Critique experte 3 — produit et exploitation

### Constats

- Une API complète sans écran d’administration est moins intuitive pour la validation produit.
- Le compte multi-organisation ne possède pas encore de sélecteur visuel.
- Mailpit n’est pas un fournisseur de production.
- Un retour CLI par trace Python rendait le bootstrap inutilement difficile à diagnostiquer.

### Corrections et verdict

Le périmètre reste volontairement borné : API et invariants en 2.3.3, UI en 2.3.5. Le script PowerShell rend toutes
les opérations vérifiables sans accès SQL. Le message CLI a été corrigé. Cette séparation réduit le risque de masquer
un défaut d’autorisation derrière une interface encore mouvante.

Les limites restantes sont explicites : pas d’envoi de production, pas d’écran de gestion et pas d’audit métier avant
les incréments prévus. Elles n’empêchent pas la validation locale de 2.3.3.

## 7. Revue de code 1 — angle architecture Clean/SOLID

### Évaluation

- Les règles métier sont indépendantes de FastAPI, SQLAlchemy, Redis et SMTP.
- Les routes convertissent HTTP vers des commandes et ne manipulent aucun client d’infrastructure.
- Le port d’organisation est orienté résultats métier, sans exception SQL exposée.
- La composition reste centralisée dans `build_container()`/`create_app()`.
- Le codec de pagination et le stockage de sessions sont injectés derrière des protocoles.
- Aucun contexte utilisateur mutable n’est global ou partagé entre requêtes.

### Conclusion

Les dépendances restent dirigées vers l’application et le domaine. Le port d’organisation est assez large mais garde
une cohésion fonctionnelle acceptable pour l’incrément ; un découpage en ports spécialisés ne deviendra utile que si
les modules 2.3.5 ou 2.4 évoluent indépendamment. Aucun refactoring supplémentaire n’est justifié maintenant.

## 8. Revue de code 2 — angle fiabilité, données et exploitation

### Évaluation

- Les commandes sans effet n’incrémentent aucune version et ne révoquent aucune session.
- Les conflits optimistes retournent la version courante sans donnée d’une autre organisation.
- Le renvoi conserve l’idempotence, invalide l’ancien lien et limite les courriels.
- La révocation est répétable sans nouvel envoi.
- Le downgrade refuse explicitement toute perte non représentable.
- La migration est compatible asyncpg et les fonctions sont accordées par signature exacte.
- Les scripts et journaux n’exposent pas les secrets.

### Conclusion

Le comportement nominal, les erreurs, les replays et les courses principales sont couverts. La base temporaire vierge
et la base peuplée réduisent fortement le risque de déploiement. La seule étape restante est la validation manuelle du
parcours par le responsable produit ; elle ne nécessite aucune correction connue.

## 9. Protocole local de validation produit

1. Exécuter `alembic upgrade head`, puis confirmer `20260802_0005 (head)` avec `alembic current`.
2. Vérifier `/api/health/ready` : PostgreSQL et Redis doivent être `ok`.
3. Démarrer Mailpit, le backend et le frontend.
4. Se connecter comme Administrateur d’organisation.
5. Exécuter `Test-OrganizationAdministrationLocal.ps1` sans option et vérifier l’organisation et les membres.
6. Inviter successivement un Gestionnaire et un Commercial, puis accepter les liens dans Mailpit.
7. Vérifier que le Gestionnaire lit les membres sans les modifier et que le Commercial ne voit pas l’annuaire.
8. Modifier un rôle et confirmer que l’ancienne session de ce membre est refusée.
9. Tenter de retirer le dernier Admin et vérifier `last_active_administrator`.
10. Ajouter un second Admin, puis tester l’auto-rétrogradation et la reconnexion obligatoire.
11. Utiliser `-SwitchMembershipId` pour changer d’organisation et confirmer `CsrfRotated=True`.
12. Tester renvoi, ancien lien et révocation, puis lancer la matrice qualité du README.

Le responsable produit a confirmé le parcours local le 2 août 2026. L’incrément 2.3.3 est accepté et la définition de
2.3.4 est autorisée.
