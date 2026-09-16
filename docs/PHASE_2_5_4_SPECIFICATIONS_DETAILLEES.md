# Incrément 2.5.4 — Conservation et déclarations d’import

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.5 — Socle prospects, conformité et conservation |
| Incrément | 2.5.4 — Conservation et déclarations d’import |
| Version | 1.0 |
| Statut | Implémentation réalisée — recette locale groupée 2.5.3–2.5.5 en attente |
| Date de proposition | 14 août 2026 |
| Validation produit | 14 août 2026 — validation des seize décisions de la section 19 |
| Prérequis | 2.5.3 implémenté ; recette locale 2.5.3–2.5.5 volontairement regroupée |
| Migration de départ | `20260814_0010` |
| Migration livrée | `20260814_0011 (head)` |
| Dépendances | Organisations/RLS 2.3, audit 2.4, modèle prospects 2.5.1, conformité 2.5.3 |
| Hors périmètre | Téléversement, parsing, prévisualisation ou import effectif d’un fichier, purge physique et interface finale |

Ce document définit les règles de conservation et le registre déclaratif des futurs imports. Il ne fixe aucune durée
légale universelle et ne constitue pas un avis juridique. Marketteo fournit un mécanisme configurable, traçable et
prudent : aucune donnée n’est détruite automatiquement dans cet incrément.

## 1. Objectifs

2.5.4 doit permettre de :

- définir des politiques de conservation versionnées par organisation et type de ressource ;
- calculer les échéances de revue sans tâche planifiée ni suppression automatique ;
- identifier les ressources à revoir, celles sans politique et celles protégées par un hold ;
- placer et libérer une mise en attente de conservation avec motif, acteur et audit ;
- archiver logiquement un prospect, un contact, un canal ou une déclaration d’import ;
- déclarer un futur import au moyen de métadonnées contrôlées, sans recevoir ni lire le fichier ;
- mettre une déclaration en quarantaine lorsque ses métadonnées sont incompatibles avec l’acquisition approuvée ;
- préserver l’isolation RLS, les versions optimistes, l’idempotence et l’audit transactionnel.

## 2. Périmètre fonctionnel

### 2.1 Inclus

- politiques locataires en états `draft`, `active` et `superseded` ;
- ressources couvertes : prospect, contact, canal, acquisition, provenance et déclaration d’import ;
- revue calculée : `policy_missing`, `upcoming`, `due`, `overdue`, `on_hold` ou `archived` ;
- holds multiples et indépendants sur une même ressource ;
- déclaration d’un lot CSV futur par métadonnées contrôlées ;
- quarantaine au niveau de la déclaration et codes de motif stables ;
- archivage logique explicite, cascade métier contrôlée et conservation de l’historique ;
- capacités, API, migration additive, RLS, audit, tests PostgreSQL et documentation.

### 2.2 Exclus

- champ de sélection de fichier, upload, stockage objet ou stockage temporaire de fichier ;
- lecture locale par le navigateur, calcul automatique d’empreinte, parsing, mapping libre ou prévisualisation ;
- création en masse de prospects, contacts, canaux ou provenances ;
- quarantaine de lignes, correction de lignes ou relance d’import ;
- exécution automatique des politiques, ordonnanceur, purge et effacement physique ;
- restauration, fusion de doublons ou réactivation d’une archive ;
- connecteur Facebook, LinkedIn, API externe ou récupération réseau ;
- nouvel écran métier, reporté à 2.5.5.

## 3. Invariants non négociables

1. Une politique produit une échéance de revue ; elle ne déclenche jamais une suppression dans 2.5.4.
2. Aucune durée de conservation universelle n’est codée en dur par Marketteo.
3. Une nouvelle politique ne réécrit pas rétroactivement la règle applicable aux ressources existantes.
4. Une ressource sans politique reste visible avec l’état `policy_missing` ; elle n’est ni ignorée ni supprimée.
5. Un hold actif interdit toute future purge et toute action automatique de conservation sur son périmètre.
6. Un hold ne supprime pas la visibilité réglementaire d’une ressource déjà archivée.
7. Libérer un hold n’archive et ne purge rien automatiquement.
8. L’archivage est logique, explicite, versionné, atomique et audité.
9. Les provenances, permissions, acquisitions et audits ne sont jamais effacés par l’archivage métier.
10. Une déclaration d’import n’est ni une acquisition approuvée, ni une validation du contenu du fichier.
11. Aucun octet du fichier, nom de fichier libre, ligne, cellule ou extrait n’est accepté ou conservé.
12. Une déclaration externe exige une acquisition 2.5.3 approuvée et cohérente.
13. Une mise en quarantaine ne conserve que des codes de contrôle et des métadonnées non personnelles.
14. Toutes les ressources sont isolées par organisation au niveau applicatif et PostgreSQL RLS.
15. Toute mutation et son audit sont validés ou annulés dans la même transaction.
16. Toutes les réponses de ce périmètre portent `Cache-Control: no-store`.

## 4. Modèle de conservation

### 4.1 `retention_policies`

La migration crée une table locataire comprenant au minimum :

- `id`, `organization_id` ;
- `resource_type` : `prospect`, `contact`, `contact_channel`, `acquisition_record`, `provenance_record` ou
  `import_declaration` ;
- `policy_code` et `label` contrôlés en longueur ;
- `status` : `draft`, `active` ou `superseded` ;
- `review_after_days`, entier de 1 à 36 500 ;
- `archive_after_days` nullable, supérieur ou égal à `review_after_days` lorsqu’il est renseigné ;
- `effective_from`, `effective_until` nullable ;
- `approved_at`, `approved_by` ;
- `created_by`, `created_at`, `updated_at`, `version`.

`archive_after_days` représente une recommandation de revue renforcée ; il ne programme aucune archive. Une politique
ne peut devenir `active` sans approbation explicite, période cohérente et capacité de gestion. Une seule politique
active peut couvrir un type de ressource à une date donnée dans une organisation. L’activation d’une nouvelle version
ferme la période de la précédente et la passe à `superseded` dans la même transaction.

Les versions antérieures restent immuables. Une correction substantielle crée une nouvelle politique ; seuls le
libellé non juridique d’un brouillon et ses paramètres peuvent être modifiés avant activation.

### 4.2 Détermination de la politique applicable

La politique applicable est déterminée à partir du type de ressource et de sa date de référence :

- `created_at` pour prospect, contact, canal et déclaration d’import ;
- `obtained_at` pour acquisition et provenance.

La version dont la période d’effet couvre cette date reste applicable à la ressource. Une nouvelle politique agit donc
prospectivement. Si aucune politique ne couvre la date, la ressource reçoit l’état calculé `policy_missing`.

La date de revue calculée est `date_de_référence + review_after_days`. Un éventuel `retention_review_at` explicitement
déjà enregistré sur le prospect constitue une échéance plus précise et prévaut, sans pouvoir masquer l’absence de
politique dans les autres catégories.

### 4.3 États de revue calculés

- `policy_missing` : aucune politique applicable ;
- `upcoming` : revue à venir au-delà de la fenêtre d’alerte ;
- `due` : revue dans la fenêtre configurable de 30 jours par défaut ;
- `overdue` : date de revue dépassée ;
- `on_hold` : au moins un hold actif couvre la ressource ;
- `archived` : ressource logiquement archivée, toujours consultable avec la capacité adéquate.

Ces états sont calculés à la lecture et ne sont pas une nouvelle colonne mutable. Le classement utilise l’horloge
serveur UTC et un curseur opaque stable. Aucun processus d’arrière-plan n’est ajouté.

## 5. Mises en attente de conservation

### 5.1 `retention_holds`

La table locataire comprend :

- `id`, `organization_id` ;
- `resource_type` et `resource_id` ;
- `reason_code` contrôlé ;
- `note` optionnelle, limitée à 500 caractères et interdite dans les journaux/audits ;
- `placed_at`, `placed_by` ;
- `released_at`, `released_by`, `release_reason_code` ;
- `version`, `created_at`, `updated_at`.

Les motifs initiaux sont `legal_request`, `contractual_obligation`, `investigation`, `data_subject_request`,
`quality_review` et `other`. Pour `other`, une note est obligatoire. Une note ne doit contenir ni valeur de canal,
ni contenu de fichier, ni secret.

Le couple polymorphe `resource_type/resource_id` est contrôlé par le serveur et par un déclencheur PostgreSQL qui
vérifie l’existence de la ressource dans la même organisation. Cette protection empêche un hold orphelin ou
inter-locataire malgré l’absence de FK polymorphe native.

### 5.2 Portée et multiplicité

Plusieurs holds actifs peuvent protéger la même ressource pour des motifs distincts. La ressource reste `on_hold` tant
qu’au moins un hold est actif. Libérer un hold n’en libère aucun autre.

- un hold sur un prospect couvre son agrégat : contacts, canaux, permissions et provenances associées ;
- un hold sur une acquisition couvre ses déclarations d’import et provenances associées ;
- un hold sur une déclaration protège sa métadonnée et les futures preuves de traitement ;
- un hold ciblé sur un contact ou un canal protège uniquement cette branche et ses preuves.
- un hold ciblé sur une provenance protège directement cette preuve lorsqu’aucun agrégat parent ne suffit.

L’archivage logique peut coexister avec un hold puisqu’il ne détruit pas les données. En revanche, toute future purge
ou anonymisation devra consulter les holds directs et hérités avant d’agir.

### 5.3 Création et libération

La création et la libération utilisent une `Idempotency-Key`. La libération exige la version courante, un motif stable
et la capacité réservée. Une libération répétée avec la même clé retourne le résultat existant ; une clé réutilisée
avec un autre corps produit `409 idempotency_key_reused`.

## 6. Déclarations d’import sans fichier

### 6.1 Distinction avec l’acquisition

`acquisition_records` répond à « avons-nous le droit d’utiliser cette source, pour cette finalité et ce territoire ? ».
`import_declarations` répond à « quel lot l’organisation prévoit-elle de traiter ultérieurement ? ».

Une acquisition approuvée est obligatoire avant la déclaration. Elle ne rend pas le futur contenu valide : chaque
ligne devra encore être contrôlée lors d’un incrément d’import effectif.

### 6.2 `import_declarations`

La table comprend :

- `id`, `organization_id`, `acquisition_record_id` ;
- `declaration_label`, libellé métier neutre de 1 à 160 caractères ;
- `format_code`, limité à `csv` dans 2.5.4 ;
- `schema_code`, version du schéma déclaratif attendu ;
- `declared_field_codes`, tableau de codes contrôlés et non de noms de colonnes libres ;
- `declared_data_categories`, sous-ensemble des catégories de l’acquisition ;
- `estimated_row_count` nullable, entier positif purement déclaratif ;
- `declared_content_sha256` nullable, empreinte fournie par l’opérateur et explicitement non vérifiée ;
- `status` : `declared`, `quarantined`, `cancelled` ou `archived` ;
- `decision_reason_codes`, liste de codes contrôlés, sans message libre ;
- `declared_by`, `declared_at`, `cancelled_at`, `archived_at`, `archived_by`, `archive_reason_code` ;
- `idempotency_key`, empreinte serveur de la commande, `version`, `created_at`, `updated_at`.

Le modèle ne contient volontairement aucun `file_path`, `storage_key`, `blob`, `payload`, `row_data`, `preview` ou
`original_filename`. L’empreinte éventuelle est une attestation déclarée ; Marketteo ne la calcule et ne la présente
jamais comme une preuve cryptographique vérifiée.

### 6.3 Catalogue initial de champs déclarés

- `business_name`, `business_identifier`, `business_address` ;
- `contact_name`, `contact_role` ;
- `email`, `phone`, `linkedin_profile`, `facebook_profile` ;
- `notes`.

Les codes sont convertis en catégories 2.5.3 par le serveur. `notes` est considéré comme une catégorie à risque et
place la déclaration en quarantaine tant qu’une future politique de traitement structurée n’est pas définie. Aucun
nom de colonne libre n’est conservé.

### 6.4 Décision de déclaration

Une déclaration devient `declared` si :

- l’acquisition existe dans l’organisation et est `approved` ;
- le fournisseur demeure identifiable dans l’historique ;
- format, schéma, champs et catégories appartiennent aux catalogues ;
- les catégories déclarées sont couvertes par l’acquisition approuvée ;
- la commande ne contient aucune propriété interdite ou donnée brute.

Une acquisition absente ou non approuvée produit `409 acquisition_not_approved` sans créer de déclaration. Une
déclaration rattachée à une acquisition approuvée devient `quarantined` pour un autre écart métier contrôlable,
notamment `category_not_acquired`, `field_not_allowed`, `high_risk_free_text` ou `provider_history_incomplete`. Une
requête JSON mal formée, trop volumineuse ou contenant une propriété inconnue est rejetée `422` sans créer de
déclaration.

### 6.5 Pas de quarantaine de lignes

2.5.4 ne crée pas `import_quarantine_rows` : aucune ligne n’existe tant qu’aucun fichier n’est reçu et parsé. Les motifs
de quarantaine portent uniquement sur la déclaration. Une table de lignes en quarantaine sera créée avec l’import
effectif, lorsque ses durées, accès, corrections et règles de suppression pourront être testés de bout en bout.

## 7. Archivage logique

### 7.1 Ressources archivables

- prospect ;
- contact ;
- canal de contact ;
- déclaration d’import.

Les acquisitions, provenances, permissions et événements d’audit restent des preuves historiques et ne disposent pas
d’une commande d’archivage métier. Un fournisseur quitte l’usage par `suspended` ou `retired`, conformément à 2.5.3.

### 7.2 Règles d’archivage

Chaque commande exige un `expected_version`, un `archive_reason_code`, un acteur autorisé et une ressource active.
Les motifs initiaux sont `duplicate`, `invalid_data`, `no_longer_relevant`, `relationship_ended`, `import_cancelled` et
`other`. Une concurrence produit `409 optimistic_lock_conflict`.

- archiver un prospect archive dans la même transaction ses contacts et canaux actifs ;
- archiver un contact archive ses canaux actifs ;
- archiver un canal conserve sa permission et sa provenance ;
- archiver une déclaration ne modifie ni son acquisition ni le fournisseur ;
- les timestamps existants ne sont jamais remplacés lors d’un rejeu idempotent ;
- l’audit de cascade ne contient que les identifiants internes et les compteurs affectés.

Les listes opérationnelles excluent les archives par défaut. `include_archived=true` exige une capacité de lecture
appropriée. La restauration et la fusion restent hors périmètre et aucune route de suppression physique n’est créée.

## 8. Matrice de capacités

| Capacité | Admin organisation | Manager | Sales |
| --- | ---: | ---: | ---: |
| `retention:read` | oui | oui | non |
| `retention:manage` | oui | non | non |
| `retention:hold:create` | oui | oui | non |
| `retention:hold:release` | oui | non | non |
| `imports:read` | oui | oui | non |
| `imports:declare` | oui | oui | non |
| `imports:archive` | oui | non | non |
| `prospects:archive` | oui | oui | non |
| `contacts:archive` | oui | oui | non |

Sales continue de créer et qualifier les données selon 2.5.2–2.5.3, mais ne décide ni des politiques, ni des holds,
ni de l’archivage. Un administrateur plateforme doit posséder une appartenance locataire active pour agir.

## 9. API applicative

Toutes les mutations exigent authentification, organisation active, capacité, JSON strict, origine de confiance et
jeton CSRF. Toutes les réponses portent `Cache-Control: no-store`.

### 9.1 Politiques et revues

- `GET /api/retention/policies` — liste des versions, filtrable par type et état ;
- `POST /api/retention/policies` — création d’un brouillon ;
- `GET /api/retention/policies/{policy_id}` — détail locataire ;
- `PATCH /api/retention/policies/{policy_id}` — modification optimiste d’un brouillon ;
- `POST /api/retention/policies/{policy_id}/activate` — activation et remplacement atomique ;
- `GET /api/retention/reviews` — file calculée et paginée, sans mutation.

La file accepte `resource_type`, `review_state`, `due_before`, `limit` et `cursor`. Le curseur encode une position
serveur signée ou opaque ; il ne contient aucune donnée personnelle lisible.

### 9.2 Holds

- `GET /api/retention/holds` — liste filtrée selon ressource et état ;
- `POST /api/retention/holds` — placement idempotent ;
- `GET /api/retention/holds/{hold_id}` — détail sans note dans les listes générales ;
- `POST /api/retention/holds/{hold_id}/release` — libération optimiste et idempotente.

### 9.3 Déclarations d’import

- `GET /api/import-declarations` — liste paginée ;
- `POST /api/import-declarations` — déclaration métadonnée uniquement ;
- `GET /api/import-declarations/{declaration_id}` — détail et codes de décision ;
- `POST /api/import-declarations/{declaration_id}/cancel` — annulation avant futur traitement ;
- `POST /api/import-declarations/{declaration_id}/archive` — archivage logique.

La route de création accepte uniquement `application/json`. `multipart/form-data`, `application/octet-stream`, champ
base64, tableau de lignes ou propriété inconnue sont refusés avant le cas d’utilisation.

### 9.4 Archivage métier

- `POST /api/prospects/{prospect_id}/archive` ;
- `POST /api/contacts/{contact_id}/archive` ;
- `POST /api/contact-channels/{channel_id}/archive`.

Les commandes sont explicites afin d’éviter de confondre un `DELETE` HTTP avec une suppression physique.

### 9.5 Erreurs stables

Les codes comprennent au minimum `policy_overlap`, `policy_not_active`, `resource_on_hold`, `hold_already_released`,
`acquisition_not_approved`, `import_declaration_quarantined`, `raw_import_content_forbidden`,
`optimistic_lock_conflict`, `idempotency_key_reused`, `resource_not_found` et `insufficient_capability`.

Une ressource d’une autre organisation reste indiscernable d’une ressource inexistante.

## 10. Ports et cas d’utilisation

Les ports applicatifs ajoutés ou complétés sont :

- `RetentionPolicyRepository` ;
- `RetentionHoldRepository` ;
- `RetentionReviewRepository` ;
- `ImportDeclarationRepository` ;
- opérations d’archivage des repositories prospects/contacts/canaux ;
- unité de travail locataire unique pour mutation et audit ;
- `Clock` et stockage d’idempotence existants.

Cas d’utilisation minimaux : créer/modifier/activer une politique, lister les revues, placer/lister/libérer un hold,
déclarer/lister/lire/annuler/archiver un import et archiver chaque agrégat métier autorisé.

Le domaine ne dépend ni de SQLAlchemy ni de FastAPI. Les routes ne décident pas des durées, des cascades ou des
capacités et les repositories ne décident pas des transitions métier.

## 11. Transactions, concurrence et idempotence

- activation de politique, remplacement de version et audit : une transaction ;
- placement/libération de hold et audit : une transaction ;
- déclaration, décision de quarantaine et audit : une transaction ;
- archivage racine, cascade, versions et audit : une transaction ;
- version optimiste obligatoire sur toute modification d’une ressource existante ;
- `Idempotency-Key` obligatoire pour holds, déclarations, annulations et archives ;
- une clé appartient à l’organisation, à l’acteur et au type de commande ;
- aucune réponse idempotente ne rejoue un audit ou ne remplace un timestamp.

## 12. Audit, confidentialité et observabilité

### 12.1 Événements

- `retention_policy.created`, `retention_policy.activated`, `retention_policy.superseded` ;
- `retention_hold.placed`, `retention_hold.released` ;
- `import_declaration.declared`, `import_declaration.quarantined`, `import_declaration.cancelled`,
  `import_declaration.archived` ;
- `prospect.archived`, `contact.archived`, `contact_channel.archived`.

### 12.2 Métadonnées autorisées

Identifiants internes, type de ressource, codes de politique, ancien/nouvel état, codes de motif, version, compteurs de
cascade et catégories contrôlées. Sont interdits : note de hold, libellé de déclaration, valeur de canal, nom de
contact, adresse, nom de fichier, empreinte déclarée, contenu, ligne, cellule, secret et preuve brute.

### 12.3 Métriques

- politiques actives, ressources sans politique, revues dues et en retard ;
- holds placés/libérés et ressources protégées, par code non personnel ;
- déclarations par état et motif de quarantaine ;
- archives par type et conflits optimistes ;
- rejets de contenu brut ou type média interdit.

Les métriques et journaux n’exposent aucun identifiant externe libre ni donnée personnelle.

## 13. Migration, RLS et privilèges

- une révision Alembic additive après `20260814_0010` ;
- création de `retention_policies`, `retention_holds` et `import_declarations` ;
- ajout raisonné des informations d’archivage manquantes sur prospects, contacts et canaux ;
- contraintes de périodes, statuts, versions, catalogues et unicité des politiques actives ;
- déclencheur de validation locataire des cibles de hold ;
- index sur organisation, type, statut, échéance, acquisition et ressource tenue ;
- RLS forcée et privilèges minimaux du rôle Web sur les nouvelles tables ;
- aucune politique par défaut, aucune date légale inventée et aucun backfill destructif ;
- aucun fichier, appel réseau, appel Google ou tâche planifiée pendant la migration ;
- upgrade testé depuis `20260814_0009` via `0010` jusqu’au nouveau `head`, puis sur base vide ;
- downgrade limité à une base de test sans données 2.5.4 significatives.

## 14. Interface utilisateur

2.5.4 livre le backend, les contrats et la migration sans changement visuel. L’interface finale appartient à 2.5.5.
Les nouvelles capacités sont néanmoins présentes dans la session afin de préparer les routes protégées.

L’écran futur de déclaration ne contiendra aucun sélecteur de fichier dans ce lot. Il présentera uniquement les
métadonnées contrôlées et un message explicite : « Aucun fichier n’est envoyé ni traité dans cette version ».

Tous les tests frontend existants restent obligatoires : routage, session, capacités, accessibilité, absence de
stockage navigateur, Google limité à vingt résultats et ajout explicite au CRM.

## 15. Stratégie de tests

### 15.1 Domaine et cas d’utilisation

- refus d’une politique invalide, chevauchante ou activée sans approbation ;
- conservation immuable de la version applicable aux anciennes ressources ;
- états `policy_missing`, `upcoming`, `due`, `overdue`, `on_hold` et `archived` déterministes ;
- plusieurs holds actifs, libération indépendante et portée héritée ;
- déclaration conforme, quarantinée, idempotente et conflit de clé ;
- refus de toute donnée brute, propriété inconnue, contenu base64 ou catégorie non acquise ;
- archivage optimiste, cascades et rejeu sans nouvel audit ;
- aucune suppression des permissions, provenances, acquisitions ou audits.

### 15.2 PostgreSQL réel

- migration sur base vide et upgrade `0009 -> 0010 -> nouveau head` ;
- contraintes de période, catalogue, version et politique active unique ;
- cible de hold inexistante ou inter-locataire refusée en base ;
- RLS positive et négative sur deux organisations pour les trois nouvelles tables ;
- rôle Web sans DDL, contournement RLS ni suppression physique ;
- rollback intégral des mutations et audits ;
- plan d’index vérifié pour la file de revue et les listes paginées ;
- `alembic current`, `alembic check` et reconstruction contrôlée.

### 15.3 API et sécurité

- matrice Admin/Manager/Sales positive et négative ;
- CSRF, origine, JSON strict, taille, `no-store` et curseurs opaques ;
- multipart, octet-stream, lignes, cellules, nom de fichier et propriétés inconnues refusés ;
- aucune fuite inter-organisation dans les listes, détails, erreurs ou holds hérités ;
- aucune donnée sensible dans audits, logs, métriques ou messages ;
- aucune route d’upload, parsing, purge, restauration ou import effectif.

### 15.4 Non-régression et qualité

- création prospect manuelle et ajout Google toujours conformes ;
- permissions et fournisseurs 2.5.3 inchangés ;
- un Text Search, vingt résultats, aucun contact et aucune pagination Google ;
- Ruff format/check, mypy, pytest réel sans `skip` ;
- ESLint, Vitest/axe et build Vite ;
- verrou qualité local et Azure Pipelines verts.

La recette fonctionnelle et PostgreSQL complète est regroupée avec 2.5.3 et 2.5.5. Les tests automatisés ciblés,
contrôles statiques et vérifications de migration restent obligatoires pendant l’implémentation de 2.5.4.

## 16. Critères d’acceptation

2.5.4 est acceptable lorsque :

- un administrateur peut créer puis activer une politique versionnée sans durée légale imposée par le produit ;
- la file de revue distingue correctement absence de politique, échéance, retard, hold et archive ;
- un manager peut placer un hold et seul un administrateur peut le libérer ;
- les holds multiples et hérités protègent les bons agrégats sans fuite locataire ;
- une déclaration conforme est enregistrée sans aucun fichier ni contenu ;
- une déclaration incohérente est quarantinée uniquement par métadonnées et codes stables ;
- les archives sont logiques, transactionnelles, optimistes et conservent toutes les preuves ;
- RLS, audit, idempotence, confidentialité et non-régression sont prouvés ;
- les contrôles automatisés de l’incrément sont verts.

## 17. Points explicitement différés

Les éléments suivants devront être redécidés avant tout import effectif :

- lieu, chiffrement et durée du stockage temporaire d’un fichier ;
- antivirus, décompression, limite de taille et formats réellement acceptés ;
- calcul serveur de l’empreinte et preuve de suppression du fichier ;
- mapping des colonnes, prévisualisation et consentement avant import ;
- quarantaine ligne par ligne et rôles autorisés à voir/corriger les valeurs ;
- déduplication, reprise partielle, annulation et rapport d’import ;
- purge/anonymisation physique et preuves réglementaires associées.

## 18. Risques et réponses

| Risque | Réponse retenue |
| --- | --- |
| Transformer une politique en suppression implicite | Revue calculée uniquement ; aucun ordonnanceur ni purge |
| Inventer une durée légale générique | Aucune valeur par défaut ; politique approuvée par organisation |
| Modifier rétroactivement l’historique | Versions à périodes d’effet immuables et application prospective |
| Lever un hold trop largement | Holds multiples, libération unitaire, capacité Admin et version optimiste |
| Prétendre valider un fichier non lu | Statut déclaratif explicite et empreinte non vérifiée |
| Stocker accidentellement du contenu | JSON strict, catalogue fermé et absence de colonnes de payload |
| Quarantaine fictive de lignes | Quarantaine limitée à la déclaration jusqu’au véritable parsing |
| Perdre les preuves lors d’une archive | Archive logique avec permissions, provenance, acquisition et audit conservés |
| Créer des données inter-locataires polymorphes | Validation applicative et déclencheur PostgreSQL sous RLS |
| Accumuler les risques avant la recette groupée | Tests automatisés et migration contrôlés à chaque sous-incrément |

## 19. Seize décisions proposées à validation

1. 2.5.4 livre les contrats backend et la migration sans nouvel écran, l’interface étant réservée à 2.5.5.
2. Aucune durée légale universelle ou politique par défaut n’est codée par Marketteo.
3. Les politiques sont locataires, versionnées, approuvées et applicables prospectivement selon leur période d’effet.
4. Une politique calcule une échéance de revue mais ne déclenche ni archive ni suppression automatique.
5. Les ressources sans politique restent visibles avec l’état `policy_missing`.
6. Plusieurs holds indépendants peuvent couvrir une ressource ; elle reste protégée jusqu’à leur libération complète.
7. Manager peut placer un hold, mais seul Admin peut le libérer ; chaque opération est idempotente et auditée.
8. Un hold bloque toute future purge ou action automatique, mais peut coexister avec une archive logique conservant les
   preuves.
9. L’archivage d’un prospect ou d’un contact cascade logiquement vers ses descendants actifs, sans suppression de
   provenance, permission, acquisition ou audit.
10. Acquisitions, provenances, permissions et audits ne disposent d’aucune commande d’archivage ou suppression métier.
11. Une déclaration d’import exige une acquisition 2.5.3 approuvée et ne vaut jamais validation du futur contenu.
12. Aucun fichier, nom de fichier libre, ligne, cellule, extrait, stockage objet ou traitement navigateur n’est livré.
13. La déclaration accepte uniquement des métadonnées et codes contrôlés ; son empreinte éventuelle est déclarée et
    explicitement non vérifiée.
14. Sans parsing, la quarantaine reste au niveau de la déclaration ; aucune table de lignes en quarantaine n’est créée.
15. Capacités, RLS, CSRF, `no-store`, version optimiste, idempotence et audit atomique protègent toutes les mutations.
16. La recette locale et les migrations 2.5.3–2.5.5 sont regroupées, mais les tests automatisés, contrôles statiques
    et vérifications de migration restent obligatoires à chaque implémentation.

## 20. Décision de sortie

- **Go implémentation 2.5.4** : les seize décisions de la section 19 sont validées ;
- **No-Go** : une règle de durée, hold, archivage, déclaration ou capacité reste ambiguë ;
- **Go 2.5.5** : implémentation, migration et rapport 2.5.4 sont conformes aux contrôles automatisés ; la recette
  humaine et PostgreSQL définitive reste regroupée à la fin de 2.5.5.

Décision produit du 14 août 2026 : les seize décisions sont validées et le GO d’implémentation a été donné.
L’implémentation backend, la migration `20260814_0011`, les tests automatisés et le rapport sont réalisés. La recette
humaine et PostgreSQL définitive reste volontairement regroupée à la fin de 2.5.5.
