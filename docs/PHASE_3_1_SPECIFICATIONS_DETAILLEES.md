# Phase 3.1 — Import CSV conforme réel

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3 — Cœur CRM |
| Incrément | 3.1 — Import CSV conforme réel |
| Version | 1.2 — clôture avec réserve |
| Prérequis | Phase 2.5 (prospects, acquisition, provenance, permissions et conservation) ; 2.6 (Redis, audit, qualité) |
| Statut | Clôturé avec réserve — 3.2 autorisé ; staging 2.6 et Azure requis avant préproduction |
| Date | 4 septembre 2026 |
| Résultat visé | Fichier temporaire, aperçu, mapping, validation, confirmation idempotente, quarantaine et rapport |

## 1. Objectif

Cet incrément rend utilisable la déclaration d’import CSV créée en 2.5.4. Il permet à une organisation d’importer son propre portefeuille ou des données issues d’un fournisseur approuvé, en préservant la provenance par donnée, la permission de contact, la conservation, RLS et l’audit.

Le fichier est un support de traitement temporaire, **pas** une nouvelle source de vérité durable. Après confirmation, seules les données CRM autorisées, leurs provenances et les décisions de traitement persistent. Le fichier source et ses lignes brutes ne sont jamais recopiés dans l’audit, les journaux, les métriques ou les rapports.

## 2. Périmètre

### 2.1 Inclus

- réception d’un seul fichier CSV par déclaration d’import active ;
- stockage temporaire privé, non exposé par URL publique, avec suppression contrôlée ;
- analyse en flux d’un CSV UTF-8 ou UTF-8 avec BOM ;
- aperçu limité des en-têtes et des 100 premières lignes pour l’utilisateur autorisé ;
- correspondance explicite entre colonnes CSV et champs CRM autorisés ;
- validation du format, de l’acquisition, du contrat, des catégories, des données et des doublons ;
- confirmation idempotente créant prospects, contacts, canaux, provenance et permissions `unknown` lorsque permis ;
- quarantaine sans création CRM des lignes impossibles ou ambiguës ;
- rapport interne en JSON et CSV minimal, avec compteurs, numéros de lignes et codes de motifs ;
- migration additive, RLS, audit transactionnel, API, interface, tests et documentation.

### 2.2 Hors périmètre

- fichiers XLS, XLSX, ODS, ZIP, PDF ou tout format non CSV ;
- formule Excel, macro, conversion automatique de format, OCR ou lecture par le navigateur ;
- correction en ligne d’une ligne en quarantaine, fusion humaine et reprise automatique ;
- traitement asynchrone massif, ordonnanceur, file de messages ou import dépassant la limite de cette phase ;
- connecteur Meta, LinkedIn, Facebook, API publique, scraping ou synchronisation planifiée ;
- export du portefeuille CRM, enrichissement, recherche Google déclenchée par import, ni création d’activité commerciale ;
- permission de prospection automatique, envoi de courriel ou appel automatique.

## 3. Acteurs et droits

| Acteur | Droit dans 3.1 |
| --- | --- |
| Administrateur d’organisation | Déclarer, téléverser, mapper, confirmer, annuler, consulter et télécharger le rapport |
| Gestionnaire | Même droit que l’administrateur, sauf si l’organisation réduit explicitement cette capacité dans une phase ultérieure |
| Commercial | Consulter les rapports sans le fichier ni les valeurs d’aperçu ; aucune écriture d’import |
| Administrateur de plateforme | Aucun accès implicite aux fichiers ni aux données d’une organisation ; accès seulement via les mécanismes d’audit plateforme déjà autorisés |

Les capacités sont vérifiées par route et cas d’utilisation. La portée d’organisation provient de la session et de la transaction RLS, jamais du navigateur.

## 4. Parcours fonctionnel

1. L’administrateur ou gestionnaire sélectionne une acquisition approuvée, active et compatible, puis crée ou reprend une déclaration CSV.
2. Il choisit un fichier CSV. Le navigateur l’envoie comme flux binaire `text/csv` ; aucun contenu n’est lu, stocké ou analysé côté React.
3. Le serveur vérifie le type, la taille, le nom technique sûr, l’encodage, les en-têtes, le nombre de colonnes et les limites de lignes, puis place les octets dans le stockage temporaire privé.
4. Le serveur retourne les colonnes détectées, un aperçu d’au plus 100 lignes et les catégories déclarées par l’acquisition. La réponse porte `Cache-Control: no-store`.
5. L’utilisateur associe explicitement les colonnes admises aux champs CRM. Les colonnes non mappées sont signalées comme ignorées et ne sont jamais persistées.
6. Le serveur valide le mapping puis le fichier complet en flux. Il affiche les compteurs prévisionnels : créations possibles, doublons exacts, lignes à revoir, lignes rejetées et lignes en quarantaine.
7. L’utilisateur confirme avec une clé d’idempotence. Le serveur vérifie à nouveau l’acquisition, la déclaration, le mapping et l’empreinte du fichier avant toute écriture.
8. Les lignes valides sont écrites avec provenance ; les lignes invalides ou ambiguës sont mises en quarantaine. La réponse donne l’état et le rapport sans valeurs brutes.
9. Le fichier et les copies de travail sont supprimés à la fin du traitement réussi, annulé ou échoué. Une quarantaine conserve seulement un numéro de ligne, des codes de motifs et une référence temporaire jusqu’à expiration ; une correction se fait par un nouveau fichier dans un incrément ultérieur.

## 5. Contrat de fichier et limites

| Règle | Valeur proposée |
| --- | --- |
| Format | CSV RFC 4180, séparateur détecté parmi virgule, point-virgule ou tabulation |
| Encodage | UTF-8 ou UTF-8 BOM uniquement |
| Taille maximale | 10 Mio |
| Lignes de données | 5 000 maximum, en plus de l’en-tête |
| Colonnes | 50 maximum |
| Longueur d’une cellule | 4 096 caractères maximum |
| Aperçu | 100 lignes maximum, uniquement à l’utilisateur autorisé |
| Durée du fichier temporaire | 24 heures maximum, ou suppression immédiate après finalisation |
| Téléversements actifs | Un fichier par déclaration ; un nouveau fichier invalide l’aperçu et mapping précédents |

Le serveur traite le fichier en flux. Toute taille, encodage, structure CSV ou limite invalide échoue avant toute écriture CRM. Aucun nom de fichier libre n’est inclus dans l’audit ou les journaux ; l’application utilise un identifiant opaque et une empreinte cryptographique du contenu.

## 6. Mapping et données admises

Le mapping est une liste blanche. Une colonne CSV peut alimenter au plus un champ cible. Les champs cibles proposés sont :

| Cible CRM | Obligatoire | Traitement |
| --- | --- | --- |
| `prospect_name` | Oui pour créer un prospect | Devient le nom interne CRM, normalisé et borné |
| `sector` | Non | Secteur CRM interne |
| `city` | Non | Ville CRM interne, non résolue automatiquement dans 3.1 |
| `contact_name` | Non | Crée ou rattache une personne au prospect de la ligne |
| `email` | Non | Canal Courriel avec provenance import et permission `unknown` |
| `phone` | Non | Canal Téléphone avec provenance import et permission `unknown` |
| `social_profile` | Non | Canal Profil social avec provenance import et permission `unknown` |
| `external_reference` | Non mais recommandé | Identifiant source exact servant à l’idempotence et à la déduplication exacte |
| `tags` | Non | Étiquettes CRM normalisées, limitées et séparées par le format déclaré |

Un fichier peut contenir seulement un prospect, ou un prospect et un contact/canal. Une ligne contenant uniquement un contact ou canal sans `prospect_name` est rejetée. Une valeur de canal ne peut être créée si la catégorie correspondante n’est pas déclarée et admise dans l’acquisition. Les colonnes non mappées n’entrent jamais dans PostgreSQL.

Les champs `place_id`, nom Google, adresse Google, résultat Google, consentement libre, note libre, mot de passe, secret, donnée financière ou donnée sensible sont interdits par le mapping 3.1. Un `place_id` ne provient que du parcours Google contrôlé existant.

## 7. Validation, déduplication et quarantaine

### 7.1 États de ligne

Chaque ligne reçoit un seul résultat principal avant confirmation :

- `ready_to_create` : toutes les validations sont satisfaites ;
- `exact_duplicate` : correspondance exacte déjà connue ; aucune seconde création ;
- `review_required` : correspondance potentielle non exacte ; aucune fusion ni création automatique ;
- `quarantined` : donnée, catégorie ou règle de conformité insuffisante ;
- `rejected` : structure ou valeur invalide sans possibilité de traitement.

### 7.2 Idempotence et doublons

Une commande de confirmation porte un `Idempotency-Key` opaque. Le même identifiant et le même contenu renvoient le résultat initial ; un même identifiant avec un contenu différent retourne `409 idempotency_key_reused`.

La déduplication exacte suit cet ordre :

1. même `external_reference` sous la même acquisition et la même organisation ;
2. même empreinte canonique de ligne sous la même acquisition ;
3. même `place_id` actif lorsqu’un prospect provient déjà du flux Google — mais le CSV ne peut jamais créer ou modifier ce `place_id`.

Un nom, une ville, une adresse, un contact ou un canal ressemblant seulement à une donnée existante produit `review_required`. Il ne modifie jamais un prospect, contact ou canal existant. Les décisions humaines de rapprochement sont reportées à un incrément futur.

### 7.3 Quarantaine

La quarantaine conserve `import_declaration_id`, numéro de ligne, catégorie de résultat et codes de motifs. Elle ne conserve pas le texte complet de la ligne dans PostgreSQL ou l’audit. Les motifs initiaux sont : `missing_required_field`, `invalid_encoding`, `invalid_value`, `undeclared_category`, `acquisition_not_approved`, `contract_not_active`, `possible_duplicate`, `unsupported_data`, `limit_exceeded` et `processing_failed`.

Une déclaration avec au moins une ligne en quarantaine devient `quarantined_with_report` après traitement. Les lignes valides peuvent être confirmées : la quarantaine ne bloque pas tout le lot, sauf acquisition inactive, contrat expiré, violation de sécurité ou erreur transactionnelle globale.

## 8. Stockage, conservation et reprise

Le port applicatif `TemporaryImportFileStore` isole le stockage. L’adaptateur de développement/staging utilise un répertoire privé monté hors des fichiers statiques, avec accès restreint au compte de service. L’adaptateur de production pourra utiliser un stockage objet privé chiffré sans modifier les cas d’utilisation.

Le fichier est référencé par un identifiant opaque, une taille, un digest SHA-256, un état et une échéance ; ni son nom libre, ni son contenu, ni une URL publique ne sont conservés. À expiration, annulation ou finalisation, la suppression physique est tentée et l’état de suppression est audité. En cas d’échec de suppression, le système le signale techniquement et refuse tout téléchargement public ; une reprise administrative sécurisée sera spécifiée avant production.

Le navigateur garde l’aperçu uniquement en mémoire. Il ne met pas le fichier, l’aperçu, le mapping ou le rapport dans `localStorage`, `sessionStorage` ou cache persistant.

## 9. Modèle de données et migrations proposées

Une migration additive prolonge `import_declarations` et introduit les tables nécessaires :

- `import_file_records` : déclaration, identifiant opaque, digest, taille, encodage, état, échéance et dates de suppression ;
- `import_mappings` : mapping versionné, digest de fichier, catégories admises et auteur ;
- `import_processing_runs` : clé d’idempotence hachée, état, compteurs, dates, rapport minimal et version ;
- `import_quarantine_rows` : run, numéro de ligne, résultat et codes de motifs sans valeur brute ;
- `import_source_fingerprints` : acquisition, organisation, empreinte canonique et référence source pour les relectures exactes.

Toutes les tables portent `organization_id`, RLS activée/forcée, index de portée et contraintes de cohérence. Les écritures de prospects, contacts, canaux, provenances, permissions, résultats d’import et événements d’audit s’exécutent dans la même transaction de confirmation. Aucun fichier n’est stocké dans PostgreSQL.

## 10. API proposée

| Route | Rôle | Résultat |
| --- | --- | --- |
| `POST /api/imports/declarations` | Admin/Gestionnaire | Crée ou reprend une déclaration CSV liée à une acquisition approuvée |
| `PUT /api/import-declarations/{id}/file` | Admin/Gestionnaire | Reçoit le flux CSV temporaire et retourne les en-têtes/l’aperçu limité |
| `GET /api/csv-imports/{id}/preview` | Selon capacité | Recharge l’aperçu limité sans écrire le CRM |
| `PATCH /api/csv-imports/{id}/mapping` | Admin/Gestionnaire | Enregistre le mapping explicite, versionné |
| `POST /api/csv-imports/{id}/validate` | Admin/Gestionnaire | Calcule les compteurs et statuts prévisionnels sans écrire le CRM |
| `POST /api/csv-imports/{id}/confirm` | Admin/Gestionnaire | Confirme avec `Idempotency-Key` et écrit les lignes valides |
| `GET /api/csv-import-runs/{id}/quarantines` | Selon capacité | Retourne les lignes/codes/références opaques du rapport, sans valeur source |

Les routes de fichier et aperçu retournent `Cache-Control: no-store`. Les erreurs utilisent les codes existants, notamment `403`, `404`, `409`, `413`, `415`, `422` et `503`, avec un `request_id` et sans valeur CSV révélée.

## 11. Interface et expérience utilisateur

L’écran « Imports » suit un assistant en quatre étapes : **Déclaration**, **Fichier et aperçu**, **Correspondance et validation**, **Confirmation et rapport**. Il montre toujours l’acquisition, la finalité et les catégories déclarées avant le bouton de confirmation.

L’aperçu rend les cellules comme texte, sans HTML, lien actif ni formule. L’écran distingue nettement : créations, doublons exacts ignorés, revues requises, quarantaine et rejets. La confirmation exige une phrase d’intention ou une case explicite indiquant que les données sont utilisables au regard de l’acquisition ; elle ne vaut pas permission de contacter.

Le rapport liste seulement les compteurs et les numéros de ligne avec codes de motifs. Il ne réaffiche pas courriel, téléphone, contenu de cellule, coordonnées ou autres données source dans une zone non nécessaire.

## 12. Tests et critères d’acceptation

1. Le navigateur ne lit ni ne stocke le fichier ; le serveur refuse tout type autre que CSV, encodage invalide, taille ou limite dépassée.
2. Une acquisition non approuvée, contrat expiré ou catégorie non déclarée bloque l’aperçu ou la confirmation selon le cas.
3. L’aperçu et le mapping ne créent aucun prospect, contact, canal, provenance ou permission.
4. Une confirmation valide crée les éléments attendus avec provenance et permission `unknown` pour chaque canal.
5. Le même `Idempotency-Key` et même commande ne crée rien une seconde fois ; un corps différent retourne `409`.
6. Les doublons exacts sont idempotents ; les rapprochements approximatifs n’écrasent ni ne fusionnent rien.
7. Les lignes ambiguës ou non conformes apparaissent en quarantaine sans valeurs brutes dans PostgreSQL, audit, logs ou métriques.
8. Une erreur transactionnelle globale ne laisse aucun écrit CRM partiel ; les compteurs et audit restent cohérents.
9. L’accès inter-organisation est refusé par API et RLS ; les rôles sans capacité ne téléversent ni ne consultent l’aperçu.
10. Annulation, succès, échec et expiration déclenchent la suppression du fichier temporaire ; un rapport minimal reste disponible selon la politique.
11. Les tests Google phase 1/2.6 restent verts : aucune recherche ou persistance Google n’est déclenchée par import.
12. Ruff, mypy, pytest réel, Alembic, ESLint, Vitest/axe, build, verrou local et Azure sont verts.

## 13. Seize décisions validées

1. 3.1 accepte uniquement des CSV UTF-8/UTF-8 BOM ; XLSX, ZIP et tout autre format sont refusés.
2. Les limites initiales sont 10 Mio, 5 000 lignes, 50 colonnes, 4 096 caractères par cellule et aperçu de 100 lignes.
3. Un fichier appartient à une déclaration CSV associée à une acquisition approuvée et compatible ; cette acquisition reste contrôlée à chaque étape.
4. Le fichier est stocké par un port temporaire privé, sans URL publique ni contenu dans PostgreSQL, et supprimé au plus tard sous 24 heures.
5. L’aperçu, le mapping et la validation n’écrivent aucune donnée CRM ; seule la confirmation explicite le fait.
6. Le mapping est une liste blanche des neuf cibles définies ; colonnes non mappées sont ignorées, interdites ou non déclarées sont refusées.
7. `prospect_name` est obligatoire ; un contact ou canal sans prospect est rejeté.
8. Chaque canal importé reçoit provenance import et permission `unknown` ; aucune importation ne crée une autorisation de contact.
9. La confirmation utilise `Idempotency-Key`, un digest du fichier et une transaction atomique ; le rejeu identique renvoie le résultat initial.
10. La déduplication automatique est strictement exacte sur référence source ou empreinte canonique ; toute proximité passe en revue humaine.
11. Les lignes valides peuvent être créées malgré des lignes en quarantaine ; seules les erreurs globales de sécurité, acquisition ou transaction bloquent le lot entier.
12. La quarantaine conserve uniquement ligne, codes et références opaques ; la correction/reprise manuelle est reportée.
13. Les rapports JSON/CSV internes excluent toute valeur source brute et sont disponibles selon les droits de l’organisation.
14. Administrateurs et Gestionnaires écrivent les imports ; les Commerciaux lisent seulement les rapports minimisés.
15. Les routes et écrans appliquent RLS, CSRF, `no-store`, journalisation à schéma fermé, audit transactionnel et interdiction de stockage navigateur.
16. 3.1 ne se clôture qu’avec tests réels PostgreSQL/Redis, tests frontend/accessibilité, migration Alembic, verrou qualité local sans skip, documentation et Azure verts.

## 14. Décision de sortie

Les seize décisions ont été validées par le responsable produit le 26 août 2026. Le GO d’implémentation a été exécuté : migration, port de stockage privé, traitements backend, routes, interface et tests ciblés sont livrés.

Le responsable produit a prononcé la clôture avec réserve de 3.1 le 4 septembre 2026 après la recette fonctionnelle locale et un verrou qualité complet vert sur la tête Alembic `20260826_0014`. La réserve porte sur la recette multi-instance 2.6 en staging et la preuve Azure Pipelines, toutes deux obligatoires avant la préproduction mais non bloquantes pour la spécification et l’implémentation de 3.2. Aucun autre module de phase 3 n’est inclus dans 3.1.
