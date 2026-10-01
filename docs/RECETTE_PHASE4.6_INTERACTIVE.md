# Kit de recette fonctionnelle interactive — Phase 4.6

Ce kit complète les contrôles automatisés déjà consignés dans [RECETTE_PHASE4.6.md](RECETTE_PHASE4.6.md). Il sert à jouer les parcours avec des comptes et des données fictifs, puis à reporter chaque preuve dans [RECETTE_PHASE4.6_REGISTRE.csv](RECETTE_PHASE4.6_REGISTRE.csv).

## Fichiers préparés

| Fichier | Utilisation |
|---|---|
| [Test-Phase4_6InteractivePreflight.ps1](../scripts/Test-Phase4_6InteractivePreflight.ps1) | Vérifie l'API, le client et les deux fixtures avant toute action métier. |
| [P4_6_IMPORT_VALID.csv](fixtures/phase4_6/P4_6_IMPORT_VALID.csv) | Deux prospects synthétiques admissibles. Importer deux fois pour contrôler les doublons exacts. |
| [P4_6_IMPORT_QUARANTAINE.csv](fixtures/phase4_6/P4_6_IMPORT_QUARANTAINE.csv) | Deux lignes à mettre en quarantaine : courriel invalide et nom d'établissement absent. |

Les fixtures sont en UTF-8, ne contiennent ni donnée personnelle, ni secret, ni référence Meta réelle.

## Prévol

Dans PowerShell, à la racine du dépôt :

```powershell
.\scripts\Test-Phase4_6InteractivePreflight.ps1
```

Le résultat doit indiquer `ok`, `ready`, `postgresql=ok`, `redis=ok`, un client HTTP 200 et deux fixtures de deux lignes. En cas d'échec, ne créez pas de données de recette.

## Comptes et organisations

Créez deux organisations jetables avec un préfixe unique, par exemple `MKT-P46-A-20260925` et `MKT-P46-B-20260925`. Utilisez le script existant de provisionnement ; il demande le mot de passe dans une fenêtre sécurisée et ne le conserve pas.

```powershell
.\scripts\Test-ProvisioningLocal.ps1 `
  -AdministratorEmail 'administrateur-plateforme@example.test' `
  -OrganizationName 'MKT-P46-A-20260925' `
  -InviteeEmail 'p46.a.admin.auteur@example.test' `
  -Locale fr-CA `
  -Timezone 'America/Toronto'

.\scripts\Test-ProvisioningLocal.ps1 `
  -AdministratorEmail 'administrateur-plateforme@example.test' `
  -OrganizationName 'MKT-P46-B-20260925' `
  -InviteeEmail 'p46.b.admin@example.test' `
  -Locale en-CA `
  -Timezone 'UTC'
```

Acceptez les invitations dans Mailpit, puis connectez-vous à chaque compte et créez les rôles suivants depuis **Organisation → Membres** :

| Organisation | Comptes de test |
|---|---|
| ORG-A | `A-ADMIN-AUTEUR`, `A-ADMIN-REVISEUR`, `A-MANAGER`, `A-SALES-1`, `A-SALES-2` |
| ORG-B | `B-ADMIN`, `B-SALES` |

L'adresse réelle de l'opérateur ne doit pas apparaître dans le registre. Remplacez uniquement les adresses `@example.test` par d'autres adresses de test si Mailpit l'exige.

## Exécution guidée

| Étape | Action interactive | Preuve à saisir dans le registre |
|---|---|---|
| E2E-01 | Se connecter comme `A-ADMIN-AUTEUR`, consulter Dashboard, basculer vers ORG-B puis revenir à ORG-A. | Organisations actives, compteurs avant/après et absence de données ORG-A dans ORG-B. **PASS — vues française et anglaise contrôlées le 2026-09-26 ; organisation active visible et état vide cohérent.** |
| E2E-02 | Créer `P4-ALPHA`, lui affecter `A-SALES-1`, le déplacer dans Pipeline, ajouter activité et tâche, créer puis gagner une opportunité CAD. | Identifiants fictifs, chronologie, étape gagnée et compteur Dashboard. **PASS — exécuté le 2026-09-27.** |
| E2E-03 | Créer une acquisition approuvée, importer `P4_6_IMPORT_VALID.csv`, puis l'importer de nouveau. Importer ensuite `P4_6_IMPORT_QUARANTAINE.csv`. | **PASS —** deux créations initiales, deux doublons exacts au rejeu et deux lignes en quarantaine rapprochés le 30 septembre 2026. |
| E2E-04 | Demander un export des données de E2E-02/E2E-03, attendre le worker, télécharger et ouvrir le CSV localement. | État terminal, nombre de lignes, en-têtes en liste blanche, accès refusé depuis ORG-B. |
| E2E-05 | Dans l'environnement WSL jetable, interrompre un worker pendant cet export, attendre l'expiration du bail puis démarrer deux workers. | Tentatives, un seul artefact publié, ancien jeton refusé et absence de fichier provisoire. |
| E2E-06 | Avec le faux fournisseur Google, lancer une recherche autorisée, consulter quota courant, rapport personnel puis organisationnel. | Réservation, tentative, résultat, quotas par portée et agrégat. |
| E2E-07 | Atteindre la limite synthétique, puis simuler l'indisponibilité du registre durable et de Redis dans la composition de test. | **PASS —** `429 google_quota_exceeded`, `503 usage_tracking_unavailable`, `503 authentication_unavailable`, puis Redis et PostgreSQL sains, API en mode `live` et page Usage rétablie le 30 septembre 2026. |
| E2E-08 | Créer fournisseur, acquisition et contrat Meta fictifs ; soumettre, refuser l'auto-approbation, faire approuver par `A-ADMIN-REVISEUR`, activer le binding et envoyer le webhook simulé signé. | **PASS —** séparation auteur/réviseur observée, webhook HTTP 200, une ingestion et un job `succeeded`, un prospect importé, deux canaux et deux permissions `allowed`. Voir la fiche E2E-08 dans [RECETTE_PHASE4.6.md](RECETTE_PHASE4.6.md). |
| E2E-09 | Rejouer dix fois ce webhook ; interrompre le worker ; désactiver le binding ou révoquer le fournisseur avant reprise ; tenter un nouvel envoi. | **PASS —** 6 tests passés dans l'infrastructure PostgreSQL isolée, rejeu durable contrôlé, révocation et refus ultérieur validés. Voir la fiche E2E-09 dans [RECETTE_PHASE4.6.md](RECETTE_PHASE4.6.md). |
| E2E-10 | Avec `A-SALES-1`, tenter des lectures et mutations sur une ressource de `A-SALES-2` puis de ORG-B ; relire en admin. | **PASS —** 4 tests RLS passés : contexte absent, lecture croisée, mutation inter organisation et réutilisation de connexion validés. Voir la fiche E2E-10 dans [RECETTE_PHASE4.6.md](RECETTE_PHASE4.6.md). |
| E2E-11 | Parcourir Dashboard, Usage, Imports, Exports, Fournisseurs, Pipeline, Opportunités et Tâches en français puis anglais ; refaire au clavier et à 200 %. | **PASS —** quatre passages manuels validés le 30 septembre 2026 : langues, clavier et focus, petit écran et zoom à 200 %, état vide et erreur réversible. |
| E2E-12 | **PASS —** 11 contrôles de rétention verts, 2 candidats synthétiques archivés par API après confirmation, compteur final à 0. | Versions mises à jour, audit conservé et aucun contact ou canal actif rattaché aux candidats. |

## Fiche de test détaillée — E2E-02

### Objectif et périmètre

Créer un prospect CRM synthétique dans `ORG-A`, le rattacher à `A-SALES-1`, le faire avancer d'une étape dans le
pipeline, puis lui ajouter une activité interne, une tâche ouverte et une opportunité CAD menée jusqu'à l'étape
`Gagnée`. Le scénario ne crée aucun contact, canal de communication ou envoi externe.

| Élément | Valeur de recette |
|---|---|
| Organisation | `ORG-A` — locale `fr-CA`, fuseau `America/Toronto` |
| Opérateur | `A-ADMIN-AUTEUR` |
| Prospect | `P4-ALPHA-20260926` (suffixer avec l'heure si le nom existe déjà) |
| Profil facultatif | Secteur `Services professionnels`, ville `Montréal`, priorité `3/5`, étiquettes `P4.6`, `E2E-02` |
| Responsable prospect | `A-SALES-1` — conserver son `membership_id` technique dans les notes privées uniquement |
| Activité | Note interne, sens `Interne`, résumé `Qualification initiale P4-ALPHA`, détail `Premier suivi commercial déclaré pour E2E-02.` |
| Tâche | `Rappeler P4-ALPHA`, priorité `Haute`, échéance dans la journée si possible, rappel 30 minutes avant |
| Opportunité | `P4-ALPHA — Offre pilote`, `12 500,00 CAD`, probabilité initiale `50 %`, échéance `2026-10-15`, responsable `A-SALES-1` |

Le formulaire de profil CRM n'expose pas encore de sélecteur de responsable prospect. L'affectation de `owner_id` doit
donc être préparée par le jeu de données ou effectuée via la session authentifiée sur `PATCH /api/prospects/{id}`
avec la version courante, `owner_id`, `purpose=commercial_follow_up` et `territory=CA-QC`. La preuve doit seulement
conserver le rôle, l'organisation et le résultat ; elle ne doit pas contenir de cookie, jeton ou adresse réelle.

### Préconditions

1. Le prévol Phase 4.6 est `ready` et l'application est ouverte sur `ORG-A`.
2. `A-SALES-1` est actif et son identifiant de membership est connu par l'opérateur sans être copié dans la preuve publique.
3. La recherche Prospects ne retourne aucun `P4-ALPHA-20260926` ; les compteurs Dashboard sont relevés avant l'essai.
4. L'opérateur possède les capacités `prospects:create`, `prospects:update`, `prospects:read`, `pipeline:move`,
   `activities:create`, `activities:read`, `tasks:create`, `tasks:read`, `opportunities:create`, `opportunities:read`,
   `opportunities:update` et `opportunities:close`.

### Déroulé contrôlé

| Étape | Action | Résultat attendu et preuve |
|---|---|---|
| 1 | Ouvrir **Prospects → Ajouter un prospect**, saisir `P4-ALPHA-20260926`, créer puis ouvrir sa fiche. | Réponse de création `201`, un UUID fictif, étape `new`, version initiale et fiche accessible. Capturer uniquement la fiche assainie. |
| 2 | Affecter le prospect à `A-SALES-1` par le pré-seed ou le PATCH prévu, puis relire la fiche. | `owner_id` correspond à `A-SALES-1`, version incrémentée, aucune autre propriété modifiée. Noter l'identifiant du prospect et la version, jamais le jeton. |
| 3 | Ouvrir **Pipeline**, filtrer `P4-ALPHA-20260926`, déplacer `Nouveau → Qualification`. | Une transition `new → qualifying`, nouvelle version, carte présente dans la colonne `Qualification`, aucun doublon après actualisation. |
| 4 | Dans la fiche, ajouter l'activité **Note interne** avec le résumé et le détail définis. | Toast de succès, une entrée active dans la chronologie, horodatage dans le fuseau de `ORG-A`, aucune action réseau externe. |
| 5 | Créer la tâche avec son échéance et sa priorité, puis relire la chronologie. | Tâche `open`, responsable attendu, badge **Prochaine action** si elle est la plus proche, événement `Tâche créée` dans la chronologie. |
| 6 | Créer l'opportunité avec les valeurs CAD indiquées et sélectionner `A-SALES-1` comme responsable. | Opportunité `Découverte`, montant et devise séparés, probabilité `50 %`, agrégat CAD cohérent, événement `Opportunité créée`. |
| 7 | Faire progresser l'opportunité un cran à la fois : `Découverte → Qualification → Proposition → Négociation`. | Chaque transition est acceptée avec la version courante, ajoute un événement unique et ne modifie pas le montant. |
| 8 | Depuis `Négociation`, utiliser **Gagnée**, puis actualiser la fiche et le Dashboard. | Étape `Gagnée`, probabilité `100 %`, date de clôture présente, un seul événement de clôture, compteur gagné et ventilation CAD rapprochables. |

### Rapprochement à consigner

Consigner dans le registre : `prospect_id`, `activity_id`, `task_id`, `opportunity_id`, versions avant/après, étape
finale du prospect, étape finale et montant de l'opportunité, statut de la tâche, et compteurs Dashboard avant/après.
Le nombre attendu est de un prospect, une transition de pipeline, une activité active, une tâche ouverte, une
opportunité, trois transitions ouvertes et une clôture gagnée. Une actualisation ou une double soumission ne doit
produire aucun doublon.

### Critère de réussite et nettoyage

E2E-02 est `PASS` si toutes les étapes 1 à 8 sont visibles et rapprochées, si les versions restent cohérentes, si
aucun contact ou canal n'est créé et si aucune requête externe n'est émise. En cas de répétition, utiliser un nouveau
suffixe d'alias. Ne pas purger cette donnée avant E2E-12 ; conserver ses identifiants dans le registre pour E2E-04,
E2E-06 et les contrôles Dashboard.

### Résultat observé — exécution du 2026-09-27

| Élément | Résultat constaté |
|---|---|
| Prospect | `P4-ALPHA-2`, identifiant `c5aa96eb-0886-4457-aa6d-ed054ed9f0fb`, visible dans la colonne `Qualification`. |
| Activité | Note interne `Une opportunité en cours`, détail interne enregistré dans la chronologie. |
| Tâche | `TASK-001`, statut ouvert, priorité normale, affichée comme **Prochaine action**. |
| Opportunité | `OPP-E2E`, identifiant `7353e865-9e8a-458d-ad88-77ea44365500`, `10 000 CAD`, échéance `2026-10-18`. |
| Progression | `Découverte → Qualification → Proposition → Négociation → Gagnée`. Version `5` à Négociation puis version `6` à Gagnée. |
| Rapprochement final | Probabilité `100 %`, valeur pondérée `10 000 CAD`, clôture enregistrée le `2026-09-27T08:46:09Z`, sans doublon. |
| Preuves | Captures utilisateur E2E-02 et réponses API fournies pour l'opportunité avant/après clôture. |

Verdict du parcours : **PASS**.

## Fiche de test détaillée — E2E-03

### Objectif et jeu de données

Contrôler le flux complet d'import CSV dans `ORG-A` : provenance approuvée, déclaration, téléversement temporaire,
mapping, validation, confirmation, rejeu idempotent, quarantaine et historique. Les fichiers sont synthétiques et
restent dans le dépôt ; aucun fichier réel ne doit être utilisé.

| Référence | Fichier | Lignes de données | Résultat attendu |
|---|---|---:|---|
| `CSV-VALID-01` | [P4_6_IMPORT_VALID.csv](fixtures/phase4_6/P4_6_IMPORT_VALID.csv) | 2 et 3 | Deux prospects créés au premier import. |
| `CSV-VALID-REPLAY` | Même fichier, nouvelle déclaration | 2 et 3 | Zéro création, deux doublons exacts. |
| `CSV-QUAR-01` | [P4_6_IMPORT_QUARANTAINE.csv](fixtures/phase4_6/P4_6_IMPORT_QUARANTAINE.csv) | 2 et 3 | Zéro création, deux lignes en quarantaine. |

Mapping à appliquer pour les deux fichiers : `Entreprise → business_name`, `Identifiant → business_identifier`,
`Adresse → business_address`, `Contact → contact_name`, `Fonction → contact_role`, `Courriel → email`,
`Téléphone → phone`, `LinkedIn → linkedin_profile`, `Facebook → facebook_profile`.

### Préconditions

1. Le prévol Phase 4.6 est `ready`, l'organisation active est `ORG-A` et l'acteur est `A-ADMIN-AUTEUR`.
2. Dans **Acquisition → Fournisseurs**, créer le fournisseur synthétique `P4.6 CSV Simulé`, type `CSV`, puis le
   passer à `Actif` avec référence contractuelle `P4.6-CSV-CONTRACT`, territoire `CA-QC`, finalité `Suivi
   commercial`, `valid_from` au plus tard à la date d'exécution, catégories `Identité établissement`, `Identité
   personne`, `Courriel`, `Téléphone`, `Profil social` et attestation des droits.
3. Dans l'onglet **Acquisitions**, déclarer `P4.6-CSV-E2E-03-20260927`, type `CSV`, territoire `CA-QC`, finalité
   `Suivi commercial`, date d'obtention du jour et volume estimé `2`. Sélectionner explicitement les cinq catégories
   `Identité établissement`, `Identité personne`, `Courriel`, `Téléphone` et `Profil social` ; la case
   `Identité établissement` seule est insuffisante pour ce mapping. L'état attendu est `Approuvée`. Si la règle
   locale place l'acquisition en `En attente de revue`, faire approuver par `A-ADMIN-REVISEUR` et relever la décision.
4. Vérifier qu'aucun prospect portant `QA-P46-ALPHA`, `QA-P46-BETA`, `QA-P46-INVALID-EMAIL` ou
   `QA-P46-MISSING-NAME` n'existe déjà dans `ORG-A`. Les deux premières références sont créées par ce test ; les deux
   dernières ne doivent jamais devenir des prospects.

### Déroulé contrôlé

| Étape | Action | Résultat attendu et preuve |
|---|---|---|
| 1 | Dans **Conservation et import**, créer la déclaration `CSV-VALID-01`, schéma `prospect_contacts_v1`, tous les champs du mapping et les cinq catégories de données (`business_identity`, `person_identity`, `email`, `phone`, `social_profile`). | Déclaration créée en état `declared` avec un identifiant technique. Aucun prospect créé avant confirmation. Une catégorie manquante produit `category_not_acquired` et doit être corrigée avant de poursuivre. |
| 2 | Téléverser `P4_6_IMPORT_VALID.csv`, afficher l'aperçu et enregistrer le mapping ci-dessus. | Session `uploaded` puis `mapped`, deux lignes visibles dans l'aperçu, encodage UTF-8 accepté et aucune valeur transformée de façon inattendue. |
| 3 | Valider le fichier puis confirmer l'import. | Validation : `row_count=2`, `ready_count=2`, `duplicate_count=0`, `review_count=0`, `quarantined_count=0`. Confirmation : `created_count=2`. Le message indique la suppression du fichier temporaire. |
| 4 | Ouvrir **Prospects** et **Historique des imports**. | `QA-P46-ALPHA` et `QA-P46-BETA` existent dans `ORG-A`, chacun avec une provenance CSV ; la session et le lot sont `confirmed`. L'historique ne montre pas le contenu CSV brut. |
| 5 | Créer une nouvelle déclaration `CSV-VALID-REPLAY` liée à la même acquisition, téléverser exactement le même fichier et réappliquer le mapping. | Une nouvelle session est utilisée ; il n'est pas permis de réutiliser la session confirmée de l'étape 3. |
| 6 | Valider puis confirmer le rejeu `CSV-VALID-REPLAY`. | Validation et rapport : `created_count=0`, `duplicate_count=2`, `review_count=0`, `quarantined_count=0`. Les deux prospects initiaux restent uniques et inchangés. |
| 7 | Créer la déclaration `CSV-QUAR-01`, téléverser `P4_6_IMPORT_QUARANTAINE.csv`, puis appliquer le même mapping. | Aperçu de deux lignes ; aucune ligne n'est créée avant validation et confirmation. |
| 8 | Valider puis confirmer `CSV-QUAR-01`, ouvrir le rapport et l'historique. | Rapport : `created_count=0`, `duplicate_count=0`, `review_count=0`, `quarantined_count=2`. Ligne 2 : `email_invalid`. Ligne 3 : `business_name_missing`. Seuls les numéros de ligne et références opaques sont affichés. |
| 9 | Relire l'historique et contrôler le stockage temporaire selon le moyen de preuve local autorisé. | Trois lots confirmés, trois sessions confirmées, aucun fichier CSV brut conservé, aucun prospect issu des lignes invalides et aucune seconde création des lignes valides. |

### Rapprochement et critères de réussite

Consigner les identifiants de l'acquisition, des trois déclarations, des sessions et des trois lots, ainsi que les
compteurs de chaque rapport. Les références opaques de quarantaine peuvent être conservées ; les valeurs source
invalides ne doivent pas être recopiées dans le registre. Le rapprochement final attendu est :

| Contrôle | Attendu |
|---|---:|
| Prospects créés par `CSV-VALID-01` | 2 |
| Prospects créés par `CSV-VALID-REPLAY` | 0 |
| Doublons exacts au rejeu | 2 |
| Prospects créés par `CSV-QUAR-01` | 0 |
| Lignes en quarantaine | 2 |
| Lignes `review_required` | 0 |
| Fichiers CSV bruts dans l'historique ou l'audit | 0 |

E2E-03 est `PASS` uniquement si les compteurs, les motifs de quarantaine, la déduplication et la suppression du fichier
temporaire sont tous rapprochés. Ne pas purger les deux prospects valides ni les rapports avant E2E-04 et E2E-12.

### Avancement constaté le 2026-09-27

| Élément | Résultat observé |
|---|---|
| Acquisition | `P4.6-CSV-E2E-03-20260927-2`, identifiant `cc0b81c9-c9fd-4063-878d-e1c2db61e41a`, approuvée en version `2`. |
| Contrat de données | Territoire `CA-QC`, finalité `commercial_follow_up` et cinq catégories acquises : `business_identity`, `person_identity`, `email`, `phone`, `social_profile`. |
| Déclaration courante | `CSV-VALID-01-R4`, format `csv`, volume estimé `20`, état `declared`. |
| Incident précédent | Les déclarations placées en quarantaine avec `category_not_acquired` sont conservées comme preuves d'audit. La nouvelle acquisition corrige le contrat de catégories. |
| Verdict intermédiaire | Préparation conforme. Le scénario reste `NOT RUN` jusqu'à la validation et la confirmation des imports valide, rejoué et mis en quarantaine. |

Prochaine action : après remplacement de `CSV-VALID-01-R4` par une déclaration complète, téléverser
[P4_6_IMPORT_VALID.csv](fixtures/phase4_6/P4_6_IMPORT_VALID.csv), appliquer les neuf correspondances, puis relever
les cinq compteurs de validation. Le volume `20` est déclaratif ; le contrôle attendu porte sur les deux lignes
réellement lues dans la fixture.

### Incident de mapping constaté le 2026-09-27

Le bouton **Enregistrer le mapping** a renvoyé `422 validation_failed` sur `PATCH /api/csv-imports/{id}/mapping`.
La cause était un décalage d'interface : le formulaire de déclaration ne proposait que six champs alors que le
mapping autorisait les neuf champs du schéma `prospect_contacts_v1`. Les colonnes `Identifiant`, `Fonction` et
`Facebook` pouvaient donc être sélectionnées dans l'aperçu sans avoir été déclarées.

La correction aligne maintenant la déclaration et le mapping sur les neuf champs, et l'API restitue le motif métier
précis en cas de mapping non déclaré. Les métadonnées d'une déclaration existante restent immuables : pour poursuivre
E2E-03, annuler `CSV-VALID-01-R4`, créer `CSV-VALID-01-R5` avec les neuf champs et les cinq catégories, puis
téléverser à nouveau la fixture valide. Le test ne doit être marqué `PASS` qu'après les compteurs attendus.

### Incident historique des imports constaté le 2026-09-27

La page **Historique des imports** renvoyait `500` et affichait « La requête a échoué ». La trace PostgreSQL
identifiait `AmbiguousParameterError` sur les filtres optionnels `status`, `declaration_id` et `author_id` lorsque leur
valeur était nulle. Les requêtes sessions et lots ont été corrigées avec des casts SQL explicites (`text`, `uuid`,
`timestamptz` et curseur UUID). Un contrôle réel avec les filtres de la page retourne maintenant `200`.

La session de `CSV-VALID-01-R5` observée est `validated` (`row_count=2`, `ready_count=2`, `confirmed_at=null`).
Elle doit être confirmée avant d'apparaître dans **Lots confirmés** ; son apparition dans **Sessions** est attendue dès
que la page historique est rechargée.

La trace indiquait également un filtre `created_to=2026-09-26T12:35Z`, antérieur à la session créée le 27 septembre.
Pour la retrouver, effacer les dates ou choisir une date de fin au 28 septembre (la borne haute est exclusive).

### Résultat du premier import valide constaté le 2026-09-27

Le téléversement de `P4_6_IMPORT_VALID.csv` avec `CSV-VALID-01-R5` a été validé puis confirmé. Le lot confirmé est
`ee158e94-336f-4ab2-819f-bb1f7ce39ec9`, lié à la session `1da27731-e5b7-4028-af7e-b887435cb5aa` et à la déclaration
`26da0bea-dd91-4871-b91d-458e9ea37bcd`.

| Compteur | Observé |
|---|---:|
| Prospects créés | 2 |
| Doublons exacts | 0 |
| Lignes à revoir | 0 |
| Lignes en quarantaine | 0 |

Les deux prospects `QA-P46-ALPHA` et `QA-P46-BETA` sont visibles dans **Prospects** et le lot est visible dans
**Historique des imports**.

### Résultat du fichier de quarantaine constaté le 2026-09-27

Le fichier `P4_6_IMPORT_QUARANTAINE.csv` a été téléversé avec la déclaration `CSV-QUAR-01`, puis confirmé. Le lot
`3b83de24-917d-4469-99aa-8730839cb78f` est lié à la session `3898e811-695d-4c51-9b99-ffddda9db3ff`.

| Compteur | Observé |
|---|---:|
| Prospects créés | 0 |
| Doublons exacts | 0 |
| Lignes à revoir | 0 |
| Lignes en quarantaine | 2 |

Les références opaques et motifs sont conformes : ligne 2 `email_invalid` (`50fbdf3690373a4a7733cde4a2f672d3`) et
ligne 3 `business_name_missing` (`05db7180a3b98a9e10d92db15eed75e8`). Aucun prospect n'a été créé à partir de ces
lignes.

### Résultat du rejeu CSV constaté le 30 septembre 2026

Le même fichier valide a été téléversé avec une nouvelle déclaration `CSV-VALID-REPLAY`, puis validé et confirmé.
La session `700ab1cf-a3bf-462f-b6a9-462af6609cad` est liée à la déclaration
`0c2a3add-36ae-4884-8e6e-c79c4bfeb0e7`. Le lot confirmé est
`89b1cdab-2221-4435-a99b-c446da58c495`.

| Compteur | Observé |
|---|---:|
| Prospects créés | 0 |
| Doublons exacts | 2 |
| Lignes à revoir | 0 |
| Lignes en quarantaine | 0 |

La session porte deux lignes, aucune ligne prête à créer et le statut `validated` avant confirmation ; le lot
confirmé porte bien les mêmes quatre compteurs. Les deux prospects issus du premier import restent uniques.

**E2E-03 — PASS.** L'import initial, le rejeu idempotent et le scénario de quarantaine sont tous rapprochés.

## Fiche de test détaillée — E2E-04

### Objectif et périmètre

Vérifier qu'un export CSV demandé par `ORG-A` est traité de façon asynchrone par le worker, publié dans un stockage
privé, téléchargeable uniquement par un membre autorisé de `ORG-A` et inaccessible depuis `ORG-B`. Le parcours réutilise
les données créées par E2E-02 et E2E-03 ; il ne crée pas de nouveau prospect et ne modifie aucune donnée CRM.

Le scénario principal porte sur le jeu `prospects` en portée `organization`, afin de rapprocher le prospect `P4-ALPHA-2`
et les prospects `QA-P46-ALPHA` / `QA-P46-BETA`. Si le compte de recette ne possède pas la capacité de portée
organisationnelle, jouer le même parcours en portée `self` et relever explicitement cette portée dans le registre. Le
contrôle d'étanchéité depuis `ORG-B` reste obligatoire dans les deux cas.

| Élément | Valeur de recette |
|---|---|
| Organisation émettrice | `ORG-A` — acteur `A-MANAGER` pour la portée organisationnelle ; `A-SALES-1` pour le repli en portée personnelle |
| Organisation de contrôle | `ORG-B` — acteur `B-ADMIN` ou `B-SALES` |
| Jeu exporté | `prospects` ; portée `organization` si autorisée, sinon `self` |
| Données attendues | `P4-ALPHA-2`, `QA-P46-ALPHA`, `QA-P46-BETA` selon la portée et les filtres actifs |
| Filtres | Aucun filtre par défaut ; si une période est renseignée, inclure le 27 septembre 2026 et utiliser une borne haute au 28 septembre 2026 |
| Clé d'idempotence | Une clé unique de la forme `E2E-04-EXPORT-<suffixe>` ; réutiliser exactement cette clé pour le contrôle de rejeu |
| Contrat de colonnes | Colonnes de la liste blanche `prospects`, jamais de chemin local, secret, cookie, contenu de fichier source ou référence brute de stockage |

Les règles d'export des sources externes restent en fermeture par défaut. Les champs issus de l'import CSV ne doivent
apparaître que si une règle d'export approuvée les autorise ; leur omission contrôlée avec `omitted_count` est un résultat
attendu et ne doit pas être contournée pendant la recette.

### Préconditions

1. Le prévol Phase 4.6 est `ready`, l'API, PostgreSQL, Redis et le worker d'export sont démarrés.
2. E2E-02 est conservé avec l'opportunité `OPP-E2E` et le prospect `P4-ALPHA-2` ; E2E-03 conserve les prospects
   `QA-P46-ALPHA` et `QA-P46-BETA`. Ne pas purger ces éléments avant E2E-12.
3. `A-MANAGER` est membre actif de `ORG-A` et possède `exports:create`, `exports:read`, `exports:download` et la
   capacité de lecture du jeu choisi. Si seule la portée personnelle est accordée, utiliser `A-SALES-1`, propriétaire
   du prospect E2E-02, avec `exports:create:self`, `exports:read` et `exports:download`. `B-ADMIN` ou `B-SALES` est
   membre actif de `ORG-B` sans appartenance à `ORG-A`.
4. Aucun export de test précédent ne doit être réutilisé. Effacer les filtres de dates de la page **Exports** avant la
   demande, ou saisir une période qui couvre les dates de création des données.
5. Le répertoire de téléchargement local est hors du dépôt (par exemple un sous-répertoire temporaire de recette) et
   ne sera pas joint aux preuves.

### Déroulé contrôlé

| Étape | Action | Résultat attendu et preuve |
|---|---|---|
| 1 | Avec `A-MANAGER` (ou `A-SALES-1` en portée `self`), ouvrir **Exports**, choisir `Prospects`, la portée autorisée et les filtres définis ci-dessus, puis demander l'export. | Une demande est créée en `queued` ou `running`, avec un `export_id` fictif et un horodatage. Noter l'identifiant, la portée, la clé d'idempotence et le `request_id` sans copier de jeton. |
| 2 | Rejouer immédiatement la même demande avec la même clé d'idempotence et le même payload. | Le même `export_id` est retourné ; aucun second job ni double comptage n'est visible dans **Exports** ou dans l'audit. Une différence de payload avec cette clé doit être rejetée par l'API. |
| 3 | Actualiser la liste jusqu'à la prise en charge par le worker (`running`), puis jusqu'à l'état terminal. | Le chemin nominal est `queued → running → ready`. Relever `row_count`, `omitted_count`, `created_at`, `completed_at` et l'absence de `failed`, `cancelled` ou `expired`. |
| 4 | Ouvrir le détail de l'export et comparer les compteurs avec les données visibles dans `ORG-A`. | Le nombre de lignes exportées correspond à la portée et aux filtres. Les champs de source externe non autorisés sont absents et, s'ils sont comptés, rapprochés dans `omitted_count`. Les devises et montants restent dans des colonnes séparées pour les jeux qui en possèdent. |
| 5 | Télécharger l'artefact depuis **Exports**, enregistrer le CSV hors du dépôt et l'ouvrir localement. | Réponse HTTP `200`, `Content-Type: text/csv; charset=utf-8`, téléchargement en pièce jointe, `Cache-Control: no-store` et protection `nosniff`. Le fichier commence par le BOM UTF-8 attendu, contient uniquement les en-têtes allowlistés et aucune référence de chemin, secret ou fichier temporaire. |
| 6 | Contrôler le contenu du CSV sans recopier ses lignes dans le registre. | Les identifiants `P4-ALPHA-2`, `QA-P46-ALPHA` et `QA-P46-BETA` apparaissent seulement lorsque la portée les inclut ; aucun enregistrement d'une autre organisation n'est présent. Toute valeur commençant par `=`, `+`, `-` ou `@` est neutralisée par le préfixe d'export ; noter le contrôle même si le jeu courant ne contient pas de formule. |
| 7 | Se déconnecter de `ORG-A`, se connecter à `ORG-B`, puis tenter `GET` du détail avec le même `export_id` et le téléchargement. | Les deux réponses sont refusées de manière indistincte (`404` attendu par le contrat), sans révéler l'existence, le statut, le nombre de lignes ou l'URL de stockage de l'export de `ORG-A`. |
| 8 | Relire l'audit et l'usage après le téléchargement. | Les événements `export_requested`, `export_ready` et `export_downloaded` sont présents pour `ORG-A`, sans chemin local ni contenu CSV. La consommation `platform.csv_export` est attribuée au bon tenant et à l'acteur attendu. |

### Rapprochement à consigner

Le registre doit contenir : `export_id`, portée, dataset, clé d'idempotence masquée ou suffixée, statuts observés,
`row_count`, `omitted_count`, `request_id`, date de création et date de fin, résultat du téléchargement, et résultat
des deux tentatives depuis `ORG-B`. Ne pas consigner les lignes CSV, l'URL de stockage, le nom du fichier temporaire,
les cookies, les jetons ou les données personnelles.

| Contrôle | Attendu |
|---|---:|
| Demandes créées avec la même clé | 1 export |
| Artefacts publiés | 1 artefact `ready` |
| Téléchargement par `ORG-A` | `200`, CSV lisible et borné par la liste blanche |
| Lecture et téléchargement par `ORG-B` | refus indistinct, `404` attendu |
| Fichiers provisoires exposés par l'API ou l'audit | 0 |
| Événements d'audit d'export | demande, publication et téléchargement rapprochés |

E2E-04 est `PASS` si la demande idempotente suit le cycle du worker jusqu'à `ready`, si le fichier téléchargé est
privé et conforme au contrat, si les compteurs et omissions sont rapprochés, et si `ORG-B` ne peut ni lire ni
télécharger l'export. Conserver l'artefact et les identifiants jusqu'à E2E-05 et E2E-12 ; ne pas le supprimer pendant
la recette.

## Fiche de test détaillée — E2E-05

### Objectif et périmètre

Vérifier qu'un export en cours reprend après l'arrêt du worker qui détient son bail, qu'un second worker ne peut pas
terminer avec l'ancien jeton, et qu'un seul artefact est publié. Le scénario utilise une nouvelle demande d'export et
ne réutilise pas les artefacts E2E-04.

### Préconditions

1. E2E-04 est `PASS`, l'API et PostgreSQL sont disponibles et le volume Docker nommé est partagé par l'API et le
   worker.
2. Conserver l'identifiant de la nouvelle demande et son `job_id` sans consigner de cookie, jeton ou chemin local.
3. Démarrer un seul worker avant la demande, puis préparer deux workers distincts pour la reprise. Compose attribue un
   nom d'hôte distinct à chaque réplique, ce qui produit deux `worker_id` distincts dans `worker_heartbeats`.

La commande `scripts/Invoke-E2E05WorkerRecovery.ps1` automatise l'armement, la détection de `running`,
l'interruption, l'attente du bail et la relance. Elle laisse une seule action manuelle : créer une nouvelle demande
d'export dans le navigateur lorsque le script indique qu'il est armé.

### Déroulé contrôlé

| Étape | Action | Résultat attendu et preuve |
|---|---|---|
| 1 | Arrêter les anciens workers, conserver l'API et PostgreSQL, puis démarrer une seule réplique : `docker compose --profile runtime up -d --scale worker=1 worker`. | Un seul worker sain. Relever uniquement son état et l'heure de début. |
| 2 | Créer une nouvelle demande `prospects` avec une nouvelle clé `E2E-05-EXPORT-<suffixe>`. | La demande est `queued`, puis le job devient `running`. Relever `export_id`, `job_id` et `attempt_count=1`. |
| 3 | Dès que le job est `running`, désactiver le redémarrage automatique puis interrompre brutalement l'unique worker : `worker_id=$(docker compose --profile runtime ps -q worker)` ; `docker update --restart=no "$worker_id"` ; `docker kill --signal KILL "$worker_id"`. Un arrêt gracieux (`stop`) peut attendre la fin du handler et ne constitue donc pas l'interruption contrôlée. | Le fichier provisoire n'est pas publié ; le job conserve son bail expirant et aucun artefact `ready` n'est créé. Si le job est déjà `succeeded`, annuler la fiche et recommencer avec une nouvelle demande : une exécution instantanée ne constitue pas ce test. |
| 4 | Attendre au moins 100 secondes, soit plus que le bail de 90 secondes, puis démarrer deux répliques avec recréation : `docker compose --profile runtime up -d --force-recreate --scale worker=2 worker`. | Un seul worker reprend le job ; le second reste disponible. Le job passe à une tentative supérieure sans second artefact. La recréation rétablit la politique `unless-stopped`. |
| 5 | Actualiser **Exports** et relever le chemin `queued → running → ready` ou l'état terminal prévu par le contrat. | Une seule publication `ready`, `row_count` et `byte_size` cohérents, aucun doublon dans `export_artifacts`. |
| 6 | Contrôler les événements et les fichiers provisoires depuis WSL, sans copier leur contenu : compter les événements du job et les fichiers `.*.tmp`. | L'ancien propriétaire ne produit aucun `succeeded` après l'expiration ; un seul événement de succès et zéro fichier provisoire résiduel. |
| 7 | Télécharger l'artefact avec le demandeur autorisé. | `200`, SHA-256 identique au registre, un seul fichier CSV. |

#### Exécution assistée recommandée

Depuis PowerShell, lancer la surveillance avant de créer l'export :

```powershell
.\scripts\Invoke-E2E05WorkerRecovery.ps1 -WslDistribution Ubuntu-24.04
```

Lorsque le script affiche `E2E-05 est armé`, créer une unique nouvelle demande d'export dans le navigateur. Le script
affiche ensuite `job_id`, `status`, `attempt_count`, le nombre d'artefacts et le nombre de fichiers provisoires. Seul le
résultat final `E2E-05 PASS` permet de clôturer le scénario. La fenêtre d'armement dure 15 minutes par défaut ; elle
peut être réduite ou augmentée dans la limite de 30 à 900 secondes avec `-WatchSeconds`.

Pour rendre l'interruption observable avec les petits jeux de données locaux, le script pose avant la demande un verrou
transactionnel temporaire sur la lecture de `prospects`. La demande est donc admise et le job devient `running`, sans
publication d'artefact, avant le `SIGKILL`. Le script libère ce verrou juste après l'interruption et aussi dans son
bloc de nettoyage ; il ne modifie aucune ligne. En cas d'arrêt forcé de PowerShell avant le nettoyage, relancer le
script permet de purger ce verrou de test avant d'armer une nouvelle exécution.

Commandes de contrôle non destructives, à exécuter depuis le dossier du projet :

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && docker compose --profile runtime ps"
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && docker compose --profile runtime exec -T worker sh -lc 'find /app/.runtime/imports/exports -maxdepth 1 -name \".*.tmp\" -type f -printf \"%f\\n\" | wc -l'"
```

### Critères de décision

E2E-05 est `PASS` uniquement si l'arrêt survient pendant l'état `running`, si le bail expire, si une réplique reprend,
si l'ancien propriétaire ne peut plus terminer le job, si un seul artefact est publié et si aucun provisoire ne reste.
Un export terminé avant l'arrêt est `NOT RUN` et doit être rejoué ; il ne peut pas être compté comme une reprise.

### Incident de disponibilité constaté le 2026-09-27

La page **Exports** a reçu `GET /api/exports?limit=25` avec `503 exports_unavailable`. Le backend était lancé sans
`JOB_IDEMPOTENCY_HMAC_KEY` ; `build_container()` ne créait donc pas `container.exports`, alors que le worker Docker
utilisait déjà la valeur de développement de la composition.

La configuration fournit maintenant cette valeur uniquement en `development` et `test`, et exige une clé explicite en
`staging` et `production`. Le processus API doit être redémarré pour relire la configuration. E2E-04 est maintenant
`PASS` : les exports `bb8d92dc-2803-46fe-b891-43586d6db56a` et `282eea94-0d7f-4401-a5ee-ffc81c7b29e9` ont été
téléchargés, les colonnes sont allowlistées et l'isolation depuis `ORG-B` a été validée par l'utilisateur.

### Incident de stockage local constaté le 2026-09-27

Le worker a ensuite traité les demandes mais chacune a terminé après trois tentatives avec `attempts_exhausted`. Le
probe du conteneur a établi que le montage OneDrive/NTFS permettait la création de fichier, mais refusait `chmod 600`.
Le worker échoue volontairement dans ce cas : il ne publie jamais un CSV dont les permissions privées ne peuvent pas
être appliquées. L'avertissement d'audit associé est corrigé : le code terminal `attempts_exhausted` est désormais une
valeur autorisée et auditée.

Pour cette recette, l'API et le worker doivent partager le volume Docker nommé, dont les permissions POSIX sont
vérifiables. Après avoir arrêté l'API Python démarrée depuis Windows, démarrer le runtime de recette depuis WSL :

```powershell
wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && docker compose --profile runtime up -d --build api worker"
```

Puis vérifier `http://localhost:8000/api/health/live`, se reconnecter dans l'application et créer une **nouvelle**
demande E2E-04. Les demandes déjà en `failed` restent des preuves de l'incident : ne pas les rejouer et ne pas les
compter comme un succès de recette.

### Reprise après `category_not_acquired`

Une déclaration déjà passée en `quarantined` ne doit pas être modifiée ni effacée. Conserver son identifiant et son
motif dans le registre, puis :

1. vérifier dans le détail de l'acquisition, et non seulement dans le fournisseur, que `data_categories` contient les
   cinq catégories ; vérifier aussi que `valid_from` est antérieur ou égal à la date d'exécution ;
2. si l'acquisition ne convient pas, corriger la date du fournisseur puis créer une nouvelle acquisition approuvée
   avec les cinq catégories. L'ancienne acquisition et sa déclaration restent conservées pour l'audit ;
3. créer une nouvelle déclaration, par exemple `CSV-VALID-01-R2`, en cochant les cinq catégories dans **Déclarer un
   import CSV** et les neuf champs du mapping (`business_name`, `business_identifier`, `business_address`,
   `contact_name`, `contact_role`, `email`, `phone`, `linkedin_profile`, `facebook_profile`) ;
4. téléverser de nouveau `P4_6_IMPORT_VALID.csv`, appliquer le même mapping et reprendre la validation ;
5. ne compter le scénario comme réussi qu'avec `ready_count=2` puis `created_count=2` sur cette nouvelle déclaration.

Le statut `category_not_acquired` signifie que le contrat de catégories de la déclaration est incomplet ; ce n'est pas
une erreur de format du fichier et il ne faut pas approuver manuellement cette déclaration pour contourner le contrôle.

## Fiche de test détaillée — E2E-06

### Objectif et limites

Exécuter une recherche Google autorisée sans contacter Google, puis rapprocher la réservation de quota avec le registre
d'usage personnel et organisationnel. Le fournisseur de recette retourne exactement deux établissements synthétiques
sans coordonnées et ne garde ni le texte de recherche ni les paramètres reçus. Les coordonnées manuelles servent
uniquement à valider le formulaire dans le navigateur : aucun jeton de carte n'est émis en mode simulé.

| Élément | Valeur de recette |
|---|---|
| Organisation et rôle | `ORG-A` avec `A-MANAGER` ; capacités `google:search`, `usage:read:self` et `usage:read:organization`. |
| Fournisseur | `SimulatedGooglePlacesGateway`, activé uniquement avec `APP_ENV=development` ou `test`. |
| Résultats attendus | `Atelier simulé Alpha` et `Atelier simulé Beta`, deux zones de service synthétiques, sans latitude ni longitude. |
| Recherche | `plombier`, coordonnées manuelles `46.8139`, `-71.2080`, rayon `15 km`, zones de service incluses. |
| Données à relever | Compteurs avant/après de Text Search, agrégats `quota_reserved`, `upstream_attempted` et `upstream_succeeded`. |

### Préparation contrôlée

Depuis PowerShell, à la racine du dépôt, reconstruire uniquement l'API locale avec le simulateur :

```powershell
.\scripts\Set-E2E06GoogleSimulation.ps1 -WslDistribution Ubuntu-24.04
```

Le script configure `GOOGLE_PLACES_SIMULATOR_ENABLED=true` seulement dans le conteneur API puis contrôle
`/api/health`, le type du fournisseur et le blocage des jetons de carte. Il reconstruit l'API sans cache pour éviter
de réutiliser une image antérieure. La valeur `google_api_key_configured: true` signifie ici que **Text Search est
disponible via le simulateur**, sans introduire de clé Google. Si l'API a été démarrée directement depuis Windows, la
commande la remplace par l'API Docker locale ; reconnectez-vous ensuite dans l'application et actualisez la page avec
`Ctrl+F5`.

### Alternative sans navigateur

Si un serveur Windows local occupe `localhost:8000` ou si le navigateur ne peut pas joindre le conteneur Docker,
exécuter la recette de services suivante. Elle reconstruit l'API simulée puis appelle le cas d'usage dans le conteneur,
avec un membre `manager` ou `admin` actif. Elle rapproche les quotas Redis et les agrégats PostgreSQL avant et après
la recherche et échoue au premier écart. Elle ne dépend d'aucun port Windows.

```powershell
.\scripts\Invoke-E2E06ContainerVerification.ps1 -WslDistribution Ubuntu-24.04
```

La sortie `E2E06_CONTAINER=PASS` constitue la preuve alternative de E2E-06. Elle couvre le fournisseur simulé, les
deux résultats synthétiques, l'absence de jeton de carte, les incréments de quota et les trois agrégats d'usage pour
les portées personnelle et organisationnelle. Elle ne valide pas l'affichage du navigateur, déjà couvert par les
tests du client.

Ne pas utiliser la saisie semi-automatique de lieu ni ouvrir une carte pendant ce scénario. En mode simulé, les routes
de localisation restent désactivées et aucun jeton de carte n'est créé. La zone de carte peut afficher
**Carte non disponible** : c'est l'état attendu du parcours sans coordonnées conservées.

### Déroulé contrôlé

| Étape | Action | Résultat attendu et preuve assainie |
|---|---|---|
| 1 | Se connecter comme `A-MANAGER` dans `ORG-A`, ouvrir **Usage**, sélectionner **Mon usage** puis **Aujourd'hui**. Noter les compteurs Text Search initiaux sans copier de corps de réponse. Refaire avec **Organisation**. | Deux valeurs de référence : `self_before` et `organization_before`. La portée affichée correspond au sélecteur. |
| 2 | Ouvrir **Recherche Google**, cliquer **Coordonnées avancées**, saisir le jeu ci-dessus, laisser **Entreprises de zone de service** activé et lancer une seule recherche. Ne pas ajouter les résultats au CRM. | Deux résultats nommés `Atelier simulé Alpha` et `Atelier simulé Beta`, `2 résultats` et `1 appel Text Search`. Aucun prospect, contact ou appel Google réel n'est créé. |
| 3 | Revenir à **Usage**, choisir **Mon usage** et **Aujourd'hui**, puis actualiser. | `used = self_before + 1`; les opérations Google Text Search augmentent exactement de `+1` pour la réservation acceptée, la tentative et le succès. La ligne `google.maps_static.request` reste égale à sa valeur de référence. |
| 4 | Dans le même écran, choisir **Organisation** et actualiser. | `used = organization_before + 1` si aucun autre membre n'a recherché entre-temps ; sinon l'écart est au moins `+1`. La ventilation par membre contient l'opération de `A-MANAGER` et aucune donnée de `ORG-B`. |
| 5 | Relire le rapport personnel puis organisationnel de la journée dans l'interface ou dans l'onglet Réseau, sans archiver les requêtes. | Les agrégats Text Search montrent `quota: accepted +1`, `request: attempted +1`, `request: succeeded +1`. Le rapport organisationnel déclenche son audit de consultation, sans contenu de recherche. |
| 6 | Conserver la sortie du script de préparation, qui vérifie seulement le schéma des tables durables et ne sélectionne aucune ligne. | Les colonnes de `usage_operation_events` et `usage_daily_counters` ne contiennent ni requête, ni réponse Google, ni latitude, longitude ou coût. Les résultats et le texte de recherche ne sont présents que dans la réponse HTTP `no-store` du navigateur. |

### Critères de décision et remise en état

E2E-06 est `PASS` si une seule recherche fait progresser les deux quotas de la valeur attendue, si les trois agrégats
Text Search sont rapprochés dans les deux portées, et si aucun enregistrement durable ne contient un paramètre de
recherche, une réponse fournisseur, une coordonnée ou une estimation de coût. Un écart de portée, une tentative sans
réservation ou un appel Google observé est `FAIL`.

Après la capture des preuves assainies, restaurer le comportement local habituel :

```powershell
.\scripts\Set-E2E06GoogleSimulation.ps1 -WslDistribution Ubuntu-24.04 -Mode Disable
```

Ce redémarrage désactive le faux fournisseur. Il ne supprime aucune donnée de recette ; conserver les compteurs et
l'identifiant de l'organisation jusqu'à E2E-12.

## Fiche de test détaillée — E2E-07

### Résultat automatisé du 28 septembre 2026

La commande suivante a été exécutée depuis la racine du dépôt :

```powershell
.\scripts\Test-E2E07QuotaResilience.ps1
```

Résultat obtenu :

```text
28 passed in 48.38s
E2E-07_SCRIPT=PASS tests=28 rapport=...\test-results\phase-4-6\scripted\e2e-07.xml
```

Le rapport JUnit est `test-results/phase-4-6/scripted/e2e-07.xml`. Le script utilise le lanceur de tests local et
un répertoire temporaire privé au projet ; il ne contacte aucun fournisseur Google réel.

### Contrôles couverts par les 28 tests

| Contrôle | Résultat observé |
|---|---|
| Politique serveur de quota | Les limites personnelles et organisationnelles, le seuil d'avertissement et le code de politique sont restitués ; une limite nulle explicite est acceptée et les valeurs invalides sont rejetées. |
| Refus avant fournisseur | Le cas de quota dépassé retourne HTTP `429`, le code `google_quota_exceeded`, la portée `organization`, `Retry-After` et `Cache-Control: no-store`. La passerelle de recherche n'est pas appelée (`0` appel). |
| Configuration Google absente | La route retourne HTTP `503` avec `google_not_configured` avant tout appel au fournisseur. |
| Échec du fournisseur de carte | L'erreur externe est transformée en erreur métier fermée (`google_map_unavailable`), avec `request_id`, sans divulguer le détail fournisseur ; le rejeu du jeton est refusé. |
| Parcours de recherche simulé | Le nombre maximal de résultats, la déduplication, le filtrage par rayon et les trois événements d'usage (`quota_reserved`, `upstream_attempted`, `upstream_succeeded`) sont contrôlés. |
| Données de résultat | Les candidats Google ne portent pas de champs de contact sensibles dans le modèle de recherche. |

### Interprétation du résultat

`E2E-07_SCRIPT=PASS` valide les contrats métier et API couverts par les tests ciblés. Le parcours fonctionnel a
ensuite été vérifié dans la composition WSL : plafond synthétique atteint, registre durable verrouillé, Redis mis en
pause, puis dépendances et interface rétablies. Le scénario est `PASS` depuis le 30 septembre 2026.

### Déroulé de l'indisponibilité réelle et réversible

Ce déroulé utilise uniquement le simulateur Google local. Il n'arrête ni ne recrée PostgreSQL, et la panne du registre
durable est limitée à un verrou temporaire de sa table d'écriture. La pause Redis conserve son volume et les sessions ;
elle est levée explicitement à l'étape 7.

1. Exécuter d'abord le contrat automatisé et le prévol :

   ```powershell
   .\scripts\Test-E2E07QuotaResilience.ps1
   .\scripts\Test-Phase4_6InteractivePreflight.ps1
   ```

   Les marqueurs attendus sont `E2E-07_SCRIPT=PASS` et des dépendances PostgreSQL/Redis `ok`.

2. Dans **Usage**, relever les compteurs du jour de la portée personnelle (`U`) et organisationnelle (`O`). Activer
   ensuite le simulateur et recréer l'API avec des limites égales à `U + 2` et `O + 2`. Ces valeurs ne vivent que dans
   le conteneur recréé pour ce scénario.

   ```powershell
   wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && GOOGLE_PLACES_SIMULATOR_ENABLED=true GOOGLE_SEARCH_USER_DAILY_LIMIT=<U+2> GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT=<O+2> docker compose --profile runtime up -d --force-recreate api"
   ```

   Actualiser la session puis vérifier que `/api/health` indique `google_places_mode: simulated`. Remplacer seulement
   les deux valeurs entre chevrons par les compteurs relevés, sans les conserver dans un fichier d'environnement.

3. Dans **Recherche d’établissements**, lancer deux recherches valides avec les coordonnées manuelles prévues par
   E2E-06. Les deux réponses aboutissent avec le simulateur. La troisième recherche doit renvoyer HTTP `429`, le code
   `google_quota_exceeded`, le champ `scope` et l'en-tête `Retry-After`. Elle ne doit pas appeler le fournisseur.

   **Résultat constaté le 30 septembre 2026 :** troisième requête refusée en HTTP `429`,
   `google_quota_exceeded`, portée `user` et identifiant de requête `647eea9e65c54f99b8c45eb48c38a5a4`.
   Le premier essai restait en HTTP `200` car Compose ne transmettait pas les limites `GOOGLE_SEARCH_*` au conteneur
   API. L'environnement de l'API a été corrigé dans `compose.yaml`, puis la limite à `2` a été vérifiée avant le rejeu.

4. Les deux premières requêtes ont consommé le plafond temporaire. Avant le test du registre durable, relever cette limite à
   `20` pour autoriser une nouvelle réservation, sans désactiver le simulateur :

   ```powershell
   wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && GOOGLE_PLACES_SIMULATOR_ENABLED=true GOOGLE_SEARCH_USER_DAILY_LIMIT=20 GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT=20 docker compose --profile runtime up -d --force-recreate api"
   ```

5. Ouvrir un second terminal WSL et lancer le verrou temporaire suivant. Dès que la commande est lancée,
   revenir au navigateur et envoyer une nouvelle recherche pendant les 45 secondes du verrou :

   ```bash
   docker compose --profile runtime exec -T postgresql psql -U prospect -d prospect -v ON_ERROR_STOP=1 -c 'BEGIN; LOCK TABLE public.usage_operation_events IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(45); COMMIT;'
   ```

   Le verrou bloque seulement l'écriture de l'événement d'usage. L'authentification et la réservation Redis restent
   disponibles. La recherche doit finir en HTTP `503`, code `usage_tracking_unavailable`. Attendre la fin normale de
   la commande : le verrou est alors libéré automatiquement. Ne pas interrompre PostgreSQL.

   **Résultat constaté le 30 septembre 2026 :** le verrou a été libéré par `COMMIT` et la requête envoyée pendant
   celui-ci a reçu HTTP `503`, code `usage_tracking_unavailable`, identifiant de requête
   `59aba15262b04f2f9d9f2ac13dd0988c`. Aucun résultat de recherche n'a été retourné.

6. Actualiser **Usage** après la libération du verrou. Le rapport durable doit redevenir accessible. Consigner que le
   refus `503` n'a créé ni résultat Google ni prospect.

7. Dans le second terminal, mettre Redis en pause, puis tenter une action authentifiée ou une recherche Google depuis
   le navigateur :

   ```powershell
   wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && docker compose --profile runtime pause redis"
   ```

   Le résultat attendu est un HTTP `503` fermé. Comme Redis conserve également les sessions, le code observable peut
   être `authentication_unavailable` avant l'étape de quota ; cela prouve que l'application ne continue pas le
   parcours Google sans sa dépendance de protection. Aucun appel fournisseur ne doit être observé.

   **Résultat constaté le 30 septembre 2026 :** la recherche a reçu HTTP `503`, code
   `authentication_unavailable`, identifiant de requête `c9aa64e7a05d478896f7826bc2f5785a`.
   L'interface a affiché « L’authentification est temporairement indisponible. » ; aucun résultat de recherche
   n'a été retourné.

8. Restaurer Redis, attendre son état sain, puis actualiser le navigateur :

   ```powershell
   wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && docker compose --profile runtime unpause redis && docker compose --profile runtime ps redis"
   ```

   La session et la page **Usage** doivent redevenir exploitables. Si la session a expiré pendant l'essai, se
   reconnecter ; aucune donnée métier n'est perdue.

   **Résultat constaté le 30 septembre 2026 :** Redis a été remis en service et affiché `healthy`. Après
   recréation de l'API, `/api/health/ready` a indiqué `ready`, PostgreSQL `ok` et Redis `ok`. La page **Usage**
   s'est chargée de nouveau ; le quota courant de l'organisation affichait `12` réservations utilisées sur `100`.
   L'avertissement de période partielle concerne le début de la plage de 30 jours, antérieur à l'activation du
   registre qualifié.

9. Restaurer le comportement local habituel après les captures :

   ```powershell
   wsl -d Ubuntu-24.04 -- bash -lc "cd '/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator' && GOOGLE_PLACES_SIMULATOR_ENABLED=false docker compose --profile runtime up -d --force-recreate api"
   ```

   Vérifier `http://localhost:5173/api/health`, puis consigner les quatre preuves : deux succès simulés, le `429`, le
   `503 usage_tracking_unavailable`, le `503` Redis et le retour au vert. Ne conserver ni cookie, ni corps contenant
   des données CRM, ni export de Redis ou PostgreSQL.

   **Résultat constaté le 30 septembre 2026 :** `/api/health` a indiqué `status: ok`, clé Google configurée et
   `google_places_mode: live`. **Verdict E2E-07 : PASS.**

## Fiche de test détaillée — E2E-11-MANUAL

### Objectif et prérequis

Cette fiche complète le contrôle Axe déjà validé sur 44 parcours. Elle vérifie les éléments qui demandent une observation humaine : ordre de tabulation, visibilité du focus, navigation au zoom, libellés français et anglais, ainsi que les états vide et erreur.

1. Démarrez l'API et le client local, puis ouvrez une session `A-MANAGER` dans Chrome ou Edge.
2. Préparez deux organisations de recette, l'une en français et l'autre en anglais, ou changez la langue de l'organisation active entre les deux passages.
3. Ouvrez les DevTools. Ils serviront seulement au zoom à 200 %, à l'émulation `320 × 568` et, pour un seul contrôle, au mode réseau hors ligne.
4. N'utilisez aucune donnée réelle. La fiche se limite à la navigation, à une recherche sans résultat et à une erreur réseau réversible.

### Passage 1 — parcours fonctionnel dans les deux langues

Effectuez le tableau une fois en français puis une fois en anglais. Notez `PASS` ou `FAIL` dans la dernière colonne et conservez une capture assainie uniquement lorsqu'un écart est constaté ou qu'une preuve visuelle est demandée.

| Page | Adresse | Contrôle à observer | Résultat |
|---|---|---|---|
| Dashboard | `/app/dashboard` | Titre, cartes et action principale lisibles ; organisation active visible. | PASS |
| Usage | `/app/usage` | Filtres, bouton `Afficher`, quota et tableau lisibles. | PASS |
| Historique des imports | `/app/imports/history` | Filtres, états des imports et éventuel état vide compréhensibles. | PASS |
| Exports | `/app/exports` | Formulaire, demandes et action de téléchargement accessibles. | PASS |
| Fournisseurs et acquisitions | `/app/compliance/sources` | Onglets, contrats et actions de connexion affichent des libellés cohérents. | PASS |
| Pipeline | `/app/pipeline` | Colonnes, compteurs et actions de déplacement ou de filtrage restent lisibles. | PASS |
| Opportunités | `/app/opportunities` | Liste, filtres et action de création ou de consultation accessibles. | PASS |
| Tâches | `/app/tasks` | Liste, filtres et action de création ou de consultation accessibles. | PASS |

**Attendu :** les libellés essentiels, les messages et les actions de chaque page correspondent à la langue de l'organisation active. Aucun bouton, titre ou message principal ne reste dans l'autre langue. Les actions et données affichées respectent l'organisation sélectionnée.

### Passage 2 — clavier et focus

Réalisez ces vérifications sur Dashboard, Exports et Fournisseurs et acquisitions.

1. Rechargez la page puis appuyez sur `Tab`. Le lien d'évitement doit devenir visible.
2. Activez ce lien avec `Entrée`. Le focus arrive dans le contenu principal.
3. Continuez avec `Tab` et `Maj+Tab` jusqu'aux principaux filtres, liens, boutons et actions de tableau.
4. Activez une action non destructive avec `Entrée` ou `Espace`, puis revenez avec `Maj+Tab`.
5. Sur Fournisseurs et acquisitions, atteignez les onglets au clavier puis vérifiez que le contenu affiché correspond à l'onglet choisi.

**Attendu :** le focus est toujours visible, l'ordre suit la lecture de la page, aucun élément interactif n'est inaccessible et l'action déclenchée est compréhensible sans souris.

### Passage 3 — petit écran et zoom à 200 %

1. Émulez une fenêtre `320 × 568`. Ouvrez le menu avec le clavier, naviguez vers Usage, fermez avec `Échap` et vérifiez que le focus revient au bouton Menu.
2. À cette taille, contrôlez Dashboard, Exports et Tâches. Le défilement de la page reste vertical et les actions importantes restent atteignables.
3. Revenez à `1280 × 720`, appliquez le zoom navigateur à `200 %`, puis contrôlez Dashboard, Exports, Fournisseurs et acquisitions, Pipeline et Tâches.

**Attendu :** aucun chevauchement ou texte tronqué ne cache une action. Un tableau peut posséder son propre défilement horizontal, mais la page ne doit pas nécessiter de défilement horizontal pour accéder aux commandes principales.

### Passage 4 — état vide et erreur réversible

1. Ouvrez la recherche ou la liste des prospects et saisissez `E2E11-AUCUN-RESULTAT` dans un filtre adapté. Vérifiez le message d'absence de résultat et la possibilité de réinitialiser le filtre.
2. Dans les DevTools, choisissez temporairement le réseau hors ligne, rechargez `/app/usage`, puis remettez immédiatement le réseau en ligne.
3. Vérifiez que l'erreur est lisible, qu'elle n'est pas signalée uniquement par une couleur et que recharger ou réessayer permet de retrouver la page.

**Attendu :** l'état vide explique clairement l'absence de données. L'état d'erreur donne une action de reprise et ne bloque pas la navigation après le retour en ligne.

### Preuve et verdict

Ajoutez une ligne au registre et une note de recette avec ce format :

```text
E2E-11-MANUAL | date UTC | navigateur et version | rôle | organisations FR/EN |
pages vérifiées | clavier/focus | 320 × 568 | 200 % | état vide | erreur réseau | PASS ou FAIL | écart et capture associée
```

Le verdict est `PASS` si les quatre passages sont conformes. Tout focus invisible, action inaccessible, libellé essentiel non traduit, chevauchement bloquant ou erreur sans reprise classe le parcours `FAIL` jusqu'à correction et nouveau passage.

### Résultat observé — 30 septembre 2026

| Passage | Résultat observé | Verdict |
|---|---|---|
| 1 — français et anglais | Dashboard, Usage, Historique des imports, Exports, Fournisseurs et acquisitions, Pipeline, Opportunités et Tâches contrôlés dans les deux langues. Les libellés, filtres, listes et actions principales correspondent à la langue de l'organisation active. | PASS |
| 2 — clavier et focus | Navigation par tabulation, lien d'évitement, activation au clavier, retour avec `Maj+Tab` et onglets de conformité contrôlés. Le focus est visible et les commandes principales restent atteignables. | PASS |
| 3 — petit écran et zoom à 200 % | Connexion, Dashboard, Exports, Fournisseurs et acquisitions, Pipeline et navigation mobile contrôlés. Le menu et la barre de navigation restent utilisables ; aucun chevauchement bloquant ni défilement horizontal de page n'a été observé. | PASS |
| 4 — état vide et erreur réversible | Une recherche de prospects sans résultat affiche un état vide explicite. Le parcours d'erreur réversible a été vérifié : le retour en ligne permet de reprendre la navigation. | PASS |

**Verdict E2E-11-MANUAL : PASS.** Les quatre passages sont validés sans écart bloquant. Les captures assainies de la recette constituent la preuve visuelle ; elles ne contiennent ni donnée sensible ni secret.

## Règles de preuve

- Utilisez seulement `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` ou `N/A` dans le registre.
- Une capture comporte la date UTC, le rôle, l'organisation et la référence E2E ; elle ne contient ni mot de passe, cookie, jeton, contenu CSV brut ni donnée réelle.
- Notez les statuts HTTP, codes d'erreur et identifiants fictifs. Ne copiez pas les corps de réponses contenant des données CRM.
- `META-EXT-01` reste hors de cette recette : aucun compte Meta réel ni formulaire externe ne doit être utilisé.

## Clôture

Après `E2E-12`, reportez les résultats dans le CSV, relancez le verrou qualité complet dans votre PowerShell WSL et joignez les rapports générés. Tout P0 en `FAIL`, `BLOCKED` ou `NOT RUN` empêche le GO de Phase 4.
