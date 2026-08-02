# Phase 2.3 — Spécifications détaillées des organisations, rôles et de l’isolation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Incrément | 2.3 — Organisations, rôles et isolation |
| Version | 1.4 |
| Date | 23 juillet 2026 |
| Statut | Spécification générale validée ; 2.3.1 accepté ; détail 2.3.2 validé |
| Validation produit | 23 juillet 2026 |
| Prérequis | Incréments 2.1 et 2.2 validés localement |
| Marché initial | Canada |

## 1. Objectif

L’incrément 2.3 transforme l’authentification livrée en 2.2 en autorisation multi-organisation exploitable. Il doit permettre de créer une organisation, inviter son premier Administrateur, administrer les appartenances, changer d’organisation active et rendre les appels Google facturables inaccessibles sans session et sans organisation autorisée.

La sécurité ne repose jamais uniquement sur l’interface. L’organisation active vient de la session, les capacités sont calculées côté serveur et PostgreSQL applique une seconde barrière avec Row-Level Security.

## 2. Résultat attendu

À la sortie de 2.3 :

- un Administrateur de plateforme peut créer une organisation et déclencher l’invitation de son premier Administrateur ;
- une organisation n’est active qu’après l’acceptation de cette première invitation ;
- un utilisateur peut appartenir à plusieurs organisations, avec une seule organisation active par session ;
- les rôles Administrateur, Gestionnaire et Commercial produisent des capacités serveur déterministes ;
- les Administrateurs gèrent les invitations, rôles et désactivations sans pouvoir supprimer le dernier Administrateur actif ;
- le rôle PostgreSQL applicatif n’est ni propriétaire, ni superutilisateur, ni `BYPASSRLS` ;
- les tables locataires de l’incrément sont protégées par RLS et un contexte transactionnel ;
- la recherche Google et la carte facturable exigent une session, une organisation active et une capacité explicite ;
- la fenêtre d’identité temporaire de la phase 1 est supprimée ;
- aucune donnée descriptive Google n’est persistée et tous les contrôles de conformité existants restent verts.

## 3. Périmètre

### 3.1 Inclus

- cycle de vie `provisioning` puis `active` d’une organisation ;
- création et consultation des métadonnées d’organisation par l’Administrateur de plateforme ;
- consultation et modification contrôlée de l’organisation active ;
- invitation initiale et invitations ultérieures à usage unique ;
- acceptation pour un nouveau compte ou un compte existant ;
- renvoi et révocation d’une invitation ;
- liste, rôle et état des appartenances ;
- protection concurrente du dernier Administrateur ;
- changement d’organisation avec rotation de session ;
- révocation des sessions après changement de privilèges ;
- contexte locataire dans l’unité de travail et politiques RLS ;
- rôle PostgreSQL d’exécution séparé du rôle de migration ;
- protection de la recherche Google et de la carte ;
- écrans Organisation, Utilisateurs, Organisations plateforme et Acceptation d’invitation ;
- sélecteur d’organisation et contrôle visuel par capacités ;
- adaptation de la CI, des tests et de la documentation.

### 3.2 Explicitement différé

- journal d’audit append-only et consultation de l’audit, livrés en 2.4 ;
- suspension et réactivation d’une organisation depuis l’API, qui exigent d’abord l’audit immuable de 2.4 ;
- prospects, pipeline, activités et données métier locataires ;
- quotas Google journaliers et verrous Redis partagés, livrés en 2.6 ;
- ajout de références Google au CRM ;
- modification du profil personnel et réinitialisation autonome du mot de passe ;
- suppression physique d’un utilisateur, d’une appartenance ou d’une organisation ;
- choix du fournisseur d’envoi d’invitations de production.

## 4. Acteurs et frontières

### 4.1 Administrateur de plateforme

Le rôle `platform_admin` appartient à l’utilisateur global. Il peut consulter les métadonnées de provisioning et créer une organisation. Il ne reçoit aucune appartenance implicite et ne peut lire aucune donnée locataire du seul fait de son rôle plateforme.

Il peut devenir Administrateur d’une organisation uniquement en se désignant comme premier invité puis en acceptant explicitement l’invitation.

### 4.2 Administrateur d’organisation

Il gère les paramètres de son organisation, consulte ses membres, invite de nouveaux utilisateurs, renvoie ou révoque une invitation et modifie les rôles ou états des appartenances.

### 4.3 Gestionnaire

Il consulte l’organisation et la liste des membres, mais ne peut ni inviter, ni changer un rôle, ni désactiver une appartenance.

### 4.4 Commercial

Il consulte les informations générales de son organisation et utilise la recherche Google. Il ne peut pas consulter l’annuaire des membres.

### 4.5 Invité

Un invité ne dispose d’aucun accès locataire avant acceptation. Le jeton prouve l’accès au canal d’invitation, mais ne permet pas de prendre le contrôle d’un compte actif existant sans authentification de ce compte.

## 5. Matrice des capacités de 2.3

| Capacité | Plateforme | Administrateur | Gestionnaire | Commercial |
| --- | :---: | :---: | :---: | :---: |
| Lister les métadonnées des organisations | Oui | Non | Non | Non |
| Créer une organisation | Oui | Non | Non | Non |
| Consulter l’organisation active | Si membre | Oui | Oui | Oui |
| Modifier nom, langue et fuseau | Si membre Admin | Oui | Non | Non |
| Consulter les membres | Si membre autorisé | Oui | Oui | Non |
| Inviter, renvoyer ou révoquer | Si membre Admin | Oui | Non | Non |
| Modifier rôle ou état d’un membre | Si membre Admin | Oui | Non | Non |
| Changer d’organisation active | Si membre | Oui | Oui | Oui |
| Rechercher avec Google | Si membre | Oui | Oui | Oui |
| Générer la carte protégée | Si membre | Oui | Oui | Oui |

Capacités serveur proposées :

- `platform:organizations:read` et `platform:organizations:create` ;
- `organization:read` et `organization:update` ;
- `members:read` et `members:manage` ;
- `invitations:read` et `invitations:manage` ;
- `google:search` et `google:map` ;
- `audit:read`, déjà réservé, reste sans route jusqu’à 2.4.

Le client utilise ces chaînes uniquement pour l’affichage. Le serveur recalcule systématiquement les capacités depuis l’utilisateur et l’appartenance relus dans PostgreSQL.

## 6. Invariants métier

1. Une organisation `active` possède toujours au moins un Administrateur actif.
2. Une organisation nouvellement créée reste `provisioning` tant que son premier Administrateur n’a pas accepté l’invitation.
3. Le rôle plateforme ne confère jamais automatiquement une appartenance locataire.
4. Une opération locataire n’accepte pas d’`organization_id` provenant du corps ou de la chaîne de requête.
5. Le changement d’organisation accepte un `membership_id` appartenant à l’utilisateur courant, jamais un identifiant d’organisation libre.
6. Une appartenance est désactivée, jamais supprimée physiquement par l’API.
7. Le rôle plateforme d’un utilisateur ne peut être modifié par une route locataire.
8. Retirer le rôle ou désactiver le dernier Administrateur actif retourne `409`.
9. La vérification du dernier Administrateur verrouille l’organisation dans la transaction afin d’empêcher deux retraits concurrents.
10. Une invitation est aléatoire, limitée dans le temps, à usage unique et stockée uniquement sous forme de hash.
11. Une invitation ne peut pas réactiver silencieusement une appartenance désactivée ; un Administrateur doit la réactiver explicitement.
12. Le changement d’organisation et toute élévation de privilège font tourner l’identifiant de session et le jeton CSRF.
13. Un changement de rôle ou d’état révoque les sessions du membre concerné.
14. Une organisation absente du contexte ou une ligne d’une autre organisation reste invisible en base et se traduit par `404` à l’API.
15. La recherche et la carte Google sont refusées avant tout appel facturable si la session, l’organisation ou la capacité manque.

## 7. Cycle de vie de l’organisation

### 7.1 Création

`POST /api/platform/organizations` reçoit un nom, une langue, un fuseau IANA, le courriel du premier Administrateur et une clé d’idempotence UUID. La plateforme :

1. vérifie le rôle plateforme ;
2. crée l’organisation avec l’état `provisioning` ;
3. crée l’invitation initiale de rôle `admin` dans la même transaction ;
4. valide la transaction ;
5. transmet le jeton brut au port d’envoi ;
6. retourne les métadonnées et l’état de livraison, jamais le jeton.

Une même clé d’idempotence renvoie la même organisation au lieu d’en créer une seconde.

Si la base est validée mais que l’envoi échoue, la création retourne tout de même la ressource avec `delivery_status=failed`. Le client ne doit pas répéter la création ; il utilise l’action de renvoi. Si aucun adaptateur n’est configuré, la commande est refusée avant toute écriture.

### 7.2 Activation

L’acceptation valide de l’invitation initiale crée l’appartenance Administrateur et passe l’organisation de `provisioning` à `active` dans la même transaction. Une organisation de provisioning ne permet ni recherche Google ni opération locataire ordinaire.

### 7.3 Suspension

Le schéma conserve l’état `suspended` et les sessions le refusent immédiatement. L’API de suspension est différée à 2.4 pour garantir que le motif et l’acteur sont enregistrés dans l’audit append-only. Aucune suppression physique n’est prévue en V1.

## 8. Invitations

### 8.1 Jeton et lien

- 256 bits aléatoires au minimum ;
- hash SHA-256 unique dans PostgreSQL ;
- expiration initiale de 72 heures, configurable ;
- une seule invitation non acceptée et non révoquée par organisation et courriel ;
- aucune valeur brute dans la base, Redis, les réponses API ou les journaux ;
- lien construit uniquement depuis `PUBLIC_APP_URL`, jamais depuis l’en-tête `Host` ;
- format recommandé : `/accept-invitation#token=...` afin que le fragment ne soit pas envoyé au serveur par la navigation ;
- la page applique `Referrer-Policy: no-referrer`, retire immédiatement le fragment de l’historique et conserve le jeton en mémoire seulement.

### 8.2 Prévisualisation

`POST /api/auth/invitations/preview` reçoit le jeton en JSON et retourne uniquement le nom de l’organisation, le rôle proposé, la date d’expiration et `existing_account`. La réponse est `no-store`, limitée par adresse et hash de jeton, et ne retourne pas le courriel.

### 8.3 Nouveau compte

Si aucun utilisateur actif ne correspond au courriel :

- l’acceptation exige `display_name` et un mot de passe de 12 à 128 caractères ;
- le compte et l’appartenance sont créés dans la transaction d’acceptation ;
- le jeton est marqué accepté ;
- l’organisation est activée s’il s’agit de son premier Administrateur ;
- une nouvelle session est émise avec cette organisation active.

Si Redis devient indisponible après la validation PostgreSQL, l’API retourne `503` sans annuler le compte déjà activé. L’utilisateur pourra se connecter normalement lorsque Redis sera revenu ; une seconde utilisation du jeton reste refusée.

### 8.4 Compte existant

Si le courriel correspond à un compte actif :

- l’utilisateur doit d’abord être authentifié avec ce compte ;
- le courriel normalisé de la session doit correspondre à l’invitation ;
- aucun mot de passe fourni dans la commande d’acceptation n’est utilisé pour modifier le compte ;
- l’appartenance est créée puis la session est renouvelée avec la nouvelle organisation active.

Cette règle empêche un lien volé de rattacher une organisation au compte actif d’une autre personne.

### 8.5 Expiration, renvoi et révocation

- jeton inconnu, expiré, révoqué ou déjà accepté : erreur générique `invitation_invalid` ;
- avant une nouvelle invitation, toute invitation expirée du même couple est révoquée dans la transaction ;
- un renvoi remplace le hash, renouvelle l’expiration et invalide immédiatement l’ancien lien ;
- une invitation déjà acceptée ne peut être révoquée ;
- une révocation répétée est idempotente ;
- si l’envoi échoue après la validation en base, l’invitation reste visible avec `delivery_status=failed` et peut être renvoyée.

### 8.6 Livraison

Un port `InvitationDelivery` reçoit le destinataire, les métadonnées minimales et le lien. Les tests utilisent un adaptateur de capture. Le développement local utilise un serveur SMTP Mailpit accessible uniquement localement. La production refuse d’activer les invitations sans adaptateur de livraison approuvé.

Le fournisseur de production, la rétention de ses journaux et son implantation géographique restent des décisions de déploiement.

## 9. Administration des membres

### 9.1 Consultation

La liste est paginée par curseur, 25 éléments par défaut et 100 maximum. Elle retourne l’identifiant d’appartenance, le nom affiché, le courriel, le rôle, l’état, la version et les dates utiles. Elle n’expose ni hash de mot de passe, ni rôle plateforme, ni appartenances à d’autres organisations.

### 9.2 Modification

`PATCH /api/organization/members/{membership_id}` accepte seulement `role`, `status` et `version`. Au moins un champ modifiable doit être présent. La version protège contre l’écrasement concurrent.

Pour toute action pouvant retirer un Administrateur actif :

1. verrouiller la ligne de l’organisation avec `SELECT ... FOR UPDATE` ;
2. relire le nombre d’Administrateurs actifs ;
3. refuser par `409 last_active_administrator` si le résultat deviendrait nul ;
4. appliquer la modification et incrémenter la version ;
5. incrémenter `users.version` pour la personne concernée dans la même transaction ;
6. valider ;
7. demander le nettoyage de ses sessions Redis.

La comparaison de `users.version` déjà appliquée par 2.2 rend toutes les anciennes sessions inutilisables dès leur prochaine requête, même si le nettoyage Redis échoue après la validation PostgreSQL. Le nettoyage est donc une réduction de données périmées, pas une condition de sécurité ni une transaction distribuée. Une panne Redis est journalisée sans secret et sera retentée ou absorbée par l’expiration normale ; la modification de privilège peut rester réussie.

### 9.3 Changement d’organisation active

`POST /api/auth/switch-organization` reçoit un `membership_id`. Le serveur vérifie que l’appartenance est active, que l’organisation est active et qu’elle appartient à l’utilisateur. Il met à jour `last_active_organization_id`, crée atomiquement une nouvelle session Redis, révoque l’ancienne, pose un nouveau cookie et renvoie un nouveau jeton CSRF.

L’ancienne session ne bénéficie d’aucune période de grâce.

L’ordre est PostgreSQL puis rotation atomique dans Redis. Une panne Redis peut donc mettre à jour la préférence sans changer la session courante, ce qui n’accorde aucun accès supplémentaire ; l’API retourne alors `503` et l’ancienne session reste limitée à son organisation précédente.

## 10. Évolution du modèle PostgreSQL

### 10.1 `organizations`

Évolutions proposées :

- autoriser `status IN ('provisioning', 'active', 'suspended')` ;
- ajouter `created_by` vers l’utilisateur plateforme ;
- ajouter `creation_request_id` UUID unique pour l’idempotence ;
- ajouter `activated_at`, nullable ;
- conserver `version`, `locale`, `timezone` et les limites existantes.

### 10.2 `memberships`

- ajouter `version` strictement positif ;
- ajouter `updated_by` et conserver `created_by` ;
- conserver l’unicité `(organization_id, user_id)` ;
- ajouter une cible unique `(organization_id, id)` pour les futures références composites ;
- ne créer aucune route de suppression physique.

### 10.3 `user_invitations`

- ajouter `delivery_status IN ('pending', 'sent', 'failed')` ;
- ajouter `delivery_attempted_at`, `delivered_at` et `updated_at` ;
- permettre la rotation transactionnelle de `token_hash` et `expires_at` ;
- conserver `invited_by`, `accepted_at` et `revoked_at` ;
- ajouter une cible unique `(organization_id, id)` ;
- révoquer explicitement les invitations expirées, car une condition d’index ne peut pas dépendre de l’heure courante de manière fiable.

### 10.4 `users`

La table reste globale pour l’authentification et son courriel demeure unique globalement. L’API ne fournit aucune recherche globale d’utilisateurs. Les listes locataires commencent toujours depuis une appartenance visible par RLS avant de joindre les champs minimaux de l’utilisateur.

Tout changement de rôle ou d’état d’appartenance incrémente `users.version` afin d’invalider les sessions antérieures sans dépendre de la disponibilité immédiate de Redis.

Une contrainte composite entre `(last_active_organization_id, id)` et `(memberships.organization_id, memberships.user_id)` sera ajoutée si elle peut être migrée sans compromettre le bootstrap plateforme. À défaut, cet invariant restera vérifié transactionnellement et couvert par un test explicite.

## 11. Rôles SQL et Row-Level Security

### 11.1 Rôles

- le rôle de migration possède les tables et applique Alembic ;
- le rôle applicatif reçoit uniquement `CONNECT`, `USAGE` et les droits DML nécessaires ;
- le rôle applicatif n’est ni propriétaire, ni superutilisateur, ni membre du rôle propriétaire, ni `BYPASSRLS` ;
- `DATABASE_URL` utilise le rôle applicatif et `MIGRATION_DATABASE_URL` le rôle propriétaire ;
- la CI vérifie ces propriétés depuis PostgreSQL.

La configuration locale doit pouvoir provisionner le rôle applicatif sans détruire le volume de développement existant.

### 11.2 Contexte transactionnel

Une unité de travail locataire reçoit un objet serveur non constructible depuis le corps HTTP :

```text
TenantContext(actor_id, organization_id, request_id)
```

Après ouverture explicite de la transaction et avant toute requête métier, elle applique avec `set_config(..., true)` :

- `app.actor_id` ;
- `app.organization_id` ;
- `app.request_id`.

Le paramètre local doit disparaître au commit, au rollback et lors du retour de la connexion au pool. Une `AsyncSession` n’est jamais partagée entre tâches concurrentes.

### 11.3 Politiques

`organizations`, `memberships` et `user_invitations` activent `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY`.

- une organisation locataire est visible si son `id` correspond au contexte ;
- une appartenance ou invitation est visible et modifiable si son `organization_id` correspond ;
- `WITH CHECK` interdit toute insertion ou modification vers une autre organisation ;
- l’absence ou l’invalidité du contexte produit un refus par défaut ;
- les politiques sont définies explicitement dans la migration Alembic.

Les contraintes uniques et clés étrangères ne sont pas présentées comme une protection de confidentialité : PostgreSQL les évalue indépendamment de RLS. Les erreurs de contrainte sont donc traduites en erreurs génériques afin de ne pas révéler une autre organisation.

### 11.4 Opérations plateforme et invitation anonyme

Les opérations sans contexte locataire utilisent des fonctions PostgreSQL étroites et explicitement accordées, pas un contournement RLS général :

- provisioning d’une organisation après vérification du rôle plateforme ;
- consultation des seules métadonnées de provisioning ;
- résolution minimale d’un hash d’invitation valide.

Toute fonction `SECURITY DEFINER` :

- possède un `search_path` limité aux schémas de confiance puis `pg_temp` ;
- qualifie les objets ;
- révoque `EXECUTE` à `PUBLIC` dans la même migration ;
- accorde uniquement la signature nécessaire au rôle applicatif ;
- ne contient aucun SQL dynamique ;
- vérifie l’acteur ou le secret fourni et retourne un jeu de champs minimal.

## 12. Architecture applicative

### 12.1 Domaine

Le domaine contient :

- états d’organisation, rôle et appartenance ;
- politique de capacités ;
- règle du dernier Administrateur ;
- décisions d’acceptation d’invitation ;
- transitions `provisioning -> active` ;
- erreurs métier indépendantes de FastAPI et SQLAlchemy.

### 12.2 Cas d’utilisation

Cas d’utilisation minimaux :

- `CreateOrganization` et `ListPlatformOrganizations` ;
- `GetOrganization` et `UpdateOrganization` ;
- `ListMembers` et `UpdateMembership` ;
- `CreateInvitation`, `ListInvitations`, `ResendInvitation`, `RevokeInvitation` ;
- `PreviewInvitation` et `AcceptInvitation` ;
- `SwitchOrganization` ;
- recherche Google et carte adaptées à `AuthenticatedTenant`.

### 12.3 Ports

- `TenantUnitOfWorkFactory` et dépôts d’organisation ;
- `PlatformOrganizationProvisioner` ;
- `InvitationTokenGenerator` ;
- `InvitationDelivery` ;
- `SessionStore.rotate(...)` en plus des opérations de 2.2 ;
- port de révocation utilisateur existant ;
- garde de recherche utilisant une clé interne, plus une concession cartographique liée à l’acteur.

### 12.4 Présentation

Une dépendance FastAPI résout une seule fois la session et fournit `AuthenticatedUser` ou `AuthenticatedTenant`. Une seconde dépendance vérifie la capacité. Les routes n’accèdent pas directement à Redis, SQLAlchemy ou aux tables.

L’ordre obligatoire pour une route Google est : authentifier, vérifier l’organisation, vérifier la capacité, vérifier la configuration, puis seulement appeler Google.

## 13. Contrat API proposé

### 13.1 Authentification et invitations publiques

| Méthode et route | Fonction |
| --- | --- |
| `POST /api/auth/switch-organization` | Faire tourner la session vers une appartenance active |
| `POST /api/auth/invitations/preview` | Prévisualiser un jeton sans exposer le courriel |
| `POST /api/auth/invitations/accept` | Accepter pour un nouveau compte ou le compte courant |

Changement d’organisation :

```json
{
  "membership_id": "018f0000-0000-7000-8000-000000000001"
}
```

Acceptation d’un nouveau compte :

```json
{
  "token": "jeton-secret",
  "new_account": {
    "display_name": "Alex Tremblay",
    "password": "mot-de-passe-confidentiel"
  }
}
```

Pour un compte existant authentifié, `new_account` doit être absent.

### 13.2 Plateforme

| Méthode et route | Permission |
| --- | --- |
| `GET /api/platform/organizations` | `platform:organizations:read` |
| `POST /api/platform/organizations` | `platform:organizations:create` |
| `POST /api/platform/organizations/{id}/first-invitation/resend` | Plateforme, uniquement pendant `provisioning` |

Création :

```json
{
  "name": "Entreprise Exemple",
  "locale": "fr-CA",
  "timezone": "America/Toronto",
  "first_administrator_email": "admin@exemple.ca",
  "creation_request_id": "018f0000-0000-7000-8000-000000000002"
}
```

### 13.3 Organisation active

| Méthode et route | Permission |
| --- | --- |
| `GET /api/organization` | `organization:read` |
| `PATCH /api/organization` | `organization:update` |
| `GET /api/organization/members` | `members:read` |
| `PATCH /api/organization/members/{membership_id}` | `members:manage` |
| `GET /api/organization/invitations` | `invitations:read` |
| `POST /api/organization/invitations` | `invitations:manage` |
| `POST /api/organization/invitations/{id}/resend` | `invitations:manage` |
| `DELETE /api/organization/invitations/{id}` | `invitations:manage` |

Les chemins préliminaires `/api/users` de la spécification générale sont remplacés par ces ressources d’organisation afin d’éviter toute ambiguïté avec les utilisateurs globaux.

### 13.4 Conventions et erreurs

- commandes strictes, sans champs inconnus ;
- aucune commande locataire ne comporte `organization_id` ;
- toutes les mutations exigent JSON, origine fiable et CSRF, sauf acceptation anonyme qui exige JSON, origine fiable et limitation dédiée ;
- données d’identité et d’organisation : `Cache-Control: private, no-store` ;
- pagination par curseur, limite 25 par défaut et 100 maximum ;
- `version` obligatoire sur les modifications concurrentes ;
- `401` session absente ou invitation existante nécessitant une connexion ;
- `403` capacité insuffisante sur une ressource visible ;
- `404` identifiant absent ou situé dans une autre organisation ;
- `409` dernier Administrateur, version, appartenance ou invitation concurrente ;
- `422` entrée invalide sans écho de secret ;
- `429` limitation avec `Retry-After` ;
- `503` PostgreSQL, Redis ou adaptateur de livraison non configuré ; une panne d’envoi postérieure à la création retourne la ressource avec `delivery_status=failed` ;
- toutes les erreurs utilisent le contrat commun et un `request_id`.

## 14. Protection Google

### 14.1 Recherche

`POST /api/google/places/search` :

- exige `google:search` et une organisation active ;
- interdit désormais le bloc `requester` et tout `organization_id` ;
- utilise `user_id` et `organization_id` internes pour le verrou ;
- conserve exactement un Text Search, vingt résultats, aucun contact, aucune pagination et `no-store` ;
- n’enregistre ni requête, ni réponse, ni contenu Google.

### 14.2 Carte

`POST /api/map/snapshot` exige `google:map`. La concession de carte contient côté serveur l’utilisateur et l’organisation autorisés, en plus de la charge cartographique. Un autre utilisateur ou une autre organisation ne peut pas la consommer, même avec le jeton.

L’authentification est vérifiée avant de réserver ou consommer la concession. Une réponse `401` ou `403` ne déclenche aucun appel Maps Static.

### 14.3 Frontière avec 2.6

Le verrou peut rester en mémoire pour une instance locale, mais sa clé ne contient plus d’adresse déclarée. Les quotas journaliers et le remplacement par Redis partagé restent obligatoires en 2.6 avant un déploiement répliqué.

## 15. Interface React

### 15.1 Routes

- `/login` ;
- `/accept-invitation` ;
- `/app/search` ;
- `/app/account` ;
- `/app/admin/organization` ;
- `/app/admin/users` ;
- `/app/platform/organizations`.

`/` redirige vers `/app/search` lorsqu’une organisation est active, vers l’administration plateforme pour un Administrateur plateforme sans organisation, sinon vers `/login`.

### 15.2 Navigation et capacités

- sélecteur d’organisation visible uniquement avec plusieurs appartenances actives ;
- changement de session atomique dans `AuthProvider` ;
- routes protégées par capacité avec page `403` accessible ;
- actions d’administration absentes lorsque la capacité manque ;
- aucun clignotement d’une action privilégiée pendant la restauration de session ;
- aucune confiance accordée au contrôle visuel côté serveur.

### 15.3 Pages

- **Plateforme — Organisations** : liste des métadonnées, formulaire de création et état de la première invitation ;
- **Organisation** : nom, langue, fuseau, état et version ;
- **Utilisateurs** : membres, invitations, rôle, état, renvoi et révocation selon capacité ;
- **Acceptation** : prévisualisation, création de compte ou invitation à se connecter avec le compte existant ;
- **Recherche** : formulaire actuel sans identité temporaire, résultats et attribution inchangés.

### 15.4 Données navigateur

Le jeton d’invitation, le jeton CSRF, les capacités et les résultats Google restent en mémoire. Aucun n’est écrit dans `localStorage`, `sessionStorage`, IndexedDB ou un service worker.

## 16. Journalisation transitoire

En attendant l’audit append-only de 2.4 :

- `organizations.created_by`, `memberships.created_by`, `memberships.updated_by` et `user_invitations.invited_by` conservent l’acteur interne ;
- les journaux techniques peuvent contenir `request_id`, identifiants internes, action, résultat et durée ;
- ils excluent courriel lorsque non indispensable, jeton d’invitation, cookie, CSRF, mot de passe, recherche et contenu Google ;
- aucune route de suspension n’est ouverte avant l’audit ;
- la mise en production des fonctions administratives reste conditionnée à 2.4.

## 17. Migration et déploiement local

### 17.1 Prérequis de sécurité des dépendances

Avant les tests RLS, les images locales et CI passent sans changement majeur de PostgreSQL `17.5` à `17.10` et de Redis `7.4.5` à `7.4.9`. Ces versions corrigent des vulnérabilités publiées en 2026. La mise à niveau PostgreSQL 17.x ne demande pas de dump/restauration selon l’éditeur, mais le passage depuis une version antérieure à 17.6 doit suivre les remarques de migration officielles et être précédé d’une sauvegarde vérifiée pour tout volume contenant des données utiles.

Les images restent figées sur un numéro de correctif explicite et seront réévaluées au verrou de déploiement.

### 17.2 Révision Alembic

La révision Alembic `20260723_0003` devra :

1. ajouter les colonnes et contraintes compatibles ;
2. faire évoluer les états avec des valeurs figées ;
3. créer les index composites ;
4. créer les fonctions d’accès étroites et révoquer leurs droits publics ;
5. activer puis forcer RLS ;
6. accorder les droits minimaux au rôle applicatif ;
7. vérifier que le rôle applicatif n’est pas propriétaire ;
8. permettre la reconstruction d’une base vide ;
9. préserver les comptes et sessions 2.2 ;
10. fournir un chemin local non destructif pour créer le rôle applicatif sur un volume existant.

Le changement de `DATABASE_URL` vers le rôle applicatif ne se fait qu’après migration et vérification des droits. Un échec ne doit jamais être contourné en donnant `BYPASSRLS` ou la propriété des tables au rôle Web.

## 18. Tests et critères d’acceptation

### 18.1 Domaine et cas d’utilisation

- matrice complète des capacités ;
- transitions de l’organisation ;
- invitation nouvelle, existante, expirée, révoquée et utilisée ;
- invitation initiale activant l’organisation ;
- ancien lien refusé après renvoi ;
- dernier Administrateur refusé, y compris deux retraits concurrents ;
- changement d’organisation vers une appartenance active seulement ;
- aucune appartenance implicite pour le rôle plateforme.

### 18.2 PostgreSQL et RLS réels

- rôle applicatif non propriétaire, non superutilisateur et sans `BYPASSRLS` ;
- aucune ligne locataire visible sans contexte ;
- organisation A incapable de lire, modifier, supprimer ou référencer une ligne B ;
- `WITH CHECK` bloquant une écriture croisée ;
- contexte `SET LOCAL` absent après commit, rollback et réutilisation du pool ;
- politiques `ENABLE` et `FORCE` présentes ;
- fonctions privilégiées refusées à un acteur non plateforme ;
- aucune fuite par message de contrainte ;
- migration base vide, downgrade contrôlé, upgrade et `alembic check` verts.
- versions PostgreSQL et Redis corrigées, services sains et données locales préservées après mise à niveau.

### 18.3 API

- `401` avant toute recherche ou carte Google et zéro appel fournisseur ;
- `403` lorsque la capacité manque et zéro appel fournisseur ;
- injection d’`organization_id` rejetée par `422` ;
- identifiant d’une autre organisation retournant `404` ;
- Gestionnaire en lecture seule et Commercial sans annuaire des membres ;
- création plateforme idempotente ;
- invitation sans jeton brut dans la réponse ;
- acceptation d’un compte existant impossible sans session correspondante ;
- session renouvelée après acceptation, changement d’organisation ou élévation ;
- sessions invalidées par version puis nettoyées après changement de rôle ou désactivation ;
- panne PostgreSQL, Redis ou livraison traduite sans détail interne.

### 18.4 Frontend

- routes et actions selon les capacités ;
- sélecteur multi-organisation ;
- acceptation d’invitation neuve et existante ;
- suppression immédiate du fragment de l’URL ;
- absence de secret dans tous les stockages Web ;
- suppression du formulaire d’identité temporaire ;
- recherche, attribution et bouton d’export désactivé inchangés ;
- erreurs `401`, `403`, `409` et `503` compréhensibles et accessibles.

### 18.5 Non-régression obligatoire

- Ruff et format ;
- mypy strict ;
- pytest avec PostgreSQL et Redis réels ;
- ESLint ;
- Vitest ;
- build Vite ;
- un seul appel Text Search ;
- aucun `nextPageToken` ;
- vingt résultats maximum ;
- aucun téléphone ou site Web dans la liste ;
- `Cache-Control: no-store` ;
- aucune route d’export historique ;
- aucune persistance navigateur ou serveur du contenu Google ;
- attribution Google Maps visible ;
- carte facturable protégée et liée à l’acteur.

## 19. Découpage d’implémentation proposé

### 2.3.1 — Rôle applicatif, contexte et RLS

- provisionnement non destructif du rôle SQL ;
- unité de travail locataire ;
- migration, politiques et tests croisés réels ;
- aucun changement visuel.

État au 23 juillet 2026 : implémenté, doublement revu et validé localement par le responsable produit. Le rapport, les risques résiduels et le protocole de validation
locale figurent dans [`PHASE_2_3_1_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_1_RAPPORT_IMPLEMENTATION.md).

### 2.3.2 — Provisioning et invitations

- création plateforme idempotente ;
- état `provisioning` ;
- livraison Mailpit locale ;
- prévisualisation, acceptation, renvoi et révocation ;
- tests nouveau compte et compte existant.

État au 23 juillet 2026 : le contrat d’implémentation détaillé, ses deux critiques préalables et ses seize décisions
complémentaires validées figurent dans
[`PHASE_2_3_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_2_SPECIFICATIONS_DETAILLEES.md). L’implémentation de 2.3.2 est
autorisée.

### 2.3.3 — Membres, capacités et changement d’organisation

- listes et mises à jour ;
- protection concurrente du dernier Administrateur ;
- rotation et révocation des sessions ;
- matrice d’autorisation API.

### 2.3.4 — Protection Google et transition de l’écran

- authentification de la recherche et de la carte ;
- concession liée à l’acteur ;
- verrou par identifiants internes ;
- retrait du bloc `requester` et de la fenêtre temporaire ;
- non-régression Google complète.

### 2.3.5 — Interface d’administration et verrou qualité

- pages, navigation et sélecteur ;
- tests React et contrôles accessibles ;
- documentation utilisateur, légale et d’exploitation ;
- deux critiques expertes finales ;
- validation produit locale avant 2.4.

Chaque sous-incrément doit garder la migration, Ruff, mypy, pytest, ESLint, Vitest et le build verts. Aucun sous-incrément ne peut affaiblir temporairement la protection des routes Google.

## 20. Double critique préalable de la spécification

### 20.1 Revue sécurité et architecture

Constats incorporés :

- le rôle plateforme ne doit pas devenir un contournement général de RLS ;
- une organisation active sans Administrateur crée un état irrécupérable ;
- un lien d’invitation volé ne doit pas modifier un compte existant ;
- un jeton de carte non lié pourrait être consommé par un autre utilisateur ;
- deux Administrateurs pourraient se retirer simultanément si le contrôle se limite à un comptage ;
- une session ancienne ne doit pas conserver un privilège après changement de rôle.

Réponses : fonctions SQL étroites, état `provisioning`, authentification du compte existant, concession liée, verrou de l’organisation et rotation/révocation des sessions.

### 20.2 Revue exploitation et maintenabilité

Constats incorporés :

- changer une variable Compose ne modifie pas un volume PostgreSQL déjà initialisé ;
- une invitation expirée continue de satisfaire l’index partiel existant ;
- l’envoi de courriel et la transaction PostgreSQL ne sont pas atomiques ;
- un contexte RLS de portée session pourrait contaminer une connexion remise au pool ;
- l’utilisation du propriétaire par le serveur Web annulerait la défense RLS ;
- les images PostgreSQL 17.5 et Redis 7.4.5 ne portent plus les correctifs de sécurité courants de leur branche ;
- un développement unique de toute la portée serait difficile à diagnostiquer et valider.

Réponses : procédure locale non destructive, révocation transactionnelle des expirées, état de livraison et renvoi, `set_config(..., true)`, rôle applicatif séparé, mise à niveau vers PostgreSQL 17.10 et Redis 7.4.9, puis cinq sous-incréments testables.

## 21. Décisions validées pour l’implémentation

1. Ajouter l’état d’organisation `provisioning` et n’activer qu’après acceptation du premier Administrateur.
2. Ne donner aucun accès locataire implicite à l’Administrateur de plateforme.
3. Utiliser `membership_id` pour changer d’organisation et administrer une appartenance.
4. Conserver la matrice stricte : Administrateur gère, Gestionnaire consulte, Commercial ne voit pas l’annuaire.
5. Interdire les suppressions physiques et protéger le dernier Administrateur sous verrou transactionnel.
6. Faire tourner la session lors d’un changement d’organisation ou de privilège et révoquer les sessions après modification d’un membre.
7. Exiger l’authentification du compte existant avant acceptation d’une invitation correspondante.
8. Utiliser un lien avec fragment, un jeton de 256 bits, un hash en base et une expiration de 72 heures.
9. Utiliser Mailpit uniquement en local et rendre obligatoire un adaptateur approuvé avant production.
10. Séparer le rôle PostgreSQL applicatif du propriétaire et appliquer `ENABLE` plus `FORCE ROW LEVEL SECURITY`.
11. Limiter les opérations sans contexte locataire à des fonctions SQL étroites, sécurisées et explicitement accordées.
12. Protéger à la fois Text Search et Maps Static, et lier chaque concession de carte à l’utilisateur et à l’organisation.
13. Différer quotas et verrous Redis partagés à 2.6, tout en remplaçant dès 2.3 l’adresse déclarée par les identifiants internes.
14. Différer la suspension par API à 2.4 afin de disposer d’un audit append-only, sans différer l’isolation ni les traces d’acteur.
15. Réaliser l’implémentation dans les cinq sous-incréments de la section 19, validés séparément.
16. Mettre à niveau les images vers PostgreSQL 17.10 et Redis 7.4.9 avant de valider RLS, sans changement de version majeure.

Ces seize décisions ont été validées par le responsable produit le 23 juillet 2026. Elles constituent le contrat obligatoire de l’incrément 2.3. Toute dérogation devra être documentée, justifiée et validée avant son implémentation.

## 22. Références

- [PostgreSQL 17 — Row Security Policies](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)
- [PostgreSQL 17 — `set_config` et `current_setting`](https://www.postgresql.org/docs/17/functions-admin.html)
- [PostgreSQL — écriture sûre des fonctions `SECURITY DEFINER`](https://www.postgresql.org/docs/current/sql-createfunction.html)
- [PostgreSQL 17.10 — notes de publication et migration](https://www.postgresql.org/docs/release/17.10/)
- [PostgreSQL — informations de sécurité de la branche 17](https://www.postgresql.org/support/security/17/)
- [Redis — correctifs de sécurité 2026 et versions corrigées](https://redis.io/blog/security-advisory-cve202623479-cve202625243-cve-2026-25588-cve202625589-cve-2026-23631/)
- [SQLAlchemy 2 — sessions et transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [OWASP — Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP — jetons temporaires à usage unique](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- [`PHASE_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_2_RAPPORT_IMPLEMENTATION.md`](PHASE_2_2_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_1_1_ACQUISITION_CONSERVATION.md`](PHASE_1_1_ACQUISITION_CONSERVATION.md)
