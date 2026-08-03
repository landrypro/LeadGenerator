# Phase 2.3.4 — Spécifications détaillées de la protection Google et de la transition de l’écran

| Élément | Valeur |
| --- | --- |
| Version | 1.0 |
| Date | 2 août 2026 |
| Statut | Implémenté et validé localement par le responsable produit ; rejeu des 17 tests d’infrastructure requis avant déploiement |
| Incrément | 2.3.4 — Protection Google et transition de l’écran |
| Prérequis | 2.3.3 validé localement le 2 août 2026 |
| Validation produit | 2 août 2026, recherche Places et parcours Places + Maps Static confirmés |
| Marché et compte de facturation Google | Canada |
| Migration SQL | Aucune nouvelle révision prévue |

## 1. Objectif

2.3.4 ferme la transition entre la recherche Google temporaire de phase 1 et l’identité multi-organisation livrée par
2.3.1 à 2.3.3. La recherche Places et la génération Maps Static deviennent inaccessibles sans session valide,
organisation active et capacité explicite.

L’identité déclarative demandant prénom, raison sociale et adresse professionnelle disparaît. L’acteur et
l’organisation proviennent exclusivement de la session résolue côté serveur. Aucun changement ne doit augmenter le
nombre de résultats, ajouter une pagination Google, exposer des coordonnées de contact ou persister du contenu Google.

## 2. Résultat attendu

À la sortie de 2.3.4 :

- `POST /api/google/places/search` exige une session locataire et `google:search` ;
- `POST /api/map/snapshot` exige la même identité locataire et `google:map` ;
- l’Administrateur de plateforme sans appartenance ne bénéficie d’aucun accès Google implicite ;
- le bloc `requester` et tout `organization_id` fourni par le client sont rejetés ;
- une seule recherche peut être en cours pour un même utilisateur dans une même organisation ;
- chaque concession cartographique est liée à l’utilisateur et à l’organisation qui ont lancé la recherche ;
- une identité différente ne peut déclencher aucun appel Maps Static avec un jeton volé ;
- l’écran déclenche directement la recherche depuis son formulaire, sans fenêtre d’identité intermédiaire ;
- les résultats, la carte et les jetons restent éphémères et absents des stockages navigateur et PostgreSQL ;
- toutes les garanties Google de phase 1 et toute la matrice qualité restent vertes.

## 3. Garanties héritées et non négociables

2.3.4 conserve sans réinterprétation :

- exactement une requête Text Search par action utilisateur acceptée ;
- `pageSize` et réponse limités à vingt établissements ;
- aucun suivi de `nextPageToken` ;
- aucun téléphone, téléphone international ou site Web dans le masque, le domaine, l’API ou l’interface ;
- aucune route HTTP historique de recherche ou d’export ;
- bouton d’export Google visible mais désactivé ;
- `Cache-Control: no-store, max-age=0` pour résultats, carte, succès et erreurs sensibles ;
- attribution visible `Google Maps` dans le conteneur des résultats ;
- aucune persistance serveur ou navigateur des résultats descriptifs Google ;
- clés Google exclusivement côté serveur et absentes des journaux, réponses et bundles frontend ;
- cookie de session `HttpOnly`, protection CSRF et origines CORS explicites ;
- capacité recalculée côté serveur, jamais déduite d’un contrôle visuel React.

Les protections RLS ne sont pas sollicitées pour stocker du contenu Google puisqu’aucune écriture métier Google n’est
introduite dans cet incrément.

## 4. Périmètre

### 4.1 Inclus

- protection authentifiée des deux routes Google facturables ;
- ajout et application de la capacité `google:map` ;
- contexte applicatif Google composé d’identifiants internes ;
- adaptation des ports de verrou et de concession cartographique ;
- liaison des concessions à l’acteur et à l’organisation ;
- retrait du schéma API `RequesterInfo` et rejet des champs transitoires ;
- retrait de `IdentityModal`, de `initialRequester` et du flux React associé ;
- contrôle de route frontend pour une session avec organisation active ;
- contrat d’erreur commun et absence d’appel fournisseur lors d’un refus local ;
- tests unitaires, API, PostgreSQL/Redis réels et React ;
- actualisation du README, des pages légales et des documents de transition ;
- protocole PowerShell de validation locale sans exposition de secret.

### 4.2 Explicitement différé

- quotas Google journaliers ou mensuels par organisation ;
- limitation séquentielle du nombre de recherches par forfait ;
- verrou et concessions Redis partagés entre plusieurs instances API, prévus en 2.6 ;
- stockage durable de `place_id` et réhydratation Places, prévus avec les prospects ;
- recherche multi-zone et pagination Google ;
- import ou export de contenu Google ;
- écran d’administration, navigation complète et sélecteur visuel d’organisation, prévus en 2.3.5 ;
- audit append-only et suspension d’organisation, prévus en 2.4 ;
- signature numérique Maps Static ou OAuth serveur, qui restent des durcissements de déploiement à évaluer ;
- toute évolution des champs, du classement ou du rayon de la recherche actuelle.

## 5. État actuel et écarts à fermer

L’implémentation avant 2.3.4 présente quatre écarts intentionnellement transitoires :

1. les routes Places et Maps Static ne résolvent pas encore la session ;
2. `GooglePlaceSearchRequest` accepte un bloc `requester` contenant une identité déclarée ;
3. le verrou mémoire dérive sa clé d’une adresse professionnelle fournie par le navigateur ;
4. la concession cartographique contient seulement la charge de carte et peut être consommée par tout détenteur du
   jeton.

La capacité `google:search` existe pour les trois rôles. `google:map`, déjà prévue par la spécification générale 2.3,
doit être ajoutée pendant 2.3.4.

## 6. Acteurs et capacités

| Capacité | Administrateur | Gestionnaire | Commercial | Admin plateforme sans appartenance |
| --- | --- | --- | --- | --- |
| `google:search` | oui | oui | oui | non |
| `google:map` | oui | oui | oui | non |

Une organisation doit être `active` et l’appartenance courante doit être `active`. Une organisation `provisioning` ou
`suspended`, une appartenance désactivée, une session expirée ou une absence d’organisation active empêche tout appel
Google.

Les deux capacités restent distinctes afin de pouvoir suspendre ultérieurement la carte sans modifier le droit de
recherche. La réponse de login, `GET /api/auth/me` et le changement d’organisation exposent les capacités recalculées.
Le frontend les utilise pour le rendu ; le backend les vérifie à chaque requête.

## 7. Contexte applicatif Google

Un objet immuable, nommé conceptuellement `GoogleAccessContext`, traverse la couche application :

```text
user_id         UUID interne
organization_id UUID interne de l’organisation active
membership_id   UUID interne de l’appartenance active
```

Il est construit depuis `RequestAuthentication` après résolution de la session. Aucun de ces identifiants n’est lu
depuis le corps, la chaîne de requête ou un en-tête client libre.

`membership_id` fournit la traçabilité technique. Le verrou et la propriété de concession reposent sur le couple
stable `(organization_id, user_id)`, conformément aux décisions déjà validées pour 2.3. Un changement d’organisation
modifie donc immédiatement la portée autorisée.

## 8. Contrat de recherche Places

### 8.1 Route et commande

`POST /api/google/places/search`

```json
{
  "query": "plombier",
  "center_latitude": 46.8139,
  "center_longitude": -71.208,
  "radius_km": 15,
  "include_service_area_businesses": true,
  "language_code": "fr",
  "region_code": "CA"
}
```

La commande est stricte. `requester`, `organization_id`, `user_id`, `membership_id`, `target`, `max_pages`,
`max_tiles`, `contact_fields` et tout autre champ inconnu produisent `422 validation_failed`. Ils ne sont ni ignorés
ni transmis au fournisseur.

Les bornes existantes restent : terme de 2 à 120 caractères, latitude `[-90, 90]`, longitude `[-180, 180]`, rayon
strictement positif et inférieur ou égal à 50 km, code région à deux lettres normalisé en majuscules.

### 8.2 Ordre obligatoire des contrôles

Avant le premier appel fournisseur, la route doit :

1. vérifier le type JSON et l’origine de confiance ;
2. résoudre la session Redis et relire l’identité PostgreSQL ;
3. exiger une organisation et une appartenance actives ;
4. exiger `google:search` ;
5. vérifier le jeton CSRF ;
6. vérifier la configuration de la clé Places ;
7. acquérir le verrou interne de l’acteur ;
8. exécuter exactement un Text Search.

Une validation Pydantic peut refuser un corps mal formé avant l’entrée dans le cas d’utilisation, mais aucun refus
local ne doit atteindre Google.

### 8.3 Réponse

Le contrat de succès demeure `GooglePlaceSearchResponse` :

- zéro à vingt `places` ;
- statistiques bornées avec `api_calls=1` ;
- `searched_at` avec fuseau ;
- `map_snapshot_token` opaque ;
- `search_parameters` effectifs sans identité ni identifiant locataire.

Les contacts restent absents. La réponse n’est ni mise en cache ni écrite en base.

## 9. Verrou de recherche

Le port `GenerationGuard` ne reçoit plus une adresse libre. Il reçoit une clé applicative typée construite avec
`organization_id` et `user_id`.

Règles :

- une seule recherche en vol pour le même utilisateur dans la même organisation ;
- une seconde requête concurrente retourne `409 google_search_in_progress` avant Google ;
- deux utilisateurs différents de la même organisation peuvent rechercher simultanément ;
- la libération se produit dans un `finally`, succès, erreur fournisseur ou annulation compris ;
- aucun terme, adresse, courriel ou coordonnée n’entre dans la clé ;
- les identifiants internes peuvent rester dans la mémoire du processus et dans les journaux techniques autorisés ;
- l’adaptateur mémoire reste borné à l’activité en cours et ne conserve aucun historique.

Cette protection est mono-instance. Deux processus peuvent encore accepter simultanément deux recherches du même
acteur. Le passage à un verrou Redis avec propriétaire et expiration reste obligatoire en 2.6 avant réplication.

## 10. Concession Maps Static

### 10.1 Émission

Après la construction des résultats temporaires, le cas d’utilisation émet un jeton aléatoire d’au moins 256 bits
d’entropie. Le jeton est opaque : il n’encode ni utilisateur, ni organisation, ni coordonnées.

La valeur serveur associée contient uniquement :

```text
owner_user_id
owner_organization_id
map_snapshot(center, rayon, points)
expires_at
state = available | in_progress
```

La durée par défaut et maximale est de cinq minutes. L’éviction de capacité continue de supprimer en priorité les
concessions expirées, puis la plus ancienne concession disponible. Une concession `in_progress` n’est jamais évincée
au profit d’une nouvelle émission.

### 10.2 Consommation

`POST /api/map/snapshot` reçoit uniquement :

```json
{
  "token": "jeton-opaque"
}
```

La route applique JSON, origine, session, organisation active, `google:map`, CSRF et configuration Maps Static avant
de réserver la concession. Elle fournit ensuite le même contexte interne au port de consommation.

Règles de propriété :

- même utilisateur et même organisation : consommation autorisée ;
- autre utilisateur, autre organisation, jeton absent ou expiré : même réponse `403 invalid_map_grant` ;
- une tentative par un autre acteur ne consomme pas la concession du propriétaire ;
- un changement vers une autre organisation rend la concession inutilisable dans ce contexte ;
- une reconnexion du même utilisateur dans la même organisation reste autorisée pendant la courte durée de vie : la
  concession est liée à l’acteur, pas au cookie particulier.

### 10.3 Usage unique et facturation

La réservation est atomique dans le processus. Un concurrent du propriétaire reçoit `409 map_grant_in_progress`.
Dès que l’appel Maps Static commence, la concession devient terminale et est supprimée après le résultat, y compris
en cas d’erreur fournisseur. Le même jeton ne peut donc jamais déclencher une seconde tentative facturable.

Ce choix privilégie la maîtrise des coûts. Après un échec Maps Static, l’utilisateur voit l’erreur et doit relancer une
nouvelle recherche s’il souhaite obtenir une nouvelle concession. Aucun retry automatique n’est introduit.

### 10.4 Réponse image

La réponse réussie conserve le type d’image validé par l’adaptateur, `X-Content-Type-Options: nosniff` et
`Cache-Control: no-store, max-age=0`. L’URL Google comprenant la clé n’atteint jamais le navigateur.

## 11. Contrats d’erreur

Toutes les erreurs de ces routes adoptent l’enveloppe API commune avec `request_id`, sans ancien champ `detail` isolé.

| HTTP | Code | Situation | Appel Google autorisé |
| --- | --- | --- | --- |
| `401` | `authentication_required` | session absente, expirée ou révoquée | non |
| `403` | `active_organization_required` | aucun contexte locataire actif | non |
| `403` | `insufficient_capability` | capacité Google absente | non |
| `403` | `request_rejected` | origine ou CSRF refusé | non |
| `403` | `invalid_map_grant` | jeton absent, expiré ou appartenant à un autre acteur | non |
| `409` | `google_search_in_progress` | recherche déjà en vol pour l’acteur | non |
| `409` | `map_grant_in_progress` | consommation concurrente du jeton propriétaire | non |
| `415` | `json_required` | type de contenu incorrect | non |
| `422` | `validation_failed` | corps ou paramètre invalide/inconnu | non |
| `429` | `google_rate_limited` | refus Places transmis de façon bornée | déjà effectué |
| `502` | `google_places_unavailable` | échec Places borné | déjà effectué |
| `502` | `google_map_unavailable` | échec Maps Static borné | déjà effectué |
| `503` | `authentication_unavailable` | PostgreSQL ou Redis d’identité indisponible | non |
| `503` | `google_not_configured` | clé serveur requise absente | non |

Les messages ne recopient pas le corps Google, son URL, la clé, le jeton de carte, la requête utilisateur ou les
coordonnées retournées. Toutes les réponses portent `no-store`.

## 12. Transition frontend

### 12.1 Suppressions

L’implémentation retire :

- `IdentityModal.jsx` et ses styles devenus inutiles ;
- `initialRequester` ;
- les états `requester` et `identityModalOpen` ;
- la saisie du prénom, de la société et de l’adresse professionnelle ;
- le passage de `requester` dans `useLeadSearch` et `leadSearchApi.search`.

### 12.2 Nouveau parcours

1. l’utilisateur authentifié ouvre l’écran avec une organisation active ;
2. il renseigne ou ajuste le formulaire existant ;
3. il clique explicitement sur « Rechercher des établissements » ;
4. le bouton passe immédiatement à l’état occupé et devient inaccessible ;
5. un seul appel HTTP de recherche est créé ;
6. le jeton reçu déclenche au maximum une demande de carte ;
7. résultats et URL objet de l’image sont détruits au remplacement ou au démontage.

Le cartouche annonçant « 1 appel Google par recherche » reste visible avant l’action. Aucun retry automatique de la
recherche ou de la carte n’est ajouté.

### 12.3 Contrôle d’accès visuel

L’écran n’est rendu que si :

- une session est restaurée ;
- `active_organization` est présente ;
- `google:search` est exposée.

Un Administrateur plateforme sans organisation reçoit l’état contrôlé « aucune organisation accessible » jusqu’à la
livraison de son écran en 2.3.5. Une capacité absente produit une page ou un état d’accès refusé, jamais un écran
facturable partiellement actif.

Le contrôle React améliore l’expérience mais n’est pas une frontière de sécurité.

### 12.4 Données navigateur

Les résultats, paramètres, capacités, jeton CSRF et concession de carte restent en mémoire React. Aucun appel à
`localStorage`, `sessionStorage`, IndexedDB, Cache API ou service worker n’est autorisé. L’URL `blob:` de la carte est
révoquée lors du remplacement, de l’erreur ou du démontage.

## 13. Conformité Google et confidentialité

La documentation Google actuelle rappelle que les clés de services Web doivent rester secrètes, être restreintes aux
API nécessaires et, pour un serveur, être limitées aux adresses IP lorsque l’environnement le permet. Le proxy doit
exiger une authentification et ne doit pas relayer des appels arbitraires du client.

Le projet applique donc :

- clés distinctes recommandées pour Places API (New) et Maps Static API ;
- restrictions d’API sur chacune ;
- restriction d’application serveur/IP au déploiement lorsque l’adresse de sortie est stable ;
- secrets injectés hors dépôt et hors bundle ;
- paramètres Google construits exclusivement par les adaptateurs ;
- masque de champs minimal ;
- surveillance des usages et alertes budgétaires dans Google Cloud avant production.

Les règles Places interdisent le préchargement, la mise en cache ou le stockage de contenu au-delà des exceptions et
exigent une attribution appropriée. Même si `place_id` peut être conservé, 2.3.4 ne le persiste pas encore. La liste
continue d’afficher l’attribution `Google Maps` et les pages publiques conservent les liens vers les conditions et la
politique de confidentialité Google.

Le compte de facturation étant canadien, les travaux restent alignés sur le parcours contractuel non-EEE identifié
lors de la phase 1.1. Cette mention documente le contexte et ne constitue pas un avis juridique.

Références officielles :

- [Google Maps Platform — sécurité des clés](https://developers.google.com/maps/api-security-best-practices) ;
- [Places API — règles et attribution](https://developers.google.com/maps/documentation/places/web-service/policies?hl=fr) ;
- [Places API — conservation des Place IDs](https://developers.google.com/maps/documentation/places/web-service/place-id) ;
- [Maps Static API — démarrage et signature recommandée](https://developers.google.com/maps/documentation/maps-static/start).

## 14. Journalisation transitoire

En attendant l’audit append-only de 2.4, les journaux techniques peuvent contenir :

- `request_id`, route normalisée, statut et durée ;
- `user_id`, `organization_id` et `membership_id` internes ;
- opération `google_places_search` ou `google_map_snapshot` ;
- résultat borné et indicateur booléen d’appel fournisseur.

Ils excluent :

- terme, latitude, longitude, rayon et paramètres de recherche ;
- résultats, noms, adresses, URLs et `place_id` ;
- jeton de carte ou hash dérivé inutile ;
- cookie, CSRF, courriel, clé Google et URL fournisseur ;
- corps ou message brut retourné par Google.

2.3.4 n’introduit pas une table d’audit anticipée. Les événements immuables arrivent en 2.4.

## 15. Architecture Clean et contrats de ports

### 15.1 Présentation

Les routes résolvent `RequestAuthentication`, vérifient origine, CSRF et capacités, construisent
`GoogleAccessContext`, puis appellent les cas d’utilisation. Elles n’accèdent directement ni à Redis, ni au stockage
des concessions, ni à `httpx`.

### 15.2 Application

- `SearchGooglePlacesUseCase.execute(criteria, access_context)` ;
- `GetMapSnapshotUseCase.execute(token, access_context)` ;
- `GenerationGuard.hold(search_owner)` ;
- `MapSnapshotGrantStore.issue(snapshot, owner)` ;
- `MapSnapshotGrantStore.redeem(token, owner)`.

Le cas d’utilisation ne connaît ni FastAPI, ni cookie, ni SQLAlchemy. Les identifiants internes sont des valeurs
typées, pas des dictionnaires de requête.

### 15.3 Adaptateurs

- l’adaptateur mémoire du verrou manipule une clé interne, sans normalisation Unicode devenue inutile ;
- l’adaptateur mémoire génère le jeton avec un générateur cryptographique, garde sa valeur opaque et compare le
  propriétaire sous le même verrou atomique que l’état ;
- les adaptateurs Google restent les seuls à connaître les clés, URLs, en-têtes et masques de champs fournisseurs ;
- les implémentations mémoire restent remplaçables par Redis sans modifier les routes ou cas d’utilisation.

## 16. Configuration et exploitation

Variables conservées :

| Variable | Règle 2.3.4 |
| --- | --- |
| `GOOGLE_MAPS_API_KEY` | clé serveur Places API (New), obligatoire en production |
| `GOOGLE_MAPS_STATIC_API_KEY` | clé serveur Maps Static distincte recommandée ; repli local seulement |
| `PLACES_TIMEOUT_SECONDS` | délai strictement positif |
| `STATIC_MAPS_TIMEOUT_SECONDS` | délai strictement positif |
| `MAP_SNAPSHOT_GRANT_TTL_SECONDS` | défaut et maximum de production : 300 secondes |
| `MAP_SNAPSHOT_GRANT_MAX_ENTRIES` | capacité mémoire positive et bornée |

Le démarrage de production refuse une clé Places absente. Le verrou de déploiement doit également refuser une
configuration Maps Static absente si la carte reste activée. Aucun nom de variable de clé ne commence par `VITE_`.

La route publique `/api/health` peut continuer à exposer uniquement un booléen de configuration, jamais la clé, son
préfixe, son projet ou sa restriction.

## 17. Migration et compatibilité

Aucune table, politique RLS, fonction SQL ou donnée persistée n’est ajoutée. La tête Alembic reste
`20260802_0005`.

La rupture volontaire concerne le contrat HTTP : un ancien client envoyant `requester` reçoit `422`. Le frontend et
le backend sont donc livrés ensemble. Aucun mode de compatibilité silencieux et aucune période acceptant les deux
schémas ne sont autorisés.

Les façades Python historiques d’export restent uniquement disponibles pour leurs tests de neutralisation Excel et ne
sont toujours pas montées en HTTP.

## 18. Tests backend obligatoires

### 18.1 Domaine et application

- clé de verrou identique pour le même utilisateur et la même organisation ;
- clés différentes entre utilisateurs ou organisations ;
- second détenteur concurrent refusé et libération garantie après exception/annulation ;
- exactement un appel Places pour une exécution acceptée ;
- limite à vingt, déduplication et rayon inchangés ;
- aucun contact et aucun suivi de page ;
- concession émise avec propriétaire exact ;
- propriétaire correct autorisé une seule fois ;
- autre utilisateur et autre organisation refusés sans consommation ;
- expiration, concurrence, capacité et éviction testées ;
- erreur Maps terminale : le jeton ne peut pas relancer un second appel.

### 18.2 API

- recherche et carte sans cookie : `401`, zéro appel fournisseur ;
- session sans organisation active : `403`, zéro appel fournisseur ;
- capacité absente : `403`, zéro appel fournisseur ;
- origine ou CSRF absent/invalide : `403`, zéro appel fournisseur ;
- configuration absente vérifiée seulement après autorisation ;
- `requester` et `organization_id` : `422`, schéma OpenAPI sans ces propriétés ;
- utilisateur Admin, Manager et Sales actif : recherche puis carte autorisées ;
- Administrateur plateforme sans appartenance : refusé ;
- concurrence du même acteur : un seul fournisseur atteint ;
- vol de concession par un autre utilisateur de la même organisation : refusé ;
- vol depuis une autre organisation : refusé ;
- concession de l’ancienne organisation après changement : refusée ;
- consommation propriétaire : image `200`, `no-store`, puis rejeu `403` ;
- erreurs communes avec `request_id` et sans fuite fournisseur ;
- anciennes routes `/api/leads/search` et `/api/leads/export` toujours absentes.

### 18.3 Intégration réelle

Les scénarios d’identité utilisent PostgreSQL et Redis réels : login, session, appartenance, capacité et changement
d’organisation. Les fournisseurs Google restent simulés pour prouver précisément le nombre d’appels sans coût réel.

Aucun test d’intégration ne contourne l’authentification en réintroduisant un faux demandeur dans le corps.

## 19. Tests frontend obligatoires

- aucun dialogue d’identité et aucun champ prénom/société/adresse ;
- un clic valide appelle `leadSearchApi.search` exactement une fois ;
- charge utile limitée aux paramètres de recherche ;
- aucun `requester`, `organization_id`, utilisateur ou capacité dans la charge utile ;
- bouton désactivé pendant la requête et double soumission neutralisée ;
- `credentials` et CSRF appliqués par le client HTTP à la recherche et à la carte ;
- `401` vide la session et revient à la connexion ;
- session sans organisation ou sans capacité : écran Google non rendu ;
- Administrateur plateforme sans organisation : écran facturable non rendu ;
- présence de `google:search` sans `google:map` : recherche visible mais aucun appel de carte automatique ;
- un jeton de réponse produit au maximum une demande de carte ;
- aucune relance automatique après erreur Places ou Maps ;
- révocation de l’URL `blob:` ;
- aucun stockage navigateur ;
- attribution Google visible et export désactivé ;
- absence des termes « générateur » et « leads » dans l’interface livrée.

## 20. Non-régression et qualité

Les contrôles suivants sont obligatoires et sans test ignoré :

1. Alembic `current` sur PostgreSQL réel, toujours à `20260802_0005 (head)` ;
2. Ruff ;
3. mypy ;
4. pytest unitaire ;
5. pytest d’intégration PostgreSQL/Redis ;
6. tests Google historiques adaptés au nouveau contexte ;
7. ESLint ;
8. Vitest ;
9. build Vite ;
10. Azure Pipelines avec les mêmes contrôles.

Les totaux réels sont consignés dans le rapport d’implémentation. Une baisse de couverture expliquée par la suppression
du dialogue n’autorise pas la suppression d’un scénario de sécurité équivalent.

## 21. Documentation à actualiser pendant l’implémentation

- README : supprimer la procédure demandant prénom, société et adresse ;
- README : documenter session, organisation et capacités Google ;
- `confidentialite.html` : retirer le traitement temporaire de ces trois champs ;
- `conditions.html` : retirer l’obligation de les fournir et décrire le verrou par compte/organisation ;
- documentation technique : contrats, erreurs, port de verrou et concession liée ;
- documentation utilisateur : recherche directe et message d’accès refusé ;
- `TRANSITIONAL_FEATURES.md` : marquer l’identité temporaire comme supprimée en 2.3.4 ;
- rapport 2.3.4 : preuves, critiques, revues et protocole local.

## 22. Protocole local prévu

1. confirmer PostgreSQL et Redis `ok` dans `/api/health/ready` ;
2. confirmer Alembic `20260802_0005 (head)` ;
3. démarrer backend, frontend et se connecter comme membre actif ;
4. vérifier l’absence de la fenêtre d’identité ;
5. effectuer une recherche explicite et constater vingt résultats maximum ;
6. inspecter la requête : aucun `requester` ou identifiant locataire, cookie et CSRF présents ;
7. vérifier une seule requête Places et au maximum une requête Maps Static ;
8. vérifier la carte, l’attribution et l’export désactivé ;
9. se déconnecter puis confirmer que l’écran et les routes Google sont refusés ;
10. utiliser un compte présent dans deux organisations pour prouver qu’une concession de l’organisation A est refusée
    dans B ;
11. confirmer qu’un autre utilisateur ne peut pas consommer cette concession ;
12. vérifier qu’aucun stockage navigateur ne contient résultats ou jeton ;
13. lancer toute la matrice qualité ;
14. contrôler les restrictions des deux clés dans Google Cloud avant tout environnement exposé.

Un script `Test-GoogleProtectionLocal.ps1` devra automatiser les contrôles HTTP non visuels avec au maximum une
recherche réelle explicitement confirmée par l’opérateur. Il ne lit ni n’affiche cookie, CSRF, concession ou clé.

## 23. Séquence d’implémentation proposée

1. ajouter `google:map` et le contexte typé ;
2. adapter les ports et tests unitaires du verrou et des concessions ;
3. adapter les deux cas d’utilisation ;
4. sécuriser les routes et uniformiser leurs erreurs ;
5. migrer les tests API vers de vraies sessions ;
6. retirer `requester` du schéma et du frontend ;
7. renforcer le routage visuel par capacité ;
8. actualiser pages légales et documentation ;
9. exécuter la matrice complète et le protocole local ;
10. réaliser trois critiques et deux revues de code avant validation produit.

## 24. Critiques préalables

### 24.1 Critique sécurité offensive et facturation

**Risques :** vol d’un jeton de carte, CSRF sur une action facturable, compte plateforme utilisé comme passe-droit,
double clic, rejeu après erreur et fuite de clé par URL.

**Réponses intégrées :** identité serveur, origine et CSRF, capacités distinctes, liaison utilisateur/organisation,
usage unique terminal, verrou en vol, proxy serveur et absence d’URL Google côté client.

**Risque résiduel accepté :** un utilisateur authentifié peut encore effectuer de nombreuses recherches séquentielles.
Les quotas atomiques arrivent en 2.6 ; 2.3.4 seul n’autorise donc pas une exposition publique sans garde opérationnelle.

### 24.2 Critique architecture et concurrence

**Risques :** faire dépendre le domaine de FastAPI, utiliser un dictionnaire d’identité non typé, casser les tests par
un faux bypass d’authentification, ou prétendre à une exclusion distribuée avec un `asyncio.Lock` local.

**Réponses intégrées :** contexte applicatif immuable, ports explicites, fournisseurs simulés derrière leurs ports,
intégrations avec session réelle et frontière mono-instance documentée.

**Risque résiduel accepté :** une désactivation strictement concurrente à une requête déjà autorisée peut laisser cette
requête en vol atteindre Google. Les requêtes suivantes sont refusées par la version de sécurité et la révocation de
session ; aucune transaction distribuée ne peut annuler un appel fournisseur déjà parti.

### 24.3 Critique conformité et expérience utilisateur

**Risques :** conserver dans les textes légaux des données qui ne sont plus demandées, cacher l’attribution, créer un
retry implicite ou transformer la suppression du dialogue en appel involontaire.

**Réponses intégrées :** documentation et pages légales synchronisées, attribution et cartouche de coût conservés,
bouton explicite, état occupé immédiat, absence de retry et tests de non-stockage.

**Compromis :** après une erreur Maps Static, l’utilisateur ne peut pas rejouer la même concession. Ce comportement est
moins confortable mais garantit qu’un jeton n’engendre pas deux appels facturables.

## 25. Décisions proposées à validation

Les seize décisions suivantes forment le contrat proposé de 2.3.4 :

1. Limiter 2.3.4 à la protection Google et à la transition de l’écran, sans nouvelle migration SQL ni écran
   d’administration.
2. Exiger session valide, organisation active et appartenance active pour Places et Maps Static.
3. Ajouter `google:map` aux trois rôles locataires et conserver `google:search` pour la recherche.
4. Ne donner aucun accès Google implicite à l’Administrateur de plateforme sans appartenance.
5. Exiger JSON, origine fiable et CSRF pour les deux actions POST facturables.
6. Supprimer `requester` et rejeter strictement tout identifiant locataire ou champ inconnu fourni par le client.
7. Appliquer l’ordre autorisation, configuration, verrou, puis fournisseur ; tout refus local produit zéro appel Google.
8. Verrouiller une seule recherche en vol par couple `(organization_id, user_id)` et conserver temporairement
   l’adaptateur mémoire jusqu’à 2.6.
9. Conserver exactement un Text Search, vingt résultats, aucun contact, aucune pagination et aucune persistance.
10. Lier chaque concession opaque à `user_id` et `organization_id`, avec au moins 256 bits d’entropie et cinq minutes
    au maximum.
11. Rendre la concession terminale après la première tentative Maps Static ; un autre acteur est refusé sans la
    consommer et aucun retry automatique n’est permis.
12. Uniformiser les erreurs Google avec l’enveloppe commune, `request_id`, `no-store` et aucune fuite fournisseur.
13. Supprimer la fenêtre d’identité et lancer directement la recherche par le bouton existant, protégé contre la
    double soumission.
14. Conserver résultats et jetons uniquement en mémoire, maintenir attribution/export désactivé et synchroniser les
    pages légales.
15. Garder les clés exclusivement côté serveur, préférer deux clés séparées et appliquer restrictions d’API et
    d’application avant déploiement.
16. Exiger la matrice qualité complète, le protocole local, trois critiques et deux revues de code avant 2.3.5 ; ne
    pas considérer 2.3.4 seul comme suffisant pour une exposition multi-instance sans les quotas/verrous de 2.6.

Ces seize décisions ont été validées sans modification par le responsable produit le 2 août 2026. Après vérification
de la limite officielle de Text Search (New), le responsable produit a confirmé le maintien de vingt résultats,
exactement une requête et aucun suivi de `nextPageToken`. Ces décisions constituent désormais le contrat obligatoire
de 2.3.4. Toute dérogation ultérieure sera documentée et soumise à validation.

## 26. Définition de « terminé »

2.3.4 sera terminé lorsque :

- les seize décisions de la section 25 sont validées puis implémentées ;
- aucune route Google facturable n’est utilisable anonymement ou sans organisation ;
- le demandeur temporaire a disparu du schéma, du frontend, du README et des pages légales ;
- le verrou utilise uniquement les identifiants internes ;
- le vol inter-utilisateur et inter-organisation d’une concession est prouvé impossible ;
- chaque jeton produit au maximum un appel Maps Static ;
- les fournisseurs ne sont jamais appelés après un refus local ;
- toutes les garanties Google de phase 1 restent vertes ;
- Ruff, mypy, pytest, intégrations, ESLint, Vitest, build et pipeline sont verts ;
- trois critiques, deux revues de code et le protocole local sont consignés ;
- le responsable produit accepte le parcours et autorise 2.3.5.

## 27. Références internes

- [`PHASE_2_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_1_1_ACQUISITION_CONSERVATION.md`](PHASE_1_1_ACQUISITION_CONSERVATION.md)
- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)
- [`../README.md`](../README.md)
