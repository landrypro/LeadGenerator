# Phase 2.3.2 — Spécifications détaillées du provisioning et des invitations

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Incrément | 2.3.2 — Provisioning et invitations |
| Version | 1.0 |
| Date | 23 juillet 2026 |
| Statut | Spécification validée ; implémentation autorisée |
| Validation produit | 23 juillet 2026 |
| Prérequis | 2.3.1 implémenté, doublement revu et validé localement |
| Référence supérieure | `PHASE_2_3_SPECIFICATIONS_DETAILLEES.md` version 1.4 |
| Changement de code | Aucun dans cette phase de spécification |

## 1. Objectif

2.3.2 doit rendre possible le premier accès à une nouvelle organisation sans affaiblir l’isolation livrée en 2.3.1.
Un Administrateur de plateforme crée une organisation de manière idempotente, l’application envoie une invitation à
son premier Administrateur, puis l’acceptation active l’organisation et ouvre une session locataire.

L’incrément doit couvrir les deux parcours suivants :

1. le destinataire ne possède pas encore de compte et le crée pendant l’acceptation ;
2. le destinataire possède déjà un compte et doit s’authentifier avec ce compte avant l’acceptation.

Le résultat attendu est testable de bout en bout en local avec Mailpit, mais aucun fournisseur de courriel de
production n’est choisi ni simulé par une configuration SMTP générique.

## 2. Contrats hérités et non rouverts

Les seize décisions validées dans la section 21 de la spécification 2.3 restent obligatoires. En particulier :

- l’organisation commence à l’état `provisioning` et n’est activée qu’après la première appartenance Admin ;
- le rôle `platform_admin` ne confère aucune appartenance locataire implicite ;
- le compte existant doit être authentifié avant d’accepter son invitation ;
- le jeton contient au moins 256 bits, expire après 72 heures et seul son hash est stocké ;
- le lien place le jeton dans le fragment de l’URL ;
- Mailpit est strictement local et un adaptateur approuvé reste obligatoire avant la production ;
- les opérations hors contexte locataire passent uniquement par des fonctions SQL étroites ;
- les tables locataires conservent `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY`.

2.3.2 précise la mise en œuvre de ces décisions ; il ne les remplace pas.

## 3. Périmètre

### 3.1 Inclus

- création idempotente d’une organisation par l’Administrateur de plateforme ;
- consultation paginée des métadonnées de provisioning par la plateforme ;
- invitation initiale de rôle `admin` ;
- génération, hash, expiration et rotation du jeton ;
- prévisualisation publique minimisée ;
- acceptation par création d’un nouveau compte ;
- acceptation par un compte existant authentifié ;
- activation atomique de l’organisation et création de l’appartenance ;
- rotation ou création de la session après acceptation ;
- renvoi et révocation de la première invitation ;
- idempotence et limitation des renvois ;
- livraison SMTP locale vers Mailpit ;
- page React minimale `/accept-invitation` ;
- migration Alembic, fonctions SQL, tests et documentation locale.

### 3.2 Explicitement différé

- invitation de Gestionnaires ou de Commerciaux dans une organisation active, livrée en 2.3.3 ;
- liste et modification des membres, livrées en 2.3.3 ;
- changement manuel d’organisation, livré en 2.3.3 ;
- protection authentifiée des routes Google et suppression du demandeur temporaire, livrées en 2.3.4 ;
- pages d’administration plateforme et organisation complètes, livrées en 2.3.5 ;
- audit append-only et suspension par API, livrés en 2.4 ;
- fournisseur et gabarit de courriel de production ;
- pipeline, prospects et autres données métier ;
- suppression physique d’une organisation, d’une invitation, d’un compte ou d’une appartenance.

Le provisioning ne crée donc aucune donnée de prospect ni étape de pipeline dans ce sous-incrément.

## 4. Acteurs et autorisations

### 4.1 Administrateur de plateforme

Un utilisateur actif avec `platform_role=platform_admin` reçoit :

- `platform:organizations:read` ;
- `platform:organizations:create`.

Il peut créer une organisation, lire ses seules métadonnées de provisioning, renvoyer ou révoquer sa première
invitation. Il ne peut pas utiliser ces routes pour lire les futures données métier de l’organisation.

### 4.2 Destinataire invité

Avant acceptation, il n’est pas membre. Le jeton donne uniquement accès à la prévisualisation minimisée et au cas
d’utilisation d’acceptation. Il ne donne aucun accès aux routes locataires.

### 4.3 Compte existant

La session doit appartenir à l’utilisateur actif dont le courriel normalisé correspond au courriel normalisé de
l’invitation. Une session d’un autre utilisateur ne peut ni accepter, ni réassigner l’invitation.

Un compte actif sans appartenance active doit pouvoir s’authentifier dans une session restreinte avec
`active_organization_id=null` et aucune capacité. Cette session sert à accepter une invitation ou à se déconnecter ;
elle n’accorde aucun accès locataire.

## 5. États et invariants

### 5.1 Organisation

Transitions autorisées dans 2.3.2 :

```text
création -> provisioning -> active
```

- `provisioning -> active` est irréversible dans cet incrément ;
- la transition se produit uniquement avec la création réussie de la première appartenance Admin active ;
- une organisation `provisioning` ne peut pas utiliser les opérations locataires ordinaires ;
- une invitation révoquée ou expirée laisse l’organisation en `provisioning` ;
- l’Administrateur de plateforme n’est jamais ajouté automatiquement comme membre.

### 5.2 Invitation

L’état métier est calculé depuis les dates, sans colonne `status` redondante :

| État calculé | Règle |
| --- | --- |
| `active` | non acceptée, non révoquée et non expirée |
| `expired` | non acceptée, non révoquée et `expires_at <= now` |
| `accepted` | `accepted_at` non nul |
| `revoked` | `revoked_at` non nul |

`accepted_at` et `revoked_at` sont mutuellement exclusifs. Un jeton n’est utilisable qu’une seule fois, y compris
lors de deux acceptations concurrentes.

### 5.3 Livraison

La livraison possède un état distinct du cycle de vie de l’invitation :

- `pending` : transaction validée, remise au transport non finalisée ;
- `sent` : l’adaptateur a accepté le message ;
- `failed` : l’adaptateur a refusé le message ou a dépassé son délai.

`sent` ne prouve ni l’ouverture, ni la lecture du courriel. Il signifie uniquement que l’adaptateur configuré en a
accepté la responsabilité.

## 6. Workflow de création d’organisation

`POST /api/platform/organizations` reçoit une commande stricte :

```json
{
  "name": "Entreprise Exemple",
  "locale": "fr-CA",
  "timezone": "America/Toronto",
  "first_administrator_email": "admin@exemple.ca",
  "creation_request_id": "018f0000-0000-7000-8000-000000000002"
}
```

### 6.1 Validation

- session active et rôle plateforme relus dans PostgreSQL ;
- CSRF, `Content-Type: application/json` et origine fiable obligatoires ;
- nom nettoyé, de 1 à 160 caractères ;
- `locale` appartenant à `fr-CA` ou `en-CA` ; ce champ prépare la localisation sans prétendre traduire l’interface
  dans 2.3.2 ;
- fuseau présent dans la base IANA disponible au serveur ;
- courriel validé par la normalisation Unicode/IDNA existante ;
- `creation_request_id` UUID fourni par le client et obligatoire ;
- adaptateur de livraison configuré et autorisé dans l’environnement avant la première écriture.

La joignabilité SMTP n’est pas utilisée comme précondition transactionnelle : elle peut changer immédiatement après
un contrôle. Une indisponibilité de Mailpit au moment de l’envoi suit donc le scénario post-commit `failed`.

### 6.2 Transaction PostgreSQL

Sous une fonction SQL privilégiée étroite, une seule transaction :

1. vérifie à nouveau que l’acteur courant est un `platform_admin` actif ;
2. sérialise les créations portant le même `creation_request_id` ;
3. compare l’empreinte canonique de la commande en cas de répétition ;
4. crée l’organisation avec `status=provisioning` ;
5. crée l’invitation initiale de rôle `admin` et de type `initial_administrator` ;
6. crée la première tentative de livraison `pending` ;
7. valide et retourne les identifiants minimaux à l’application.

Le hash du jeton est écrit dans l’invitation. Le jeton brut ne traverse la fonction SQL que sous forme de hash et ne
quitte jamais la mémoire du processus applicatif.

### 6.3 Idempotence

- même `creation_request_id` et même commande canonique : aucune nouvelle organisation, invitation ou livraison ;
- même `creation_request_id` et commande différente : `409 idempotency_key_reused` ;
- deux requêtes concurrentes avec la même clé produisent exactement une organisation ;
- une répétition après perte de la réponse retourne la ressource existante et ne renvoie pas automatiquement le
  courriel ;
- si l’état est `failed`, l’opérateur utilise explicitement l’action de renvoi avec un nouveau `resend_request_id`.

Le serveur stocke le UUID et une empreinte SHA-256 de la représentation canonique des champs métier déjà nettoyés :
nom, langue, fuseau et courriel normalisé. Le mot de passe, le jeton et les en-têtes ne participent pas à cette
empreinte.

### 6.4 Livraison après commit

Après validation PostgreSQL :

1. le cas d’utilisation construit le lien exclusivement depuis `PUBLIC_APP_URL` ;
2. il appelle le port `InvitationDelivery` avec le jeton brut encore en mémoire ;
3. il finalise la tentative par une fonction SQL étroite ;
4. il efface toute référence au jeton à la fin de la commande.

La transaction PostgreSQL n’est jamais conservée ouverte pendant l’appel SMTP.

Si SMTP échoue, l’organisation et l’invitation restent créées, la tentative passe à `failed` et l’API retourne la
ressource créée avec cet état. Si SMTP réussit mais que l’enregistrement du résultat devient impossible, l’API retourne
`503 provisioning_outcome_unknown`. L’appelant doit relire ou répéter la création avec le même
`creation_request_id` ; il ne doit jamais changer la clé pour contourner cette réponse.

### 6.5 Réponse

Première création : `201 Created`. Répétition idempotente : `200 OK`.

```json
{
  "organization": {
    "id": "018f0000-0000-7000-8000-000000000010",
    "name": "Entreprise Exemple",
    "locale": "fr-CA",
    "timezone": "America/Toronto",
    "status": "provisioning",
    "version": 1,
    "created_at": "2026-07-23T15:00:00Z"
  },
  "first_invitation": {
    "id": "018f0000-0000-7000-8000-000000000011",
    "recipient_email": "admin@exemple.ca",
    "role": "admin",
    "state": "active",
    "delivery_status": "sent",
    "expires_at": "2026-07-26T15:00:00Z"
  },
  "replayed": false
}
```

Le jeton brut, son hash et l’identifiant d’une tentative de transport ne figurent jamais dans la réponse.

## 7. Consultation plateforme

`GET /api/platform/organizations` retourne une pagination par curseur, 25 éléments par défaut et 100 maximum. Le tri
stable est `created_at DESC, id DESC`.

La ressource contient uniquement :

- identifiant, nom, langue, fuseau, état, version et dates de l’organisation ;
- identifiant, courriel destinataire, rôle, état calculé, expiration et livraison de la première invitation ;
- aucun membre, donnée Google, donnée CRM ou secret.

Cette lecture utilise une fonction SQL privilégiée distincte, vérifie le rôle plateforme en base et porte
`Cache-Control: private, no-store`.

Lorsqu’il existe plusieurs versions d’une première invitation, la liste retourne uniquement la version la plus
récente. Les anciennes lignes restent disponibles pour les contrôles internes et le futur audit, sans être exposées
par cette réponse.

## 8. Prévisualisation d’invitation

`POST /api/auth/invitations/preview` reçoit :

```json
{
  "token": "JETON_BASE64URL"
}
```

La commande exige JSON et une origine fiable, mais ni cookie ni CSRF. La réponse valide contient uniquement :

```json
{
  "organization_name": "Entreprise Exemple",
  "role": "admin",
  "expires_at": "2026-07-26T15:00:00Z",
  "existing_account": false
}
```

Elle ne contient ni courriel, ni identifiant interne, ni état de livraison. Un jeton inconnu, mal formé, expiré,
révoqué ou accepté produit la même erreur `400 invitation_invalid`.

Le format V1 est un jeton base64url sans remplissage de 43 caractères, issu de 32 octets aléatoires. Toute entrée
plus longue que 128 caractères est rejetée avant hash ou accès base.

Les tentatives sont limitées atomiquement dans Redis par HMAC de l’adresse réseau et hash du jeton. La clé HMAC reste
hors des journaux et de Redis ; le hash du jeton est sûr contre l’inversion grâce à ses 256 bits aléatoires. Redis
indisponible provoque un refus fermé `503 invitation_service_unavailable`.

## 9. Acceptation par un nouveau compte

La commande est :

```json
{
  "token": "JETON_BASE64URL",
  "new_account": {
    "display_name": "Alex Tremblay",
    "password": "mot-de-passe-confidentiel"
  }
}
```

### 9.1 Validations

- invitation valide et de type `initial_administrator` ;
- aucun utilisateur global ne porte le même courriel normalisé ;
- nom affiché de 1 à 120 caractères ;
- mot de passe de 12 à 128 caractères, sans normalisation ni troncature ;
- origine fiable et limitation dédiée ;
- aucune session active d’un autre compte ; le navigateur doit d’abord se déconnecter ;
- le mot de passe est haché avec le port Argon2id avant l’appel SQL ;
- aucun cookie de session n’est requis et le champ CSRF est absent.

### 9.2 Transaction atomique

La fonction d’acceptation :

1. verrouille l’invitation et l’organisation ;
2. relit expiration, révocation et acceptation ;
3. vérifie qu’aucune appartenance active ou désactivée n’existe déjà pour ce couple ;
4. crée l’utilisateur actif ;
5. crée l’appartenance Admin active avec `created_by=invited_by` ;
6. marque l’invitation acceptée et renseigne `accepted_by` ;
7. active l’organisation, renseigne `activated_at` et incrémente sa version ;
8. place cette organisation dans `last_active_organization_id` ;
9. valide l’ensemble ou ne conserve rien.

Si un compte apparaît concurremment après la prévisualisation, la contrainte globale de courriel gagne. La transaction
n’accepte pas l’invitation et retourne `401 invitation_authentication_required` ; le destinataire doit se connecter au
compte désormais existant.

### 9.3 Session

Après le commit, une nouvelle session Redis est créée avec l’organisation active. Le cookie et le jeton CSRF suivent
le contrat 2.2. La réponse est le contrat `AuthenticationResponse` existant, enrichi des nouvelles capacités calculées.

Si Redis échoue après le commit, l’API retourne `503 session_creation_failed_after_acceptance`. L’invitation reste
utilisée et l’organisation active ; l’utilisateur se connecte ensuite normalement avec son nouveau mot de passe.

## 10. Acceptation par un compte existant

La commande ne contient aucun mot de passe :

```json
{
  "token": "JETON_BASE64URL"
}
```

Règles :

- session active obligatoire ;
- `X-CSRF-Token`, JSON et origine fiable obligatoires ;
- égalité stricte des courriels normalisés de la session et de l’invitation ;
- compte `disabled` refusé ;
- un compte actif sans appartenance peut ouvrir une session sans organisation et sans capacité pour ce parcours ;
- une appartenance désactivée n’est jamais réactivée par l’invitation ;
- une session d’un autre compte reçoit `403 invitation_account_mismatch` ;
- une absence de session reçoit `401 invitation_authentication_required`.

La transaction verrouille les mêmes lignes, crée l’appartenance, accepte l’invitation, active l’organisation et
place la nouvelle organisation dans `last_active_organization_id`, puis incrémente `users.version`. Cette
incrémentation invalide immédiatement les anciennes sessions, même si Redis tombe ensuite.

Après commit, `SessionStore.rotate(...)` crée atomiquement une nouvelle session vers l’organisation acceptée, révoque
l’ancien identifiant et produit un nouveau CSRF. En cas de panne Redis, l’API retourne `503`, l’ancienne session devient
invalide par sa version et l’utilisateur peut se reconnecter.

Le cas d’usage de connexion 2.2 évolue donc de façon bornée : tout utilisateur global `active` avec un mot de passe
valide peut s’authentifier, mais l’absence d’appartenance active produit une identité sans organisation et sans
capacité. Les dépendances locataires continuent de la refuser avant toute opération métier.

## 11. Renvoi et révocation

### 11.1 Renvoi

`POST /api/platform/organizations/{organization_id}/first-invitation/resend` reçoit :

```json
{
  "resend_request_id": "018f0000-0000-7000-8000-000000000012"
}
```

Sous verrou de l’organisation et de l’invitation :

- l’organisation doit encore être `provisioning` ;
- l’invitation ne doit pas être acceptée ;
- la clé de requête rend le renvoi idempotent ;
- l’invitation précédente est révoquée sans modifier son hash ni effacer ses dates ;
- une nouvelle ligne d’invitation, liée à la précédente, reçoit un nouveau jeton et une expiration de 72 heures ;
- l’ancien lien devient invalide dès le même commit, avant l’appel SMTP ;
- une nouvelle tentative de livraison durable est créée ;
- le même `resend_request_id` ne produit jamais un second courriel ;
- une minute minimale sépare deux renvois ;
- cinq renvois au maximum sont autorisés par fenêtre glissante de 24 heures ;
- les limites sont configurables, mais ne peuvent être désactivées en staging ou production.

Les limites de renvoi sont comptées dans PostgreSQL depuis les tentatives durables, sous le même verrou. Elles ne
dépendent donc ni de la mémoire du processus, ni d’un redémarrage Redis.

### 11.2 Révocation

`POST /api/platform/organizations/{organization_id}/first-invitation/revoke` reçoit un objet JSON vide et exige session
plateforme, CSRF et origine fiable.

- une invitation active ou expirée est marquée `revoked_at` ;
- une seconde révocation retourne le même résultat sans erreur ;
- une invitation acceptée retourne `409 invitation_already_accepted` ;
- l’organisation reste `provisioning` ;
- un renvoi ultérieur crée une nouvelle version d’invitation liée à la ligne révoquée ;
- aucune ligne n’est supprimée.

## 12. Courriel et Mailpit local

### 12.1 Contenu minimal

Le message contient :

- le nom de l’application ;
- le nom de l’organisation ;
- le rôle proposé ;
- la date d’expiration ;
- le lien `${PUBLIC_APP_URL}/accept-invitation#token=...` ;
- une consigne d’ignorer le message si l’invitation n’était pas attendue.

Il ne contient aucun mot de passe, cookie, CSRF, identifiant interne, donnée Google ou information sur d’autres
organisations.

### 12.2 Environnement local

- Mailpit est ajouté au profil Compose de développement et de test ;
- SMTP est publié sur `127.0.0.1:1025` ;
- l’interface Mailpit est publiée sur `127.0.0.1:8025` ;
- aucun port Mailpit n’écoute sur toutes les interfaces de la machine ;
- le conteneur est éphémère et ne reçoit que des adresses et contenus de test ;
- le corps du message et le lien ne sont jamais recopiés dans les journaux applicatifs.

L’image sera figée sur un numéro de version explicite au moment de l’implémentation, puis contrôlée comme les autres
dépendances de conteneur.

### 12.3 Verrou de production

L’adaptateur `mailpit` est accepté seulement pour `APP_ENV=development` ou `test`. En `staging` et `production`, son
activation fait échouer le démarrage. Tant qu’un adaptateur approuvé n’existe pas, le provisioning de production reste
désactivé ; une simple adresse SMTP ne suffit pas à lever ce verrou.

## 13. Modèle PostgreSQL cible

La migration prévue est `20260723_0004` et descend de `20260723_0003`.

### 13.1 `organizations`

- étendre `status` à `provisioning`, `active`, `suspended` ;
- changer le défaut sécurisé vers `provisioning` ;
- ajouter `created_by UUID NOT NULL` vers `users` avec `ON DELETE RESTRICT` ;
- ajouter `creation_request_id UUID UNIQUE`, nullable uniquement pour les lignes historiques ;
- ajouter `creation_request_fingerprint CHAR(64)` avec cohérence de nullité ;
- ajouter `activated_at TIMESTAMPTZ`, nul pour `provisioning` et obligatoire pour `active` ou `suspended` ;
- conserver `version`, `locale`, `timezone` et la limite Google existante.

Les organisations historiques sont rétroalimentées depuis leur première appartenance traçable. Une organisation dont
l’acteur créateur ne peut pas être dérivé fait échouer la migration avec une procédure de correction explicite ; la
migration n’attribue jamais arbitrairement la ligne au premier Administrateur de plateforme.

Le précontrôle exige aussi qu’une organisation historique `active` possède au moins un Administrateur actif. Pour les
lignes historiques actives ou suspendues valides, `activated_at` est initialisé avec `created_at` faute d’une date plus
précise, et cette approximation est signalée dans le rapport de migration.

### 13.2 `user_invitations`

- ajouter `invitation_kind IN ('initial_administrator', 'member')` ;
- ajouter `delivery_status IN ('pending', 'sent', 'failed')` ;
- ajouter `delivery_attempted_at`, `delivered_at`, `updated_at` ;
- ajouter `accepted_by` vers `users`, nullable ;
- ajouter `supersedes_invitation_id`, auto-référence nullable avec `ON DELETE RESTRICT` ;
- renforcer l’exclusion mutuelle entre acceptation et révocation ;
- conserver le hash unique, l’expiration, `invited_by` et l’index d’invitation active ;
- révoquer explicitement l’ancienne ligne avant d’insérer toute version de renvoi.

Une ligne d’invitation devient immuable pour son courriel, son rôle, son hash et son expiration après commit. Seuls ses
dates de cycle de vie et son état de livraison peuvent évoluer. Un retour SMTP tardif ne met à jour que sa propre
version et ne peut donc pas écraser l’état d’un renvoi plus récent.

Comme aucune route d’invitation n’existait avant 2.3.2, une base normale ne doit contenir aucune ligne héritée dans
`user_invitations`. La migration refuse néanmoins de leur inventer un état de livraison : si elle en trouve, elle
s’arrête et demande une décision explicite de conservation ou de révocation. Aucune ligne n’est supprimée ou marquée
`sent` par supposition.

### 13.3 `invitation_delivery_attempts`

Nouvelle table technique locataire, sans jeton ni courriel :

| Colonne | Règle |
| --- | --- |
| `id` | UUID, clé primaire |
| `organization_id` | UUID obligatoire |
| `invitation_id` | référence composite dans la même organisation |
| `request_id` | UUID unique d’idempotence |
| `kind` | `initial` ou `resend` |
| `status` | `pending`, `sent` ou `failed` |
| `failure_code` | code technique borné, nullable, jamais un message SMTP |
| `requested_by` | utilisateur plateforme |
| `created_at`, `completed_at` | UTC |

Une invitation possède exactement une tentative d’envoi automatique. Un échec ne déclenche pas un retry invisible :
le renvoi explicite crée une nouvelle version d’invitation et une nouvelle tentative.

Cette table fournit l’idempotence des renvois, la limitation durable et le diagnostic minimal en attendant l’audit
append-only de 2.4. Elle n’est pas présentée comme un journal d’audit réglementaire.

### 13.4 `memberships` et `users`

- l’acceptation crée une appartenance Admin active ;
- `memberships.created_by` reçoit l’acteur ayant émis l’invitation ;
- une cible unique `(organization_id, id)` est ajoutée pour les références composites ;
- l’acceptation par un compte existant incrémente `users.version` ;
- aucune suppression physique n’est accordée au rôle applicatif.

### 13.5 Downgrade

Le downgrade vers 0003 est autorisé seulement si aucune organisation `provisioning`, aucune invitation enrichie et
aucune tentative de livraison utile n’existent. Il échoue de manière explicite plutôt que de supprimer ou transformer
silencieusement des données. Le parcours base vide `upgrade -> downgrade -> upgrade` reste testé.

## 14. Fonctions SQL et RLS

### 14.1 Contexte acteur sans locataire

2.3.2 introduit un contexte serveur :

```text
ActorContext(actor_id, request_id)
```

Il pose `app.actor_id` et `app.request_id` avec `set_config(..., true)` dans une transaction, mais aucun
`app.organization_id`. Il sert uniquement aux opérations plateforme. Une route ne peut pas construire ce contexte
depuis le corps HTTP.

### 14.2 Fonctions privilégiées minimales

Les responsabilités sont séparées entre fonctions étroites :

- provisionner une organisation et sa première invitation ;
- lister les métadonnées de provisioning ;
- préparer un renvoi ou une révocation ;
- résoudre une prévisualisation depuis un hash valide ;
- accepter pour un nouveau compte ;
- accepter pour le compte courant ;
- finaliser une tentative de livraison sur sa version d’invitation.

Chaque fonction :

- est détenue par `prospect_rls_definer` ;
- fixe `search_path` aux schémas de confiance puis `pg_temp` ;
- qualifie toutes les relations ;
- n’utilise aucun SQL dynamique ;
- révoque `EXECUTE` à `PUBLIC` ;
- accorde seulement sa signature à `prospect_app` ;
- vérifie en base l’acteur, l’état ou le hash requis ;
- retourne le minimum nécessaire au cas d’utilisation ;
- n’accepte jamais un jeton brut ou un mot de passe brut.

### 14.3 Politiques

`invitation_delivery_attempts` reçoit `ENABLE` et `FORCE ROW LEVEL SECURITY`, avec `USING` et `WITH CHECK` sur
`organization_id`. Les politiques existantes des organisations, appartenances et invitations restent actives.

Le rôle Web ne reçoit ni propriété, ni `BYPASSRLS`, ni accès direct transversal. Les opérations plateforme et anonymes
ne sont possibles qu’à travers les fonctions accordées.

## 15. Architecture Clean Architecture

### 15.1 Domaine

Le domaine ajoute, sans dépendance à FastAPI, SQLAlchemy, Redis ou SMTP :

- `OrganizationStatus.PROVISIONING` ;
- `InvitationKind`, état calculé et règles de transition ;
- `InvitationDeliveryStatus` ;
- politique d’activation du premier Administrateur ;
- décisions de renvoi, révocation et acceptation ;
- erreurs métier stables.

### 15.2 Cas d’utilisation

- `CreateOrganization` ;
- `ListPlatformOrganizations` ;
- `PreviewInvitation` ;
- `AcceptInvitation` ;
- `ResendInitialInvitation` ;
- `RevokeInitialInvitation`.

Les routes font uniquement validation HTTP, dépendances de sécurité, appel du cas d’utilisation et mapping de réponse.

### 15.3 Ports

- `PlatformOrganizationProvisioner` ;
- `InvitationResolver` ;
- `InvitationTokenGenerator` ;
- `InvitationDelivery` ;
- `InvitationRateLimiter` ;
- `ActorUnitOfWorkFactory` ;
- extension `SessionStore.rotate(...)` ;
- ports existants `PasswordHasher` et `Clock`.

### 15.4 Adaptateurs

- PostgreSQL pour les fonctions et transactions ;
- générateur `secrets` pour les jetons base64url ;
- Redis pour la limitation des prévisualisations et acceptations ;
- SMTP Mailpit pour le développement local ;
- adaptateur de capture déterministe dans les tests unitaires.

Le domaine et l’application n’importent ni `smtplib`, ni SQLAlchemy, ni client Redis.

## 16. Contrat API consolidé

| Méthode et route | Authentification | Idempotence |
| --- | --- | --- |
| `GET /api/platform/organizations` | plateforme | lecture |
| `POST /api/platform/organizations` | plateforme + CSRF | `creation_request_id` |
| `POST /api/platform/organizations/{id}/first-invitation/resend` | plateforme + CSRF | `resend_request_id` |
| `POST /api/platform/organizations/{id}/first-invitation/revoke` | plateforme + CSRF | état idempotent |
| `POST /api/auth/invitations/preview` | publique, origine fiable | lecture |
| `POST /api/auth/invitations/accept` | publique nouvelle ou session correspondante | jeton à usage unique |

Conventions communes :

- schémas Pydantic stricts, champs inconnus refusés ;
- tailles maximales avant tout hash ou accès base ;
- `Cache-Control: private, no-store` pour la plateforme et `no-store` pour l’invitation ;
- aucun secret dans l’URL HTTP, la réponse ou le message d’erreur ;
- toutes les erreurs utilisent le contrat commun et un `request_id` ;
- aucune route ne renvoie de trace SQL, Redis ou SMTP.

### 16.1 Erreurs attendues

| HTTP | Code | Usage |
| --- | --- | --- |
| `400` | `invitation_invalid` | jeton inconnu, expiré, révoqué ou utilisé |
| `401` | `authentication_required` | route plateforme sans session |
| `401` | `invitation_authentication_required` | compte existant sans sa session |
| `403` | `insufficient_capability` | acteur non plateforme |
| `403` | `invitation_account_mismatch` | session d’un autre compte |
| `409` | `session_conflict` | création de compte demandée avec une autre session active |
| `409` | `idempotency_key_reused` | même UUID, commande différente |
| `409` | `invitation_already_accepted` | révocation après acceptation |
| `409` | `membership_reactivation_required` | appartenance désactivée existante |
| `429` | `invitation_rate_limited` | limitation de tentative ou de renvoi |
| `503` | `invitation_service_unavailable` | PostgreSQL, Redis ou livraison indisponible |
| `503` | `provisioning_outcome_unknown` | résultat post-commit non finalisable |

Les erreurs d’invitation invalides ne distinguent jamais la cause dans le message public.

## 17. Page React d’acceptation

2.3.2 livre uniquement la page fonctionnelle `/accept-invitation`, sans navigation d’administration ni refonte de
l’écran de recherche.

Un utilisateur authentifié sans organisation et sans rôle plateforme n’est jamais dirigé vers la recherche. Hors du
parcours d’invitation, un état contrôlé « Aucune organisation accessible » lui permet uniquement de se déconnecter ou
de revenir au lien d’invitation. Cet état n’ajoute aucune capacité locataire.

Avant même `createRoot(...).render(...)`, un petit bootstrap synchrone :

1. lire le fragment `#token=...` ;
2. le retirer immédiatement avec `history.replaceState` avant tout appel réseau ;
3. transmettre le jeton à l’application en mémoire seulement ;
4. le composant le conserve dans une référence mémoire et appelle la prévisualisation une seule fois ;
5. ne jamais écrire le jeton dans l’état persistant, un journal ou une télémétrie.

La page et le document appliquent `Referrer-Policy: no-referrer`.
Un garde explicite empêche React Strict Mode de déclencher deux prévisualisations en développement. La référence est
vidée après acceptation réussie ou erreur terminale et disparaît au démontage.

### 17.1 Nouveau compte

La page affiche le nom d’organisation, le rôle, l’expiration, un nom affiché et deux champs de mot de passe. Après
succès, `AuthProvider` reçoit la nouvelle session et redirige vers l’application.

### 17.2 Compte existant

- si la bonne session existe, l’utilisateur confirme l’acceptation ;
- sans session, un formulaire de connexion intégré à la page utilise le cas d’usage de connexion existant ;
- un compte sans appartenance reçoit une session restreinte, reste sur cette page et ne voit aucune route locataire ;
- le parcours ne change pas de page avant l’acceptation, afin que le jeton reste uniquement en mémoire ;
- si un autre compte est connecté, la page demande de se déconnecter puis de se connecter avec le compte destinataire,
  sans afficher l’adresse invitée.

Le jeton n’est jamais placé dans `localStorage`, `sessionStorage`, IndexedDB, un cookie ou un paramètre de requête.

## 18. Configuration proposée

| Variable | Défaut local | Règle |
| --- | --- | --- |
| `INVITATION_TTL_SECONDS` | `259200` | déjà présente, 72 heures |
| `INVITATION_DELIVERY_BACKEND` | `mailpit` | `mailpit` seulement en développement/test |
| `INVITATION_FROM_EMAIL` | `no-reply@prospect.local` | adresse d’expédition locale |
| `INVITATION_SMTP_HOST` | `127.0.0.1` | jamais dérivé de la requête |
| `INVITATION_SMTP_PORT` | `1025` | entier borné |
| `INVITATION_SMTP_TIMEOUT_SECONDS` | `5` | aucun retry automatique dans la requête |
| `INVITATION_ATTEMPT_WINDOW_SECONDS` | `900` | fenêtre preview/accept |
| `INVITATION_ATTEMPT_ADDRESS_MAX` | `30` | maximum par adresse pseudonymisée |
| `INVITATION_ATTEMPT_TOKEN_MAX` | `10` | maximum par hash de jeton |
| `INVITATION_RESEND_COOLDOWN_SECONDS` | `60` | minimum entre renvois |
| `INVITATION_RESEND_WINDOW_SECONDS` | `86400` | fenêtre durable |
| `INVITATION_RESEND_MAX_PER_WINDOW` | `5` | maximum de renvois |
| `RATE_LIMIT_HMAC_KEY` | aucun | secret aléatoire d’au moins 32 octets, partagé avec le limiteur de connexion |

`PUBLIC_APP_URL` existe déjà et doit rester une origine absolue sans chemin, requête ni fragment. Le serveur n’utilise
jamais `Host`, `Origin` ou `Referer` pour fabriquer le lien.

Les secrets futurs d’un fournisseur ne seront ni ajoutés à `.env.example` avec une valeur réelle, ni exposés par les
routes de santé.

Le limiteur de connexion existant est adapté pour utiliser la même clé HMAC au lieu d’un SHA-256 non secret de
l’adresse. Cette clé est obligatoire en staging et production ; les tests injectent une valeur fixe et le poste local
utilise une valeur générée dans `.env`, jamais versionnée. Sa rotation remet seulement les compteurs Redis à zéro.

La disponibilité SMTP ne participe pas à `/api/health/ready`, afin qu’une panne de courriel ne rende pas la recherche
et la connexion indisponibles. La commande de provisioning contrôle sa propre configuration et traduit son propre
échec de transport.

## 19. Sécurité, confidentialité et journalisation

### 19.1 Données interdites dans les journaux

- jeton brut ou hash de jeton ;
- fragment ou lien complet d’invitation ;
- corps des commandes d’acceptation ;
- mot de passe ou hash Argon2id ;
- cookie et CSRF ;
- corps du courriel ;
- réponse SMTP brute ;
- courriel destinataire lorsqu’un identifiant interne suffit.

### 19.2 Données techniques autorisées

- `request_id` ;
- identifiants internes d’organisation, invitation et tentative ;
- action normalisée ;
- résultat, durée et code d’erreur borné ;
- état de livraison sans détail fournisseur.

### 19.3 En-têtes et navigateur

- toutes les réponses de l’incrément portent `X-Content-Type-Options: nosniff` via le middleware commun ;
- les réponses ne sont pas mises en cache ;
- la page d’acceptation applique `no-referrer` ;
- aucune ressource tierce n’est chargée sur la page d’acceptation ;
- le jeton est supprimé de l’adresse avant prévisualisation ;
- les tests inspectent tous les stockages Web.

## 20. Atomicité et reprises

| Incident | État conservé | Reprise sûre |
| --- | --- | --- |
| PostgreSQL échoue avant commit | rien | répéter la même commande |
| Adaptateur absent ou interdit avant écriture | rien | corriger la configuration puis répéter |
| SMTP échoue après création | organisation `provisioning`, invitation `failed` | renvoi explicite avec nouveau UUID |
| réponse HTTP perdue | résultat possiblement validé | répéter le même UUID |
| finalisation de livraison échoue | tentative `pending` possible | relire, ne pas renvoyer implicitement |
| Redis échoue avant acceptation | rien | réessayer après retour Redis |
| Redis échoue après acceptation | organisation active, invitation utilisée | se connecter normalement |
| deux acceptations concurrentes | une seule appartenance | la seconde reçoit `invitation_invalid` |
| compte créé concurremment | invitation encore active | s’authentifier avec ce compte |

Aucune reprise ne crée silencieusement une deuxième organisation ni ne réutilise un ancien lien.

## 21. Tests obligatoires

### 21.1 Domaine et cas d’utilisation

- transitions de l’organisation et de l’invitation ;
- acceptation initiale activant exactement une fois ;
- nouveau compte, compte existant et compte incorrect ;
- connexion d’un compte actif sans appartenance produisant zéro capacité ;
- appartenance désactivée jamais réactivée ;
- jeton expiré, révoqué, utilisé et remplacé ;
- même clé/même commande et même clé/commande différente ;
- échec SMTP, échec de finalisation et échec Redis après commit ;
- limite de renvoi et délai minimal.

### 21.2 PostgreSQL réel

- migration base vide vers `head` ;
- précontrôle de rétroalimentation des organisations historiques ;
- downgrade sans donnée, puis ré-upgrade ;
- downgrade refusé avec donnée non convertible ;
- deux créations concurrentes avec un seul `creation_request_id` ;
- deux acceptations concurrentes avec une seule appartenance ;
- unicité globale du courriel face à une course ;
- ancien hash invalide après renvoi ;
- résultat SMTP tardif incapable d’écraser une invitation plus récente ;
- limite de renvoi conservée après redémarrage applicatif ;
- absence de visibilité directe sans contexte ;
- fonctions refusées à un acteur non plateforme ;
- rôle applicatif toujours non propriétaire et sans `BYPASSRLS` ;
- RLS `ENABLE` et `FORCE` sur la nouvelle table ;
- aucune permission `DELETE` ajoutée ;
- `alembic check` vert.

### 21.3 API

- création `201`, replay `200`, conflit `409` ;
- réponse et OpenAPI sans jeton ni hash ;
- création refusée à un utilisateur non plateforme ;
- liste plateforme limitée aux métadonnées ;
- prévisualisation sans courriel ;
- toutes les invalidités de jeton avec le même code public ;
- compte existant impossible sans session correspondante et CSRF ;
- nouveau compte refusé si un compte apparaît concurremment ;
- rotation de session et nouveau CSRF après acceptation ;
- renvoi idempotent et ancien lien refusé ;
- révocation répétée idempotente ;
- `no-store`, origine fiable et JSON strict sur toutes les routes ;
- clés Redis ne contenant ni adresse réseau, ni courriel, ni jeton brut ;
- zéro secret dans les erreurs capturées et les journaux de test.

### 21.4 Mailpit et adaptateur

- un seul message pour une création, même en cas de replay HTTP ;
- un seul message pour un même `resend_request_id` ;
- lien construit depuis `PUBLIC_APP_URL` avec fragment ;
- ancien lien invalidé avant le message de renvoi ;
- absence de mot de passe et d’identifiants internes dans le message ;
- refus du backend Mailpit en staging/production ;
- ports Compose liés à `127.0.0.1`.

### 21.5 Frontend

- fragment retiré avant l’appel de prévisualisation ;
- jeton conservé en mémoire seulement ;
- rendu nouveau compte et compte existant ;
- connexion intégrée puis acceptation sans navigation intermédiaire ;
- session restreinte sans organisation affichant l’état contrôlé, jamais l’écran de recherche ;
- gestion accessible des erreurs `400`, `401`, `403`, `409`, `429` et `503` ;
- mise à jour d’`AuthProvider` après succès ;
- aucun appel si le fragment est absent ou mal formé ;
- absence de jeton dans `localStorage`, `sessionStorage`, IndexedDB, cookie et historique ;
- aucune régression visuelle de l’écran Google.

### 21.6 Non-régression

- Ruff et format ;
- mypy strict ;
- pytest avec PostgreSQL et Redis réels, sans test ignoré ;
- ESLint ;
- Vitest ;
- build Vite ;
- protections RLS 2.3.1 ;
- authentification 2.2 ;
- limitation de connexion toujours atomique après passage au HMAC ;
- un seul Text Search, vingt résultats, aucun contact, aucune pagination ;
- aucune route d’export historique ;
- aucune persistance Google ;
- carte facturable toujours protégée selon le comportement actuellement livré.

Le rapport d’implémentation enregistrera les nouveaux nombres de tests. Les références actuelles de 83 tests backend
et 15 tests React doivent uniquement augmenter, jamais être remplacées par des tests ignorés.

## 22. Validation locale prévue

Après implémentation, le protocole remis au responsable produit permettra de :

1. démarrer PostgreSQL, Redis et Mailpit ;
2. provisionner les rôles et appliquer la migration 0004 ;
3. démarrer le backend et le frontend ;
4. se connecter comme Administrateur de plateforme ;
5. créer une organisation avec un UUID de requête ;
6. vérifier dans Mailpit qu’un seul courriel existe ;
7. ouvrir le lien et créer le premier compte Admin ;
8. constater la connexion et l’état `active` ;
9. créer une seconde organisation vers ce même courriel ;
10. tester le parcours du compte existant ;
11. tester un renvoi, l’invalidité de l’ancien lien et une révocation ;
12. exécuter toute la matrice qualité.

La page plateforme complète étant prévue en 2.3.5, la création sera testée dans 2.3.2 avec un script PowerShell local
documenté qui appelle l’API réelle avec cookie et CSRF. Ce script ne contournera ni les routes ni les autorisations.

## 23. Ordre d’implémentation proposé

1. domaine, erreurs et ports ;
2. migration 0004, droits, fonctions et tests PostgreSQL ;
3. générateur de jetons, cas d’utilisation et adaptateur de capture ;
4. Mailpit Compose et adaptateur SMTP local ;
5. routes plateforme et invitations ;
6. rotation de session et scénarios post-commit ;
7. page React d’acceptation ;
8. tests d’intégration et non-régression ;
9. documentation locale et rapport d’implémentation ;
10. deux critiques expertes puis validation produit manuelle.

Chaque étape doit garder les contrôles déjà livrés verts. Le rôle propriétaire n’est jamais utilisé pour faire
fonctionner temporairement le serveur Web.

## 24. Double critique de la spécification

### 24.1 Revue sécurité et architecture

Risques identifiés puis traités :

- **prise de contrôle d’un compte existant par lien volé** : session du même courriel et CSRF obligatoires ;
- **fuite du jeton par URL ou stockage** : fragment, retrait immédiat, `no-referrer` et mémoire seulement ;
- **contournement de RLS par la plateforme** : fonctions séparées, ACL explicites et résultat minimal ;
- **brute force d’un jeton** : 256 bits, réponse générique et limitation fermée par Redis ;
- **double acceptation** : verrou de ligne, état relu dans la transaction et jeton à usage unique ;
- **course sur le courriel global** : contrainte PostgreSQL et repli vers l’authentification du compte existant ;
- **ancienne session privilégiée** : incrément de version avant rotation Redis ;
- **compte actif sans organisation bloqué** : session restreinte sans capacité, acceptée uniquement par les routes
  d’identité et refusée par toutes les dépendances locataires ;
- **abus de renvoi** : idempotence, délai et plafond durable en PostgreSQL.

Risque résiduel accepté pour le développement : Mailpit contient nécessairement le lien brut dans le message local.
Il est donc lié à la boucle locale, alimenté uniquement par des données de test et interdit hors développement/test.

### 24.2 Revue exploitation et maintenabilité

Risques identifiés puis traités :

- **transaction base/courriel non atomique** : commit avant SMTP, états de tentative et renvoi explicite ;
- **requête HTTP répétée** : UUID durable et empreinte de commande ;
- **retour SMTP tardif** : versions immuables, chacune finalisant uniquement sa propre tentative ;
- **replay d’un renvoi** : table de tentatives avec `request_id` unique ;
- **perte Redis après acceptation** : version utilisateur invalidant l’ancienne session et reconnexion possible ;
- **migration historique ambiguë** : rétroalimentation déterministe ou arrêt explicite ;
- **downgrade destructif** : refus en présence de données non convertibles ;
- **périmètre trop large** : seule la page d’acceptation est livrée, l’administration complète reste en 2.3.5.

Risque résiduel : l’absence de page plateforme rend le test manuel de création moins convivial dans 2.3.2. Un script
local passant par l’API réelle est retenu afin de garder l’incrément testable sans dupliquer prématurément l’interface
prévue en 2.3.5.

## 25. Décisions détaillées validées

Les décisions 1 à 16 de la spécification 2.3 étaient déjà validées et ne sont pas soumises une seconde fois. Les
décisions suivantes complètent le contrat obligatoire de 2.3.2 :

1. Limiter 2.3.2 à la première invitation Admin ; les invitations de membres d’une organisation active restent en
   2.3.3.
2. Conserver `creation_request_id` dans le corps JSON, avec une empreinte canonique pour détecter la réutilisation avec
   une commande différente.
3. Valider organisation, invitation et tentative en base avant l’appel SMTP, sans garder la transaction ouverte.
4. Ne jamais annuler l’organisation après un échec SMTP ; exposer `failed` et imposer un renvoi explicite.
5. Créer `invitation_delivery_attempts` sans jeton ni courriel pour l’idempotence, la limitation et le diagnostic.
6. Exiger `resend_request_id`, une minute entre renvois et cinq renvois maximum sur 24 heures ; limiter aussi
   preview/accept à 30 requêtes par HMAC d’adresse et 10 par hash de jeton sur 15 minutes par défaut, avec une clé HMAC
   partagée par les limiteurs d’identité.
7. Révoquer l’ancienne invitation puis créer une nouvelle version immuable, avec un nouveau hash, avant l’envoi du
   nouveau message.
8. Livrer dès 2.3.2 la page minimale `/accept-invitation`, tout en laissant les pages d’administration à 2.3.5.
9. Garder le jeton uniquement dans une référence mémoire et supprimer le fragment avant tout appel réseau.
10. Pour un compte existant, exiger la session correspondante et le CSRF, autoriser une session restreinte sans
    organisation ni capacité, et ne jamais accepter un mot de passe dans la commande d’acceptation.
11. Incrémenter `users.version` dans l’acceptation existante avant de faire tourner la session Redis.
12. Introduire `ActorContext` sans organisation et des fonctions SQL distinctes plutôt qu’un accès transversal aux
    tables.
13. Rétroalimenter `created_by` uniquement depuis une appartenance traçable et arrêter la migration si cela est
    impossible.
14. Lier Mailpit à `127.0.0.1`, utiliser uniquement des données de test et refuser cet adaptateur en staging/production.
15. Tester la création plateforme avec un script local passant par l’API réelle jusqu’à la livraison de la page 2.3.5.
16. Conserver tous les contrôles 2.3.1, 2.2 et Google verts avant toute validation produit de 2.3.2.

Ces seize décisions détaillées ont été validées par le responsable produit le 23 juillet 2026. L’implémentation de
2.3.2 est autorisée ; toute dérogation devra être documentée et validée avant modification du code.

## 26. Définition de « prêt pour 2.3.3 »

2.3.2 sera terminé lorsque :

- les seize décisions de la section 25 sont implémentées sans dérogation non validée ;
- une base vide et une base 0003 compatible migrent vers 0004 ;
- le parcours Mailpit fonctionne pour un nouveau compte et un compte existant ;
- l’organisation ne s’active qu’avec sa première appartenance Admin ;
- les preuves de concurrence, RLS, secrets et idempotence sont vertes ;
- la matrice Ruff, mypy, pytest, ESLint, Vitest et build est entièrement verte ;
- deux critiques expertes de l’implémentation sont documentées ;
- le responsable produit a exécuté et accepté le protocole local.

## 27. Références internes

- [`PHASE_2_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_1_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_1_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_SPECIFICATIONS_DETAILLEES.md)
- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)
- [`../README.md`](../README.md)
