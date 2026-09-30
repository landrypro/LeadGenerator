# Phase 4 — Pilotage et échanges

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 4 — Pilotage et échanges |
| Version | 2.5 — clôture locale 4.6 |
| Statut | Phase 4.6 clôturée localement avec GO produit le 30 septembre 2026 ; la preuve Azure sur le commit de clôture est requise avant l'entrée en phase 5 |
| Date | 30 septembre 2026 (UTC) |
| Prérequis acquis | Phase 3.4 clôturée avec réserves transférées ; verrou global vert sur `20260922_0021` |
| Source de périmètre | [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md), modules 8 et 9 et feuille de route de la phase 4 |

## 1. Objectif et frontière de phase

La phase 4 transforme les données CRM internes déjà suivies en indicateurs de pilotage et en échanges contrôlés. Elle
livre un tableau de bord, des exports internes, l’administration des imports, des rapports d’usage, un traitement
asynchrone fiable et le premier parcours de connecteur approuvé. Les tests de bout en bout prouvent que ces fonctions
cohabitent avec l’isolation des organisations, les permissions, la provenance et la conservation existantes.

La validation de ce cadrage fixe l’ordre et les principes des lots. Elle ne constitue pas un GO pour une migration, un
nouveau connecteur de production ou un déploiement. La phase 5 conserve la préproduction, la revue de
sécurité et juridique finale, les essais de charge/coûts, la facturation et le lancement progressif.

La clôture de 3.4 ne vaut pas clôture globale de la phase 3 : les lots 3.5 et 3.6 conservent leurs propres décisions
et preuves. Le démarrage de la conception 4 est possible en parallèle ; les dépendances de fin de phase 3 seront
vérifiées avant de déclarer un lot 4 livré ou de prononcer la recette finale 4.6.

## 2. Périmètre et séquence validée

| Lot | Résultat démontrable | Dépendances principales |
| --- | --- | --- |
| **4.1 — Tableau de bord** | Indicateurs CRM exacts, filtrés selon le rôle, la période, le fuseau et la devise | Pipeline 3.2, tâches 3.3, opportunités 3.4 |
| **4.2 — Worker et traitements fiables** | File de travaux, reprise, idempotence, supervision et nettoyage borné | PostgreSQL, Redis, audit et conservation existants |
| **4.3 — Exports et administration des imports** | Export à colonnes autorisées, téléchargement protégé et suivi des imports/quarantaines | 3.1 et 4.2 ; le contrat validé fait passer tous les exports par le worker |
| **4.4 — Quotas et rapports d’usage** | Compteurs explicables par utilisateur et organisation, limites serveur et vues autorisées | Mesures Google existantes, 4.1 et 4.2 |
| **4.5 — Fournisseurs et connecteur pilote** | Registre contractuel contrôlé et pilote Meta Lead Ads après revue préalable | Provenance/permission 2.5, 4.2, contrats et accès fournisseur |
| **4.6 — Recette de phase et tests de bout en bout** | Parcours complets, réserves reprises, sécurité et verrou qualité sans skip | Lots 4.1 à 4.5 effectivement autorisés et livrés |

Le découpage rend chaque lot testable. Une fonction de connecteur conditionnée à une approbation
externe ne peut pas être réputée livrée parce qu’un simulateur réussit : le pilote, ses prérequis externes et son
verdict doivent apparaître séparément dans le rapport de phase.

## 3. Invariants transversaux

1. Chaque lecture et chaque travail asynchrone porte explicitement l’organisation et applique l’isolation RLS et les
   capacités métier. Un identifiant d’une autre organisation ne révèle ni existence ni contenu.
2. Les contenus Google affichés en direct ne deviennent ni données de tableau de bord, ni colonnes d’export, ni
   matière d’un rapport d’usage. Seuls des compteurs techniques autorisés sont agrégés.
3. La provenance et l’attestation des droits demeurent attachées aux données importées. Une provenance ne crée jamais
   une permission de contact ; un canal inconnu reste `unknown` tant qu’une action autorisée ne change pas son état.
4. Les montants d’opportunité utilisent l’arithmétique décimale et restent séparés par devise ; aucun total combiné
   CAD/USD, taux implicite ou conversion automatique.
5. Les périodes métier utilisent le fuseau IANA de l’organisation. Les frontières de jour et les instants ambigus
   sont déterminés côté serveur ; l’interface formate en `fr-CA` ou `en-CA`.
6. Mutations, demandes de travaux et reprises portent les protections existantes : CSRF pour la session, autorisation
   serveur, idempotence, audit minimisé et absence d’écriture partielle.
7. Les exports et fichiers temporaires sont privés, de durée bornée, non indexés par le navigateur et exclus des
   journaux. Les réponses sensibles portent `Cache-Control: no-store`.
8. Toute nouvelle chaîne fonctionnelle est cataloguée en français canadien et en anglais canadien. Les états vides,
   erreurs, téléchargements et parcours clavier font partie de la recette.

## 4. Lot 4.1 — Tableau de bord

### 4.1.1 Indicateurs et règles de calcul

La V1 présente les indicateurs prévus par la spécification CRM : prospects actifs par étape ; tâches dues aujourd’hui
et en retard ; appels, rendez-vous et activités sur une période ; taux de passage entre étapes ; opportunités ouvertes,
gagnées et perdues ; montant brut et pondéré du pipeline par devise ; performance par commercial pour Administrateur
et Gestionnaire ; consommation Google par utilisateur et organisation.

Chaque carte doit définir dans le contrat 4.1 : population retenue, date de référence, période, unité, filtres, règle
de déduplication et règle d’absence de données. Le taux de passage exige une définition commune du numérateur, du
dénominateur et de la période de cohorte avant implémentation : un simple décompte des cartes actuelles ne mesure pas
une transition historique. Les indicateurs dérivés doivent pouvoir être rapprochés des lectures CRM autorisées.

Les tâches dues et en retard reposent sur leurs échéances et statuts. Une tâche terminée ou annulée ne compte pas
comme ouverte en retard. Les opportunités gagnées/perdues conservent leur cycle propre, indépendamment de l’étape du
prospect. Les montants et les valeurs pondérées sont regroupés par code de devise, avec précision décimale conservée.

### 4.1.2 Droits et interface

Le Commercial voit ses indicateurs personnels selon les règles de propriété déjà établies. L’Administrateur et le
Gestionnaire peuvent consulter le périmètre de leur organisation et une ventilation par commercial. Le changement de
rôle ou d’organisation invalide les données affichées ; une requête en retard ne doit pas réinjecter le contexte
précédent. Les cartes sont lisibles au clavier, à 200 %, sans dépendre d’une couleur seule, et disposent d’un libellé
et d’un état vide dans les deux langues.

La première version privilégie des agrégats serveur paginables/filtrables et des tableaux accessibles. Le choix d’une
visualisation graphique ne doit pas introduire une seconde logique de calcul ou masquer les valeurs exactes.

### 4.1.3 Critères de recette

- Deux organisations ayant des données distinctes n’obtiennent aucun total croisé, y compris lors d’un changement de
  session, d’un appel direct à l’API ou d’un travail asynchrone.
- Les totaux CAD et USD restent séparés et se rapprochent des opportunités autorisées ; les périodes chevauchant un
  changement d’heure utilisent le fuseau de l’organisation.
- Le Commercial ne peut obtenir les agrégats de l’équipe en modifiant un filtre ou un identifiant dans l’URL.
- Les données Google descriptives sont absentes des réponses et des exports du tableau de bord.

## 5. Lot 4.2 — Worker et traitements fiables

Le worker sert aux traitements qui ne doivent pas bloquer une requête HTTP : exports volumineux, reprise des imports,
connecteurs approuvés et travaux de maintenance/rappel explicitement activés. Le cycle d’un travail est traçable :
`queued`, `running`, `succeeded`, `failed` ou `cancelled`, avec identifiant, organisation, acteur ou origine système,
type, dates, tentative et résultat minimal. Une file Redis seule ne fait pas foi pour l’état métier durable : les
transitions nécessaires à l’idempotence et à l’audit sont persistées et testées après interruption du worker.

L’admission, la réservation, les reprises avec attente croissante, la limite de tentatives et la file d’échec doivent
être précisées par type de travail. Une reprise ne crée ni deuxième prospect, ni deuxième export autorisé, ni deuxième
événement d’import. Les secrets et données personnelles ne figurent pas dans le nom des travaux, leurs journaux ou
leurs métriques. Une licence expirée ou une révocation d’accès est revérifiée au moment d’exécuter un connecteur.

Le [contrat détaillé 4.2](PHASE_4_2_SPECIFICATIONS_DETAILLEES.md) fixe le modèle de déploiement, les durées de
conservation et les paramètres de reprise approuvés dans les décisions `P4.2-01` à `P4.2-08` le 23 septembre 2026.
Le GO d’implémentation a été donné le 23 septembre 2026 ; les preuves de réalisation sont suivies dans le
[`rapport 4.2`](PHASE_4_2_RAPPORT_IMPLEMENTATION.md). Le verrou qualité local 4.2 est VERT depuis le
24 septembre 2026 à 00:11 UTC. Les tests doivent couvrir l’arrêt pendant un
traitement, le redémarrage, le rejeu, une erreur permanente, la concurrence entre workers et le nettoyage des
fichiers temporaires. Les fichiers de sortie téléchargeables seront contractualisés avant activation en 4.3.

## 6. Lot 4.3 — Exports internes et administration des imports

### 6.1 Export

Un export est initié par une personne autorisée dans son organisation, avec périmètre, filtres et colonnes provenant
d’une liste blanche versionnée. La V1 couvre les prospects et coordonnées CRM internes ; étapes, responsables,
priorités, étiquettes ; et, selon les permissions, activités, tâches et opportunités. Les champs Google affichés en
direct et le `place_id` sont exclus. Chaque type de données a un schéma stable, un encodage et une représentation des
dates/devise documentés. Les valeurs susceptibles d’être interprétées comme des formules de tableur sont neutralisées
et vérifiées par test.

La demande et le téléchargement sont deux contrôles d’accès distincts. Le serveur revérifie organisation, capacité,
état de session et durée de validité du fichier au téléchargement. L’audit conserve auteur, date, catégorie de
données, filtres et volume, sans conserver le fichier ni les coordonnées exportées. Les limites de taille et durées
de conservation sont des décisions du contrat 4.3.

### 6.2 Administration des imports

La phase 4 étend la visibilité et la gestion des imports CSV livrés en 3.1 : état des lots, nombres acceptés/rejetés,
quarantaine, motifs et relance contrôlée. L’aperçu, la confirmation explicite, les permissions `unknown`, la
déduplication exacte et la suppression du fichier source restent obligatoires. Une action de relance doit prouver son
idempotence et ne peut pas requalifier silencieusement une source rejetée. Les droits de lecture, de correction et de
confirmation sont définis séparément avant implémentation.

### 6.3 Critères de recette

- Un utilisateur d’une autre organisation ne peut ni lister, ni télécharger, ni relancer un lot ou un export.
- Un export ne contient que les colonnes autorisées, même si le client envoie un nom de colonne supplémentaire.
- Les formules de tableur, les filtres de période, les refus de permission et l’expiration du fichier sont testés.
- L’import de rejeu conserve le même résultat métier, et les fichiers temporaires sont supprimés après succès et
  échec selon la durée retenue.

## 7. Lot 4.4 — Quotas et rapports d’usage

Les rapports distinguent usage technique, limite serveur et droit commercial futur. Ils présentent les compteurs
Google déjà autorisés par utilisateur et organisation, ainsi que les opérations de plateforme pertinentes, sans
exposer requêtes, réponses, lieux, coordonnées ou jetons. Une limite est appliquée côté serveur avant l’appel coûteux ;
une course concurrente ne doit pas dépasser le budget autorisé. La source du compteur, sa période, sa remise à zéro,
son fuseau et son unité sont visibles dans le contrat et dans l’interface.

Aucun prix, plan commercial, taxe ou paiement n’est créé par ce lot : ces décisions appartiennent à la phase 5.
Le rapport d’usage ne doit pas être confondu avec une facture. Les administrateurs consultent l’organisation ; le
Commercial ne voit que ses compteurs personnels si cette vue est autorisée. Les seuils chiffrés et la granularité
historique restent à valider sur des mesures de coûts réels.

## 8. Lot 4.5 — Registre des fournisseurs et connecteur pilote

Le registre existant de fournisseurs/sources est la source de vérité des droits : fournisseur, licence/contrat, durée,
territoire, catégories de données, finalités et état d’approbation. Un connecteur ne démarre que si la source, le
contrat, l’organisation et le périmètre de données sont admissibles. Une licence expirée bloque les nouvelles
synchronisations ; les données CRM déjà légalement conservées suivent leurs propres règles de rétention.

Meta Lead Ads est le candidat prioritaire, **conditionné** à la revue de l’application, aux permissions officielles,
aux conditions contractuelles et à un environnement de test autorisé. Le flux proposé reçoit un événement signé,
vérifie sa fraîcheur et son identité, l’enregistre de façon idempotente, puis le traite via 4.2. Les jetons sont
chiffrés, rotatifs et révocables ; aucune valeur secrète n’entre dans l’audit. Chaque champ persistant reçoit une
provenance et la permission de contact reste explicite. Les événements rejoués ou hors périmètre sont refusés sans
doublon. La configuration et la révocation sont réservées aux rôles autorisés.

La simulation technique du webhook est une preuve d’intégration, pas une autorisation d’activer un connecteur réel.
Toute autre API publique ou fournisseur B2B requiert sa propre revue. Scraping social et intégration indirecte non
approuvée restent exclus.

## 9. Lot 4.6 — Recette finale et qualité

Le dossier de recette doit relier chaque indicateur, export, import, quota et événement connecteur à une donnée
fictive connue et à une preuve d’isolation. Il rejoue les parcours essentiels de connexion, changement de rôle et
d’organisation, ajout d’un prospect, Kanban, tâche, opportunité gagnée/perdue, import, export et révocation d’un
connecteur. Les vues, erreurs et contenus sont contrôlés en `fr-CA` et `en-CA`, au clavier et à 200 %.

Chaque incrément passe son propre verrou qualité technique. Celui de 4.1 a été exécuté par le responsable produit le
23 septembre 2026 avec un résultat **VERT** : 313 tests backend et 193 tests frontend réussis sans skip, migrations
PostgreSQL reconstruites, contrôles statiques, build et inspection de l’artefact conformes. Le détail est consigné
dans le contrat 4.1. La recette fonctionnelle des incréments est menée ensemble à la fin de la phase 4 dans ce lot
4.6 ; la réussite du verrou 4.1 ne préjuge pas du verdict de cette recette.

Les réserves transférées de 3.4 restent cinq obligations nominatives dans cette recette :

| Réserve | Preuve de sortie attendue |
| --- | --- |
| `OPP-14-R1` (ancien identifiant `OPP-14-A`) | Sales A2 : `GET`, `PATCH` et transition interdits ; relecture Admin, version et événements inchangés |
| `OPP-03-R1` | Devise `ZZZ` refusée seule, erreur de champ précise et aucune écriture |
| `OPP-11-R1` | Saisie partielle d’une devise sans requêtes `415` ; filtre valide toujours fonctionnel |
| `OPP-17-C-R1` | Rapports axe exhaustifs des vues prévues en `fr-CA` et `en-CA`, anomalies suivies |
| `REG-31-33-R1` (scénarios `REG-31` à `REG-33`) | Import CSV, Kanban et chronologie/tâches rejoués et documentés |

Les identifiants de la première colonne sont ceux des réserves suivies dans
[`PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md) ; les identifiants entre parenthèses
désignent l’ancien identifiant ou les scénarios de recette, pas de nouvelles réserves.

Le verrou de sortie reconstruit les migrations sur PostgreSQL réel, lance les analyses statiques et tests backend/
frontend sans skip, les tests d’accessibilité, le build et l’inspection de l’artefact. Les scénarios dépendant d’une
approbation fournisseur sont marqués avec leur statut réel. Les réserves restantes ont un responsable, un risque,
une échéance et une décision produit explicite ; un contrôle reporté ne devient jamais `OK` par transfert.

## 10. Décisions produit validées

Le responsable produit a validé explicitement les huit décisions `P4-01` à `P4-08` le 23 septembre 2026 dans la tâche
de cadrage, puis les choix de conception du lot 4.1. Les paramètres qui exigent encore des mesures sont précisés dans
le contrat de chaque lot ; leur valeur n’est pas inventée par cette approbation.

| ID | Décision validée | Application |
| --- | --- | --- |
| `P4-01` | Ordre des lots | 4.1 tableau de bord, 4.2 worker, 4.3 exports/imports, 4.4 quotas, 4.5 pilote connecteur, 4.6 recette ; le worker précède les échanges longs |
| `P4-02` | Fenêtres et définition des indicateurs | Jour/semaine/mois dans le fuseau de l’organisation ; cohorte et règle de transition précisées et approuvées dans le contrat 4.1 |
| `P4-03` | Visibilité des performances et exports | Commercial : soi ; Gestionnaire/Admin : organisation ; capacités du tableau de bord précisées et approuvées en 4.1, capacités d’export à détailler en 4.3 |
| `P4-04` | Types, volume et durée des exports | CSV interne à schéma versionné en premier ; fixer plafonds et expiration après mesure du volume réel |
| `P4-05` | Frontière du worker | Travaux longs de 4.3 et 4.5 d’abord ; choisir stockage durable, politique de reprise et déploiement avant codage |
| `P4-06` | Granularité et seuils des quotas | Compteurs par utilisateur et organisation ; seuils après mesure de coûts, sans introduire les plans SaaS de phase 5 |
| `P4-07` | Condition d’entrée de Meta Lead Ads | Pilote uniquement après revue de l’application, contrat, permissions officielles et données de test autorisées |
| `P4-08` | Porte de sortie | Recette globale et réserves transférées démontrées ; décision distincte si un prérequis externe bloque le connecteur |

Le contrat **4.1 — Tableau de bord** consigne les choix de conception approuvés et le GO d’implémentation donné par
le responsable produit le 23 septembre 2026, ainsi que les paramètres opérationnels retenus :
[`PHASE_4_1_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_1_SPECIFICATIONS_DETAILLEES.md). Le verrou qualité technique
de 4.1 est VERT et sa recette fonctionnelle relève du lot 4.6. Les paramètres 4.2 sont validés dans son contrat ;
les plafonds initiaux 4.3 sont approuvés et la volumétrie QA mesurée est documentée dans le contrat 4.3.

Le contrat détaillé du lot **4.3 — Exports internes et administration des imports** est disponible dans
[`PHASE_4_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_3_SPECIFICATIONS_DETAILLEES.md). Ses décisions `P4.3-01` à
`P4.3-08`, y compris les plafonds opérationnels initiaux, ont été validées par le responsable produit le
24 septembre 2026. La mesure QA exécutée le même jour compte quatre organisations actives, trois prospects et
une opportunité ; elle est trop petite pour valider les plafonds à grande échelle. Le GO d’implémentation 4.3 a été
donné le 24 septembre 2026 et le verrou qualité local est VERT sur la révision `20260924_0023`. La décision
`P4.3-04` précise `P4-04` : les plafonds conservateurs restent approuvés après cette mesure ; tout changement demandera
une nouvelle validation. La qualification synthétique proche des limites reste distincte de cette petite mesure QA.

Le contrat détaillé du lot **4.4 — Quotas et rapports d’usage** est disponible dans
[`PHASE_4_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_4_SPECIFICATIONS_DETAILLEES.md). Les décisions
`P4.4-01` à `P4.4-08` et le GO d’implémentation 4.4 ont été validés explicitement par le responsable produit le
24 septembre 2026. L’implémentation est réalisée et son verrou qualité complet est VERT ; les preuves sont consignées
dans [`PHASE_4_4_RAPPORT_IMPLEMENTATION.md`](PHASE_4_4_RAPPORT_IMPLEMENTATION.md).

Le contrat détaillé du lot **4.5 — Fournisseurs et connecteur pilote** est disponible dans
[`PHASE_4_5_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_5_SPECIFICATIONS_DETAILLEES.md). Ses décisions `P4.5-01` à
`P4.5-08` et son GO d’implémentation ont été validés explicitement par le responsable produit le 24 septembre 2026.
L’implémentation est réalisée et le verrou local est VERT sur `20260924_0025` depuis le 25 septembre 2026 UTC. Le
contrat distingue explicitement le verrou technique de l’incrément, l’autorisation interne, l’approbation Meta et
l’essai sur environnement autorisé.

Le contrat du lot **4.6 — Recette de phase et tests de bout en bout** est disponible dans
[`PHASE_4_6_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_6_SPECIFICATIONS_DETAILLEES.md). Il définit les parcours
transversaux, la levée obligatoire des cinq réserves de 3.4, la porte de sécurité, les preuves sans skip et trois
verdicts distincts pour la phase, le pilote Meta technique et son activation réelle. Ses décisions `P4.6-01` à
`P4.6-08` ont été validées explicitement par le responsable produit le 25 septembre 2026. Le GO d’implémentation
a été donné le 25 septembre 2026 ; l’implémentation et les preuves sont suivies dans
[`PHASE_4_6_RAPPORT_IMPLEMENTATION.md`](PHASE_4_6_RAPPORT_IMPLEMENTATION.md). Le verdict de recette et
l’autorisation Meta restent séparés. Le verrou qualité local de la tête `20260925_0026` est VERT.
