# Analyse croisée — Étape interne 2 et socle des Phases 1 à 4

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Objet | Vérifier la cohérence produit de l’Étape interne 2 avec le socle conçu et livré des Phases 1 à 4 |
| Étape évaluée | Étape interne 2 — Conception fonctionnelle et UX |
| Porte visée | Porte 2 — Désirabilité et clarté |
| Date de référence | 30 septembre 2026 |
| Verdict produit | **Porte 2 : GO avec réserves** ; Étape 3 de conception technique autorisée ; aucun GO de production |
| Décision Vague A | Contre-validée avec réserves transférées ; `P2-PRE3-01` reportée à la clôture de la Phase 5 |
| Document d’étape | [Étape 2 — Conception fonctionnelle et UX](./ETAPE_2_CONCEPTION_FONCTIONNELLE_UX.md) |
| Prototype | [Prototype cliquable du parcours Nouveau prospect](./PROTOTYPE_CLIQUABLE_ETAPE_2.html) |
| Livrables Vague A | [Dix décisions produit approuvées et contre-validées](./VAGUE_A_FONDATIONS_DECISION.md) |
| Rapport de contre-validation | [Avis Design, Ingénierie, Confiance, Sécurité et Qualité](./CONTRE_VALIDATIONS_VAGUE_A.md) |
| Dossier Vague B | [Produit entièrement testable : cycles, erreurs, prototype, playbooks et preuves](./VAGUE_B_PRODUIT_TESTABLE.md) |
| Décision de sortie | [Porte 2 — GO avec réserves](./PORTE_2_GO_AVEC_RESERVES.md) |
| Référence transmise | [`RF-AUT-2.1` — référence fonctionnelle figée](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) |
| Étape au moment de l’analyse | [Étape 3 — Architecture, données et sécurité](./ETAPE_3_ARCHITECTURE_DONNEES_SECURITE.md) |
| État consolidé actuel | Porte 3 `GO conditionnel` ; [Étape 4 — Plan de livraison et protocole de validation](./ETAPE_4_PLAN_LIVRAISON_VALIDATION.md) autorisée |

## 1. Décision exécutive

L’Étape interne 2 est cohérente avec la trajectoire produit construite depuis la Phase 1. Elle transforme les actifs existants du CRM — provenance, permissions, membres, prospects, tâches, opportunités, worker, audit et rapports d’usage — en une expérience d’automatisation guidée. Elle ne nécessite pas de reconstruire un deuxième CRM.

La direction produit est donc confirmée :

- le **Passeport de prise en charge** agrège des preuves déjà présentes ;
- le **Feu relationnel** interprète des permissions et contraintes existantes sans en inventer ;
- le **Copilote « Aujourd’hui »** priorise les tâches, échéances et exceptions du CRM ;
- les **playbooks** commandent les cas d’usage CRM existants avec des règles, versions et limites nouvelles ;
- le **Prévol** rend les effets compréhensibles avant activation ;
- les **brouillons et approbations** ajoutent un contrôle humain sans prétendre qu’un service d’envoi général existe déjà.

Les actions des Vagues A et B, puis la recette V2.1, ont fermé les conditions fonctionnelles nécessaires à la décision. La compréhension sans accompagnement par des PME demeure non démontrée et est acceptée comme réserve post-production. Les contrats techniques, la sécurité et les contrôles d’effets restent à établir à l’Étape 3.

La décision actualisée est donc :

1. clôturer l’Étape 2 sur la référence fonctionnelle V2.1 ;
2. ouvrir l’Étape 3 pour la conception de l’architecture, des données et de la sécurité ;
3. conserver les sessions PME comme réserve post-production obligatoire avant tout élargissement du périmètre initial ;
4. conserver la preuve Azure 4.6 comme réserve obligatoire à la clôture de la Phase 5 ;
5. maintenir un `NO-GO` sur le développement actif, les effets réels et la production jusqu’aux portes ultérieures.

## 2. Sources de vérité utilisées

L’analyse s’appuie sur les éléments suivants :

- [Phase 1.1 — Sources d’acquisition et règles de conservation](../PHASE_1_1_ACQUISITION_CONSERVATION.md) ;
- [Phase 2 — Fondations CRM](../PHASE_2_SPECIFICATIONS_DETAILLEES.md) et ses rapports d’implémentation ;
- [Phase 3 — Cœur CRM](../PHASE_3_SPECIFICATIONS_DETAILLEES.md) et les rapports des lots 3.1 à 3.4 ;
- [Phase 4 — Pilotage et échanges](../PHASE_4_SPECIFICATIONS_DETAILLEES.md) ;
- [Rapport d’implémentation 4.6](../PHASE_4_6_RAPPORT_IMPLEMENTATION.md) ;
- le modèle de domaine et la navigation réellement présents dans le dépôt ;
- le [document fonctionnel de l’Étape 2](./ETAPE_2_CONCEPTION_FONCTIONNELLE_UX.md) ;
- le [prototype cliquable](./PROTOTYPE_CLIQUABLE_ETAPE_2.html).

En cas de divergence entre une intention ancienne et le socle réalisé, le modèle et les contrats livrés jusqu’en Phase 4.6 prévalent pour la conception de l’Automatisation, sauf décision produit explicite de réouverture.

## 3. Lecture produit des Phases 1 à 4

### 3.1 Phase 1 — Gouvernance de l’acquisition

La Phase 1 a séparé quatre notions essentielles :

1. découvrir une organisation ;
2. créer une référence de prospect ;
3. conserver une donnée avec sa provenance ;
4. être autorisé à contacter une personne ou une organisation sur un canal précis.

Elle a également posé :

- les sources admissibles ;
- la quarantaine des sources inconnues ou insuffisamment justifiées ;
- la provenance obligatoire ;
- la déduplication exacte et la fusion contrôlée ;
- la priorité des oppositions ;
- les règles de conservation et de suppression ;
- la limitation particulière des données Google.

**Conséquence pour l’Étape 2 :** le Feu relationnel ne peut jamais déduire une autorisation du seul fait qu’un prospect existe ou qu’une coordonnée est publique. Le Passeport doit distinguer source, provenance, permission, finalité et restrictions. Un type de source reconnu ne prouve pas qu’un connecteur est disponible.

### 3.2 Phase 2 — Plateforme CRM sécurisée

La Phase 2 a établi :

- PostgreSQL comme source de vérité ;
- les organisations et leur isolation ;
- les rôles `admin`, `manager` et `sales` ;
- les capacités vérifiées côté serveur ;
- les appartenances actives ;
- les sessions, CSRF et protections de connexion ;
- la provenance, les permissions, les fournisseurs et la rétention ;
- l’audit append-only et minimisé ;
- Redis pour les protections partagées, verrous, jetons et quotas ;
- l’observabilité sans contenu personnel ou fournisseur sensible.

**Conséquence pour l’Étape 2 :** l’Automatisation reste locataire du même contexte d’organisation et de la même matrice de rôles. Elle ajoute des capacités explicites ; elle ne crée pas de rôle « IA », « Automatisation » ou « Confiance » en V1. Une affectation cible une appartenance active, jamais une équipe fictive ou une chaîne libre.

### 3.3 Phase 3 — Cœur opérationnel du CRM

La Phase 3 a livré ou clôturé avec les preuves reprises ensuite en Phase 4 :

- l’import CSV avec déclaration, aperçu, confirmation, idempotence et quarantaine ;
- le portefeuille de prospects et le pipeline ;
- les activités, tâches, rappels et prochaines actions ;
- les opportunités, leur cycle, leur responsable et leurs événements ;
- la concurrence optimiste, les transitions contrôlées et l’audit métier ;
- les interfaces de consultation et d’action correspondantes.

**Conséquence pour l’Étape 2 :** une tâche créée par un playbook est une tâche CRM. Une opportunité suivie par « Proposition en attente » ou « Occasion oubliée » reste l’opportunité canonique. Le pipeline prospect et le cycle d’opportunité demeurent distincts. Le Copilote ne possède pas son propre registre de tâches.

### 3.4 Phase 4 — Pilotage, fiabilité et échanges

La Phase 4 a ajouté :

- un tableau de bord fondé sur les objets CRM ;
- un worker durable avec idempotence, reprise, bail, tentatives et suivi ;
- les exports internes et l’administration des imports ;
- un registre d’usage et des rapports non facturants ;
- le registre des fournisseurs ;
- un pilote Meta Lead Ads techniquement vérifié avec doubles locaux ;
- la recette transversale, l’accessibilité et les parcours bilingues.

La Phase 4.6 possède un GO de clôture locale et un verrou local vert. Deux limites demeurent :

- l’activation Meta réelle reste bloquée par les prérequis externes ;
- la preuve Azure du commit de clôture reste requise pour le verdict global du socle ; par décision produit du 30 septembre 2026, son exécution est reportée à la clôture de la Phase 5.

**Conséquence pour l’Étape 2 :** le moteur de playbooks devra prolonger le worker durable, le registre d’usage, l’audit et les contrôles d’admission existants. Il ne doit pas introduire une file parallèle. Facebook/Meta peut être représenté comme source reconnue et pilote conditionnel ; LinkedIn et le webhook générique ne sont pas livrés.

## 4. Matrice de cohérence croisée

| Capacité de l’Étape 2 | Ancrage Phases 1–4 | Réutilisation obligatoire | Nouvelle capacité réelle | Décision produit |
| --- | --- | --- | --- | --- |
| Démarrage Automatisation | Navigation et rôles existants | Session, organisation active, capacités, coque applicative | Route, Assistant encadré et onboarding Automatisation | Placer Automatisation après Tableau de bord et faire d’Aujourd’hui l’unique point d’entrée d’une intention utilisateur |
| Prospect test | Aucun objet client réel nécessaire | Formes et règles du parcours | Jeu de démonstration isolé et réinitialisable | Ne jamais mélanger ses données avec le CRM de l’organisation |
| Ajout manuel | Prospect et provenance manuelle | Cas d’usage de création existant | Déclenchement du playbook sur événement admis | Doit pouvoir alimenter Nouveau prospect |
| Ajout Google | Sélection Google et `place_id` | Création idempotente et interdiction de persister le descriptif Google | Déclenchement après création de la référence | Permission de contact initialement prudente ; ne pas copier les coordonnées Google |
| Import CSV | Import 3.1 et administration 4.3 | Déclaration, aperçu, confirmation, doublons, quarantaine | Émission du déclencheur après confirmation | L’onboarding doit rediriger vers l’import existant, pas le recréer |
| Meta/Facebook | Registre fournisseurs et pilote 4.5 | Admission signée, provenance, worker, usage, arrêt d’urgence | Activation externe et paramètres Automatisation | Afficher le statut réel ; ne pas déclarer le connecteur actif sans approbation |
| LinkedIn | Type de source et canal reconnus | Modèle de provenance et permission | Connecteur, contrat et autorisations externes | Différé ; jamais présenté comme livré |
| Formulaire Web/API | Provenance `api`, acquisitions et worker | Fournisseur, acquisition, permission, idempotence | Formulaire, contrat d’entrée et authentification | Nouvelle capacité V1 potentielle, à contractualiser |
| Webhook générique | Patron du webhook Meta | Signature, fraîcheur, déduplication, worker, audit | Contrat générique et gestion des secrets | Nouvelle capacité ; ne pas assimiler au webhook Meta |
| Boîte d’entrée prospects | Prospects, imports, quarantaine, sources | Objets et statuts existants | Projection unifiée et actions de résolution | Ne crée aucun second portefeuille |
| Passeport | Provenance, permission, responsable, tâche | Agrégats CRM existants | Projection et explication consolidées | Doit être accessible depuis la fiche prospect et le Copilote |
| Feu relationnel | Permissions et restrictions existantes | Statuts, dates, finalité, opposition | Règles de calcul et explications versionnées | Déterministe ; Vert n’est jamais une garantie juridique |
| Copilote Aujourd’hui | Tâches, prochaines actions, pipeline, tableau de bord | Lectures CRM et droits existants | Priorisation explicable et limite de cartes | À intégrer au Tableau de bord ou à Automatisation sans seconde liste de tâches |
| Nouveau prospect | Prospect, responsable, tâches, échéances | Cas d’usage CRM et clés d’idempotence | Déclencheur, version, règles et exécution | Playbook de référence, indépendant de la source |
| Proposition en attente | Opportunité et événements | Étape `proposal`, responsable, activités | Détection d’attente et règles de relance | L’opportunité reste canonique ; aucun changement silencieux du pipeline prospect |
| Occasion oubliée | Opportunité, tâches, activités | États ouverts et échéances | Détection d’inactivité et priorisation | Ne ferme ni ne déplace automatiquement l’occasion en V1 Lite |
| Prévol | Worker, audit et cas d’usage CRM | Même validation déterministe que l’exécution | Simulation, résultat et comparaison de version | Aucun effet métier ; mêmes règles que l’exécution réelle |
| Brouillon | Activités de type courriel et permissions | Destinataire, canal, permission et contexte | Objet de brouillon versionné | Aucun envoi autonome en V1 |
| Approbation | Identité, capacités et audit | Approbateur actif et audit minimisé | Décision, expiration, invalidation et refus | Porte sur une action et un contenu précis |
| Suspension | Arrêt du binding Meta comme patron | Autorisation, audit et prévention de nouvel effet | Suspension de playbook et reprise contrôlée | Doit être trouvable et testée avant la Porte 2 |
| Usage et coûts | Registre d’usage 4.4 | Contrats fermés et agrégats locataires | Codes d’événements Automatisation | Étendre le registre existant, sans présenter une facture |
| Assistance IA | Aucun moteur métier requis | Contexte autorisé, masquage et audit | Résumé, rédaction ou explication facultative | Ne décide jamais permission, opposition, attribution ou autonomie |

## 5. Forces confirmées de l’Étape 2

### 5.1 Une promesse compréhensible

« Chaque prospect pris en charge. Chaque suivi maîtrisé. » traduit le bénéfice en résultat PME. La proposition évite de vendre un moteur abstrait ou des agents à configurer.

### 5.2 Une démarcation crédible

La combinaison Assistant IA encadré, Passeport, Feu relationnel, Prévol et Copilote crée une expérience distincte des constructeurs de workflows génériques. L’utilisateur dispose d’un seul endroit pour exprimer son objectif ; Marketteo le convertit en plan explicable et le rattache aux recettes autorisées. L’expérience vend ainsi la confiance et la clarté, pas seulement l’automatisation.

### 5.3 Une portée Lite protégée

Le noyau limite les capacités visibles, les paramètres et l’autonomie. Il privilégie trois playbooks guidés et refuse l’envoi externe autonome.

### 5.4 Une continuité avec le CRM

Le document d’Étape 2 interdit explicitement la duplication des prospects, tâches, opportunités, permissions et audits. Cette contrainte est conforme au socle livré.

### 5.5 Une stratégie de sources réaliste

La valeur peut être démontrée avec un prospect test et les sources existantes. Elle ne dépend ni de Meta réel, ni de LinkedIn, ni d’un fournisseur d’IA.

## 6. Écarts à fermer avant l’Étape 3

### 6.1 Intégration UX au produit réel

Le prototype cible emploie une navigation interne « Aujourd’hui / Entrées et exceptions / Playbooks ». `Aujourd’hui` porte l’Assistant IA encadré, unique point d’entrée pour une nouvelle intention utilisateur. `Playbooks` et `Entrées et exceptions` restent des surfaces de contrôle et de résolution. L’application actuelle possède déjà Tableau de bord, Tâches, Prospects, Pipeline, Opportunités, Imports, Sources et Audit. Les sources restent un domaine existant : leur diagnostic est accessible dans le contexte d’une exception, sans menu Sources autonome dans Automatisation.

**Risque :** créer un deuxième espace opérationnel obligeant l’utilisateur à vérifier deux listes de tâches, deux boîtes d’entrée ou deux historiques.

### 6.2 Déclenchement incomplet par rapport aux sources existantes

Le prototype met en avant prospect test, CSV, Web et webhook. Les parcours manuels, Google et Meta déjà présents dans le socle doivent être inclus dans le contrat du playbook Nouveau prospect.

**Risque :** une PME utilisant les fonctions actuelles ne bénéficierait pas de l’Automatisation sans changer son processus d’acquisition.

### 6.3 Contrats fonctionnels encore ouverts

Les cycles de vie de playbook, version, simulation, exécution, brouillon, approbation, suspension, exception et explication ne sont pas encore assez gelés pour guider un schéma de données ou une API.

**Risque :** l’architecture choisirait prématurément des objets et transitions que le produit n’a pas validés.

### 6.4 Suspension représentée dans la V2.1

Le prototype V2.1 démontre la suspension et la reprise des Playbooks et annonce la conservation des tâches et de l’historique. Les garanties de persistance, d’idempotence et de non-répétition des effets sont transférées à la conception technique de l’Étape 3.

### 6.5 Validation limitée à un seul playbook observable

Nouveau prospect est démontré. Proposition en attente et Occasion oubliée disposent de spécifications, mais leur valeur, leurs paramètres Lite et leur vocabulaire doivent au minimum être testés sous forme de cartes ou de scénarios.

### 6.6 Recherche utilisateur non réalisée

La validation statique confirme le fonctionnement du fichier, pas la compréhension par une PME. Le vocabulaire Prévol, Préparer, Feu, Passeport et approbation doit être observé sans accompagnement.

### 6.7 Capacités et mandats non gelés

Les rôles restent correctement limités à `admin`, `manager` et `sales`, mais les capacités pour configurer, prévisualiser, activer, suspendre et approuver ne sont pas décidées.

### 6.8 Preuve globale du socle

Le verrou local 4.6 est vert. La preuve Azure manque encore pour le verdict global. Par décision produit du 30 septembre 2026, elle devient une réserve acceptée jusqu’à la clôture de la Phase 5. Elle ne bloque plus les travaux de conception, l’ouverture de l’Étape 3 ni la construction ultérieure autorisée par les portes du programme. Elle bloque toutefois le verdict final de la Phase 5 et toute affirmation que la chaîne CI de clôture est prouvée.

## 7. Plan d’actions concret avant l’Étape 3

Les actions ci-dessous constituent le chemin obligatoire vers la Porte 2. Les identifiants `P2-PRE3-*` doivent être utilisés dans le journal de décision et le dossier de porte.

| ID | Action concrète | Responsable principal | Livrable ou preuve | Condition de clôture | Bloque l’Étape 3 |
| --- | --- | --- | --- | --- | --- |
| `P2-PRE3-01` | Reporter la preuve Azure 4.6 à la clôture de la Phase 5 et figer immédiatement la référence locale 4.6 | Ingénierie / Qualité | Décision de report, révision locale de référence et preuve Azure finale avec JUnit archivées | Référence locale 4.6 consignée maintenant ; pipeline Azure vert sur la révision de clôture de la Phase 5 avant verdict final | Non pour l’Étape 3 ; oui pour la clôture de la Phase 5 |
| `P2-PRE3-02` | Produire la matrice détaillée Écran → Action → Objet CRM → Cas d’usage/API → Capacité → Audit | Produit / Ingénierie | Matrice de traçabilité P1–P4 | Aucune action du prototype sans ancrage ou étiquette « nouvelle capacité » | Oui |
| `P2-PRE3-03` | Décider l’architecture de navigation fonctionnelle | Produit / Design | Carte d’information approuvée | Automatisation placée dans la coque actuelle ; aucun doublon avec Tableau de bord, Tâches, Prospects ou Imports | Oui |
| `P2-PRE3-04` | Geler le contrat fonctionnel des sources et déclencheurs | Produit / Confiance | Tableau par origine : manuel, Google, CSV, Meta, Web/API, webhook | Événement d’admission, règle de doublon, permission initiale et statut de disponibilité définis pour chaque source | Oui |
| `P2-PRE3-05` | Produire la matrice détaillée du Feu relationnel | Produit / Confiance | Table de décision Vert/Jaune/Rouge | Priorité des oppositions, données inconnues, expiration, conflit et canal définie avec explication attendue | Oui |
| `P2-PRE3-06` | Geler les cycles de vie fonctionnels | Produit / Ingénierie | Diagrammes d’états playbook, Prévol, exécution, brouillon, approbation, suspension et exception | États, transitions, acteurs, effets et invariants approuvés | Oui |
| `P2-PRE3-07` | Décider la matrice des capacités Automatisation | Produit / Confiance / Sécurité | Matrice `admin` / `manager` / `sales` | Consulter, configurer, prévisualiser, activer, suspendre et approuver ont chacun une capacité et un périmètre | Oui |
| `P2-PRE3-08` | Compléter le catalogue des erreurs, blocages et récupérations | Produit / Design / Qualité | Catalogue bilingue des états | Chaque échec indique ce qui s’est passé, ce qui n’a pas été fait et la prochaine action possible | Oui |
| `P2-PRE3-09` | Mettre à jour le prototype en V2 intégré | Design / Produit | Prototype cliquable V2 | Coque réelle, liens CRM, suspension, reprise, source déconnectée, membre inactif, doublon/quarantaine et approbation démontrés | Oui |
| `P2-PRE3-10` | Représenter les deux autres playbooks | Produit / Design | Cartes et scénarios Proposition en attente / Occasion oubliée | Déclencheur, paramètres Lite, Prévol, résultat et exception compréhensibles | Oui pour la Porte 2 |
| `P2-PRE3-11` | Finaliser les scénarios d’acceptation et la télémétrie | Produit / Qualité / Données | Catalogue de scénarios et événements | Mesures de réussite, abandon, suspension, approbation, blocage et première valeur définies sans données excessives | Oui |
| `P2-PRE3-12` | Conduire les sessions de recherche PME après la mise en production | Design / Produit | Notes, mesures et rapport de recherche post-production | Parcours observés sans accompagnement ; profils et résultats consignés | Non pour l’Étape 3 par décision Produit ; oui pour lever la réserve et élargir le déploiement |
| `P2-PRE3-13` | Corriger les problèmes critiques ou élevés révélés par les sessions | Produit / Design | Produit, prototype et spécifications corrigés | Aucun problème critique ; tout problème élevé corrigé ou décision de suspension documentée | Non pour l’Étape 3 ; conditionne l’élargissement post-production |
| `P2-PRE3-14` | Faire la revue d’intégration Ingénierie / Qualité / Confiance | Responsable de l’étape | Procès-verbal de revue | Absence de registre parallèle, faisabilité reconnue et risques techniques transmis explicitement | Oui |
| `P2-PRE3-15` | Assembler et faire approuver le dossier de Porte 2 | Responsable de l’étape | Dossier de décision | Critères évalués, preuves liées, risques résiduels acceptés et décision formelle enregistrée | Oui |

## 8. Ordonnancement recommandé

### Vague A — Sécuriser les fondations de décision

À réaliser en premier :

- `P2-PRE3-01` — report formalisé de la preuve Azure 4.6 et gel de la référence locale ;
- `P2-PRE3-02` — traçabilité détaillée ;
- `P2-PRE3-03` — navigation ;
- `P2-PRE3-04` — sources et déclencheurs ;
- `P2-PRE3-05` — Feu relationnel ;
- `P2-PRE3-07` — capacités.

La décision de report de la preuve Azure est actée. Son absence ne bloque plus les tests du prototype, l’ouverture de l’Étape 3 ni les travaux ultérieurement autorisés par les portes du programme. La révision locale 4.6 demeure la référence de départ. La preuve Azure devra être exécutée sur la révision de clôture de la Phase 5, inclure la non-régression du socle 4.6 et être verte avant tout verdict final de cette phase.

#### État d’autorisation de la Vague A

| Action | État après contre-validation | Prochaine preuve |
| --- | --- | --- |
| `P2-PRE3-01` | Décision clôturée ; preuve différée et réserve non bloquante pour l’Étape 3 | Référence locale consignée dans le dossier Vague A ; preuve Azure à la clôture de la Phase 5 |
| `P2-PRE3-02` | Contre-validée avec réserves d’implémentation transférées | Corrélation structurée, registres fermés et acteur technique à concevoir à l’Étape 3 |
| `P2-PRE3-03` | Contre-validée avec réserve mobile | Accès par `Plus`, routes imbriquées et focus à prouver dans le prototype V2 |
| `P2-PRE3-04` | Contre-validée | Déclencheur transactionnel/idempotent à concevoir à l’Étape 3 |
| `P2-PRE3-05` | Contre-validée après séparation stricte du Feu et des exceptions opérationnelles | Scénarios `CV-QA-07` à `CV-QA-15` à exécuter avant la Porte 2 |
| `P2-PRE3-07` | Contre-validée avec contrôles Sécurité bloquants pour l’implémentation | Double autorisation, empreinte d’approbation et modèle de menace à prouver à l’Étape 3 |

### Vague B — Rendre le produit entièrement testable

**État :** `GO` Produit reçu et livrables élaborés. La recette V2.1 est validée par le responsable Produit. La validation PME est transférée après la mise en production et reste une réserve non levée.

Après les décisions de la vague A :

- `P2-PRE3-06` — cycles de vie ;
- `P2-PRE3-08` — erreurs et récupération ;
- `P2-PRE3-09` — prototype V2 ;
- `P2-PRE3-10` — représentation des deux autres playbooks ;
- `P2-PRE3-11` — acceptation et télémétrie.

### Vague C — Produire après la mise en production les preuves de désirabilité et de clarté

- `P2-PRE3-12` — sessions PME ;
- `P2-PRE3-13` — corrections ;
- rejeu des scénarios critiques après correction.

### Vague D — Fermer l’Étape 2

- `P2-PRE3-14` — revue croisée ;
- `P2-PRE3-15` — dossier de Porte 2 ;
- décision `GO`, `GO avec réserves` ou `NO-GO` ;
- mise à jour de la boussole et du journal de décision.

## 9. Décisions produit recommandées à prendre maintenant

### 9.1 Navigation

**Recommandation :** ajouter **Automatisation** immédiatement après **Tableau de bord** dans la navigation principale. À l’intérieur, limiter le premier niveau à :

- Aujourd’hui — point d’entrée utilisateur unique et priorités ;
- Playbooks — consultation, Prévol, activation et suspension ;
- Entrées et exceptions — résolution des blocages.

Ces vues doivent fournir des liens profonds vers les fiches Prospect, Tâche, Opportunité, Import et réglages d’intégration existants. Elles ne remplacent pas ces pages. Aucun autre écran ne doit offrir une création générique d’automatisation ou un second champ d’intention.

### 9.2 Déclencheur de Nouveau prospect

**Recommandation :** rendre le playbook indépendant de la source. Il s’applique à tout prospect nouvellement admis après création ou confirmation, selon une politique configurée par source. La permission et le Feu peuvent varier ; le playbook ne change pas de définition.

### 9.3 Mode initial

**Recommandation :** conserver `Préparer` comme unique mode d’activation du noyau Lite. Les actions internes réversibles peuvent être produites selon les capacités ; les communications externes restent soumises à approbation.

### 9.4 Suspension

**Recommandation :** une suspension interdit toute nouvelle exécution du playbook, mais ne supprime ni ne termine silencieusement les tâches déjà créées. Celles-ci restent visibles avec leur origine et peuvent être annulées manuellement selon les droits.

### 9.5 Boîte d’entrée

**Recommandation :** renommer la surface en **Entrées et exceptions** si les tests montrent que « Boîte d’entrée prospects » est confondue avec le portefeuille Prospects. Elle doit agréger les cas à traiter, pas répliquer tous les prospects.

### 9.6 Autres playbooks

**Recommandation :** ne pas construire immédiatement deux prototypes complets. Tester d’abord leurs cartes, déclencheurs, Prévol et exceptions dans le même prototype V2. Détailler leur parcours complet après validation des mécanismes communs de Nouveau prospect.

## 10. Périmètre autorisé par le `GO` de Porte 2

### Autorisé

- documents fonctionnels ;
- matrices de règles et de rôles ;
- prototype HTML ou maquettes ;
- recherche utilisateur ;
- jeux de données fictifs ;
- revue de faisabilité ;
- contrats conceptuels d’événements et d’API non engageants ;
- estimation de coût et de performance.

### Non autorisé comme engagement de production

- migration de données Automatisation ;
- ajout d’un moteur de playbooks dans le produit actif ;
- nouveau registre parallèle de prospects, tâches ou audit ;
- activation réelle Meta ou LinkedIn ;
- webhook générique exposé publiquement ;
- service d’envoi externe ;
- délégation d’une décision de permission à l’IA ;
- promesse commerciale d’une capacité non validée.

## 11. Définition de préparation à l’Étape 3

L’Étape interne 3 — Architecture, données et sécurité peut être ouverte uniquement si toutes les affirmations suivantes sont vraies et reliées à une preuve :

- [x] la Porte 2 possède une décision formelle [`GO avec réserves`](./PORTE_2_GO_AVEC_RESERVES.md) ;
- [x] la recette V2.1 est validée et ses contrôles applicables sont documentés ;
- [x] le report des sessions PME possède les responsables Produit/Design, un périmètre initial contrôlé et le jalon « avant tout élargissement » ;
- [x] la cible de première valeur sous dix minutes est définie et demeure à mesurer en post-production ;
- [x] l’intégration à la navigation et aux pages CRM existantes est approuvée ;
- [x] toutes les sources existantes ou futures sont classées comme livrées, conditionnelles, nouvelles ou différées ;
- [x] le playbook Nouveau prospect est indépendant de la source ;
- [x] les trois playbooks ont des critères d’acceptation et une proposition de valeur testable ;
- [x] la matrice du Feu est approuvée ;
- [x] les cycles de vie fonctionnels sont gelés au niveau fonctionnel ;
- [x] la suspension et la reprise sont visibles et comprises dans la recette V2.1 ;
- [x] la matrice des capacités est approuvée ;
- [x] aucun écran ou objet ne crée un second registre CRM ;
- [x] les scénarios critiques et les exceptions sont représentés ;
- [x] le plan de télémétrie et les limites de données sont définis ;
- [x] aucun défaut critique connu de la recette n’est ouvert ; les problèmes issus de la recherche post-production déclenchent suspension ou correction ;
- [x] les risques élevés restants possèdent un responsable et une décision dans le dossier de Porte 2 ;
- [x] Produit, Design, Ingénierie, Qualité et Confiance ont contribué aux contre-validations et au paquet transféré ;
- [x] le report de la preuve Azure 4.6 est formellement consigné ; la preuve est obligatoire avant la clôture de la Phase 5, et non avant l’Étape 3.

La liste est satisfaite pour l’ouverture de la conception technique. Les réserves `P2-RSV-01` et `P2-RSV-02` demeurent actives selon leurs propres jalons. Cette préparation ne permet pas de démarrer une migration ou une implémentation structurelle sous couvert de l’Étape 3.

## 12. Paquet d’entrée remis à l’Étape 3

Après `GO`, le dossier transmis à l’architecture devra contenir :

1. référence fonctionnelle [`RF-AUT-2.1`](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md), prototype approuvé, recette V2.1 et protocole de recherche post-production sous réserve `P2-RSV-01` ;
2. carte de navigation et inventaire consolidé des surfaces ;
3. matrice de traçabilité Phases 1–4 ;
4. contrats fonctionnels des trois playbooks ;
5. matrice du Feu relationnel ;
6. cycles de vie et diagrammes d’états ;
7. matrice des rôles et capacités ;
8. catalogue des erreurs, explications et récupérations ;
9. scénarios d’acceptation et scénarios sentinelles ;
10. catalogue conceptuel des événements et plan de télémétrie ;
11. hypothèses de volume, latence et coût ;
12. registre des risques et décisions ouvertes techniques ;
13. référence exacte du socle 4.6 validé ;
14. décision de Porte 2 signée.

## 13. Conclusion

L’Étape interne 2 repose sur un socle solide et son orientation produit est confirmée. Le principal danger demeure de construire une nouvelle couche visible qui ferait double emploi avec les écrans et objets déjà présents.

La Porte 2 est désormais fermée avec la réserve PME post-production. L’architecture peut se concentrer sur les vrais éléments nouveaux — moteur de règles, versions, simulations, exécutions, approbations et suspension — tout en préparant un lancement contrôlé et la possibilité de suspendre l’élargissement si les sessions révèlent un problème critique.

La validation de la recette V2.1 et la décision de Porte 2 ferment la preuve fonctionnelle attendue à cette étape. Elles ne remplacent pas les validations d’architecture, de sécurité, de qualité et de production.

## 14. Journal de décisions

| Date | Décision | Effet |
| --- | --- | --- |
| 30 septembre 2026 | `GO` donné à la Vague A | `P2-PRE3-02`, `P2-PRE3-03`, `P2-PRE3-04`, `P2-PRE3-05` et `P2-PRE3-07` peuvent être élaborées |
| 30 septembre 2026 | `P2-PRE3-01` reportée à la clôture de la Phase 5 | La preuve Azure ne bloque plus l’Étape 3 ; elle reste obligatoire pour le verdict final de la Phase 5 |
| 30 septembre 2026 | `VA-DEC-01` à `VA-DEC-10` approuvées | Les décisions Produit de la Vague A sont gelées ; les contre-validations transversales restent à produire |
| 1er octobre 2026 | Porte 2 prononcée `GO avec réserves` | Étape 3 de conception technique ouverte ; sessions PME et preuve Azure conservées comme réserves ; aucun GO de production |
| 1er octobre 2026 | Référence fonctionnelle `RF-AUT-2.1` figée | Le prototype et les comportements validés deviennent le contrat d’entrée versionné de l’Étape 3 |
| 30 septembre 2026 | Contre-validations transversales réalisées | Vague A fermée avec réserves transférées ; ouverture de la Vague B, sans GO de développement |
| 30 septembre 2026 | Vague B autorisée et documentée | Cycles de vie, catalogue de récupération, prototype V2, deux playbooks complémentaires et événements produit prêts pour validation |
