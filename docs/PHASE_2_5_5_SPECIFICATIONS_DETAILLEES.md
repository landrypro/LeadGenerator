# Incrément 2.5.5 — Interface CRM et verrou qualité final

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.5.5 — Interface CRM et verrou qualité final |
| Version | 0.1 |
| Statut | Décisions validées ; 2.5.5-A à 2.5.5-E implémentés ; recette QA à signer |
| Prérequis | 2.5.2 validé avec réserves ; 2.5.3 et 2.5.4 implémentés |
| Migration de départ | `20260814_0011 (head)` |
| Recette attendue | Recette locale regroupée 2.5.3–2.5.5 et verrou qualité complet |
| Résultat attendu | Un portefeuille prospects utilisable, conforme, accessible et prêt pour la suite CRM |

## 1. Finalité

2.5.5 transforme les contrats backend des incréments 2.5.1 à 2.5.4 en parcours utilisateur cohérents. Il ne livre
pas encore le Kanban, l’import CSV effectif ni les activités commerciales, mais il doit permettre à une équipe de :

- consulter son portefeuille de prospects ;
- créer un prospect manuellement ou l’ajouter explicitement depuis une recherche Google ;
- enrichir le profil CRM d’un établissement avec des informations propres à l’organisation ;
- gérer ses personnes de contact, leurs canaux et leurs permissions ;
- administrer les fournisseurs, acquisitions, politiques de conservation et déclarations d’import ;
- constater clairement les limites fonctionnelles de la version sans action morte ni promesse trompeuse ;
- terminer la phase 2.5 avec une recette PostgreSQL réelle, une documentation QA et un verrou qualité vert.

## 2. Principes directeurs

1. L’interface n’est jamais une frontière de sécurité : capacités, RLS, CSRF et validations restent appliqués côté
   serveur.
2. Le profil CRM appartient à l’organisation. Il ne constitue pas une copie durable de la fiche Google.
3. Toute mutation est optimiste, transactionnelle et auditée ; le client transmet la `version` courante.
4. La provenance d’une donnée et la permission de contacter restent distinctes et visibles.
5. Les actions destructrices de 2.5.5 sont des archivages logiques ou des annulations contrôlées, jamais des purges.
6. Aucune donnée CRM, valeur de canal ou jeton n’est conservé dans `localStorage` ou `sessionStorage`.
7. Les réponses métier sensibles portent `Cache-Control: no-store`.
8. La recherche Google conserve les règles actuelles : un Text Search, vingt résultats au maximum, aucun contact et
   aucune pagination.

## 3. Périmètre fonctionnel

### 3.1 Inclus

- entrée « Prospects » dans la navigation locataire ;
- liste paginée côté serveur, filtres, états vide/chargement/erreur et visibilité des archives ;
- création manuelle d’un prospect ;
- ajout individuel ou groupé depuis les résultats Google déjà affichés ;
- fiche prospect et édition du profil commercial ;
- liste et création des personnes de contact ;
- ajout de canaux et décision explicite de permission ;
- consultation et administration des fournisseurs et acquisitions selon capacité ;
- consultation et administration de la conservation, des holds et des déclarations d’import selon capacité ;
- confirmation avant archivage ou décision irréversible dans le workflow courant ;
- routage dynamique, liens partageables après authentification et retour cohérent à la liste ;
- tests frontend, backend, intégration PostgreSQL, accessibilité, documentation et recette QA regroupée.

### 3.2 Exclus

- Kanban, déplacement d’étape, historique commercial, activités, tâches, rappels et opportunités ;
- import ou parsing d’un fichier CSV ;
- connexion directe à Facebook, LinkedIn ou une API tierce ;
- récupération ou stockage durable des détails descriptifs Google ;
- courriel ou appel automatisé depuis l’application ;
- fusion de doublons, purge physique, restauration d’archives et traitement automatisé de conservation ;
- internationalisation complète français/anglais, reportée à son incrément dédié ;
- facturation, plans, quotas commerciaux et paiement.

## 4. Découpage d’implémentation obligatoire

L’implémentation est découpée en cinq lots vérifiables. Chaque lot conserve une application exécutable et testable.

| Lot | Contenu | Critère de passage |
| --- | --- | --- |
| **2.5.5-A** | Compléments backend du profil, routage et liste Prospects | Migration, API, RLS et liste React verts |
| **2.5.5-B** | Fiche prospect, contacts, canaux et permissions | Parcours de bout en bout et accessibilité verts |
| **2.5.5-C** | Fournisseurs et acquisitions | Capacités, décisions et provenance vérifiées |
| **2.5.5-D** | Conservation et déclarations d’import | Holds, archivage et limites d’import vérifiés |
| **2.5.5-E** | Recette regroupée, documentation et verrou final | Go/No-Go 2.5 documenté |

Les lots peuvent partager la même révision de produit, mais aucun écran ne doit être enregistré dans le routeur avant
d’être fonctionnel, protégé et testé.

## 5. Complément du modèle de profil prospect

Le modèle actuel couvre l’identité technique du prospect mais pas l’enrichissement commercial demandé. 2.5.5-A
ajoute une migration additive, prévue comme `20260814_0012`, et les contrats applicatifs associés.

### 5.1 Champs éditables

- `internal_alias` : nom interne obligatoire, 1 à 160 caractères ;
- `industry_label` : secteur libre contrôlé, nullable, 120 caractères maximum ;
- `segment_code` : `unspecified`, `micro`, `small`, `medium`, `enterprise` ;
- `size_band` : `unknown`, `solo`, `2_10`, `11_50`, `51_200`, `201_plus` ;
- `address_line_1`, `address_line_2`, `city`, `region`, `postal_code`, `country_code` : adresse CRM saisie
  volontairement, indépendante de Google ;
- `tags` : au maximum vingt étiquettes normalisées et uniques par prospect ;
- `owner_id` : membre actif de l’organisation ou `null` ;
- `priority` : entier de 0 à 5 ;
- `profile_provenance_id` : provenance de la dernière acquisition ou saisie du profil ;
- `version`, `updated_at` : concurrence optimiste et traçabilité.

Les coordonnées de contact restent dans `contact_channels`. Aucune adresse électronique, aucun téléphone, aucun site
Web et aucune note libre sensible ne sont ajoutés directement à `prospects`.

### 5.2 Provenance du profil

- une création ou modification manuelle crée une provenance `manual` avec finalité explicite ;
- une modification issue d’une acquisition approuvée référence cette acquisition ;
- `google_maps` ne peut alimenter que `google_place_id` ;
- un libellé, une adresse ou une catégorie observés dans Google ne peuvent pas être enregistrés comme `manual` ;
- l’audit conserve les noms des champs modifiés, jamais leur ancienne ou nouvelle valeur sensible en clair.

### 5.3 Contraintes

- l’adresse est entièrement nullable, mais `country_code` est un code ISO 3166-1 alpha-2 en majuscules lorsqu’il est
  fourni ;
- les étiquettes sont normalisées Unicode, comparées sans ambiguïté et ne contiennent aucun caractère de contrôle ;
- `owner_id` doit désigner une adhésion active de la même organisation ;
- une mise à jour avec une version obsolète retourne `409 conflict` et n’écrase rien ;
- un prospect archivé reste lisible avec le filtre approprié mais n’est plus modifiable.

## 6. API complémentaire

Les contrats déjà livrés restent la source principale. Les compléments suivants sont requis par l’interface :

- `PATCH /api/prospects/{prospect_id}` — mise à jour partielle du profil avec `version` et provenance ;
- `GET /api/prospects` — ajout de filtres serveur : texte, origine, statut d’archive, propriétaire, priorité et curseur ;
- `GET /api/prospects/{prospect_id}` — profil complet, sans détail Google persistant ;
- `GET /api/prospects/{prospect_id}/contacts` — contacts actifs ou archivés selon filtre ;
- `GET /api/prospects/{prospect_id}/channels` — canaux directs de l’établissement ;
- `GET /api/contacts/{contact_id}/channels` — canaux d’une personne ;
- `GET /api/prospects/{prospect_id}/provenance` — résumé de provenance sans preuve sensible.

Les routes 2.5.2 à 2.5.4 existantes sont réutilisées. Une éventuelle correction de schéma ou de pagination est
autorisée uniquement si elle est rétrocompatible et couverte par un test de contrat.

## 7. Capacités et rôles

### 7.1 Capacités

- `prospects:read` : liste et détail ;
- `prospects:create` : création manuelle et ajout Google ;
- `prospects:update` : enrichissement du profil ;
- `prospects:archive` : archivage logique ;
- `contacts:read` et `contacts:write` : lecture et ajout de contacts/canaux ;
- `permissions:restrict` et `permissions:allow` : restriction ou autorisation explicite d’un canal ;
- `providers:read` et `providers:manage` : consultation et administration des fournisseurs ;
- `compliance:read`, `acquisitions:declare` et `acquisitions:review` : consultation, déclaration et décision
  d’acquisition ;
- capacités `retention:*` et `imports:*` déjà introduites : écrans et actions correspondants.

### 7.2 Matrice attendue

| Fonction | Admin | Manager | Commercial |
| --- | --- | --- | --- |
| Lire les prospects | Oui | Oui | Oui |
| Créer et modifier un prospect | Oui | Oui | Oui |
| Archiver un prospect | Oui | Oui | Non |
| Ajouter contacts et canaux | Oui | Oui | Oui |
| Autoriser / restreindre un canal | Oui / Oui | Oui / Oui | Non / Oui |
| Administrer fournisseurs/acquisitions | Oui | Consulter et déclarer | Non |
| Administrer politiques de conservation | Oui | Non | Non |
| Créer un hold ou déclarer un import | Oui | Oui selon capacité existante | Non |

La matrice réellement appliquée provient des capacités renvoyées par `/api/auth/me`. L’interface masque les actions
indisponibles, mais un appel direct demeure refusé par le serveur.

## 8. Navigation et routage

Les chemins proposés sont :

- `/app/prospects` — portefeuille ;
- `/app/prospects/new` — création manuelle ;
- `/app/prospects/:prospectId` — fiche ;
- `/app/compliance/providers` — fournisseurs ;
- `/app/compliance/acquisitions` — acquisitions ;
- `/app/compliance/retention` — conservation et holds ;
- `/app/compliance/imports` — déclarations d’import.

Le routeur interne doit prendre en charge les segments dynamiques, le rechargement direct d’une URL et la navigation
précédent/suivant sans dépendre d’un état conservé dans le navigateur. Après changement d’organisation, les données
de l’ancienne organisation sont invalidées en mémoire et la page courante est rechargée dans le nouveau contexte ou
redirigée vers `/app/prospects`.

## 9. Portefeuille prospects

### 9.1 Liste

La liste affiche uniquement des données CRM persistées : alias, origine, propriétaire, priorité, secteur, ville CRM,
étiquettes, état d’archivage et date de mise à jour. Elle ne réaffiche pas silencieusement les détails Google.

- pagination par curseur opaque ;
- recherche déclenchée explicitement ou avec temporisation, jamais un appel par frappe brute ;
- filtres encodés dans l’URL pour permettre le retour arrière ;
- filtre « Actifs » par défaut et option « Archivés » ;
- états distincts : chargement, aucun résultat, aucun droit, erreur récupérable ;
- ouverture de la fiche par lien accessible au clavier.

### 9.2 Création manuelle

Le formulaire demande au minimum le nom interne, la finalité et le territoire. Les champs enrichis sont facultatifs.
La soumission est protégée contre le double clic par une clé d’idempotence. Après succès, l’utilisateur est dirigé
vers la fiche créée.

### 9.3 Ajout depuis Google

L’écran de recherche conserve l’action individuelle et groupée déjà livrée. Après ajout :

- chaque ligne indique clairement « Ajouté au CRM » ou « Déjà présent » ;
- un lien ouvre la fiche CRM ;
- seul le `place_id` est transmis avec le jeton de sélection ;
- la sélection expire avec le jeton et ne survit pas à un rechargement ;
- aucun enrichissement automatique du profil n’est effectué.

## 10. Fiche prospect

La fiche comporte quatre sections :

1. **Profil** — informations CRM éditables, propriétaire, priorité et provenance ;
2. **Contacts** — personnes liées et rôle déclaré ;
3. **Canaux et permissions** — courriel, téléphone ou réseau social, finalité, provenance et état de permission ;
4. **Conformité** — origine, acquisition éventuelle, date de revue et état d’archivage.

Les états de permission sont présentés avec des termes explicites :

- `unknown` : « Permission non déterminée — aucun envoi automatisé » ;
- `allowed` : « Contact autorisé selon la base déclarée » ;
- `do_not_contact` : « Ne pas contacter » ;
- `opted_out` : « Opposition enregistrée ».

La fiche ne propose aucune action d’envoi. Une confirmation est requise pour archiver un prospect, un contact ou un
canal. Le motif d’archivage est obligatoire.

## 11. Fournisseurs et acquisitions

### 11.1 Fournisseurs

L’écran permet selon capacité de lister, consulter, créer et modifier : type de source, statut, référence contractuelle,
URL des conditions, dates de validité, territoires, finalités, catégories autorisées et attestation de droits.

- un fournisseur `draft`, `suspended` ou `retired` n’est jamais présenté comme utilisable ;
- les dates expirées sont signalées sans calcul juridique implicite ;
- une URL externe s’ouvre avec protections `noopener`/`noreferrer` ;
- aucune clé d’API ou pièce contractuelle brute n’est stockée dans cette fiche.

### 11.2 Acquisitions

La liste distingue `pending_review`, `approved`, `quarantined` et `rejected`. L’administrateur peut approuver ou
rejeter avec un motif contrôlé et une confirmation. L’interface explique qu’une approbation de provenance ne vaut pas
permission de contact.

## 12. Conservation et holds

- liste et détail des politiques, avec version et état ;
- création/modification/activation réservées à `retention:manage` ;
- tableau de revue : échéance, ressource, état et présence d’un hold ;
- création et levée d’un hold avec motifs contrôlés ;
- la note sensible d’un hold n’apparaît que dans son détail autorisé ;
- aucune action « Purger » n’existe dans 2.5.5 ;
- l’archivage logique indique clairement qu’il ne supprime pas physiquement la donnée.

## 13. Déclarations d’import

L’écran permet de déclarer une intention d’import CSV sans accepter de fichier :

- fournisseur, finalité, territoire, schéma, empreinte déclarée, catégories et champs attendus ;
- résultat de contrôle : `declared` ou `quarantined`, avec motifs contrôlés ;
- consultation, annulation et archivage logique ;
- encart permanent : « Le téléversement et le traitement du fichier seront disponibles dans un prochain incrément » ;
- aucun sélecteur de fichier, zone de dépôt ou collage de contenu brut.

## 14. Expérience utilisateur et accessibilité

- continuité visuelle avec le shell Marketteo existant ;
- formulaires avec labels visibles, aide contextuelle et erreurs rattachées aux champs ;
- focus déplacé vers le résumé d’erreur après échec ;
- dialogues accessibles, focus piégé, fermeture `Escape` et retour du focus au déclencheur ;
- tableaux utilisables au clavier et alternative lisible sur petit écran ;
- contraste WCAG 2.1 AA, états non distingués uniquement par la couleur ;
- annonces `aria-live` pour chargement, succès, conflit et archivage ;
- aucun libellé « LeadGenerator », « générateur » ou « leads » dans l’interface livrée.

Le français reste la langue active de 2.5.5. Les textes sont regroupés par fonctionnalité pour préparer la future
internationalisation, sans introduire un sélecteur de langue incomplet.

## 15. Gestion des erreurs et concurrence

- `400/422` : message métier et erreurs par champ ;
- `401` : expiration de session et retour à la connexion ;
- `403` : page ou message d’accès refusé sans fuite de données ;
- `404` : ressource inexistante ou invisible dans le contexte locataire ;
- `409` : conflit de version, proposition de recharger la fiche, aucune fusion silencieuse ;
- `429` : temporisation et message clair ;
- `5xx` ou réseau : avis récupérable avec identifiant de requête.

Les erreurs passent par le client HTTP et les composants de feedback partagés. Aucun écran ne réimplémente son propre
format de réponse d’erreur.

## 16. Sécurité et confidentialité

- cookies de session `HttpOnly`, `Secure` en environnement HTTPS et `SameSite` conforme au déploiement ;
- jeton CSRF exigé sur toutes les mutations ;
- aucun secret, jeton de sélection, valeur de canal ou contenu de formulaire dans les logs frontend ;
- aucune donnée métier dans le stockage navigateur, IndexedDB ou cache persistant d’un service worker ;
- invalidation en mémoire à la déconnexion et au changement d’organisation ;
- `Cache-Control: no-store` sur toutes les réponses CRM et conformité ;
- protection contre les collisions Unicode et neutralisation des contenus affichés ;
- liens externes et textes utilisateurs rendus sans injection HTML ;
- tests négatifs de capacité et RLS pour toutes les nouvelles routes.

## 17. Audit et observabilité

Les événements suivants sont obligatoires et atomiques avec la mutation :

- création et mise à jour d’un prospect ;
- ajout d’un contact ou d’un canal ;
- changement de permission ;
- archivage d’un prospect, contact ou canal ;
- création/modification/activation d’un fournisseur ou d’une politique ;
- décision d’acquisition ;
- création/levée d’un hold ;
- déclaration, annulation ou archivage d’un import.

L’audit contient les identifiants, versions, codes de motif et noms de champs modifiés. Il exclut les valeurs de canal,
adresses complètes, notes de hold, empreintes brutes, secrets et données Google descriptives.

## 18. Stratégie de tests automatisés

### 18.1 Backend et PostgreSQL

- migration depuis `20260814_0011`, base vide, `upgrade head`, `current` et `alembic check` ;
- contraintes des nouveaux champs, propriétaire inter-organisation et concurrence optimiste ;
- tests API positifs et négatifs pour profil, filtres et routes de lecture complémentaires ;
- RLS sur deux organisations et rôle applicatif sans contournement ;
- audit atomique et absence de données sensibles ;
- `no-store`, CSRF, idempotence et capacités ;
- non-régression complète des tests 2.5.1 à 2.5.4.

### 18.2 Frontend

- routes statiques et dynamiques, garde de capacité et changement d’organisation ;
- liste, filtres, pagination, création et édition du profil ;
- ajout Google individuel/groupé et dispositions `created`/`existing` ;
- contacts, canaux, permissions et confirmations ;
- fournisseurs, acquisitions, conservation, holds et déclarations d’import ;
- erreurs 401/403/404/409/429/5xx et reprise ;
- absence de stockage navigateur ;
- tests `axe` sur chaque page et chaque dialogue majeur ;
- preuve qu’aucun upload de fichier ni action de purge n’est disponible.

### 18.3 Non-régression Google

- exactement un Text Search par action ;
- vingt résultats maximum ;
- aucun `nextPageToken` suivi ;
- aucun téléphone, site Web ou autre champ de contact dans la réponse ;
- seul le `place_id` est persisté lors de l’ajout ;
- attribution Google Maps visible et export historique absent.

## 19. Recette locale regroupée 2.5.3–2.5.5

La recette produit, exécutée après l’implémentation de 2.5.5, doit inclure :

1. démarrage PostgreSQL, Redis et Mailpit dans Ubuntu-24.04 ;
2. provisioning des rôles, migration de la base locale jusqu’à la nouvelle tête et contrôle `current` ;
3. connexion admin, manager et membre dans deux organisations ;
4. création manuelle, ajout Google, doublon idempotent et enrichissement du profil ;
5. changement d’organisation et preuve d’isolation ;
6. contact, canal, permission et archivage logique ;
7. fournisseur actif puis expiré, acquisition approuvée puis quarantainée/rejetée ;
8. politique, revue, création et levée d’un hold ;
9. déclaration d’import sans fichier, annulation et archivage ;
10. consultation des événements d’audit et contrôle de l’absence de données sensibles ;
11. reprise formelle des réserves des étapes 9 et 10 de la recette 2.5.1–2.5.2 ;
12. verrou qualité local complet avec rapport conservé dans `test-results`.

Un cahier de recette détaillé et rejouable sera produit pendant 2.5.5-E. Une anomalie bloquante ou une preuve RLS
manquante entraîne un No-Go de la phase 2.5.

## 20. Verrou qualité et livraison

Les contrôles suivants doivent être verts :

- Ruff lint et format ;
- mypy sur le backend ;
- pytest sans skip dans la cible qualité ;
- tests d’intégration PostgreSQL réel et Alembic ;
- ESLint ;
- Vitest avec accessibilité ;
- build Vite de production ;
- contrôle automatisé des fonctions transitoires interdites ;
- Azure Pipelines sur la même tête de migration ;
- `git diff --check` et documentation à jour.

Le rapport final consigne les commandes, versions, nombres de tests, éventuelles réserves, double critique technique et
verdict Go/No-Go. Un test vert sur doubles mémoire ne remplace pas la preuve PostgreSQL réelle regroupée.

## 21. Critères d’acceptation

2.5.5 est acceptable lorsque :

- chaque écran annoncé est réellement routable, protégé, accessible et sans action morte ;
- un utilisateur autorisé gère son portefeuille et enrichit une fiche sans copier une donnée Google interdite ;
- les contacts, canaux et permissions sont compréhensibles et correctement séparés ;
- les fonctions de conformité et conservation respectent les capacités ;
- l’import est explicitement déclaratif et ne reçoit aucun fichier ;
- les archives restent lisibles selon filtre et aucune purge n’est exposée ;
- l’isolation inter-organisation, l’audit, `no-store` et l’absence de stockage navigateur sont prouvés ;
- les réserves 2.5.2 sont clôturées ou transformées en anomalies formellement acceptées ;
- la recette groupée 2.5.3–2.5.5 et tous les contrôles du verrou qualité sont verts ;
- la documentation technique, utilisateur et QA reflète le comportement réel.

## 22. Risques et mesures

| Risque | Mesure imposée |
| --- | --- |
| Écran trop vaste livré en bloc | Découpage A à E et test de passage par lot |
| Confusion entre fiche Google et profil CRM | Champs manuels distincts, provenance et interdiction serveur |
| Permission assimilée à la provenance | Libellés séparés et test métier négatif |
| Fuite inter-organisation au changement de contexte | Invalidation mémoire, RLS et tests sur deux organisations |
| Écrasement concurrent | Version obligatoire et réponse 409 |
| Exposition de données personnelles dans l’audit | Liste blanche de métadonnées et tests de redaction |
| Interface de conformité trop permissive | Garde de capacité côté UI et serveur |
| Fausse promesse d’import | Aucun composant d’upload et message permanent |
| Dette qualité masquée par des mocks | Recette PostgreSQL réelle obligatoire |
| Périmètre dérivant vers le Kanban | Étapes commerciales visibles en lecture seulement ; workflow reporté |

## 23. Seize décisions proposées à validation

1. 2.5.5 livre l’interface du socle prospects et conformité, pas le Kanban ni les activités commerciales.
2. L’implémentation est découpée en cinq lots 2.5.5-A à 2.5.5-E, chacun testable avant le suivant.
3. Une migration additive complète le profil prospect avec secteur, segment, taille, adresse CRM, étiquettes,
   propriétaire, priorité et provenance.
4. Les informations enrichies sont propres au CRM ; aucune donnée descriptive Google n’est copiée durablement.
5. `PATCH /api/prospects/{id}` exige la version courante et refuse tout écrasement concurrent par `409`.
6. La navigation ajoute Prospects et les écrans de conformité selon les capacités réellement renvoyées par le serveur.
7. La liste est filtrée et paginée côté serveur ; les archives sont exclues par défaut mais consultables explicitement.
8. La fiche sépare Profil, Contacts, Canaux/permissions et Conformité.
9. Une permission inconnue bloque tout envoi automatisé et une opposition reste prioritaire ; aucun envoi n’est livré
   dans 2.5.5.
10. Les fournisseurs, acquisitions, politiques, holds et déclarations d’import sont administrables uniquement selon
    leurs capacités dédiées.
11. L’import reste strictement déclaratif : aucun fichier, parsing, aperçu de lignes ou stockage de contenu brut.
12. L’archivage est logique, motivé et confirmé ; aucune purge ni restauration n’est exposée dans cet incrément.
13. Le français reste la langue active, avec textes préparés pour l’internationalisation mais sans sélecteur incomplet.
14. Les réponses portent `no-store`, aucune donnée CRM n’est stockée dans le navigateur et les caches mémoire sont
    invalidés au changement d’organisation.
15. La recette locale PostgreSQL réelle regroupe 2.5.3, 2.5.4 et 2.5.5 et clôt explicitement les réserves 2.5.2.
16. Le Go final exige Ruff, mypy, pytest, PostgreSQL/Alembic, ESLint, Vitest/axe, build, Azure Pipelines,
    documentation et contrôles Google entièrement verts.

## 24. Décision de passage

- **Go implémentation 2.5.5** : validation explicite des seize décisions de la section 23 ;
- **No-Go** : décision non validée, contradiction juridique ou technique, ou périmètre à redéfinir ;
- **Go phase 2.5** : uniquement après implémentation A–E, recette groupée et verrou qualité final sans écart bloquant.
