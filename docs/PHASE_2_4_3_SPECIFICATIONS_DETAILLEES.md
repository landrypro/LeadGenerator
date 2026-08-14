# Phase 2.4.3 — Spécifications détaillées de la consultation de l’audit

| Élément | Valeur |
| --- | --- |
| Version | 1.0 |
| Date | 9 août 2026 |
| Statut | Validé localement — passage Azure reporté au verrou final de la phase 2.4 |
| Pré-requis | 2.4.1 sous `20260809_0006` et 2.4.2 sous `20260809_0007` |
| Portée | API et interfaces de consultation locataire et plateforme |
| Recette produit | Cumul 2.4.1, 2.4.2 et 2.4.3 validé le 9 août 2026 |

Ce document raffine le contrat validé de
[`PHASE_2_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_SPECIFICATIONS_DETAILLEES.md). Les seize décisions de la section 23
ont été validées le 9 août 2026 et leur implémentation est livrée. La clôture produit reste conditionnée à la recette
utilisateur cumulée 2.4.1–2.4.3.

## 1. Objectif

2.4.3 rend consultables les événements append-only produits depuis 2.4.1 et 2.4.2. Il livre deux vues strictement
séparées : le journal de l’organisation active pour Admin et Manager, puis le journal de portée plateforme pour
l’Administrateur de plateforme.

La consultation doit permettre de répondre simplement à quatre questions : quelle transition métier a réussi,
quand, sur quelle entité et sous l’action de quel compte. Elle ne transforme pas l’audit en outil analytique, en
journal de sécurité, en export ou en copie des objets métier.

## 2. Résultat utilisateur attendu

- un Admin ou un Manager consulte la chronologie de son organisation active ;
- un Commercial ne voit ni lien, ni écran, ni donnée d’audit ;
- l’Administrateur de plateforme consulte uniquement les événements `platform` ;
- un Administrateur de plateforme également membre d’une organisation passe par la vue locataire et ses capacités
  ordinaires pour consulter cette organisation ;
- l’utilisateur filtre une période, une action, un type d’entité ou un acteur sans recherche libre ;
- il charge progressivement les événements sans total artificiel ni pagination numérique ;
- il ouvre le détail autorisé d’un événement sans second appel HTTP ;
- les libellés sont compréhensibles, tandis que les codes stables restent la source de vérité de l’API.

## 3. Clôture fonctionnelle différée

La recette manuelle de 2.4.1 et 2.4.2 a été volontairement regroupée à la fin de 2.4.3. Cette décision n’a jamais
reporté les tests automatisés déjà exécutés. Après l’implémentation de 2.4.3, la recette cumulée doit donc vérifier à
la fois :

1. que les mutations produisent les événements attendus ;
2. qu’un rollback, un refus, un conflit ou un rejeu sans transition n’en produit pas ;
3. que les événements deviennent visibles uniquement dans le bon périmètre ;
4. que les métadonnées affichées restent minimales et intelligibles ;
5. que l’ordre, les filtres et le chargement progressif sont cohérents.

Une anomalie d’écriture demeure corrigée dans le lot 2.4.2 concerné. Une anomalie de lecture ou d’affichage relève de
2.4.3. Le GO de 2.4.4 n’est donné qu’après cette recette cumulée.

## 4. Invariants hérités

1. `audit_events` reste append-only ; aucune interface ne modifie ni ne supprime un événement.
2. Aucun événement antérieur à l’activation de l’audit n’est inventé.
3. Les portées `tenant` et `platform` restent disjointes jusque dans PostgreSQL.
4. La plateforme ne reçoit aucun droit implicite sur les événements locataires.
5. L’organisation active et l’acteur proviennent de la session serveur, jamais d’un en-tête déclaratif.
6. Les capacités sont contrôlées dans l’application et l’isolation est répétée par RLS.
7. Le courriel, les secrets, les contacts et tout contenu Google sont absents du journal et de sa réponse HTTP.
8. Les métadonnées restent conformes à la liste blanche de `AuditMetadataPolicy`.
9. Les dates sont échangées en UTC avec fuseau explicite.
10. Aucun audit, filtre ou curseur n’est conservé dans le stockage Web.
11. Aucun export CSV, Excel, PDF ou impression spécialisée n’est livré.
12. Google demeure à un Text Search, vingt résultats, aucun contact, aucune pagination et aucune persistance.

## 5. Périmètre

### 5.1 Inclus

- port de lecture, modèles de vue et cas d’utilisation dédiés à l’audit ;
- adaptateur PostgreSQL en lecture seule sous contexte RLS ;
- curseur signé, versionné et lié au périmètre et aux filtres ;
- `GET /api/audit-events` pour l’organisation active ;
- `GET /api/platform/audit-events` pour la portée plateforme ;
- filtres stricts et fenêtre temporelle bornée ;
- résolution contrôlée du nom affiché actuel de l’acteur, sans courriel ;
- routes React `/app/audit` et `/app/platform/audit` ;
- chronologie accessible, détails repliables et chargement progressif ;
- catalogues centralisés de libellés préparant `fr-CA` et `en-CA` ;
- correction prospective de l’organisation cible des événements plateforme ;
- tests automatisés et recette utilisateur cumulée 2.4.1–2.4.3.

### 5.2 Exclu

- suspension et réactivation d’une organisation, livrées en 2.4.4 ;
- historique complet des invitations terminales, livré en 2.4.4 ;
- journalisation des connexions, refus d’accès, IP ou appareils ;
- recherche libre, par courriel, dans les métadonnées ou dans les contenus métier ;
- agrégations, graphiques, statistiques, total exact ou tableau de bord d’audit ;
- export, téléchargement, partage public ou envoi par courriel ;
- API de lecture d’un événement isolé ;
- actualisation automatique en arrière-plan ou temps réel ;
- purge, archivage, partitionnement ou scellement WORM ;
- chantier complet de changement de langue ;
- audit des futurs prospects, imports, abonnements ou fournisseurs.

## 6. Acteurs et capacités

| Action | Plateforme | Admin | Manager | Sales |
| --- | :---: | :---: | :---: | :---: |
| Ouvrir `/app/audit` | Avec appartenance et capacité locataire | Oui | Oui | Non |
| Lire `/api/audit-events` | Avec appartenance et capacité locataire | Oui | Oui | Non |
| Ouvrir `/app/platform/audit` | Oui | Non | Non | Non |
| Lire `/api/platform/audit-events` | Oui | Non | Non | Non |
| Exporter ou modifier un événement | Non | Non | Non | Non |

`audit:read` reste attribuée aux rôles Admin et Manager. `platform:audit:read` est ajoutée aux capacités du seul
`platform_admin`. Une capacité plateforme n’est jamais interprétée comme `audit:read`.

L’absence de capacité produit `403` sur une route connue. Une ligne située dans un autre périmètre n’est jamais
distinguée d’une ligne inexistante et ne peut pas être demandée individuellement.

## 7. Routes et contrat HTTP

### 7.1 Journal locataire

```http
GET /api/audit-events
```

Préconditions : session valide, organisation active et `audit:read`. L’organisation n’est pas acceptée en paramètre ;
elle est toujours déduite de la session.

### 7.2 Journal plateforme

```http
GET /api/platform/audit-events
```

Préconditions : session valide et `platform:audit:read`. Cette route fixe `scope = platform` et ne peut jamais
retourner une ligne `tenant`, même si le compte possède aussi une appartenance active.

### 7.3 En-têtes

Chaque succès ou erreur authentifiée de ces routes porte :

- `Cache-Control: no-store` ;
- `X-Request-ID` ;
- le type JSON UTF-8 habituel de l’API.

Les routes sont des lectures `GET` et ne requièrent donc pas de jeton CSRF. Elles restent limitées à une origine de
confiance par le contrat de session existant.

## 8. Paramètres et validation

| Paramètre | Règle |
| --- | --- |
| `limit` | entier de 1 à 100, valeur par défaut 50 |
| `cursor` | opaque, signé, versionné, 1 024 caractères maximum |
| `occurred_from` | date UTC incluse |
| `occurred_to` | date UTC exclue |
| `action` | un code exact du registre et de la portée de la route |
| `entity_type` | un type exact autorisé par le registre |
| `entity_id` | UUID exact, accepté uniquement avec `entity_type` |
| `actor_id` | UUID interne exact |

Règles temporelles :

- sans date, l’API utilise `[maintenant - 30 jours, maintenant)` ;
- une période personnalisée fournit obligatoirement les deux bornes ;
- `occurred_from` doit précéder strictement `occurred_to` ;
- la durée ne dépasse pas 90 jours ;
- les offsets valides sont normalisés en UTC ; une date sans fuseau est refusée.

Un `action` appartenant à l’autre portée, une clé inconnue ou une combinaison invalide produit `422`. Un UUID valide
mais hors périmètre produit une page vide ; il ne révèle pas l’existence de l’entité ou de l’acteur.

Il n’existe ni paramètre `organization_id` sur la route locataire, ni courriel, ni texte libre, ni filtre de clé ou de
valeur de `metadata`, ni ordre choisi par le client.

## 9. Pagination et cohérence du curseur

Le tri immuable est `occurred_at DESC, id DESC`. La requête lit `limit + 1` lignes, retourne au plus `limit` éléments
et produit `next_cursor` uniquement si une suite existe. Aucun `count(*)` n’est exécuté.

Le curseur contient sous signature HMAC :

- sa version ;
- la portée `tenant` ou `platform` ;
- l’organisation active pour la portée locataire ;
- les bornes temporelles normalisées ;
- l’empreinte canonique des filtres ;
- le couple exclusif `occurred_at` et `id` de la dernière ligne ;
- un espace de nom distinct des autres curseurs de l’application.

Le secret de pagination existant est dérivé avec un contexte propre à l’audit ; aucun nouveau secret n’est nécessaire.
Toute altération, mauvaise signature, portée différente, changement d’organisation ou réutilisation avec d’autres
filtres produit `422 invalid_cursor`. Le message public ne précise pas quelle partie est incorrecte.

Comme les lignes sont immuables, la pagination par clé reste stable. Les événements ajoutés après la première page
apparaissent seulement après **Actualiser** ; ils ne sont pas injectés au milieu d’une lecture en cours.

## 10. Modèle de réponse

```json
{
  "items": [
    {
      "id": "1cebc02a-7a50-4718-8a39-d0f604cb23ef",
      "occurred_at": "2026-08-09T15:00:00Z",
      "action": "membership.role_changed",
      "entity_type": "membership",
      "entity_id": "6b419ae2-c0ab-4935-aed4-daf2acb8180b",
      "actor": {
        "kind": "user",
        "id": "6b35de43-8bb7-48f8-923e-ae378471744d",
        "display_name": "Gestionnaire"
      },
      "request_id": "req-opaque",
      "correlation_id": "req-opaque",
      "source": "api",
      "metadata": {
        "previous_role": "sales",
        "new_role": "manager"
      },
      "schema_version": 1
    }
  ],
  "next_cursor": null,
  "occurred_from": "2026-07-10T15:00:00Z",
  "occurred_to": "2026-08-09T15:00:00Z"
}
```

Le tableau conserve l’ordre de la requête. Le courriel de l’acteur, `organization_id` locataire et toute donnée
Google sont absents. Un acteur système utilise `{"kind":"system","id":null,"display_name":null}` et reçoit un
libellé frontend fixe.

Les noms affichés sont résolus à la lecture depuis le compte courant. Ils ne sont ni dupliqués ni figés dans
`audit_events`. Le détail d’un événement ancien peut donc montrer le nom affiché actuel ; l’identifiant interne reste
la référence historique. Cette limite est explicitée dans l’aide utilisateur.

L’API retourne des codes et des métadonnées typées, jamais des phrases localisées. Une version de schéma inconnue
reste retournée de manière sûre, mais l’interface masque ses métadonnées et affiche un libellé générique plutôt que du
JSON brut.

## 11. Organisation cible des événements plateforme

Le contrat général exige `organization_id` lorsqu’un événement de portée plateforme cible une organisation. La
fonction actuelle `platform_audit_event` force pourtant cette valeur à `null`.

2.4.3 corrige ce point prospectivement :

- l’aide accepte un `organization_id` cible facultatif ;
- provisioning et événements d’invitation initiale transmettent l’organisation concernée ;
- les événements plateforme sans cible organisation conservent `null` ;
- aucune ligne existante n’est modifiée ou reconstruite ;
- les événements déjà présents avec `null` restent consultables ;
- cette correction reçoit des tests dans le lot transactionnel 2.4.2 et des tests de lecture 2.4.3.

Cette correction ne donne aucun accès aux données locataires. `organization_id` est une dimension de cible
plateforme et la politique RLS continue d’exiger `scope = platform`.

## 12. Architecture backend

### 12.1 Domaine et application

Les nouveaux contrats sont séparés de l’écriture :

- `AuditEventFilter` : période et filtres normalisés ;
- `AuditEventView` : projection immutable exposable ;
- `AuditEventPage` : `items` et `next_cursor` ;
- `AuditEventReader` : port de lecture sans `commit()` ;
- `AuditCursorCodec` : port de curseur lié aux filtres ;
- `ListTenantAuditEvents` et `ListPlatformAuditEvents` : cas d’utilisation distincts.

Le cas d’utilisation choisit la portée à partir de son type, jamais d’une valeur reçue du client. Il valide période,
registre et curseur avant l’accès SQL.

### 12.2 Adaptateur PostgreSQL

Deux unités de lecture dédiées ouvrent une transaction courte et posent avec `set_config(..., true)` :

- `app.actor_id`, `app.organization_id`, `app.audit_scope = tenant` et `app.request_id` pour le locataire ;
- `app.actor_id`, organisation vide, `app.audit_scope = platform` et `app.request_id` pour la plateforme.

L’adaptateur interroge directement `audit_events` sous RLS, applique la fenêtre, les filtres et la clé de pagination,
puis joint uniquement `users.id` et `users.display_name` pour l’acteur. Il ne sélectionne jamais le courriel, le hash
ou un autre attribut du compte. La transaction est annulée ou terminée sans écriture.

### 12.3 Présentation FastAPI

Les schémas Pydantic restent stricts. Les routes transforment les erreurs applicatives vers l’enveloppe publique
existante, ajoutent `no-store` et ne construisent aucun SQL, libellé métier ou curseur.

## 13. PostgreSQL, RLS et migration

Le schéma, les politiques et les index nécessaires existent depuis `20260809_0006` :

- `(scope, organization_id, occurred_at DESC, id DESC)` ;
- `(scope, organization_id, entity_type, entity_id, occurred_at DESC, id DESC)` ;
- `(scope, actor_id, occurred_at DESC, id DESC)` ;
- index plateforme partiel par date et identifiant.

Aucune migration Alembic corrective n’est planifiée pour 2.4.3. La correction d’`organization_id` plateforme touche
la construction des nouveaux événements, pas la table. Un index supplémentaire n’est ajouté que si un plan
`EXPLAIN (ANALYZE, BUFFERS)` sur une base de test représentative prouve un besoin ; il exigerait alors une décision et
une migration documentées avant implémentation.

Les tests réels prouvent de nouveau :

- zéro ligne sans `app.audit_scope` ;
- zéro ligne avec mauvais acteur, organisation ou scope ;
- visibilité locataire limitée à l’organisation active ;
- visibilité plateforme limitée aux lignes `platform` ;
- impossibilité pour `prospect_app` de modifier ou supprimer une ligne.

## 14. Erreurs publiques

| Situation | Réponse |
| --- | --- |
| Session absente ou expirée | `401` |
| Capacité absente | `403` |
| Filtre, période ou combinaison invalide | `422 validation_failed` |
| Curseur invalide, altéré ou réutilisé dans un autre contexte | `422 invalid_cursor` |
| PostgreSQL indisponible | `503 audit_unavailable` |

Une page vide reste un succès `200`. L’erreur n’expose ni SQL, ni règle RLS, ni existence d’un acteur ou d’une entité
hors périmètre. Le `request_id` permet le rapprochement avec les journaux techniques.

## 15. Interface locataire

La route `/app/audit` est enregistrée avec `requiredCapability: audit:read` et une organisation active obligatoire.
La navigation affiche **Journal d’activité** après les pages d’administration locataire et avant **Compte**.

La page contient :

- un titre et le nom de l’organisation active ;
- les périodes rapides **7 jours**, **30 jours** et **90 jours** ;
- une période personnalisée respectant la fenêtre maximale ;
- les filtres **Action**, **Type d’entité** et **Acteur** ;
- **Appliquer**, **Réinitialiser** et **Actualiser** ;
- une chronologie ordonnée du plus récent au plus ancien ;
- un détail repliable par événement ;
- **Charger la suite** tant que `next_cursor` existe.

Le filtre Acteur utilise l’annuaire autorisé déjà disponible et envoie uniquement son UUID. Il n’envoie jamais le
courriel. Un Manager peut lire l’annuaire et le journal mais ne gagne aucune capacité de mutation.

## 16. Interface plateforme

La route `/app/platform/audit` est enregistrée avec `requiredCapability: platform:audit:read`, sans organisation
active requise. La navigation plateforme sépare **Organisations** et **Audit plateforme**.

La page reprend période, action, type d’entité, actualisation et chargement progressif. Elle ne contient aucune action
de suspension avant 2.4.4 et n’affiche aucun événement `tenant`. Le filtre acteur peut se limiter à **Tous** et
**Moi** tant qu’aucun annuaire des Administrateurs de plateforme n’existe.

Les deux écrans utilisent les mêmes composants génériques de chronologie, filtres, état et présentation, mais des
hooks et clients API distincts afin qu’une portée ne puisse pas être changée par une prop issue du navigateur.

## 17. Catalogue de présentation

Chaque code connu possède : une clé de traduction, une catégorie, une icône non signifiante seule et un présentateur
de métadonnées sur liste blanche.

Exemples de libellés français :

| Code | Libellé |
| --- | --- |
| `organization.updated` | Organisation modifiée |
| `account.organization_preference_changed` | Organisation active changée |
| `membership.role_changed` | Rôle d’un membre modifié |
| `membership.status_changed` | État d’un membre modifié |
| `invitation.created` | Invitation créée |
| `invitation.resend_requested` | Renvoi d’invitation demandé |
| `invitation.delivery_completed` | Livraison d’invitation terminée |
| `invitation.revoked` | Invitation révoquée |
| `invitation.accepted` | Invitation acceptée |
| `organization.activated` | Organisation activée |
| `organization.provisioned` | Organisation provisionnée |
| `organization.initial_invitation.created` | Invitation initiale créée |
| `organization.initial_invitation.resend_requested` | Renvoi initial demandé |
| `organization.initial_invitation.delivery_completed` | Livraison initiale terminée |
| `organization.initial_invitation.revoked` | Invitation initiale révoquée |

Les rôles, états et statuts de livraison sont eux aussi traduits depuis des catalogues fermés. Le frontend ne rend
jamais `JSON.stringify(metadata)`. Une action ou une version inconnue affiche **Événement non pris en charge**,
l’horodatage et la référence de suivi, sans métadonnée brute.

L’heure locataire est présentée dans le fuseau de l’organisation avec l’UTC précis dans le détail. La vue plateforme
utilise UTC pour éviter toute ambiguïté d’exploitation.

## 18. États, accessibilité et comportement

- le chargement initial possède un statut annoncé sans masquer le titre ;
- l’état vide distingue **aucun événement dans cette période** d’une erreur ;
- une erreur offre **Réessayer** sans perdre les filtres en mémoire ;
- **Charger la suite** est désactivé pendant l’appel et son résultat est annoncé ;
- le focus reste sur le bouton de chargement, puis la nouvelle portion est annoncée sans déplacement forcé ;
- **Réinitialiser** revient à 30 jours et replace le focus de manière prévisible ;
- les détails utilisent un bouton avec `aria-expanded` et `aria-controls` ;
- la date est portée par un élément `time` avec valeur ISO ;
- ordre, acteur, action et cible restent compréhensibles sans couleur ni icône ;
- les écrans fonctionnent au clavier, à 320 px, à 200 % de zoom et sous axe sans violation sérieuse.

Un changement d’organisation annule les requêtes en cours, démonte la page grâce à la clé d’organisation existante,
efface les éléments et filtres en mémoire puis recharge la nouvelle portée. Une réponse tardive de l’ancienne
organisation ne peut pas être rendue.

## 19. Confidentialité et stockage navigateur

Événements, curseurs et filtres vivent uniquement dans l’état React de la page. Ils ne sont écrits dans aucun des
emplacements suivants :

- `localStorage` ou `sessionStorage` ;
- IndexedDB ;
- Cache API ou service worker ;
- paramètre d’URL ou fragment ;
- fichier téléchargé ou presse-papiers automatique.

Le client ne précharge pas le journal au démarrage global et n’effectue aucun polling. Le rafraîchissement est une
action explicite. Le client API central applique les erreurs communes et n’écrit ni réponse ni métadonnée dans la
console de production.

## 20. Performance et observabilité

- objectif initial : p95 inférieur à 500 ms côté serveur pour 50 lignes sur une fenêtre de 30 jours, hors réseau ;
- une page ne sélectionne que les colonnes du contrat et utilise `limit + 1` ;
- aucun total, tri dynamique ou chargement N+1 de l’acteur ;
- les appels concurrents obsolètes sont annulés avec `AbortController` ;
- la taille de réponse et la latence sont mesurées par route et statut, sans action, acteur ni identifiant d’entité
  comme dimension métrique ;
- les logs contiennent route, statut, durée, taille, `request_id` et portée, jamais les métadonnées ou filtres ;
- aucune métrique à cardinalité non bornée n’utilise un UUID ou un code futur non validé.

Le seuil de performance est vérifié sur une base de test suffisamment remplie. Il s’agit d’un objectif d’alerte et non
d’une raison pour contourner RLS ou ajouter un cache de données d’audit.

## 21. Tests automatisés obligatoires

### 21.1 Unitaires backend

- période par défaut, bornes inclusives/exclusives et maximum 90 jours ;
- action et type d’entité validés selon la portée ;
- dépendance `entity_id`/`entity_type` ;
- curseur signé, version, empreinte des filtres, scope et organisation ;
- rejet d’altération, de réutilisation et de longueur excessive ;
- pagination `occurred_at DESC, id DESC` sans doublon ;
- projection acteur sans courriel ;
- correction prospective d’`organization_id` plateforme.

### 21.2 PostgreSQL réel

- lecture Admin et Manager de leur organisation ;
- zéro ligne pour Sales, sans contexte, mauvais scope ou mauvaise organisation ;
- séparation entre deux organisations ;
- plateforme lisant seulement `platform` ;
- Administrateur de plateforme incapable de lire `tenant` par sa route plateforme ;
- filtres date, action, entité et acteur ;
- ordre déterministe avec horodatages identiques ;
- métadonnée conforme et acteur système ;
- privilèges append-only toujours intacts ;
- plans des requêtes principales documentés, sans `skip`.

### 21.3 API

- `401`, `403`, `422`, `503` et succès vide ;
- organisation fournie par le client refusée sur la route locataire ;
- portée fournie par le client refusée sur les deux routes ;
- 50 par défaut, 100 maximum et `next_cursor` exact ;
- curseur incompatible après changement de filtre ou d’organisation ;
- `Cache-Control: no-store` et `X-Request-ID` sur succès et erreur ;
- absence de courriel, secret, contact et contenu Google dans la sérialisation.

### 21.4 Frontend

- routes et navigation selon les capacités ;
- Admin/Manager autorisés, Sales refusé et plateforme séparée ;
- filtres, application, remise à zéro et rafraîchissement ;
- chargement de la suite, fin, déduplication défensive et annulation ;
- changement d’organisation sans résidu visuel ;
- libellés de chaque action et métadonnées autorisées ;
- action/version inconnue sans JSON brut ;
- chargement, vide, erreur et retry ;
- clavier, focus, 320 px, 200 % et axe ;
- aucun événement, filtre ou curseur dans les stockages Web ou l’URL.

### 21.5 Régression et verrou qualité

- tests transactionnels de 2.4.1 et 2.4.2 rejoués intégralement ;
- authentification, provisioning, invitations, organisation, membres et changement d’organisation ;
- recherche Google inchangée : un appel, vingt résultats, aucun contact, aucune pagination ;
- carte protégée et attribution Google Maps ;
- Ruff, mypy, pytest unitaire et PostgreSQL réel zéro `skip` ;
- ESLint, audit npm, Vitest, axe et build ;
- Azure Pipelines exécute les mêmes familles de contrôles.

## 22. Recette utilisateur cumulée 2.4.1–2.4.3

### 22.1 Jeu de comptes

La recette utilise au minimum :

- un Administrateur de plateforme ;
- une organisation A avec Admin, Manager et Sales actifs ;
- une organisation B avec un autre Admin ;
- un compte membre de A et B afin de tester le changement de contexte ;
- une adresse locale Mailpit pour les invitations.

Les mots de passe restent interactifs et aucun cookie, CSRF ou jeton d’invitation n’est affiché par les scripts.

### 22.2 Scénario locataire

1. Modifier le nom ou le fuseau de l’organisation A.
2. Inviter un membre, demander un renvoi, puis révoquer une invitation distincte.
3. Modifier le rôle puis l’état d’un membre sans toucher au dernier Admin actif.
4. Accepter une autre invitation via Mailpit.
5. Changer l’organisation active d’un compte appartenant à A et B.
6. Ouvrir `/app/audit` comme Admin A et vérifier les actions, l’ordre, les auteurs et les détails minimisés.
7. Répéter comme Manager A, puis vérifier l’absence du journal et le refus HTTP comme Sales A.
8. Passer à B et vérifier qu’aucune ligne de A ne reste affichée ni accessible.
9. Tester 7, 30 et 90 jours, un acteur, une action, une entité, la remise à zéro et **Charger la suite**.

### 22.3 Scénario plateforme

1. Provisionner une organisation et laisser Mailpit terminer la livraison initiale.
2. Demander un renvoi initial puis révoquer une invitation initiale distincte.
3. Ouvrir `/app/platform/audit` et vérifier uniquement les actions plateforme.
4. Confirmer qu’aucun événement locataire créé précédemment n’apparaît.
5. Confirmer que `/app/audit` n’est accessible au même compte que s’il possède aussi une appartenance Admin ou
   Manager active, et qu’il ne voit alors que cette organisation.

### 22.4 Contrôles négatifs

- provoquer une validation invalide, un conflit de version et un rejeu idempotent sans transition ;
- vérifier qu’aucun faux événement de succès n’apparaît ;
- inspecter le réseau pour `no-store`, l’absence de courriel et le chargement par curseur ;
- inspecter les stockages du navigateur et confirmer l’absence d’audit, filtre et curseur ;
- confirmer qu’aucun bouton d’export ou d’action plateforme 2.4.4 n’est présent.

Un guide ou script local dédié pourra préparer les identifiants et appeler les routes réelles, mais il ne doit jamais
lire directement `audit_events` pour produire la preuve fonctionnelle utilisateur.

## 23. Seize décisions validées

Validation produit reçue le 9 août 2026. Les choix ci-dessous constituent le contrat implémenté de 2.4.3.

1. Deux routes et deux écrans distincts : organisation active et plateforme, sans paramètre de portée client.
2. `audit:read` pour Admin/Manager, aucune lecture pour Sales ; `platform:audit:read` pour le seul rôle plateforme.
3. Aucun accès locataire implicite pour la plateforme, même lorsqu’un compte cumule rôle plateforme et appartenance.
4. Pagination signée par `(occurred_at, id)`, 50 par défaut, 100 maximum, sans total exact.
5. Curseur versionné et lié à la portée, l’organisation, la période et l’empreinte de tous les filtres.
6. Fenêtre de 30 jours par défaut et intervalle personnalisé maximal de 90 jours, avec bornes UTC explicites.
7. Filtres exacts période, action, type/identifiant d’entité et acteur ; aucun tri choisi par le navigateur.
8. Aucune recherche libre, par courriel, dans les métadonnées ou dans les contenus métier.
9. Réponse par codes stables, acteur sans courriel, nom affiché résolu à la lecture et métadonnées toujours autorisées.
10. Aucun endpoint de détail : la ligne contient le détail minimal et l’interface le replie localement.
11. `no-store`, aucun stockage Web ou paramètre d’URL, aucun polling, export ou téléchargement.
12. Routes `/app/audit` et `/app/platform/audit`, navigation pilotée par capacités et composants de vue réutilisables.
13. Catalogues centralisés, aucun JSON brut, fuseau de l’organisation côté locataire et UTC côté plateforme.
14. Lecture directe sous RLS avec unités de lecture dédiées ; aucune migration corrective planifiée.
15. `organization_id` des nouvelles actions plateforme ciblées est corrigé prospectivement, sans rétro-audit ni
    modification des lignes existantes.
16. La recette utilisateur clôt simultanément 2.4.1–2.4.3 ; tous les verrous automatisés et PostgreSQL réel restent
    obligatoires avant le GO de 2.4.4.

## 24. Critères d’acceptation

2.4.3 est accepté lorsque :

- les deux API respectent capacités, portée, RLS, filtres, curseur et `no-store` ;
- Admin et Manager voient uniquement leur organisation active et Sales n’obtient rien ;
- la plateforme ne voit aucune ligne locataire ;
- l’ordre est déterministe, la suite complète et sans doublon ;
- aucune réponse ne contient courriel, secret, contact ou contenu Google ;
- les deux interfaces sont accessibles, responsives et sans stockage navigateur ;
- les événements 2.4.2 sont présentés avec les bons libellés et détails minimisés ;
- les nouveaux événements plateforme ciblés portent leur organisation sans modifier le passé ;
- la recette cumulée de la section 22 est signée par le responsable produit ;
- tous les contrôles backend, PostgreSQL, frontend et Azure sont verts sans `skip`.

## 25. Séquencement d’implémentation recommandé

1. Ajouter projections, filtres, port de lecture et codec de curseur.
2. Ajouter unités de lecture et adaptateur PostgreSQL sous RLS.
3. Corriger prospectivement la cible organisation des événements plateforme et ses tests 2.4.2.
4. Ajouter cas d’utilisation, schémas et routes FastAPI.
5. Ajouter client API et hooks séparés locataire/plateforme.
6. Ajouter catalogues, chronologie et filtres accessibles.
7. Enregistrer routes, capacités et navigation.
8. Exécuter tests unitaires, API, PostgreSQL réels et frontend.
9. Exécuter la régression complète et Azure Pipelines.
10. Produire le rapport d’implémentation et le guide de recette cumulée.
11. Faire exécuter la recette utilisateur avant toute spécification d’implémentation 2.4.4.

## 26. Critique experte préalable

### 26.1 Sécurité et isolation

Le principal risque est une réutilisation générique d’une route ou d’un hook avec un `scope` contrôlé par le client.
Deux cas d’utilisation, deux routes et deux clients rendent la séparation structurelle. L’autorisation applicative ne
remplace pas RLS ; le mauvais `app.audit_scope` doit retourner zéro ligne.

### 26.2 Cohérence historique

Afficher un nom actuel à côté d’un événement ancien peut laisser croire qu’il s’agit du nom à l’époque. La solution
retenue évite de stocker une donnée personnelle dupliquée, conserve l’UUID comme vérité et documente explicitement la
sémantique du nom affiché. Le défaut d’`organization_id` plateforme est corrigé uniquement pour l’avenir afin de ne
jamais inventer l’historique.

### 26.3 Performance et produit

Des filtres riches, un total exact et du temps réel sembleraient pratiques, mais augmenteraient coût, cardinalité et
surface de fuite avant d’apporter une valeur commerciale démontrée. La fenêtre bornée, la clé de pagination et
l’actualisation explicite rendent le premier journal prévisible. Les index ne seront multipliés qu’à partir de plans
réels, pas d’hypothèses.

## 27. Définition de « terminé »

- les seize décisions ont été validées et le GO d’implémentation donné ;
- le code respecte les sections 4 à 20 sans élargissement tacite ;
- aucune migration inutile ni rétro-audit n’a été introduit ;
- les preuves automatisées sont archivées dans le rapport 2.4.3 ;
- la recette cumulée 2.4.1–2.4.3 est exécutée et signée ;
- documentation technique, utilisateur et commandes locales sont à jour ;
- trois critiques et deux revues de code indépendantes concluent sans anomalie bloquante ;
- le responsable produit prononce la clôture et le GO de spécification 2.4.4.

## 28. Références internes

- [`PHASE_2_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_4_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_2_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_4_2_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_2_RAPPORT_IMPLEMENTATION.md)
- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)
- [`Test de Qualité.md`](Test%20de%20Qualité.md)
