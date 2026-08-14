# Phase 2.5 — Socle prospects, conformité et conservation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.5 — Socle prospects, conformité et conservation |
| Version | 1.0 |
| Prérequis | Phase 2.4.5 clôturée avec Go, migrations à `20260813_0008 (head)` |
| Statut | Validé par le responsable produit |
| Validation produit | 14 août 2026 — validation des seize décisions de la section 10 |
| Résultat attendu | Un modèle CRM persistant, traçable et prêt pour le pipeline commercial |

Ce document définit le contrat fonctionnel et technique de l’incrément 2.5. Il prépare la valeur commerciale de
Marketteo sans encore livrer le Kanban complet, les activités, la facturation ou les connecteurs sociaux.

## 0. Découpage d’implémentation obligatoire

L’implémentation de 2.5 est volontairement découpée en cinq sous-incréments. Aucun sous-incrément ne démarre sans
validation du précédent et sa recette automatisée. Cette règle limite le risque de mélanger les migrations, les
politiques de conformité et l’interface.

| Sous-incrément | Objet principal | Dépendances | Sortie attendue |
| --- | --- | --- | --- |
| **2.5.1** | Modèle de données et migrations | 2.4.5 | Tables, contraintes, RLS, ports et audit prêts |
| **2.5.2** | Socle prospect et ajout Google | 2.5.1 | Validé avec réserves ; preuves des étapes 9 et 10 à consigner |
| **2.5.3** | Provenance, permissions et fournisseurs | 2.5.1 | Canaux, permissions, contrats et quarantaine |
| **2.5.4** | Conservation et déclarations d’import | 2.5.1, 2.5.3 | Politiques, holds, archivage logique, déclaration sans parsing |
| **2.5.5** | Interface et verrou qualité | 2.5.2, 2.5.3, 2.5.4 | Écrans, documentation, tests complets et Go/No-Go |

### 0.1 Critères de passage entre sous-incréments

- migration et `alembic check` verts sur base vide et base de test dédiée ;
- tests backend ciblés et tests de non-régression exécutés sans `skip` ;
- RLS, capacités et audit vérifiés par tests positifs et négatifs ;
- aucun changement hors périmètre introduit sans décision produit ;
- rapport d’implémentation et anomalies mis à jour avant le sous-incrément suivant.

Exception produit validée le 14 août 2026 : 2.5.1 étant un socle sans parcours frontend, sa recette utilisateur est
regroupée avec celle de 2.5.2. Les migrations, tests d’intégration et contrôles statiques de 2.5.1 restent exécutés
avant et pendant 2.5.2 ; seul le verdict fonctionnel humain est différé.

Les spécifications proposées de 2.5.2 sont consignées dans
[`PHASE_2_5_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_5_2_SPECIFICATIONS_DETAILLEES.md).

Le rapport d’implémentation 2.5.2 est consigné dans
[`PHASE_2_5_2_RAPPORT_IMPLEMENTATION.md`](PHASE_2_5_2_RAPPORT_IMPLEMENTATION.md).

Le Kanban, les activités, l’import CSV effectif, les connecteurs externes et la facturation restent hors de 2.5 et
seront planifiés dans les incréments CRM V1 suivants.

## 1. Objectifs

2.5 doit permettre de :

- créer un établissement prospect manuellement ou depuis une référence Google explicitement sélectionnée ;
- distinguer l’établissement, les personnes de contact et leurs canaux ;
- conserver la provenance de chaque donnée persistante ;
- représenter séparément la permission de contact par canal ;
- déclarer et contrôler les acquisitions/imports sans conserver un fichier brut inutilement ;
- appliquer une politique de conservation configurable, avec revue et mise en attente ;
- fournir les contrats d’application nécessaires au pipeline et à l’import CSV de la phase suivante.

## 2. Périmètre

### Inclus

- établissements/prospects actifs, archivage logique et déduplication ;
- contacts, canaux courriel/téléphone et permissions ;
- registre des acquisitions, fournisseurs et preuves de provenance ;
- ajout explicite de références Google (`place_id` uniquement) ;
- déclaration d’import et lignes en quarantaine, sans traitement de fichier dans cet incrément ;
- politiques de conservation, dates de revue et mises en attente ;
- capacités, RLS, audit transactionnel et API REST ;
- tests PostgreSQL réels, non-régression Google, frontend et documentation.

### Exclus

- Kanban complet, activités, tâches, opportunités et rappels ;
- import CSV effectif, Facebook, LinkedIn et connecteurs externes ;
- enrichissement Google persistant (nom, adresse, téléphone, site, horaires, avis) ;
- export des données Google ou des fichiers sources ;
- facturation, plans et quotas commerciaux ;
- décision juridique de durées universelles de conservation.

## 3. Invariants non négociables

1. Un établissement et une personne de contact sont deux entités distinctes.
2. Toute donnée persistante possède une provenance, une finalité et un créateur ou fournisseur identifiable.
3. Une provenance ne constitue jamais une permission de contacter.
4. Une permission est portée par un canal et vaut `unknown` en l’absence de preuve recevable.
5. `google_maps` ne peut pas être la provenance d’un téléphone, d’un site Web ou d’une adresse persistante.
6. Depuis Google, seul le `place_id` est conservé durablement ; les détails sont relus en direct.
7. Un même `place_id` actif ne peut apparaître deux fois dans une organisation.
8. Une coordonnée ne peut appartenir simultanément à un établissement et à une personne.
9. Les données d’une organisation restent isolées par RLS et capacités serveur.
10. Toute mutation métier et son audit sont atomiques.
11. Une acquisition sans source déclarée, finalité ou droit d’utilisation est rejetée ou placée en quarantaine.
12. Un contrat fournisseur expiré bloque toute nouvelle acquisition concernée.
13. Une mise en attente de conservation interdit la purge automatique.
14. Les fichiers importés ne sont pas conservés après la fenêtre technique prévue et ne sont pas exportables.
15. Les réponses de données sensibles portent `Cache-Control: no-store` et aucune donnée CRM n’est stockée dans le navigateur.
16. Les limites Google restent un Text Search par action, 20 résultats maximum, sans pagination ni champs de contact.

## 4. Modèle de données cible

Les tables sont locataires et doivent être protégées par RLS :

- `prospects` : établissement suivi, `organization_id`, `google_place_id` nullable, alias interne, origine, propriétaire,
  étape initiale, priorité, dates d’acquisition/revue, version et archivage ;
- `contacts` : personne rattachée à un prospect, nom affiché, rôle, provenance et archivage ;
- `contact_channels` : type (`email`, `phone` ou futur canal), valeur normalisée, cible établissement ou contact,
  provenance, finalité, dates de vérification et archivage ;
- `contact_permissions` : statut (`unknown`, `allowed`, `denied`), base légale/contractuelle, preuve, dates d’effet,
  d’expiration et motif ;
- `acquisition_records` : source, fournisseur, finalité, territoire, attestation de droits, identifiant externe,
  horodatage, utilisateur et statut ;
- `provenance_records` : référence par donnée, type de donnée, source, preuve, obtenu le, vérifié le et auteur ;
- `source_providers` : fournisseur autorisé, licence/conditions, territoires, champs autorisés, statut et expiration ;
- `retention_policies` : organisation, type de donnée, durée ou date de revue, action, version et approbation ;
- `retention_holds` : donnée ou acquisition concernée, motif, créé par, dates et état ;
- `import_declarations` : déclaration de fichier/source, empreinte, colonnes annoncées, finalité, statut et suppression prévue ;
- `import_quarantine_rows` : erreurs et données minimales nécessaires à la correction, sans exposition aux rôles non autorisés.

Contraintes obligatoires : unicité partielle `(organization_id, google_place_id)` sur prospects actifs, FK strictes,
contrôle d’un seul propriétaire de canal, index sur organisation/source/revue et colonnes normalisées non nulles.

## 5. Règles métier

### 5.1 Création d’un prospect

- création manuelle : alias et origine sont obligatoires ;
- création Google : l’utilisateur sélectionne explicitement zéro à vingt résultats de l’action en cours ; le serveur
  accepte les `place_id` connus et ne reçoit aucune donnée descriptive comme source de vérité ;
- création idempotente : un rejeu retourne le prospect existant sans doublon ni nouvel audit ;
- l’étape initiale est `new`, sans déduire une activité commerciale.

### 5.2 Contacts et canaux

- un prospect peut avoir zéro à plusieurs contacts ;
- un canal est rattaché à un seul prospect ou contact ;
- une valeur sans provenance est rejetée ;
- `unknown` interdit l’envoi automatisé mais n’empêche pas la correction ou la qualification manuelle ;
- `denied` bloque toute action de contact et prévaut sur les autres états.

### 5.3 Acquisition et fournisseurs

- une source doit être dans la liste blanche ou faire l’objet d’une quarantaine ;
- fournisseur, licence, finalité et territoire sont contrôlés avant écriture ;
- l’expiration d’un contrat refuse les nouvelles acquisitions mais ne supprime pas silencieusement l’historique ;
- toute opposition est enregistrée et propagée aux canaux concernés.

### 5.4 Conservation

- chaque type de donnée possède une politique versionnée ou une date de revue ;
- aucune purge irréversible n’est activée par défaut en 2.5 ;
- un `retention_hold` suspend la décision de purge ;
- l’archivage logique précède toute future suppression et reste audité.

## 6. API applicative proposée

Routes locataires, toutes soumises à authentification, CSRF, capacité et RLS :

- `POST /api/prospects` — création manuelle ;
- `POST /api/prospects/from-google` — ajout explicite de 1 à 20 `place_id` ;
- `GET /api/prospects` / `GET /api/prospects/{id}` — liste et détail minimal ;
- `PATCH /api/prospects/{id}` — alias, propriétaire, priorité et archivage logique ;
- `POST /api/prospects/{id}/contacts` — création d’un contact ;
- `POST /api/contact-channels` / `PATCH /api/contact-channels/{id}` — canal avec provenance obligatoire ;
- `GET/PATCH /api/contact-channels/{id}/permission` — consultation et décision de permission ;
- `POST /api/acquisitions/declarations` — déclaration d’acquisition/import ;
- `GET /api/sources/providers` — fournisseurs autorisés visibles selon capacité ;
- `GET /api/retention/policies` / `POST /api/retention/holds` — consultation et mise en attente ;
- `POST /api/imports/declarations` — déclaration uniquement, sans upload ni parsing en 2.5.

Les sorties sont des schémas explicites, paginés par curseur opaque, et ne renvoient jamais de secret, fichier brut,
preuve sensible ou champ Google interdit.

## 7. Interface attendue

Sans refonte visuelle majeure :

- nouvelle entrée « Prospects » dans le shell, protégée par capacité ;
- liste avec filtres serveur, état vide, archivés et provenance ;
- action « Ajouter au CRM » sur les résultats Google, individuelle ou groupée jusqu’à 20 ;
- fiche établissement avec sections Contacts, Canaux et Conformité ;
- enrichissement manuel de la fiche établissement avec des données CRM propres à l’organisation : nom interne,
  secteur d’activité, segment, taille, adresse indépendante, étiquettes, propriétaire et priorité ;
- chaque donnée issue d’une source externe doit conserver sa provenance réelle ; un contenu observé dans Google ne
  peut pas être requalifié artificiellement en saisie manuelle pour être persisté ;
- formulaires indiquant explicitement provenance, permission et finalité ;
- écran de déclaration d’import affichant « traitement de fichier disponible dans un prochain incrément » ;
- libellés bilingues préparés, sans stockage de données dans `localStorage`/`sessionStorage`.

## 8. Sécurité, audit et observabilité

- capacités distinctes : `prospects:read`, `prospects:create`, `prospects:update`, `contacts:write`, `compliance:read`,
  `compliance:update` ;
- contrôles serveur indépendants de l’interface et vérification RLS sur deux organisations ;
- audit des créations, modifications, décisions de permission, déclarations, quarantaine et holds ;
- métadonnées d’audit filtrées : aucune valeur de canal en clair, clé Google, mot de passe ou fichier brut ;
- journaux structurés avec identifiant de corrélation, sans données personnelles inutiles ;
- métriques sur rejets de provenance, contrats expirés, doublons et mises en quarantaine.

## 9. Stratégie de tests et critères de sortie

Tests obligatoires :

- migrations vierges, RLS, privilèges et contraintes d’unicité ;
- création manuelle, ajout Google idempotent et limite 20 ;
- rejet source inconnue, coordonnée sans provenance, provenance Google interdite ;
- permission `unknown` par défaut, refus `denied`, contrat expiré et hold ;
- séparation établissement/contact/canal et isolation inter-organisation ;
- absence de fichier traité ou conservé par la déclaration d’import ;
- audit atomique, `no-store`, absence de stockage navigateur ;
- React/Vitest, axe, Ruff, mypy, pytest, Alembic, ESLint et build verts ;
- non-régression des règles Google de phase 1 et 2.4.

2.5 est terminé si les migrations, API, UI minimale, preuves de conformité, documentation et contrôles qualité sont
verts, sans test ignoré ni écart bloquant. L’import CSV effectif et le Kanban deviennent les sujets des incréments
suivants.

## 10. Seize décisions proposées à validation

1. 2.5 livre le socle de données et de conformité, pas le Kanban complet.
2. Les établissements, contacts et canaux sont des entités distinctes.
3. Toute donnée persistante exige une provenance et une finalité.
4. La provenance et la permission de contact restent deux concepts indépendants.
5. Une permission absente vaut `unknown` et interdit l’envoi automatisé.
6. Une permission `denied` prévaut sur toute autre permission.
7. Google ne fournit durablement que `place_id` ; aucun téléphone, site, adresse ou libellé Google n’est copié.
8. L’ajout Google est explicite, idempotent et limité à vingt références par action.
9. Les sources et fournisseurs sont contrôlés par liste blanche et contrat en vigueur.
10. Une acquisition non conforme est rejetée ou placée en quarantaine, jamais silencieusement acceptée.
11. Les imports sont déclarés en 2.5 mais aucun fichier n’est parsé ou conservé au-delà de la fenêtre technique.
12. Les politiques de conservation sont versionnées et révisables par organisation.
13. Les holds bloquent toute purge future et sont audités.
14. Aucune purge irréversible n’est activée par défaut avant validation juridique et opérationnelle.
15. Les API sont paginées côté serveur, protégées par capacités, RLS, CSRF et `no-store`.
16. Le Go de 2.5 exige migrations, tests réels, contrôles statiques, documentation et aucune régression Google.

## 11. Décision de sortie

- **Go implémentation 2.5** : les seize décisions sont validées et les écarts sont tracés ;
- **No-Go** : une décision ou un invariant reste en attente, avec responsable et action suivante.
