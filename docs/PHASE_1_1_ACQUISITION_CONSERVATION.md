# Phase 1.1 — Sources d’acquisition et règles de conservation

**Statut :** référentiel validé pour la conception de la phase 2  
**Date :** 22 juillet 2026  
**Validation produit :** 22 juillet 2026  
**Portée :** décisions structurantes à intégrer au modèle de données de la phase 2 ; aucune modification fonctionnelle du code pendant cette phase.

## 1. Objectif

Le CRM doit pouvoir agrandir durablement le portefeuille sans transformer Google Maps en base de données commerciale. Il distingue donc :

1. la découverte temporaire d’un établissement ;
2. la création d’une référence de prospect ;
3. la conservation de données internes ou autorisées ;
4. l’autorisation de contacter une personne ou une organisation.

L’existence d’un prospect dans le CRM ne constitue jamais, à elle seule, une autorisation de l’appeler, de lui envoyer un courriel ou de lui adresser un message commercial.

## 2. Sources d’acquisition autorisées

| Code | Source | Usage prévu | Données persistantes autorisées | Niveau de contrôle |
| --- | --- | --- | --- | --- |
| `google_reference` | Résultat Google sélectionné explicitement | Découverte ponctuelle | `place_id` uniquement, plus les données CRM saisies indépendamment | Strict |
| `manual` | Saisie par un utilisateur | Rencontre, appel entrant, recherche propre, connaissance commerciale | Données saisies avec provenance et auteur | Standard |
| `customer_import` | Fichier fourni par l’organisation cliente | Migration d’un portefeuille existant | Colonnes déclarées comme appartenant à l’organisation ou utilisables par elle | Élevé |
| `inbound` | Formulaire, demande de devis, inscription ou appel entrant | Acquisition directe | Données fournies, finalité, version de l’avis et preuve disponible | Élevé |
| `referral_partner` | Recommandation ou partenaire | Mise en relation | Données nécessaires, identité ou libellé de la source, conditions de la transmission | Élevé |
| `licensed_provider` | Fournisseur B2B contractuel | Acquisition de volume | Champs et usages expressément autorisés par le contrat | Très élevé |
| `authorized_public_source` | Registre ou source publique sous licence compatible | Recherche sectorielle autorisée | Uniquement les champs couverts par la licence et la finalité documentée | Très élevé |

### 2.1 Sources refusées

Le système refuse ou met en quarantaine :

- les listes dont la provenance est inconnue ;
- les fichiers acquis sans preuve de droit d’utilisation ;
- les données extraites automatiquement de Google Maps ou d’un site qui l’interdit ;
- les listes revendues sans licence décrivant la conservation, le contact et l’export ;
- les données personnelles manifestement excessives par rapport à la finalité commerciale ;
- les fichiers contenant des secrets, mots de passe, numéros d’assurance sociale ou données sensibles non nécessaires.

Une source publique n’est pas automatiquement une source librement réutilisable. Sa licence, ses conditions et la finalité doivent être vérifiées.

## 3. Règles propres à Google Maps

### 3.1 Découverte

- la recherche Google reste une action explicite de l’utilisateur ;
- les résultats sont temporaires et portent l’attribution `Google Maps` ;
- les noms, adresses, catégories, coordonnées, téléphones, sites Web, notes et autres contenus Google ne sont ni persistés, ni exportés, ni écrits dans les journaux ;
- les champs détaillés peuvent être affichés en direct avec Place Details lorsqu’un utilisateur ouvre un établissement ;
- le téléphone et le site Web Google ne préremplissent jamais un champ de contact interne.

### 3.2 Ajout au CRM

L’utilisateur pourra sélectionner un ou plusieurs résultats visibles, au maximum vingt par action, puis exécuter **Ajouter la sélection au CRM**. Pour chaque sélection, le serveur :

1. accepte le `place_id` ;
2. recherche un prospect actif de la même organisation possédant déjà cet identifiant ;
3. crée une référence si elle n’existe pas ;
4. initialise uniquement les champs internes : origine, responsable, étape, priorité et auteur ;
5. ne reçoit et n’enregistre aucun champ descriptif Google dans la commande de création ;
6. journalise le nombre de références demandées, créées et déjà existantes, sans contenu Google.

L’opération est idempotente pour `(organization_id, google_place_id)`.

### 3.3 Conservation du Place ID

Le `place_id` est la seule donnée Google conservée durablement. Une date `google_place_id_checked_at` permettra de planifier une vérification après douze mois. Un identifiant obsolète est remplacé uniquement par le résultat d’une opération de rafraîchissement autorisée et auditée.

## 4. Provenance obligatoire

### 4.1 Prospect

Tout prospect porte :

- `origin` parmi les codes autorisés ;
- `source_label`, lisible par l’organisation ;
- `acquired_at` ;
- `created_by` ou un identifiant de traitement d’import ;
- une référence vers la déclaration, le contrat ou l’événement d’acquisition lorsqu’elle existe.

### 4.2 Coordonnée de contact

Chaque téléphone, courriel, adresse postale ou site interne porte séparément :

- son type et sa valeur normalisée ;
- sa provenance ;
- le libellé précis de la source ;
- la date d’obtention ;
- l’auteur ou le traitement d’import ;
- la finalité déclarée ;
- le statut de vérification ;
- la date de dernière vérification ;
- les restrictions contractuelles éventuelles.

Une coordonnée sans provenance est rejetée par le domaine, l’API et l’import.

## 5. Autorisation de contact

La provenance d’une coordonnée et l’autorisation de l’utiliser sont deux informations distinctes.

Une autorisation est gérée par prospect et par canal :

| Champ | Valeurs ou usage |
| --- | --- |
| `channel` | `email`, `sms`, `phone`, `postal` |
| `status` | `unknown`, `allowed`, `blocked`, `withdrawn`, `expired` |
| `basis` | consentement exprès, consentement implicite documenté, relation commerciale, publication manifeste applicable, autre base validée |
| `evidence_reference` | formulaire, contrat, événement, URL ou document interne |
| `effective_at` | début de validité |
| `expires_at` | échéance lorsqu’une base est limitée dans le temps |
| `recorded_by` | utilisateur ou import ayant établi la règle |
| `reason` | justification lisible et obligatoire pour un blocage ou une levée |

Règles :

- `unknown`, `blocked`, `withdrawn` et `expired` bloquent les actions automatisées du canal ;
- une adresse publiquement visible ne produit pas automatiquement un statut `allowed` ; les conditions de pertinence, de publication et d’absence d’opposition doivent être documentées ;
- une opposition est prioritaire sur toute autorisation antérieure ;
- une levée d’opposition exige un rôle Administrateur ou Gestionnaire, une justification et un audit ;
- une campagne ne peut cibler que les contacts dont le canal est `allowed` au moment de l’envoi.

Les règles exactes de télémarketing et les listes d’exclusion devront être configurées selon le territoire ciblé avant la production.

## 6. Import client

### 6.1 Déclaration obligatoire

Avant l’aperçu d’un fichier, l’importateur renseigne :

- le propriétaire ou fournisseur du fichier ;
- la source et la date de collecte ;
- la finalité d’origine ;
- le territoire concerné ;
- la confirmation des droits de conservation et d’utilisation ;
- les restrictions d’export et de contact ;
- la date d’expiration éventuelle ;
- un commentaire ou une référence contractuelle.

### 6.2 Traitement

1. Le fichier est placé dans un stockage temporaire isolé.
2. Le serveur analyse le format sans exécuter de formule ni de macro.
3. L’utilisateur associe les colonnes à une liste blanche.
4. Les données interdites ou inconnues sont rejetées.
5. Un aperçu présente les créations, doublons, conflits et rejets.
6. Une confirmation explicite lance l’écriture transactionnelle.
7. Le fichier source et les copies de travail sont supprimés après succès ou échec.
8. Le rapport conserve uniquement les compteurs, erreurs non sensibles et identifiants internes nécessaires à l’audit.

Les valeurs importées sont considérées comme données de l’organisation, jamais comme contenu Google, seulement après validation de la déclaration de provenance.

## 7. Fournisseurs B2B et partenaires

Chaque fournisseur possède un enregistrement de gouvernance comprenant :

- nom légal et contact contractuel ;
- territoires et finalités autorisés ;
- catégories de données ;
- droits de conservation, contact, enrichissement et export ;
- durée du contrat et échéance ;
- procédure de correction, suppression et opposition ;
- restrictions de sous-traitance ;
- date de dernière revue.

Un connecteur est désactivé automatiquement lorsque le contrat est expiré ou suspendu. Les données déjà reçues suivent les obligations de restitution ou de suppression du contrat.

## 8. Déduplication et fusion

### 8.1 Correspondances exactes

- Google : unicité partielle de `(organization_id, google_place_id)` pour les prospects actifs ;
- courriel : comparaison d’une valeur normalisée au sein de l’organisation ;
- téléphone : comparaison en format international normalisé lorsque le pays est connu ;
- identifiant externe : unicité par fournisseur et organisation.

### 8.2 Correspondances probables

Le nom, l’adresse, le domaine Web ou leur combinaison produisent seulement une suggestion de doublon. Ils ne provoquent jamais de fusion automatique.

### 8.3 Fusion

- la fusion est réservée aux rôles autorisés ;
- le prospect conservé et le prospect absorbé sont explicitement choisis ;
- la provenance de chaque coordonnée est conservée ;
- les oppositions au contact sont cumulées et ne sont jamais affaiblies ;
- l’opération est auditée et réversible administrativement pendant une période à définir.

## 9. Conservation et suppression

### 9.1 Principe

La durée n’est pas déterminée uniquement par l’origine. Elle dépend de la finalité, du statut commercial, du contrat fournisseur, du consentement, du territoire et des obligations légales. Le produit impose donc une politique configurable avec une durée minimale et maximale documentée plutôt qu’une conservation illimitée.

### 9.2 Matrice

| Catégorie | Conservation proposée | Fin de conservation |
| --- | --- | --- |
| Réponse Google descriptive | Mémoire de la réponse ou de la vue uniquement | Destruction à la fin de la vue ou de la réponse |
| `place_id` | Tant que la référence de prospect a une finalité valide | Suppression avec le prospect, sauf obligation documentée |
| Prospect actif | Pendant le suivi commercial justifié | Révision périodique de la finalité |
| Prospect inactif ou non qualifié | Jusqu’à l’échéance configurable de l’organisation | Suppression ou anonymisation après revue |
| Coordonnée interne | Tant que la finalité et la base de contact restent valides | Archivage ou suppression à l’expiration ou à la demande applicable |
| Opposition au contact | Enregistrement minimal de suppression pendant la durée juridiquement nécessaire | Revue juridique avant purge |
| Fichier d’import | Durée du traitement uniquement | Suppression physique après succès ou échec |
| Rapport d’import | Compteurs et erreurs minimisées | Selon la politique d’audit |
| Preuve de consentement ou de provenance | Tant que nécessaire pour démontrer la conformité et traiter une contestation | Selon la politique légale validée |
| Audit métier | Durée configurable validée avant production | Purge contrôlée et journalisée |

### 9.3 Mécanisme

- `retention_review_at` indique la prochaine revue ;
- l’archivage retire le prospect des parcours actifs sans supprimer immédiatement les preuves nécessaires ;
- une tâche de rétention signale, puis traite, les éléments arrivés à échéance ;
- une mise en attente empêche la suppression pendant une demande d’accès, un litige ou une obligation légale ;
- la suppression physique ou l’anonymisation est journalisée sans recopier les données supprimées ;
- les sauvegardes suivent un délai de rotation documenté et ne servent pas à restaurer sélectivement des données volontairement supprimées.

Aucune durée chiffrée universelle n’est fixée dans cette phase. Les valeurs par défaut devront être validées avec le conseiller juridique et selon les provinces ou pays servis.

## 10. Export

- seules les données internes, manuelles, entrantes, importées ou issues d’un fournisseur autorisant l’export sont éligibles ;
- une liste blanche est définie par type de source ;
- aucun nom, adresse, téléphone, site Web, catégorie, note ou coordonnée provenant de Google n’est exporté ;
- le `place_id` est exclu des exports utilisateur de la V1 ;
- une opposition ou une restriction contractuelle suit la donnée exportée ou bloque l’export ;
- l’auteur, la finalité, les filtres, le volume et le schéma de colonnes sont audités ;
- les fichiers d’export sont chiffrés pendant leur courte disponibilité, puis supprimés.

## 11. Modèle minimal à préparer en phase 2

| Entité ou ajout | Responsabilité |
| --- | --- |
| `prospects.origin`, `source_label`, `acquired_at`, `acquisition_record_id` | Origine commune du prospect |
| `acquisition_records` | Déclaration ou événement justifiant l’acquisition |
| `prospect_contacts` | Coordonnées internes et provenance champ par champ |
| `contact_permissions` | Autorisation et opposition par canal |
| `consent_evidence` | Référence minimale vers les preuves et avis applicables |
| `data_providers` | Gouvernance des fournisseurs et partenaires |
| `provider_contract_rules` | Champs, territoires, usages et échéances autorisés |
| `retention_policies` | Durées configurables par catégorie et organisation |
| `retention_holds` | Suspension motivée d’une suppression |
| `import_jobs` | Déclaration, état, compteurs et audit sans conserver le fichier |

Les valeurs sensibles de preuve ne doivent pas être copiées dans le journal d’audit. L’audit conserve des identifiants techniques et des métadonnées minimales.

## 12. Critères d’acceptation futurs

- une création sans origine valide est rejetée ;
- une coordonnée sans provenance est rejetée ;
- la commande Google refuse tout champ descriptif autre que `place_id` ;
- l’ajout répété du même `place_id` est idempotent dans une organisation ;
- un import sans déclaration de droits ne peut atteindre l’étape de confirmation ;
- un contrat fournisseur expiré bloque les nouvelles acquisitions ;
- une correspondance probable ne fusionne jamais deux prospects automatiquement ;
- une opposition bloque toutes les actions du canal concerné ;
- les résultats Google ne sont présents dans aucune table, export ou trace de test ;
- les fichiers temporaires sont supprimés après succès et après échec ;
- les règles de conservation produisent un aperçu avant suppression ;
- une mise en attente empêche effectivement la purge ;
- toutes les opérations sensibles sont isolées par organisation et auditées.

## 13. Décisions validées

1. Autoriser les sept sources listées à la section 2 et refuser toute source inconnue.
2. Autoriser l’ajout groupé de références Google sélectionnées, limité à vingt `place_id` par action.
3. Conserver uniquement le `place_id` pour l’origine Google ; afficher les détails en direct.
4. Avancer l’import conforme immédiatement après le module de prospects internes afin d’accélérer la croissance du portefeuille.
5. Séparer provenance, autorisation de contact et conservation dans le modèle.
6. Bloquer par défaut les actions automatisées lorsque l’autorisation du canal est inconnue.
7. Ne fixer aucune durée universelle avant la validation juridique ; préparer des politiques configurables et des dates de revue.
8. Conserver une opposition sous forme minimale pendant la durée juridiquement nécessaire afin d’éviter une réacquisition ou un nouveau contact accidentel.

Ces huit décisions ont été validées par le responsable produit le 22 juillet 2026. Elles constituent désormais des règles de conception obligatoires pour la phase 2.

## 14. Références officielles

- Google Places API — Policies and attributions : https://developers.google.com/maps/documentation/places/web-service/policies
- Google Places API — Place IDs : https://developers.google.com/maps/documentation/places/web-service/place-id
- Commissariat à la protection de la vie privée du Canada — Principes relatifs à l’équité dans le traitement de l’information : https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/
- CRTC — FAQ sur la Loi canadienne anti-pourriel : https://www.crtc.gc.ca/eng/com500/faq500.htm
- Gouvernement du Canada — Obtenir le consentement pour envoyer des courriels : https://ised-isde.canada.ca/site/canada-anti-spam-legislation/en/getting-consent-send-email

Ce document est une spécification produit et technique. Il ne remplace pas un avis juridique adapté aux territoires, canaux de contact, contrats et catégories de personnes effectivement concernés.
