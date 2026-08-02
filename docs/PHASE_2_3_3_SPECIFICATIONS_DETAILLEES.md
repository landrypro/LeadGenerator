# Phase 2.3.3 — Spécifications détaillées des membres, capacités et organisations actives

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Incrément | 2.3.3 — Membres, capacités et changement d’organisation |
| Version | 1.0 |
| Date | 2 août 2026 |
| Statut | Implémenté et validé automatiquement ; validation locale produit attendue |
| Validation produit | 2 août 2026 |
| Prérequis | 2.3.2 implémenté, revu et validé localement de bout en bout |
| Référence supérieure | `PHASE_2_3_SPECIFICATIONS_DETAILLEES.md` version 1.4 |
| Changement de code | Aucun dans cette phase de spécification |

## 1. Clarification de numérotation

L’incrément 2.3.2 est déjà implémenté et son parcours local a été validé : provisioning, réception Mailpit,
acceptation et connexion du nouvel utilisateur fonctionnent. Le présent document spécifie donc le prochain incrément,
**2.3.3**, même si la demande initiale répétait le numéro 2.3.2.

Cette interprétation et les décisions de la section 26 ont été confirmées par le responsable produit le 2 août 2026.

## 2. Objectif

2.3.3 doit rendre exploitable une organisation active sans encore construire son interface d’administration complète.
Un Administrateur d’organisation doit pouvoir consulter et modifier l’organisation, inviter ses membres, gérer leurs
rôles et états, et un utilisateur appartenant à plusieurs organisations doit pouvoir changer de contexte actif.

L’incrément doit simultanément garantir que :

- aucun acteur ne peut lire ou modifier une autre organisation ;
- un Gestionnaire reste en lecture seule et un Commercial ne voit pas l’annuaire ;
- une organisation conserve toujours au moins un Administrateur actif ;
- toute réduction ou élévation effective de privilège invalide immédiatement les anciennes sessions concernées ;
- un changement d’organisation renouvelle uniquement la session courante ;
- aucune course PostgreSQL/Redis ne réactive un privilège ancien ou ne supprime une session plus récente par erreur.

## 3. Contrats hérités et non rouverts

Les décisions validées des sections 21 de la spécification 2.3 et 25 de la spécification 2.3.2 restent obligatoires.
En particulier :

- l’organisation active provient de la session, jamais du corps d’une commande locataire ;
- le rôle plateforme ne confère aucun accès locataire implicite ;
- l’administration d’une appartenance et le changement d’organisation utilisent `membership_id` ;
- aucune suppression physique d’organisation, de compte, d’appartenance ou d’invitation n’est permise ;
- le dernier Administrateur actif est protégé sous verrou transactionnel ;
- le rôle Web PostgreSQL demeure non propriétaire, sans `BYPASSRLS` ;
- les tables locataires conservent `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY` ;
- les fonctions privilégiées sont étroites, ont un `search_path` fixé et ne sont accordées que par signature ;
- les jetons d’invitation restent dans le fragment, en mémoire et sous forme de hash en base ;
- Mailpit reste strictement réservé au développement et aux tests ;
- les résultats Google et les protections facturables existantes ne sont pas modifiés dans cet incrément.

2.3.3 complète ces contrats ; il ne remplace ni 2.3.1 ni 2.3.2.

## 4. Périmètre

### 4.1 Inclus

- lecture et modification des métadonnées de l’organisation active ;
- liste paginée des membres de l’organisation active ;
- modification optimiste du rôle ou de l’état d’une appartenance ;
- protection concurrente du dernier Administrateur actif ;
- invitation d’un Administrateur, Gestionnaire ou Commercial dans une organisation active ;
- liste des invitations actionnables, renvoi et révocation ;
- acceptation d’une invitation de membre par un nouveau compte ou un compte existant ;
- changement d’organisation active par `membership_id` ;
- rotation atomique du cookie de session et du CSRF lors du changement d’organisation ;
- invalidation par version d’identité après une modification de privilège ;
- purge Redis sélective des sessions antérieures à une version donnée ;
- migration Alembic 0005, fonctions SQL, contrats API, tests et scripts locaux ;
- adaptation minimale de la page d’acceptation existante aux invitations de membre ;
- mise à jour de la documentation technique et du protocole de test local.

### 4.2 Explicitement différé

- pages React d’organisation, membres et invitations, livrées en 2.3.5 ;
- sélecteur visuel multi-organisation, livré en 2.3.5 ;
- authentification des routes Google et retrait du demandeur temporaire, livrés en 2.3.4 ;
- suspension d’organisation et audit append-only, livrés en 2.4 ;
- quotas Google partagés et règles commerciales de forfait, livrés en 2.6 ;
- fournisseur de courriel de production ;
- récupération d’un membre désactivé par simple invitation ;
- changement du courriel, du nom affiché ou du mot de passe par un Administrateur d’organisation ;
- suppression physique et transfert automatique de propriété ;
- recherche globale d’utilisateurs entre organisations ;
- historique complet des invitations terminales dans l’API ;
- données de prospects, pipeline, tâches, notes et documents.

## 5. Acteurs et matrice d’autorisation

### 5.1 Capacités locataires

| Capacité | Administrateur | Gestionnaire | Commercial |
| --- | --- | --- | --- |
| `organization:read` | oui | oui | oui |
| `organization:update` | oui | non | non |
| `members:read` | oui | oui | non |
| `members:manage` | oui | non | non |
| `invitations:read` | oui | non | non |
| `invitations:manage` | oui | non | non |
| `audit:read` | oui | oui | non |
| `google:search` | oui | oui | oui |

`audit:read` reste réservé à une route future. `google:search` reste calculée comme aujourd’hui, mais les routes Google
ne consommeront l’identité authentifiée qu’en 2.3.4.

La réponse d’authentification expose les capacités calculées côté serveur. Le frontend peut les utiliser pour préparer
2.3.5, mais leur présence dans le navigateur n’est jamais une autorisation.

### 5.2 Administrateur de plateforme

L’Administrateur de plateforme conserve ses capacités plateforme. Sans appartenance active dans l’organisation
courante, il ne peut appeler aucune route de la section 15. Il doit être explicitement invité comme tout autre membre.

### 5.3 Compte multi-organisation

Un même utilisateur global peut avoir plusieurs appartenances actives. Une session possède exactement zéro ou une
organisation active. Deux sessions du même utilisateur peuvent rester simultanément attachées à deux organisations
différentes, tant que la version d’identité et les appartenances restent valides.

## 6. États et invariants métier

### 6.1 Organisation

Les routes locataires de 2.3.3 exigent `status=active`. Une organisation `provisioning` ou `suspended` est refusée
avant le cas d’utilisation. 2.3.3 n’ajoute aucune transition d’état d’organisation.

### 6.2 Appartenance

États autorisés :

```text
création par acceptation -> active <-> disabled
```

- une ligne `(organization_id, user_id)` est unique et durable ;
- une appartenance n’est jamais supprimée ;
- `disabled` retire toutes les capacités dans cette organisation ;
- la réactivation se fait uniquement par modification administrative explicite, pas par une nouvelle invitation ;
- un changement sans effet ne modifie ni la version de l’appartenance ni celle de l’utilisateur ;
- une organisation active possède toujours au moins un membre `admin/active`.

### 6.3 Invitation de membre

- `invitation_kind=member` ;
- rôle proposé parmi `admin`, `manager` et `sales` ;
- organisation obligatoirement active ;
- une seule invitation non terminale par organisation et courriel normalisé ;
- une appartenance active produit un conflit ;
- une appartenance désactivée produit un conflit de réactivation explicite ;
- une invitation expirée est révoquée transactionnellement avant la création d’une nouvelle version ;
- une acceptation crée exactement une appartenance active avec le rôle de l’invitation ;
- elle ne change jamais l’état de l’organisation.

## 7. Modèle de données cible et migration 0005

### 7.1 `memberships`

Ajouter :

| Colonne | Type | Règle |
| --- | --- | --- |
| `updated_by` | UUID nullable puis non nul | utilisateur ayant effectué la dernière modification effective |
| `version` | entier non nul, défaut 1 | strictement positif et incrémenté à chaque modification effective |

La migration rétroalimente `updated_by=created_by` et `version=1`. Elle crée les contraintes et index utiles sans
retirer les contraintes d’unicité existantes.

### 7.2 `organizations`

Le champ `version` existant devient le verrou optimiste de `PATCH /api/organization`. Une modification effective
incrémente `version` et `updated_at`. Une commande sans effet retourne la ressource actuelle sans incrément.

### 7.3 `users`

`users.version` reste un **epoch de sécurité**, pas un numéro de profil :

- il est incrémenté après toute modification effective du rôle ou de l’état d’une appartenance de l’utilisateur ;
- il n’est pas incrémenté pour un changement volontaire d’organisation active ;
- il n’est pas incrémenté pour une commande sans effet ;
- toute session portant une version antérieure est refusée lors de la résolution d’identité.

### 7.4 Invitations et tentatives de livraison

Aucune copie de jeton, de hash ou de courriel n’est ajoutée à `invitation_delivery_attempts`. Le `request_id` unique,
l’invitation jointe et l’acteur permettent de reconnaître un replay identique et de refuser un UUID réutilisé pour une
autre commande.

### 7.5 Compatibilité et retour arrière

La migration doit être testée :

- sur une base vide ;
- sur une base 0004 contenant une organisation active, des membres et des invitations acceptées ;
- avec le rôle Web réellement non propriétaire ;
- en upgrade puis downgrade contrôlé.

Le downgrade refuse de perdre une information non représentable. Il ne supprime ni membre, ni invitation, ni
organisation.

## 8. Lecture et modification de l’organisation active

### 8.1 Lecture

`GET /api/organization` retourne uniquement :

```json
{
  "id": "018f0000-0000-7000-8000-000000000010",
  "name": "Entreprise Exemple",
  "locale": "fr-CA",
  "timezone": "America/Toronto",
  "status": "active",
  "version": 2,
  "created_at": "2026-08-02T15:00:00Z",
  "updated_at": "2026-08-02T15:10:00Z"
}
```

Les limites Google et les acteurs internes ne sont pas exposés dans cette ressource.

### 8.2 Modification

`PATCH /api/organization` accepte une commande stricte :

```json
{
  "name": "Entreprise Exemple Canada",
  "locale": "fr-CA",
  "timezone": "America/Toronto",
  "version": 2
}
```

- au moins un champ métier est obligatoire ;
- `version` est toujours obligatoire ;
- le nom est nettoyé et limité à 160 caractères ;
- la langue est `fr-CA` ou `en-CA` ;
- le fuseau doit exister dans la base IANA disponible au serveur ;
- un champ inconnu ou `organization_id` produit `422` ;
- une version périmée produit `409 organization_version_conflict` avec la version courante, sans données d’une autre
  organisation.

## 9. Liste des membres

`GET /api/organization/members?limit=25&cursor=...` retourne :

```json
{
  "items": [
    {
      "membership_id": "018f0000-0000-7000-8000-000000000011",
      "user": {
        "id": "018f0000-0000-7000-8000-000000000012",
        "email": "membre@example.ca",
        "display_name": "Membre Exemple"
      },
      "role": "manager",
      "status": "active",
      "version": 1,
      "created_at": "2026-08-02T15:00:00Z",
      "updated_at": "2026-08-02T15:00:00Z"
    }
  ],
  "next_cursor": null
}
```

- 25 éléments par défaut, 100 au maximum ;
- ordre stable `(created_at, membership_id)` ;
- curseur opaque signé selon le composant de pagination existant ;
- aucun filtre global par courriel ;
- une requête commence par les appartenances visibles sous RLS avant de joindre `users` ;
- un Commercial reçoit `403`, pas une liste vide ambiguë.

## 10. Modification d’un membre

`PATCH /api/organization/members/{membership_id}` reçoit :

```json
{
  "role": "sales",
  "status": "active",
  "version": 3
}
```

- `role` et `status` sont facultatifs, mais au moins l’un des deux est requis ;
- `version` est obligatoire ;
- seul un Administrateur actif peut modifier ;
- l’identifiant d’une autre organisation ou absent produit le même `404` ;
- une version périmée produit `409 membership_version_conflict` ;
- une commande identique retourne `200` sans incrément ni révocation ;
- le compte global et les autres appartenances ne sont jamais modifiés par effet secondaire.

### 10.1 Protection du dernier Administrateur

Une fonction SQL étroite effectue dans une seule transaction :

1. la vérification de l’acteur Administrateur actif ;
2. le verrouillage `FOR UPDATE` de l’organisation ;
3. le verrouillage de l’appartenance cible ;
4. la vérification de la version attendue ;
5. le calcul du nombre d’Administrateurs actifs après la modification ;
6. le refus `409 last_active_administrator` si le résultat serait zéro ;
7. la modification, l’incrément de `memberships.version` et de `users.version`.

Toutes les commandes administratives susceptibles de modifier le nombre d’Administrateurs actifs verrouillent
l’organisation avant l’appartenance, dans le même ordre. Deux retraits concurrents ne peuvent donc pas réussir
simultanément.

### 10.2 Auto-modification

Un Administrateur peut se rétrograder ou se désactiver uniquement si un autre Administrateur actif subsiste. Après
succès, la réponse métier est renvoyée puis le cookie courant est expiré : une nouvelle authentification est exigée.
Cela évite de continuer une requête avec des capacités devenues obsolètes.

## 11. Invitations de membres

### 11.1 Création

`POST /api/organization/invitations` reçoit :

```json
{
  "email": "nouveau@example.ca",
  "role": "manager",
  "invitation_request_id": "018f0000-0000-7000-8000-000000000013"
}
```

Règles :

- Administrateur actif, JSON strict, origine fiable et CSRF ;
- UUID d’idempotence obligatoire ;
- rôle `admin`, `manager` ou `sales` ;
- courriel normalisé par la fonction existante ;
- expiration de 72 heures ;
- adaptateur de livraison autorisé avant la première écriture ;
- commit PostgreSQL avant l’appel SMTP ;
- aucun jeton ou hash dans la réponse, OpenAPI ou les journaux.

Réponses : `201` pour une création, `200` pour un replay identique, `409` si le même UUID représente une autre
commande.

### 11.2 Conflits métier

| Situation | Résultat |
| --- | --- |
| appartenance active au même courriel | `409 membership_already_active` |
| appartenance désactivée | `409 membership_reactivation_required` |
| invitation active créée par une autre requête | `409 invitation_already_pending` |
| invitation expirée | révocation atomique puis nouvelle invitation |
| organisation non active | `409 organization_not_active` |

Aucune réponse ne révèle l’existence d’un compte global dans une autre organisation.

### 11.3 Liste

`GET /api/organization/invitations?limit=25&cursor=...` est réservé aux Administrateurs. Il retourne seulement la
version la plus récente des invitations non acceptées et non révoquées, avec un état calculé `active` ou `expired`.
Les invitations acceptées et révoquées restent en base pour le futur audit, mais ne sont pas exposées ici.

### 11.4 Renvoi et révocation

- `POST /api/organization/invitations/{invitation_id}/resend` reçoit `resend_request_id` ;
- `DELETE /api/organization/invitations/{invitation_id}` reçoit un corps JSON vide strict et exige CSRF ;
- le renvoi conserve une minute minimale et cinq renvois par 24 heures ;
- un renvoi révoque l’ancienne version avant de créer un nouveau jeton ;
- un replay du même `resend_request_id` ne renvoie pas un second courriel ;
- la révocation est idempotente pour la même invitation déjà révoquée ;
- un identifiant croisé produit `404`.

## 12. Acceptation d’une invitation de membre

Les routes publiques existantes restent inchangées :

- `POST /api/auth/invitations/preview` ;
- `POST /api/auth/invitations/accept`.

La fonction d’acceptation distingue désormais explicitement :

| Type | Organisation attendue | Effet |
| --- | --- | --- |
| `initial_administrator` | `provisioning` | crée l’Admin et active l’organisation |
| `member` | `active` | crée l’appartenance au rôle proposé, sans changer l’organisation |

Les garanties 2.3.2 restent applicables : jeton à usage unique, verrou de ligne, compte existant authentifié avec le
même courriel, nouveau compte atomique, mot de passe jamais transmis pour un compte existant, et ancien lien invalidé
après renvoi.

Si une appartenance est apparue concurremment, l’acceptation échoue sans réassigner ni réactiver la ligne. Après une
acceptation réussie, la nouvelle organisation devient l’organisation active de la nouvelle session ou de la session
renouvelée.

La page React existante adapte uniquement son texte à l’invitation de membre. Aucun annuaire ni formulaire
d’administration n’est ajouté dans 2.3.3.

## 13. Changement d’organisation active

`POST /api/auth/switch-organization` reçoit :

```json
{
  "membership_id": "018f0000-0000-7000-8000-000000000011"
}
```

### 13.1 Préconditions

- session active, JSON strict, origine fiable et CSRF courant ;
- appartenance appartenant à l’utilisateur courant ;
- appartenance `active` ;
- organisation `active` ;
- absence, appartenance croisée ou inaccessible produisant `404` ;
- appartenance désactivée ou organisation suspendue produisant `403`.

### 13.2 Effets

1. PostgreSQL enregistre `users.last_active_organization_id` sans incrémenter `users.version` ;
2. Redis remplace atomiquement l’ancienne session par une nouvelle ;
3. le cookie opaque, le CSRF et l’organisation active changent ;
4. l’ancien cookie est immédiatement inutilisable ;
5. la réponse est le contrat complet `AuthenticationResponse` actuel.

Les autres sessions du même utilisateur restent attachées à leur organisation respective. Un replay avec l’ancien
cookie échoue avec `401`.

### 13.3 Panne Redis

Si PostgreSQL a enregistré la préférence mais que Redis ne peut pas faire tourner la session :

- la route retourne `503` ;
- l’ancienne session conserve son ancienne organisation active ;
- aucune capacité de la nouvelle organisation n’est accordée ;
- une reconnexion peut reprendre la préférence PostgreSQL si l’appartenance reste valide.

## 14. Sessions, versions et concurrence inter-stockages

### 14.1 Autorité de sécurité

La comparaison `session.user_version == users.version` demeure la barrière de sécurité. Redis accélère la révocation,
mais son nettoyage ne conditionne jamais l’invalidité logique d’une session ancienne.

### 14.2 Purge sélective

Le port `SessionStore` remplace l’usage administratif de `revoke_user(user_id)` par :

```python
revoke_user_before_version(user_id, minimum_valid_version)
```

Un script Redis atomique parcourt l’index des sessions de l’utilisateur, décode chaque enregistrement et ne supprime
que les sessions dont `user_version < minimum_valid_version`. Une entrée absente ou corrompue est nettoyée sans
supprimer une session valide plus récente.

Cette règle évite la course suivante : modification du rôle, nouvelle connexion à la version courante, puis purge
tardive supprimant par erreur cette nouvelle session.

### 14.3 Échec de purge

Après le commit PostgreSQL, un échec Redis :

- ne rétablit pas l’ancien rôle ;
- n’annule pas la réponse métier réussie ;
- est journalisé avec `request_id`, `user_id`, version minimale et code technique sans secret ;
- laisse les anciennes sessions refusées au prochain appel par la vérification de version.

### 14.4 Rotation et révocation

- changement volontaire d’organisation : rotation de la seule session courante ;
- acceptation d’une invitation par compte existant : incrément de version, rotation courante, puis purge des autres
  sessions antérieures à la nouvelle version ;
- rôle ou état modifié par un tiers : incrément de version puis purge sélective des anciennes sessions ;
- auto-rétrogradation ou auto-désactivation : cookie courant expiré et réauthentification obligatoire ;
- déconnexion : révocation de la seule session courante.

## 15. Contrat API consolidé

| Méthode et route | Capacité | Résultat principal |
| --- | --- | --- |
| `GET /api/organization` | `organization:read` | organisation active |
| `PATCH /api/organization` | `organization:update` | organisation mise à jour |
| `GET /api/organization/members` | `members:read` | page de membres |
| `PATCH /api/organization/members/{membership_id}` | `members:manage` | appartenance mise à jour |
| `GET /api/organization/invitations` | `invitations:read` | invitations actionnables |
| `POST /api/organization/invitations` | `invitations:manage` | invitation créée ou rejouée |
| `POST /api/organization/invitations/{id}/resend` | `invitations:manage` | nouvelle version envoyée |
| `DELETE /api/organization/invitations/{id}` | `invitations:manage` | invitation révoquée |
| `POST /api/auth/switch-organization` | session | nouvelle session et nouvel état d’authentification |

Conventions communes :

- aucune commande locataire ne contient `organization_id` ;
- modèles Pydantic stricts avec champs inconnus refusés ;
- mutations authentifiées avec JSON, origine fiable et CSRF ;
- réponses d’identité avec `Cache-Control: private, no-store` ;
- `401` sans session valide, `403` sans capacité, `404` pour absent ou croisé, `409` pour conflit métier ou version,
  `422` pour commande invalide, `429` pour limite d’invitation et `503` pour dépendance indisponible ;
- un `request_id` commun traverse route, cas d’utilisation, transaction et journal technique ;
- aucun détail SQL, Redis, SMTP ou secret dans les erreurs publiques.

## 16. Architecture applicative

### 16.1 Domaine

Ajouter des modèles immuables pour l’organisation éditable, le membre, la page de membres, l’invitation de membre et
les commandes validées. Les règles de transition et de capacité restent indépendantes de FastAPI, SQLAlchemy et
Redis.

### 16.2 Ports et cas d’utilisation

Prévoir des ports orientés cas d’utilisation :

- `OrganizationAdministrationGateway` ;
- `MemberAdministrationGateway` ;
- extension contrôlée des ports d’invitation ;
- extension du `SessionStore` pour la purge par version.

Cas d’utilisation distincts : lecture/modification de l’organisation, liste/modification des membres, liste/création/
renvoi/révocation des invitations, acceptation étendue et changement d’organisation.

### 16.3 Adaptateurs

PostgreSQL implémente les transactions et RLS ; Redis implémente la rotation et la purge atomiques ; Mailpit conserve
la livraison locale ; FastAPI ne manipule directement aucun client d’infrastructure.

### 16.4 Composition

`create_app()` construit et injecte les nouveaux cas d’utilisation. Les routes dépendent de protocoles et de
dépendances d’autorisation. Aucun singleton ne porte un contexte utilisateur mutable.

## 17. PostgreSQL, RLS et fonctions privilégiées

### 17.1 Contexte locataire

Chaque unité de travail pose transactionnellement `actor_id`, `organization_id` et `request_id`. Le contexte est
effacé au commit ou rollback et ne peut contaminer une connexion remise au pool.

### 17.2 Politiques

- `organizations` : seule la ligne correspondant au contexte est visible ;
- `memberships`, `user_invitations`, `invitation_delivery_attempts` : seules les lignes du contexte sont visibles ;
- `WITH CHECK` empêche de déplacer une ligne vers une autre organisation ;
- aucune politique permissive nouvelle ne rend les lignes globales visibles ;
- les contraintes d’intégrité ne sont jamais présentées comme une protection de confidentialité.

### 17.3 Fonctions

Les fonctions de modification du membre, d’invitation et d’acceptation :

- utilisent un `search_path` explicite ;
- qualifient les objets système nécessaires ;
- vérifient l’acteur et son appartenance en base ;
- verrouillent les ressources dans un ordre documenté ;
- retournent le minimum requis ;
- ne reçoivent jamais cookie, CSRF, mot de passe ou jeton brut ;
- révoquent `EXECUTE` à `PUBLIC` puis accordent uniquement les signatures requises à `prospect_app`.

## 18. Sécurité et confidentialité

- l’autorisation est recalculée sur chaque requête sensible ;
- une capacité frontend n’est jamais suffisante ;
- les réponses croisées sont minimisées en `404` ;
- les courriels sont visibles seulement aux rôles autorisés dans leur organisation active ;
- aucun jeton d’invitation ne sort de l’adaptateur de livraison ou de la mémoire du parcours d’acceptation ;
- le changement de privilège renouvelle ou invalide la session conformément à l’epoch de sécurité ;
- le journal technique exclut cookie, CSRF, mot de passe, jeton, hash de jeton et contenu Google ;
- aucune donnée de membre ou d’invitation n’est stockée dans le navigateur ;
- les en-têtes `no-store` restent obligatoires ;
- les protections Google existantes doivent rester strictement inchangées et vertes.

## 19. Observabilité transitoire

En attendant l’audit append-only de 2.4, journaliser de manière structurée :

- `request_id`, action, résultat, durée ;
- `actor_user_id`, `organization_id`, `membership_id` ou `invitation_id` si pertinent ;
- ancien et nouveau rôle/état sous forme de valeurs métier non secrètes ;
- version attendue et version résultante ;
- statut de purge Redis sans token de session ;
- statut de livraison sans jeton ni détail SMTP sensible.

Ces traces techniques ne remplacent pas l’audit métier. La production des fonctions administratives reste
conditionnée à la livraison de 2.4.

## 20. Tests obligatoires

### 20.1 Domaine et capacités

- matrice exacte des trois rôles ;
- aucun accès locataire implicite pour `platform_admin` ;
- validation des rôles, états, langues, fuseaux et versions ;
- commande sans effet sans incrément ;
- sélection déterministe de l’organisation active.

### 20.2 PostgreSQL et RLS réels

- aucune ligne visible sans contexte ;
- organisation A incapable de lire ou modifier B ;
- `WITH CHECK` bloquant une écriture croisée ;
- rôle Web non propriétaire, sans `BYPASSRLS` ni `DELETE` ;
- contexte effacé après commit, rollback et réutilisation du pool ;
- fonctions avec ACL et `search_path` exacts ;
- migration vide et migration depuis 0004 avec données ;
- downgrade non destructif ;
- deux rétrogradations concurrentes laissant exactement un Administrateur actif ;
- modification et acceptation concurrentes sans appartenance dupliquée.

### 20.3 API et autorisations

- Administrateur lisant et modifiant organisation, membres et invitations ;
- Gestionnaire lisant les membres, mais refusé pour organisation, membres et invitations en écriture ;
- Commercial refusé pour membres et invitations ;
- identifiant croisé retournant `404` ;
- `organization_id` injecté retournant `422` ;
- conflits de versions retournant `409` ;
- création, replay et collision d’UUID d’invitation ;
- appartenance active, désactivée et invitation déjà active ;
- renvoi idempotent et ancien lien invalide ;
- révocation répétée sans courriel supplémentaire ;
- aucune donnée terminale exposée par la liste courante.

### 20.4 Acceptation

- nouveau compte invité comme Admin, Gestionnaire et Commercial ;
- compte existant pour les trois rôles ;
- rôle de l’invitation exactement conservé ;
- organisation active inchangée ;
- organisation `provisioning` ou `suspended` refusée pour une invitation de membre ;
- appartenance apparue concurremment refusée ;
- appartenance désactivée non réactivée implicitement ;
- un seul usage du jeton et ancien lien refusé après renvoi ;
- session et CSRF renouvelés après acceptation existante.

### 20.5 Sessions et changement d’organisation

- changement vers chaque appartenance active ;
- ancien cookie refusé et nouveau CSRF obligatoire ;
- autre session du même utilisateur non modifiée ;
- appartenance d’un autre utilisateur, désactivée ou organisation non active refusée ;
- panne Redis n’accordant jamais la nouvelle organisation ;
- changement de rôle incrémentant `users.version` ;
- ancienne session refusée avant même la purge Redis ;
- purge supprimant uniquement les versions antérieures ;
- connexion concurrente à la nouvelle version survivant à une purge tardive ;
- auto-rétrogradation expirant le cookie courant.

### 20.6 Frontend et confidentialité

- page d’acceptation affichant correctement une invitation de membre ;
- aucun double appel de prévisualisation sous React StrictMode ;
- jeton retiré du fragment et conservé uniquement en mémoire ;
- mise à jour d’`AuthProvider` après acceptation ;
- aucun `localStorage`, `sessionStorage`, IndexedDB ou service worker ;
- aucune régression visuelle ou fonctionnelle de l’écran Google.

### 20.7 Matrice qualité

Avant validation :

- migration Alembic et `alembic check` ;
- Ruff et format ;
- mypy strict ;
- pytest unitaire et intégration PostgreSQL/Redis réels, sans test ignoré ;
- ESLint ;
- Vitest ;
- build Vite ;
- tests Google historiques ;
- vérification que la route d’export historique reste absente.

Le rapport d’implémentation enregistrera les nombres réels de tests au lieu de recopier un ancien total.

## 21. Protocole local prévu

La validation manuelle de 2.3.3 devra permettre de :

1. migrer une base 0004 vers 0005 et confirmer `alembic current` ;
2. démarrer PostgreSQL, Redis, Mailpit, backend et frontend ;
3. se connecter avec l’Administrateur créé pendant 2.3.2 ;
4. créer par script une invitation Manager puis l’accepter dans le navigateur ;
5. créer une invitation Commercial puis l’accepter avec un compte existant ;
6. lister les membres et vérifier les capacités de chaque rôle ;
7. modifier un rôle et constater que l’ancienne session est refusée ;
8. tenter de retirer le dernier Administrateur et constater le conflit ;
9. ajouter un second Administrateur puis réussir l’auto-rétrogradation avec reconnexion obligatoire ;
10. connecter un utilisateur commun à deux organisations et changer de contexte ;
11. vérifier que l’ancien cookie et l’ancien CSRF sont refusés ;
12. tester renvoi, ancien lien, révocation et Mailpit ;
13. exécuter la matrice qualité complète.

Jusqu’à 2.3.5, des scripts PowerShell documentés appellent exclusivement les vraies routes HTTP. Ils ne lisent pas la
base, ne contournent pas RLS et n’affichent aucun jeton.

## 22. Ordre d’implémentation proposé

1. fermer les écarts documentaires de 2.3.2 et améliorer l’erreur CLI de mot de passe court ;
2. domaine, capacités, erreurs et ports ;
3. migration 0005, fonctions SQL et preuves de concurrence/RLS ;
4. organisation et membres côté application/API ;
5. invitations de membres et acceptation étendue ;
6. purge Redis par version et changement d’organisation ;
7. adaptation minimale de la page d’acceptation ;
8. scripts et protocole local ;
9. non-régression complète ;
10. trois critiques et deux revues de code, puis validation produit.

Chaque étape garde les contrôles antérieurs verts. Aucun rôle propriétaire ni accès direct à la base ne sert de
solution provisoire.

## 23. Critique experte 1 — sécurité et autorisation

### 23.1 Risques identifiés

- un simple contrôle applicatif du dernier Administrateur est vulnérable à deux retraits concurrents ;
- joindre `users` avant de filtrer les appartenances peut révéler un compte d’une autre organisation ;
- réutiliser une invitation pour réactiver un membre désactivé contournerait une décision administrative ;
- une réponse distincte pour un identifiant croisé faciliterait l’énumération ;
- une session ancienne peut conserver des privilèges si la version n’est pas relue ;
- une auto-rétrogradation peut laisser le navigateur dans un état privilégié incohérent.

### 23.2 Corrections intégrées

- verrou d’organisation puis d’appartenance et contrôle en fonction SQL ;
- requêtes partant de la ligne RLS-visible ;
- conflit de réactivation explicite ;
- `404` uniforme ;
- epoch `users.version` vérifié sur chaque résolution ;
- expiration du cookie après auto-rétrogradation ou auto-désactivation.

## 24. Critique experte 2 — concurrence et systèmes distribués

### 24.1 Risques identifiés

- PostgreSQL et Redis ne partagent pas de transaction distribuée ;
- une purge globale Redis exécutée tardivement peut supprimer une session créée après le changement de rôle ;
- une rotation Redis échouée après l’écriture de la préférence PostgreSQL peut créer un état apparent ambigu ;
- un appel SMTP dans une transaction conserverait des verrous trop longtemps ;
- un UUID d’idempotence rejoué avec une autre commande pourrait masquer une erreur client.

### 24.2 Corrections intégrées

- PostgreSQL reste l’autorité par version, Redis seulement un nettoyage accéléré ;
- purge strictement antérieure à la version minimale ;
- en cas d’échec de rotation, l’ancienne session garde son ancien contexte et la route retourne `503` ;
- livraison après commit avec état durable ;
- comparaison sémantique lors des replays d’invitation et de renvoi.

## 25. Critique experte 3 — produit, exploitation et maintenabilité

### 25.1 Risques identifiés

- livrer l’API et toute l’interface d’administration ensemble rendrait l’incrément difficile à diagnostiquer ;
- exposer l’historique complet avant l’audit 2.4 créerait un contrat incomplet ;
- confondre plateforme et locataire produirait des accès implicites difficiles à expliquer ;
- recopier des totaux de tests périmés donnerait une fausse preuve de qualité ;
- le traceback actuel du bootstrap pour un mot de passe court nuit à l’exploitation locale.

### 25.2 Corrections intégrées

- API et invariants en 2.3.3, interface complète en 2.3.5 ;
- liste limitée aux invitations actionnables ;
- capacités plateforme et locataires séparées ;
- totaux enregistrés uniquement après exécution réelle ;
- correction de l’erreur CLI incluse au verrou d’entrée de l’implémentation.

Risque résiduel accepté : jusqu’à 2.3.5, les scripts locaux sont moins conviviaux qu’une interface. Ils rendent néanmoins
les invariants testables sans construire deux fois les mêmes écrans.

## 26. Décisions détaillées validées

Les décisions 1 à 16 de la spécification 2.3 et les décisions 1 à 16 de 2.3.2 restent acquises. Les seize décisions
suivantes complètent le contrat de 2.3.3 :

1. Limiter 2.3.3 au domaine, à la migration, aux API, aux scripts et à l’adaptation de l’acceptation ; réserver les
   écrans d’administration et le sélecteur visuel à 2.3.5, sans modifier Google avant 2.3.4.
2. Livrer `GET/PATCH /api/organization`, avec nom, langue, fuseau et verrou optimiste par `organizations.version`.
3. Ajouter `memberships.version` et `memberships.updated_by`, sans suppression physique et avec rétroalimentation
   déterministe.
4. Appliquer la matrice stricte : Administrateur gère ; Gestionnaire lit seulement les membres ; Commercial ne voit
   ni membres ni invitations ; seules les invitations sont réservées à l’Administrateur.
5. Autoriser les invitations de membre pour `admin`, `manager` et `sales`, avec UUID d’idempotence, version immuable,
   livraison après commit et limites de renvoi héritées de 2.3.2.
6. Refuser explicitement une invitation si l’appartenance est active, désactivée ou si une autre invitation active
   existe ; ne jamais réactiver implicitement une appartenance.
7. Étendre l’acceptation aux invitations `member` d’une organisation active, en conservant exactement le rôle proposé
   et sans modifier l’état de l’organisation.
8. Paginer les membres et invitations courantes dans l’organisation active seulement ; différer recherche globale et
   historique terminal à un contrat futur.
9. Modifier une appartenance uniquement par `role`, `status` et `version` ; traiter une commande sans effet comme un
   succès sans incrément de version ni révocation de session.
10. Protéger le dernier Administrateur par verrou de l’organisation puis de l’appartenance dans une transaction SQL,
    et prouver la règle avec un test réellement concurrent.
11. Incrémenter `users.version` pour toute modification effective de rôle ou d’état, puis refuser immédiatement toute
    session portant une version antérieure.
12. Remplacer la purge administrative globale par `revoke_user_before_version` ; la sécurité repose sur PostgreSQL et
    un échec de purge Redis n’annule pas la modification validée.
13. Changer d’organisation par `membership_id`, sans incrémenter `users.version`, en faisant tourner atomiquement la
    seule session courante et son CSRF ; les autres sessions restent valides dans leur contexte.
14. Conserver la double autorisation application/RLS, les fonctions SQL étroites et le `404` uniforme pour toute
    ressource absente ou croisée ; aucune commande locataire ne transporte `organization_id`.
15. Livrer la migration 0005 sans perte de données et la tester sur base vide, base 0004 peuplée, rôle Web réel et
    downgrade contrôlé.
16. Exiger migrations, Ruff, mypy, pytest réel, ESLint, Vitest, build, tests Google, protocole local, trois critiques
    et deux revues de code avant d’autoriser 2.3.4.

Ces seize décisions ont été validées sans modification par le responsable produit le 2 août 2026. Elles constituent
désormais le contrat obligatoire de l’implémentation 2.3.3. Toute dérogation devra être documentée et validée avant
modification du code concerné.

## 27. Définition de « prêt pour 2.3.4 »

2.3.3 sera terminé lorsque :

- les seize décisions de la section 26 sont validées puis implémentées sans dérogation silencieuse ;
- migration, RLS et verrou concurrent du dernier Administrateur sont prouvés sur PostgreSQL réel ;
- les trois rôles respectent exactement la matrice d’autorisation ;
- invitations de membres et acceptation fonctionnent pour nouveau compte et compte existant ;
- changement d’organisation, rotation CSRF et invalidation par version sont prouvés avec Redis réel ;
- une nouvelle session survit à une purge tardive d’anciennes versions ;
- aucune régression 2.3.2, 2.3.1, 2.2 ou Google n’est constatée ;
- toute la matrice qualité est verte sans test ignoré ;
- trois critiques et deux revues de code sont consignées ;
- le responsable produit a exécuté et accepté le protocole local.

## 28. Références

### 28.1 Internes

- [`PHASE_2_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_2_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_2_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_2_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_SPECIFICATIONS_DETAILLEES.md)
- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)
- [`../README.md`](../README.md)

### 28.2 Techniques

- [PostgreSQL 17 — Row Security Policies](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)
- [PostgreSQL 17 — Explicit Locking](https://www.postgresql.org/docs/17/explicit-locking.html)
- [Redis — Scripting with Lua](https://redis.io/docs/latest/develop/interact/programmability/eval-intro/)
- [OWASP — Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
