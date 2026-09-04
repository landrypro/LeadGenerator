# Incrément 2.5.3 — Provenance, permissions et fournisseurs

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.5 — Socle prospects, conformité et conservation |
| Incrément | 2.5.3 — Provenance, permissions et fournisseurs |
| Version | 1.0 |
| Statut | Implémentation réalisée — recette locale à exécuter |
| Date de proposition | 14 août 2026 |
| Validation produit | 14 août 2026 — validation des seize décisions de la section 18 et GO d’implémentation |
| Prérequis | 2.5.1–2.5.2 validés avec réserves ; migration `20260814_0009 (head)` |
| Dépendances | Organisations/RLS 2.3, audit 2.4, modèle prospect 2.5.1, création prospect 2.5.2 |
| Hors périmètre | Parsing CSV, connecteurs Facebook/LinkedIn, appels API fournisseurs, Kanban, facturation et purge |

Ce document définit le contrôle de la provenance des données commerciales et de leur droit d’utilisation. Il ne
constitue pas un avis juridique et n’autorise aucune collecte par simple présence d’une source dans le produit.
Marketteo doit enregistrer les faits, appliquer les règles configurées et bloquer les usages non démontrés.

## 1. Objectifs

2.5.3 doit permettre de :

- administrer, par organisation, une liste de fournisseurs de données autorisés ;
- contrôler le type de source, la période contractuelle, les territoires, les finalités et catégories de données ;
- déclarer une acquisition externe sans transmettre ni conserver son fichier ou ses lignes ;
- accepter, mettre en quarantaine ou rejeter cette acquisition avec un motif machine stable ;
- créer un contact ou un canal avec une provenance générée et validée côté serveur ;
- créer automatiquement une permission `unknown` pour tout nouveau canal ;
- enregistrer les autorisations et restrictions de contact selon une matrice de capacités explicite ;
- propager immédiatement une opposition aux canaux identiques de la même organisation ;
- conserver l’isolation RLS, l’audit atomique et l’absence de données sensibles dans les journaux.

## 2. Périmètre fonctionnel

### 2.1 Inclus

- fournisseurs locataires pour `csv`, `facebook`, `linkedin`, `open_data`, `api` et `other` ;
- cycle de vie contractuel et contrôle de validité à la date de l’opération ;
- acquisitions déclaratives et décisions de conformité ;
- quarantaine au niveau de l’acquisition, sans ligne métier ni fichier brut ;
- provenance manuelle ou rattachée à une acquisition approuvée ;
- création minimale des contacts et canaux établissement/personne ;
- permission courante par canal et historique complet par audit ;
- capacités, API, migration additive, RLS, tests PostgreSQL et documentation.

### 2.2 Exclus

- upload, lecture, prévisualisation ou parsing de fichier CSV ;
- import effectif de prospects, contacts ou canaux en masse ;
- scraping, automatisation navigateur ou contournement des conditions de Facebook ou LinkedIn ;
- connexion OAuth, secret fournisseur, clé API externe ou webhook ;
- envoi de courriel, appel téléphonique ou message social ;
- écran utilisateur complet, reporté à 2.5.5 ;
- politique de conservation et suppression, traitées en 2.5.4 ;
- enrichissement ou persistance de données descriptives Google.

## 3. Principes non négociables

1. La provenance décrit l’origine d’une donnée ; elle ne prouve pas à elle seule le droit de contacter.
2. Une permission absente vaut `unknown` et interdit tout envoi automatisé futur.
3. `do_not_contact` et `opted_out` bloquent tout usage commercial du canal.
4. Une restriction peut toujours être enregistrée par un rôle commercial ; une autorisation exige un rôle habilité.
5. Une source externe exige un fournisseur actif et une acquisition approuvée.
6. `manual` et `google_maps` sont des sources système et ne sont jamais configurées comme fournisseurs locataires.
7. `google_maps` reste interdit comme provenance d’un courriel, téléphone, site ou profil social persistant.
8. La création d’un fournisseur n’autorise ni scraping ni appel à son API.
9. Aucun fichier, ligne importée, secret, jeton OAuth ou preuve brute n’entre dans les API de 2.5.3.
10. Toute vérification contractuelle est refaite côté serveur au moment de l’écriture métier.
11. Une acquisition en quarantaine ne peut alimenter aucun prospect, contact ou canal.
12. Les faits d’origine sont immuables ; une correction crée une nouvelle provenance ou une nouvelle acquisition.
13. Toutes les ressources locataires restent protégées par RLS et capacités applicatives.
14. Toute mutation et son événement d’audit sont atomiques.
15. Les réponses portent `Cache-Control: no-store` et aucune donnée CRM n’est stockée dans le navigateur.
16. Les règles Google de 2.5.2 restent inchangées : un Text Search, vingt résultats, aucun contact ni pagination.

## 4. Modèle de données cible

La migration 2.5.3 est additive et suit `20260814_0009`. Elle complète les tables existantes sans modifier les
migrations historiques.

### 4.1 `source_providers`

La table existante est enrichie avec :

- `source_kind` : `csv`, `facebook`, `linkedin`, `open_data`, `api` ou `other` ;
- `label` : nom interne du fournisseur ;
- `status` : `draft`, `active`, `suspended` ou `retired` ;
- `terms_reference` : référence contractuelle ou juridique interne, sans document brut ;
- `terms_url` nullable : URL HTTPS informative, jamais appelée automatiquement ;
- `valid_from` et `valid_until` nullable ;
- `allowed_territories` : liste non vide de codes ou zones contrôlés ;
- `allowed_purposes` : liste non vide de finalités contrôlées ;
- `allowed_data_categories` : liste non vide, par exemple `business_identity`, `person_identity`, `email`, `phone`,
  `social_profile` ;
- `rights_attested_at`, `rights_attested_by` ;
- `version`, `created_at`, `updated_at`.

Un fournisseur est utilisable si et seulement si son état persistant est `active`, son attestation est présente, la
date courante appartient à sa période de validité et l’opération demandée respecte type, territoire, finalité et
catégories autorisés. « Expiré » est un état calculé ; aucune tâche planifiée n’est requise pour modifier la ligne.

La migration convertit les anciens états minimaux `active` et `disabled` vers `active` et `suspended`. Aucune ligne
existante ne devient exploitable si les nouveaux champs obligatoires d’activation sont absents.

### 4.2 `acquisition_records`

La table existante est complétée avec :

- `external_reference` nullable : référence opaque du lot, jamais un jeton ou un fichier ;
- `data_categories` : catégories déclarées ;
- `status` : `pending_review`, `approved`, `quarantined` ou `rejected` ;
- `decision_reason_code` nullable ;
- `decided_at`, `decided_by` et `version` ;
- les champs existants `source_kind`, `source_label`, `provider_id`, `purpose`, `territory`, `obtained_at` et
  `declared_by`.

Pour une source externe, `provider_id` est obligatoire. Les faits déclarés (`source_kind`, fournisseur, finalité,
territoire, date, catégories) sont immuables après création. Seuls le statut, la décision et la version évoluent.

Une déclaration conforme peut être approuvée immédiatement par le serveur. Une source inconnue, un contrat hors
période, une catégorie ou un territoire non couvert produit une acquisition `quarantined`, sans écrire les données
à acquérir. Une incohérence structurelle de requête reste un rejet HTTP `422` et ne crée aucun enregistrement.

### 4.3 `provenance_records`

La table existante reçoit `acquisition_record_id` nullable avec FK composite locataire. Deux formes sont autorisées :

- provenance manuelle : `source_kind=manual`, sans fournisseur ni acquisition, auteur serveur obligatoire ;
- provenance externe : fournisseur et `acquisition_record_id` approuvé obligatoires et cohérents.

Les provenances sont append-only. L’API métier ne reçoit jamais un `provenance_id` arbitraire à rattacher : elle reçoit
une intention de source discriminée, puis le serveur crée la provenance dans la transaction du contact ou du canal.

### 4.4 `contact_permissions`

La table existante représente une permission courante unique par canal :

- contrainte unique `(organization_id, channel_id)` ;
- `status` : `unknown`, `allowed`, `do_not_contact` ou `opted_out` ;
- `legal_basis_code` nullable et contrôlé ;
- `provenance_id` nullable pour la preuve interne ;
- `reason`, `decided_at`, `decided_by`, `valid_from`, `valid_until`, `version` ;
- `created_at`, `updated_at`.

Chaque canal crée atomiquement une permission `unknown`. L’historique des changements est conservé dans l’audit
append-only ; la table porte uniquement l’état courant.

### 4.5 Quarantaine

2.5.3 ne crée pas encore de `import_quarantine_rows`. La quarantaine est portée par `acquisition_records.status` et
un code de motif. Aucune valeur de prospect, contact, canal ou ligne source n’est conservée. La quarantaine détaillée
des imports appartient à 2.5.4.

## 5. Catalogues contrôlés

### 5.1 Finalités initiales

- `commercial_follow_up` — qualification et suivi commercial ;
- `customer_relationship` — relation avec un client déjà établi ;
- `supplier_relationship` — relation fournisseur explicitement déclarée.

Le client ne peut pas créer librement une nouvelle finalité. Toute extension exige migration ou configuration
versionnée ultérieure.

### 5.2 Catégories de données initiales

- `business_identity` ;
- `person_identity` ;
- `email` ;
- `phone` ;
- `social_profile`.

Les catégories déclarées doivent être un sous-ensemble de celles autorisées par le fournisseur.

### 5.3 Motifs de quarantaine

Les réponses utilisent des codes stables, notamment :

- `provider_not_active` ;
- `contract_not_started` ;
- `contract_expired` ;
- `source_kind_mismatch` ;
- `territory_not_allowed` ;
- `purpose_not_allowed` ;
- `data_category_not_allowed` ;
- `rights_attestation_missing`.

Le message utilisateur reste localisable et n’est pas utilisé comme clé métier.

## 6. Règles de création des contacts et canaux

### 6.1 Contact

Un contact est une personne et non un établissement. Sa création exige :

- un prospect actif de l’organisation courante ;
- un `display_name` et un `role_label` optionnel ;
- une source `manual` ou une acquisition externe approuvée ;
- une provenance créée par le serveur dans la même transaction ;
- un événement `contact.created` ne contenant aucune donnée personnelle en clair.

### 6.2 Canal

Un canal vise exactement un prospect ou un contact. Les types initiaux restent `email`, `phone`, `linkedin`,
`facebook` et `other`.

- la valeur affichée et la valeur normalisée sont calculées côté serveur ;
- les caractères de contrôle, valeurs vides et formats manifestement invalides sont rejetés ;
- un courriel normalise au minimum les espaces et le domaine IDNA ;
- un téléphone est normalisé au format E.164 à partir d’un territoire explicite ;
- un profil social doit utiliser une URL HTTPS d’un domaine autorisé pour son type ;
- aucune unicité globale n’est imposée, car un standard ou une boîte partagée peut servir plusieurs entités ;
- un doublon exact sur la même cible active est refusé de manière contrôlée ;
- la provenance et la permission `unknown` sont créées atomiquement avec le canal.

Un canal social enregistré manuellement n’active aucune messagerie et ne prouve aucun droit d’utilisation de
Facebook ou LinkedIn.

## 7. Règles de permission

### 7.1 Transitions

- création du canal → `unknown` ;
- `unknown` → `allowed` uniquement avec capacité d’autorisation, base documentée, preuve et période cohérente ;
- tout état → `do_not_contact` avec motif ;
- tout état → `opted_out` lorsqu’une opposition explicite est reçue ;
- `do_not_contact` ou `opted_out` → `allowed` uniquement par un administrateur, avec nouvelle preuve et audit ;
- une permission `allowed` expirée est traitée comme `unknown` lors de toute vérification d’usage.

### 7.2 Propagation des restrictions

Lorsqu’un canal passe à `do_not_contact` ou `opted_out`, le serveur applique dans la même transaction la restriction à
tous les canaux actifs de la même organisation possédant le même couple `(channel_type, value_normalized)`. Une
autorisation n’est jamais propagée automatiquement.

### 7.3 Absence d’envoi

2.5.3 ne livre aucun moteur de campagne. Les permissions servent de garde-fou aux futurs cas d’utilisation ; aucune
route d’envoi, aucun webhook et aucune file de messages ne sont introduits.

## 8. Cycle de vie des fournisseurs

- `draft` : modifiable, inutilisable pour une acquisition ;
- `active` : utilisable si toutes les règles contractuelles sont satisfaites ;
- `suspended` : bloque immédiatement toute nouvelle acquisition, sans altérer l’historique ;
- `retired` : état terminal pour les nouvelles acquisitions ;
- expiration calculée : blocage automatique lorsque `valid_until` est dépassé.

L’activation exige une attestation explicite de l’administrateur. Pour Facebook et LinkedIn, cette attestation signifie
que l’organisation dispose d’un accès ou d’une licence autorisés ; elle ne rend jamais le scraping acceptable.

Une modification de période, territoire, finalité, catégorie ou statut utilise la version optimiste et produit un
audit limité aux noms de champs modifiés.

## 9. Matrice de capacités

| Capacité | Admin organisation | Manager | Sales |
| --- | ---: | ---: | ---: |
| `prospects:read` | oui | oui | oui |
| `prospects:create` | oui | oui | oui |
| `contacts:read` | oui | oui | oui |
| `contacts:write` | oui | oui | oui |
| `compliance:read` | oui | oui | non |
| `permissions:restrict` | oui | oui | oui |
| `permissions:allow` | oui | oui | non |
| `providers:read` | oui | oui | non |
| `providers:manage` | oui | non | non |
| `acquisitions:declare` | oui | oui | non |
| `acquisitions:review` | oui | non | non |

Un administrateur plateforme ne contourne pas ces capacités dans une organisation : il doit disposer d’une
appartenance locataire active. Le frontend masque les actions non autorisées, mais le serveur reste l’autorité.

## 10. API applicative

Toutes les routes exigent authentification, organisation active, capacité, RLS, CSRF et origine de confiance pour
les mutations. Toutes les réponses portent `Cache-Control: no-store`.

### 10.1 Fournisseurs

- `GET /api/source-providers` — liste paginée par curseur opaque ;
- `POST /api/source-providers` — création en `draft` ;
- `GET /api/source-providers/{provider_id}` — détail filtré ;
- `PATCH /api/source-providers/{provider_id}` — modification optimiste et transition d’état.

Le corps ne contient ni clé API, ni secret, ni document contractuel brut.

### 10.2 Acquisitions

- `GET /api/acquisitions` — liste pour les rôles de conformité ;
- `POST /api/acquisitions` — déclaration métadonnée uniquement ;
- `GET /api/acquisitions/{acquisition_id}` — détail sans donnée source ;
- `POST /api/acquisitions/{acquisition_id}/decision` — approbation ou rejet d’une quarantaine.

La création retourne `approved` ou `quarantined` avec des codes de décision. Un rejeu avec la même
`Idempotency-Key` et le même corps retourne la même ressource ; une clé réutilisée avec un autre corps produit `409`.

### 10.3 Contacts, canaux et permissions

- `POST /api/prospects/{prospect_id}/contacts` ;
- `GET /api/prospects/{prospect_id}/contacts` ;
- `POST /api/contact-channels` ;
- `GET /api/contact-channels/{channel_id}/permission` ;
- `PATCH /api/contact-channels/{channel_id}/permission`.

La source fournie à la création est discriminée :

```json
{"kind":"manual","purpose":"commercial_follow_up","territory":"CA-QC"}
```

ou :

```json
{"kind":"acquisition","acquisition_id":"00000000-0000-0000-0000-000000000000"}
```

Le serveur génère la provenance ; aucun identifiant de provenance arbitraire n’est accepté du client.

### 10.4 Erreurs stables

Les codes applicatifs comprennent au minimum : `provider_not_usable`, `acquisition_quarantined`,
`acquisition_not_approved`, `source_not_allowed`, `channel_duplicate`, `invalid_permission_transition`,
`optimistic_lock_conflict`, `resource_not_found` et `insufficient_capability`.

Les erreurs de présence d’une ressource d’une autre organisation restent indiscernables d’une absence locale.

## 11. Ports et cas d’utilisation

Les ports applicatifs sont complétés sans dépendance ORM dans le domaine :

- `SourceProviderRepository` ;
- `AcquisitionRepository` ;
- `ProvenanceRepository` ;
- `ContactRepository` ;
- `ContactChannelRepository` ;
- `ContactPermissionRepository` ;
- `ProspectComplianceUnitOfWork` ou extension cohérente de l’unité existante ;
- `Clock` pour rendre les contrôles de validité déterministes ;
- `IdempotencyStore` existant ou port dédié pour les déclarations.

Cas d’utilisation minimaux : créer/modifier un fournisseur, déclarer/décider une acquisition, créer/lister un contact,
créer un canal, lire/changer une permission et propager une restriction.

Les routes ne construisent pas les entités ORM et les repositories ne prennent aucune décision de permission.

## 12. Audit, confidentialité et observabilité

### 12.1 Événements

- `source_provider.created`, `source_provider.updated`, `source_provider.status_changed` ;
- `acquisition.declared`, `acquisition.quarantined`, `acquisition.approved`, `acquisition.rejected` ;
- `contact.created`, `contact_channel.created` ;
- `contact_permission.changed`, avec nombre de canaux propagés.

### 12.2 Métadonnées autorisées

Identifiants internes, type de source, ancien/nouvel état, codes de motif, catégories non sensibles, champs modifiés et
compteurs. Sont interdits : valeur de canal, nom de personne, URL de profil, référence externe libre, preuve brute,
contenu contractuel, fichier, secret ou jeton.

### 12.3 Métriques

- acquisitions approuvées, mises en quarantaine et rejetées par code ;
- fournisseurs actifs, suspendus et expirés calculés ;
- canaux créés par type sans valeur ;
- permissions par statut et nombre de propagations ;
- conflits optimistes et refus de capacité.

Les métriques ne portent aucune donnée permettant d’identifier une personne ou un établissement.

## 13. Migration, RLS et compatibilité

- révision Alembic unique après `20260814_0009` ;
- ajout des colonnes, contraintes et index sans réécrire la migration 2.5.1 ;
- backfill prudent des tables préparatoires existantes ;
- activation/maintien de RLS sur toutes les tables touchées ;
- privilèges Web minimaux, aucun DDL et aucun contournement locataire ;
- tests sur base vide et upgrade depuis `20260814_0009` ;
- downgrade réservé à une base de test vide ;
- aucune modification des données prospects déjà créées en 2.5.2 ;
- aucun appel Google et aucune dépendance réseau pendant la migration.

## 14. Interface utilisateur

2.5.3 est un lot backend et contrats, sans nouvelle page métier. Les capacités sont ajoutées à la session pour préparer
2.5.5. L’interface existante ne doit afficher ni action morte ni information de conformité partielle.

Les tests frontend existants restent obligatoires, notamment l’ajout Google, l’absence de stockage navigateur, les
routes protégées et l’accessibilité. Les écrans fournisseurs, provenance et permissions seront spécifiés en 2.5.5.

## 15. Stratégie de tests

### 15.1 Domaine et cas d’utilisation

- activation refusée sans attestation ou catalogue complet ;
- fournisseur suspendu, retiré, non commencé ou expiré inutilisable ;
- source, territoire, finalité ou catégorie non couverts mis en quarantaine ;
- déclaration idempotente et conflit de clé ;
- provenance externe impossible sans acquisition approuvée ;
- provenance Google refusée pour tout canal ;
- normalisation déterministe et doublon de même cible ;
- permission `unknown` atomique à la création du canal ;
- transitions autorisées/refusées et permission expirée traitée comme `unknown` ;
- propagation des restrictions, jamais des autorisations.

### 15.2 PostgreSQL réel

- migration sur base vide et depuis `20260814_0009` ;
- contraintes composites, unicité de permission et version optimiste ;
- RLS positive/négative sur deux organisations ;
- impossibilité de rattacher fournisseur, acquisition ou provenance d’un autre locataire ;
- rollback intégral contact/canal/provenance/permission/audit ;
- privilèges effectifs du rôle Web et `alembic check`.

### 15.3 API et sécurité

- matrice complète des capacités pour Admin, Manager et Sales ;
- CSRF, origine de confiance, type JSON, validation et `no-store` ;
- absence de fuite inter-organisation par `404`, erreur ou curseur ;
- aucune donnée sensible dans audit, logs, métriques et réponses de quarantaine ;
- aucune route d’upload, de scraping, de connecteur ou d’envoi ;
- non-régression Google : un seul appel, vingt résultats, aucun contact, aucune pagination.

### 15.4 Qualité

- Ruff format/check, mypy, pytest réel sans `skip` ;
- ESLint, Vitest/axe et build Vite ;
- `alembic current`, `alembic check`, reconstruction contrôlée ;
- verrou qualité local et Azure Pipelines verts ;
- rapport d’implémentation et recette technique mis à jour.

## 16. Critères d’acceptation

2.5.3 est acceptable lorsque :

- un administrateur peut configurer et activer un fournisseur conforme ;
- une acquisition conforme est approuvée et une acquisition non conforme est quarantinée sans donnée brute ;
- un contact et un canal peuvent être créés avec provenance serveur ;
- chaque nouveau canal possède exactement une permission `unknown` ;
- les restrictions sont enregistrables par Sales et propagées aux canaux identiques ;
- seuls Admin et Manager peuvent établir une autorisation ;
- RLS, audit atomique, idempotence et conflits optimistes sont prouvés ;
- aucune règle Google, sécurité frontend ou isolation locataire ne régresse ;
- tous les contrôles qualité sont verts sans test ignoré.

## 17. Risques et réponses

| Risque | Réponse retenue |
| --- | --- |
| Confondre fournisseur configuré et droit légal acquis | Attestation explicite, contrat borné et message produit non juridique |
| Introduire du scraping social implicitement | Aucun connecteur ni appel réseau ; source sociale inutilisable sans fournisseur autorisé |
| Persister des données rejetées | Quarantaine au niveau métadonnée seulement, sans payload |
| Autoriser un canal faute de preuve | `unknown` par défaut ; autorisation réservée et documentée |
| Perdre une opposition dupliquée | Propagation transactionnelle par type et valeur normalisée |
| Fuite de données personnelles dans l’audit | Liste blanche stricte des métadonnées et tests négatifs |
| Complexifier prématurément l’interface | Aucun nouvel écran avant 2.5.5 |
| Bloquer la suite par les réserves 2.5.2 | Suivi QA conservé ; clôture obligatoire avant le Go final 2.5.5 |

## 18. Seize décisions proposées à validation

1. 2.5.3 livre le backend, les contrats et la migration, sans nouvelle page utilisateur.
2. Les fournisseurs restent propres à chaque organisation ; aucun catalogue plateforme partagé n’est introduit.
3. `manual` et `google_maps` sont des sources système et ne sont jamais des fournisseurs configurables.
4. Un fournisseur n’est utilisable que s’il est actif, attesté, dans sa période et compatible avec source, territoire,
   finalité et catégories.
5. Facebook et LinkedIn ne sont que des types de provenance ; aucun scraping, connecteur ou appel API n’est livré.
6. Une acquisition externe est déclarative, idempotente et ne contient ni fichier, ni ligne, ni donnée de contact.
7. Une acquisition non conforme est mise en quarantaine au niveau métadonnée avec un code stable.
8. Une provenance externe exige une acquisition approuvée ; une saisie manuelle crée sa provenance côté serveur.
9. Le client ne peut jamais rattacher directement un `provenance_id` arbitraire à une nouvelle donnée.
10. La création d’un canal crée atomiquement une permission courante `unknown`.
11. `do_not_contact` et `opted_out` bloquent l’usage et se propagent aux canaux identiques de l’organisation.
12. Sales peut enregistrer une restriction, mais seuls Admin et Manager peuvent établir une autorisation.
13. La valeur normalisée est calculée côté serveur ; un doublon exact sur la même cible active est refusé.
14. Les modifications utilisent version optimiste, audit atomique, RLS, CSRF et réponses `no-store`.
15. Les audits, journaux et métriques ne contiennent aucune valeur de canal, preuve brute, secret ou donnée source.
16. Le Go de 2.5.3 exige migration réelle, tests de capacités/RLS/audit, non-régression Google et verrou qualité vert ;
    les réserves 2.5.2 restent suivies jusqu’à leur clôture au plus tard avant 2.5.5.

## 19. Décision de sortie

- **Go implémentation 2.5.3** : les seize décisions de la section 18 sont validées ;
- **No-Go** : une règle de provenance, permission, fournisseur ou capacité reste ambiguë ;
- **Go incrément suivant** : implémentation, migration, rapport et recette technique 2.5.3 sont conformes.

Décision produit du 14 août 2026 : les seize décisions sont validées et l’implémentation 2.5.3 est réalisée. La sortie
définitive reste soumise à la recette locale avec PostgreSQL réel et au verrou qualité complet.
