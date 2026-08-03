# Phase 2.3.5-D — Spécifications détaillées de l’administration plateforme

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Lot | 2.3.5-D — Plateforme |
| Version | 1.2 |
| Date | 3 août 2026 |
| Statut | Implémenté et validé localement |
| Validation produit | 3 août 2026 — seize décisions puis parcours local complet validés |
| Prérequis | 2.3.5-A/B/C validés ; décisions D validées |
| Migration SQL | Aucune prévue |
| Nouvelle API | Aucune prévue |
| Révision Alembic cible | `20260802_0005 (head)` |

## 1. Objectif

Le lot D remplace le script local de provisioning comme parcours utilisateur principal par une interface réservée à
l’Administrateur de plateforme. Cette interface permet uniquement :

- de consulter les métadonnées de provisioning des organisations ;
- de créer une organisation et sa première invitation Administrateur ;
- de renvoyer ou révoquer cette première invitation lorsque son état le permet.

Le lot ne transforme pas l’Administrateur de plateforme en membre des organisations. Il ne crée aucune fonction
d’impersonation et ne donne aucun accès aux données CRM, aux recherches Google, aux membres ou aux invitations
locataires.

## 2. Périmètre

### 2.1 Inclus

- activation de la route `/app/platform/organizations` ;
- destination par défaut d’un Administrateur plateforme sans organisation active ;
- client `platformApi` et hook paginé dédié ;
- liste des organisations, état vide, actualisation et pagination par curseur ;
- formulaire de provisioning ;
- intention idempotente de création ;
- renvoi idempotent de la première invitation ;
- révocation confirmée ;
- traduction des erreurs stables déjà exposées par le backend ;
- tests React, API, routage, confidentialité et non-régression ;
- documentation utilisateur et protocole local avec Mailpit.

### 2.2 Explicitement exclu

- suspension, réactivation ou suppression d’une organisation ;
- modification du nom, de la langue ou du fuseau d’une organisation existante ;
- accès aux membres, prospects, données Google ou données d’audit d’un locataire ;
- invitation de membres ordinaires depuis la plateforme ;
- sélection forcée d’une organisation active ou impersonation d’un utilisateur ;
- recherche, tri ou filtre serveur non prévus par l’API actuelle ;
- total global d’organisations ;
- persistance navigateur d’un formulaire ou d’une intention ;
- nouvelle migration, nouvel endpoint ou nouveau rôle.

Ces besoins éventuels relèvent d’un futur incrément, notamment 2.4 pour les changements d’état audités.

## 3. Invariants de sécurité

1. La session serveur et `platform:organizations:read` sont nécessaires pour ouvrir la page.
2. `platform:organizations:create` est nécessaire pour chaque mutation et pour afficher ses contrôles.
3. Le rôle plateforme n’accorde aucune appartenance locataire implicite.
4. Un rôle Admin locataire sans rôle plateforme reçoit un `403` sur le lien profond.
5. Les identifiants d’organisation utilisés par renvoi/révocation proviennent d’une ressource retournée par l’API.
6. Le frontend ne forge jamais de contexte locataire et ne transmet aucun `organization_id` dans la création.
7. CSRF, origine de confiance, cookie HttpOnly, fonctions SQL étroites et contrôle serveur restent les autorités.
8. Les réponses portent `Cache-Control: no-store` et ne sont jamais copiées dans un stockage Web.
9. Aucun jeton d’invitation, hash, identifiant de livraison, mot de passe ou secret n’est rendu.
10. Aucun échec ne déclenche automatiquement une seconde mutation.

## 4. Acteurs et capacités

| Acteur | Route plateforme | Liste | Créer | Renvoyer/révoquer | Accès locataire implicite |
| --- | --- | --- | --- | --- | --- |
| Administrateur plateforme sans appartenance | oui | oui | oui | oui | aucun |
| Administrateur plateforme avec appartenance explicite | oui | oui | oui | oui | seulement via son appartenance active |
| Administrateur locataire | non (`403`) | non | non | non | son organisation uniquement |
| Gestionnaire ou Commercial | non (`403`) | non | non | non | selon leur rôle locataire |
| Anonyme | redirection `/login` | non | non | non | aucun |

Le shell peut afficher à la fois les pages locataires et Plateforme si le compte possède réellement les deux familles
de capacités. La page Plateforme ne fournit toutefois aucun bouton « Entrer dans l’organisation ».

## 5. Routage et destination initiale

- la route canonique est `/app/platform/organizations` ;
- elle exige `platform:organizations:read` et ne requiert pas d’organisation active ;
- un Administrateur plateforme sans organisation active est dirigé de `/` vers cette route ;
- un compte disposant d’une organisation active conserve la priorité actuelle : Recherche si elle est autorisée,
  sinon Organisation ; Plateforme reste accessible dans la navigation ;
- Compte demeure toujours accessible ;
- un retour/avance navigateur restaure la route, mais aucun curseur n’est placé dans l’URL ;
- toute rotation ou invalidation de session démonte l’écran, annule les requêtes et abandonne les intentions locales.

## 6. Contrats HTTP consommés

| Action | Contrat existant | Corps |
| --- | --- | --- |
| Lister | `GET /api/platform/organizations?limit=25&cursor=…` | aucun |
| Créer | `POST /api/platform/organizations` | nom, langue, fuseau, courriel initial, `creation_request_id` |
| Renvoyer | `POST /api/platform/organizations/{id}/first-invitation/resend` | `resend_request_id` |
| Révoquer | `POST /api/platform/organizations/{id}/first-invitation/revoke` | `{}` |

La limite frontend est fixée à 25, dans la plage serveur `1..100`. Aucun endpoint individuel, recherche serveur ou
compteur n’est inventé.

## 7. Modèle d’affichage

Chaque ligne provient d’un `ProvisioningResponse` et présente :

- organisation : nom, langue, fuseau, état, création et activation éventuelle ;
- première invitation la plus récente : destinataire, rôle, état, livraison et expiration ;
- aucune version technique, clé idempotente ou valeur `replayed` comme donnée métier principale.

Les libellés sont contrôlés :

| Valeur | Libellé |
| --- | --- |
| organisation `provisioning` | En cours d’activation |
| organisation `active` | Active |
| invitation `active` | Active |
| invitation `expired` | Expirée |
| invitation `revoked` | Révoquée |
| invitation `accepted` | Acceptée |
| livraison `pending` | En attente |
| livraison `sent` | Envoyée |
| livraison `failed` | Échec de livraison |

Les dates utilisent `Intl.DateTimeFormat` et des éléments `<time datetime="…">`. L’interface respecte l’ordre du
serveur, du plus récent au plus ancien, sans tri local concurrent.

## 8. Liste et pagination

Le chargement initial expose `loading`, `success`, `empty` ou `error`. Une actualisation conserve la liste visible et
annonce `refreshing`. « Charger la suite » :

- n’apparaît que si `next_cursor` est présent ;
- ajoute les résultats sans remplacer les précédents ;
- déduplique par `organization.id` ;
- ne fabrique aucun total ;
- neutralise la double commande ;
- conserve le curseur uniquement en mémoire.

Une requête est annulée au démontage. Un numéro de séquence interdit à une réponse ancienne de remplacer une liste
plus récente. Aucune relance automatique n’est autorisée après erreur.

## 9. Formulaire de création

Le formulaire, visible uniquement avec `platform:organizations:create`, contient :

- nom : requis, 1 à 160 caractères après normalisation serveur ;
- langue : `fr-CA` ou `en-CA` ;
- fuseau IANA : requis, modifiable ;
- courriel du premier Administrateur : requis, 3 à 254 caractères ;
- rôle initial fixé à Administrateur, non sélectionnable.

Le fuseau initial vient de `Intl.DateTimeFormat().resolvedOptions().timeZone` si une construction
`Intl.DateTimeFormat` l’accepte ; sinon `America/Toronto`. Une liste de suggestions canadiennes est proposée sans
remplacer la validation serveur.

Le bouton reste désactivé tant que les champs requis sont vides et pendant sa propre soumission. Un verrou synchrone
neutralise deux clics avant le prochain rendu React.

Après succès ou rejeu confirmé :

- la réponse serveur est insérée ou remplace la ligne de même identifiant ;
- le formulaire et son intention sont réinitialisés ;
- un état `delivery_status=failed` est affiché comme avertissement, pas comme échec de création ;
- aucun accès à la nouvelle organisation n’est ajouté au compte plateforme.

## 10. Intentions idempotentes

### 10.1 Création

À la première soumission valide, le client capture en mémoire :

```text
{ creation_request_id, payload_normalisé }
```

Le même UUID et exactement le même corps sont réutilisés après :

- erreur réseau ;
- `provisioning_outcome_unknown` ;
- indisponibilité dont l’issue ne peut être prouvée par le client.

Toute modification sémantique d’un champ abandonne l’intention et impose un nouvel UUID à la prochaine soumission.
Un succès, y compris `replayed=true`, clôt l’intention.

`idempotency_key_reused` est traité comme incohérence terminale de l’intention : aucun retry automatique. Le formulaire
reste visible et une action explicite « Abandonner cette intention » permet seulement de générer un nouvel UUID à la
prochaine soumission.

### 10.2 Renvoi

Chaque organisation possède au plus une intention de renvoi active :

```text
{ organization_id, invitation_id_observé, resend_request_id }
```

Le même identifiant est conservé après erreur réseau ou résultat inconnu. Une réponse réussie remplace la ressource
avec la réponse serveur et clôt l’intention. Deux organisations distinctes peuvent être traitées en parallèle ; une
double commande sur la même organisation est neutralisée.

Les identifiants sont générés par l’utilitaire injectable livré en C, jamais affichés, journalisés, placés dans l’URL,
`localStorage` ou `sessionStorage`.

## 11. Actions de première invitation

| Organisation | Invitation | Renvoyer | Révoquer |
| --- | --- | --- | --- |
| `provisioning` | `active` | oui | oui, avec confirmation |
| `provisioning` | `expired` | oui | oui, avec confirmation |
| `provisioning` | `revoked` | oui | non |
| `active` | `accepted` | non | non |
| autre combinaison retournée | non par défaut | non par défaut |

Un échec de livraison laisse « Renvoyer » disponible lorsque l’état métier l’autorise. Le renvoi ne demande pas de
confirmation, mais affiche qu’il invalidera le lien précédent. La révocation utilise le dialogue accessible livré en
C, restaure le focus et envoie strictement `{}`.

Après mutation réussie, la ligne est entièrement remplacée par la réponse serveur. L’interface ne déduit jamais seule
qu’une organisation est devenue active.

## 12. Matrice des erreurs

| HTTP/code | Comportement interface |
| --- | --- |
| `401 authentication_required` | purge centrale de session et retour à `/login` |
| `403 insufficient_capability` | session conservée, page/action refusée |
| `403 request_rejected` | message contrôlé, aucun détail CSRF/origine |
| `404 provisioning_not_found` | message générique et proposition d’actualiser, sans révélation supplémentaire |
| `409 idempotency_key_reused` | intention bloquée, aucune répétition, abandon explicite possible |
| `409 invitation_already_accepted` | action retirée après actualisation explicite |
| `422 validation_failed` | formulaire conservé, message contrôlé, aucune mutation automatique |
| `429 invitation_rate_limited` | délai `Retry-After` affiché en secondes, sans compte à rebours |
| `503 invitation_delivery_unavailable` | formulaire conservé ; configuration requise, aucun retry automatique |
| `503 provisioning_outcome_unknown` | même intention proposée au retry explicite |
| `503 provisioning_unavailable` | état conservé, actualisation ou retry manuel selon l’opération |
| erreur réseau | message de connexion ; même intention conservée pour la mutation |

Le texte serveur reste la base, complétée seulement lorsque le code impose une conduite sûre. Aucun détail interne,
email global ou existence d’appartenance n’est ajouté.

## 13. Architecture frontend

Le lot introduira :

- `platformApi` : liste, création, renvoi, révocation ;
- `usePlatformOrganizations` : pagination, déduplication, annulation et réconciliation ;
- `PlatformOrganizationsPage` : orchestration des capacités et états ;
- composants de formulaire, liste et ligne de provisioning ;
- réutilisation de `createRequestId`, `ConfirmationDialog`, `ApiError.retryAfter` et du hook paginé lorsque pertinent.

Les composants ne réalisent aucun `fetch`. Les intentions sont des objets explicites et injectables en test. Une
mutation possède son contrôleur, son verrou synchrone et son état d’annonce. Quitter la page annule les contrôleurs et
empêche toute réponse tardive de modifier un écran remonté.

## 14. Accessibilité et responsive

- titre `h1` unique et régions nommées ;
- formulaire associé par `label` et erreurs annoncées par `role=alert` ;
- succès et actualisations via régions `aria-live` ;
- actions disponibles au clavier, focus visible et retour du focus après dialogue ;
- aucune information transmise uniquement par couleur ;
- tableau sur écran large, cartes lisibles sous 820 px ;
- aucune perte à 320 px ni à 200 % de zoom ;
- `prefers-reduced-motion` respecté ;
- contrôles axe intégrés au verrou final E, sans reporter les défauts évidents de D.

## 15. Confidentialité et exploitation

- aucune écriture dans les stockages Web ;
- aucun UUID d’intention dans les messages, le DOM utile, l’URL ou la console ;
- aucun token d’invitation reçu ou affiché ;
- `Mailpit` reste strictement local ;
- l’interface devient le parcours utilisateur principal, tandis que `Test-ProvisioningLocal.ps1` reste un diagnostic ;
- l’absence de backend de livraison en production reste bloquante ;
- les pages légales ne changent pas, car D n’introduit ni donnée ni finalité nouvelle par rapport à 2.3.2.

## 16. Tests obligatoires

### 16.1 Routage et capacités

- plateforme sans organisation dirigée vers `/app/platform/organizations` ;
- plateforme avec appartenance explicite conservant les deux navigations ;
- locataire non plateforme en `403` sur lien profond ;
- aucune action pendant la restauration de session ;
- Compte et déconnexion toujours accessibles.

### 16.2 Liste

- chargement, vide, erreur, actualisation ;
- pagination à 25, ajout et déduplication ;
- ordre serveur conservé et aucun total inventé ;
- annulation au démontage et réponse tardive ignorée ;
- absence de donnée locataire ou secrète.

### 16.3 Création

- fuseau local valide et fallback Toronto ;
- corps exact, CSRF et absence de `organization_id` ;
- verrou de double soumission ;
- UUID stable et corps identique après erreur ambiguë ;
- nouvel UUID après modification ;
- succès 201 et rejeu 200 réconciliés ;
- échec de livraison affiché sans perdre la ressource ;
- conflit d’idempotence terminal et abandon explicite.

### 16.4 Invitation initiale

- actions exactes pour chaque couple état organisation/invitation ;
- renvoi stable par intention et indépendant entre organisations ;
- révocation précédée d’une confirmation et corps `{}` ;
- `429` avec délai ;
- invitation acceptée sans action ;
- `404`, résultat inconnu et indisponibilité sans rejeu automatique.

### 16.5 Qualité transversale

- aucune écriture `localStorage`/`sessionStorage` ;
- aucune clé ou secret dans l’URL/DOM/console ;
- ESLint, Vitest et build verts ;
- Ruff, mypy, pytest et Alembic inchangés ;
- tests Google 2.3.4 inchangés ;
- `git diff --check` vert.

## 17. Protocole local d’acceptation

1. Démarrer PostgreSQL, Redis, Mailpit, backend et frontend ; confirmer `/api/health/ready` à `ready`.
2. Se connecter comme Administrateur plateforme sans appartenance et vérifier la redirection vers Plateforme.
3. Confirmer que Recherche, Organisation et Membres ne deviennent pas accessibles implicitement.
4. Créer une organisation avec un courriel inédit ; vérifier la ligne `provisioning` et le message Mailpit.
5. Ouvrir le lien Mailpit, accepter l’invitation et vérifier que la ligne devient `active/accepted` après actualisation.
6. Créer une seconde organisation, révoquer sa première invitation et confirmer que le lien ne fonctionne plus.
7. Renvoyer cette invitation, vérifier le nouveau courriel et l’invalidation de l’ancien lien.
8. Tester un renvoi trop rapide et vérifier le délai `429` sans boucle automatique.
9. Se connecter comme Admin locataire non plateforme et vérifier l’absence du menu et le `403` direct.
10. Vérifier les stockages navigateur, l’URL et le responsive mobile.
11. Confirmer que le script PowerShell de diagnostic continue de fonctionner sans être nécessaire au parcours normal.

## 18. Critique experte 1 — Sécurité et séparation des autorités

### Risques

- confondre visibilité globale du provisioning et accès aux données locataires ;
- ajouter un bouton d’entrée dans une organisation sans appartenance ;
- faire confiance aux capacités seulement côté interface ;
- exposer des identifiants techniques ou un jeton dans la liste.

### Réponses intégrées

- page limitée au `ProvisioningResponse` minimal ;
- aucune impersonation, aucun changement d’organisation depuis une ligne ;
- capacités serveur, rôle plateforme et fonctions SQL restent obligatoires ;
- contrôle explicite de l’absence de secrets et de données CRM dans les tests.

## 19. Critique experte 2 — Idempotence et résultats distribués

### Risques

- créer deux organisations après un timeout ;
- régénérer une clé en cliquant à nouveau trop vite ;
- réutiliser une clé avec un formulaire modifié ;
- interpréter un échec de courriel comme annulation de la transaction PostgreSQL.

### Réponses intégrées

- verrou synchrone et objet d’intention `{id, corps}` ;
- même intention après réseau/résultat inconnu, nouvelle intention après édition ;
- conflit terminal sans retry automatique ;
- ressource conservée et avertissement distinct lorsque la livraison échoue.

## 20. Critique experte 3 — UX et exploitation

### Risques

- inventer un total ou un statut non fourni ;
- bloquer toute la page pendant l’action d’une ligne ;
- laisser croire qu’une révocation supprime l’organisation ;
- rendre l’interface dépendante de Mailpit ou du script local.

### Réponses intégrées

- pagination sans total et réconciliation par réponse serveur ;
- verrous par intention, opérations indépendantes entre lignes ;
- textes distinguant invitation, organisation et livraison ;
- adaptateur de livraison abstrait, Mailpit local et script conservé comme diagnostic seulement.

## 21. Séquence d’implémentation proposée

1. activer route, destination plateforme et tests de capacités ;
2. ajouter `platformApi`, hook paginé, liste et états vides/erreurs ;
3. ajouter création idempotente et réconciliation ;
4. ajouter renvoi/révocation selon état ;
5. ajouter tests d’erreurs, confidentialité, responsive et matrice complète ;
6. effectuer deux revues de code et préparer la validation locale avant D terminé.

## 22. Seize décisions validées

1. Réutiliser exclusivement les quatre endpoints plateforme existants, sans migration ni nouvelle API.
2. Activer `/app/platform/organizations` avec `platform:organizations:read`, sans organisation active obligatoire.
3. Diriger vers Plateforme un Administrateur plateforme sans appartenance, tout en gardant la priorité locataire
   actuelle lorsqu’une organisation active existe réellement.
4. Ne fournir aucune impersonation, entrée forcée dans un locataire ou appartenance automatique.
5. Afficher seulement les métadonnées de provisioning et la première invitation, sans données CRM, Google ou membres.
6. Paginer par 25, conserver l’ordre serveur, dédupliquer par organisation et ne jamais inventer de total.
7. Réserver formulaire et actions à `platform:organizations:create`, avec rôle initial Admin non modifiable.
8. Initialiser le fuseau depuis `Intl`, avec fallback `America/Toronto`, tout en laissant le serveur valider.
9. Conserver un couple UUID/corps stable après réseau ou résultat inconnu et créer une nouvelle intention après édition.
10. Traiter `idempotency_key_reused` comme terminal, avec abandon explicite et sans retry automatique.
11. Autoriser renvoi pour une invitation active, expirée ou révoquée tant que l’organisation est `provisioning`.
12. Exiger confirmation pour révoquer une invitation active/expirée et masquer toute action après acceptation/activation.
13. Afficher `Retry-After`, distinguer échec de livraison et échec de création, et conserver la ressource créée.
14. Garder toutes les intentions, listes et curseurs uniquement en mémoire et les purger au changement de session/route.
15. Conserver suspension, modification d’organisation, audit et exploitation locataire hors de D.
16. Exiger la matrice de tests de la section 16 et la validation locale de la section 17 avant de passer à E.

Ces décisions ont été validées par le responsable produit le 3 août 2026. Elles constituent le contrat obligatoire de
2.3.5-D. Toute dérogation devra être documentée et validée avant son implémentation.

## 23. Références internes

- [`PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_2_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_2_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_2_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_SPECIFICATIONS_DETAILLEES.md)
