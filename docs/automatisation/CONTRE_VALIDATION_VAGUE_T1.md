# Contre-validation de la Vague T1

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Étape parente | [Étape interne 3 — Architecture, données et sécurité](./ETAPE_3_ARCHITECTURE_DONNEES_SECURITE.md) |
| Dossier contrôlé | [Vague T1 — Cartographie du socle et des frontières](./VAGUE_T1_CARTOGRAPHIE_SOCLE_FRONTIERES.md) |
| Référence fonctionnelle | [`RF-AUT-2.1`](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) |
| Date | 1er octobre 2026 |
| Statut | **CONTRE-VALIDÉE — GO T1 avec prescriptions obligatoires** |
| Portée | Architecture, Sécurité/Confiance, Produit PME, Exploitation/Qualité |
| Autorisation produite | Clôture de l’analyse T1 et recommandation d’ouvrir T2 |
| Autorisation non produite | Aucun développement, aucune migration, aucun endpoint actif, aucun GO de production |

## 1. Verdict

La cartographie T1 est cohérente avec le socle réel de Marketteo et avec `RF-AUT-2.1`.

Les dix décisions `T1-DEC-01` à `T1-DEC-10` sont contre-validées. Sept sont acceptées sans réserve de principe et trois sont acceptées sous prescriptions techniques obligatoires :

- `T1-DEC-01` — maintien du monolithe modulaire, avec critères de réouverture mesurables ;
- `T1-DEC-03` — réutilisation du worker, à condition de fermer ses écarts d’autorisation, de reprise et de capacité ;
- `T1-DEC-09` — lancement contrôlé, à condition de concevoir un vrai arrêt serveur global, locataire et par Playbook.

Aucun défaut ne justifie un `NO-GO`. Les prescriptions doivent être intégrées aux livrables T2 et T3 ; elles ne peuvent pas être reportées à l’implémentation sans décision formelle.

> **Verdict de contre-validation : GO T1 avec prescriptions obligatoires. T2 peut être recommandé, mais ne s’ouvre qu’après autorisation explicite.**

## 2. Méthode de contre-validation

La contre-validation a appliqué quatre lectures complémentaires :

1. **Architecture** — frontières, propriété des données, couplage, idempotence et évolutivité ;
2. **Sécurité et Confiance** — organisation, capacités, IA, audit, permissions et effets différés ;
3. **Produit PME** — simplicité, explicabilité, valeur visible et cohérence avec l’offre Lite ;
4. **Exploitation et Qualité** — reprise, suspension, observabilité, coût, charge et testabilité.

Chaque décision a été confrontée à cinq questions :

- respecte-t-elle le contrat fonctionnel V2.1 ?
- s’appuie-t-elle sur une capacité réellement présente dans le code ?
- empêche-t-elle la création d’un second CRM ou d’une autorité parallèle ?
- reste-t-elle sûre sous rejeu, perte de droit, panne ou changement de données ?
- demeure-t-elle exploitable et abordable pour une offre PME ?

Les preuves ont été recherchées dans les domaines Identité, Prospects, Conformité, Tâches, Pipeline, Opportunités, Audit, file durable, worker, observabilité, usage, configuration, routes client et tests d’intégration.

## 3. Contre-validation des dix décisions

| Décision | Architecture | Sécurité / Confiance | Produit PME | Exploitation / Qualité | Verdict |
| --- | --- | --- | --- | --- | --- |
| `T1-DEC-01` — conserver le monolithe modulaire en V1 | Réduit les frontières réseau et réutilise la composition actuelle | Diminue les nouveaux chemins de confiance | Évite un coût de plateforme prématuré | Demande des seuils de réouverture fondés sur la charge | **GO sous prescription** |
| `T1-DEC-02` — créer un module `automation` distinct | Sépare clairement orchestration et CRM | Permet une frontière d’autorisation dédiée | Préserve une expérience unique | Rend tests et ownership explicites | **GO** |
| `T1-DEC-03` — réutiliser PostgreSQL, RLS et le worker | Le socle durable existe réellement | RLS forte, mais garde d’effet incomplète | Accélère la valeur sans nouvelle infrastructure | Capacité, reprise incertaine et principal système à fermer | **GO sous prescriptions** |
| `T1-DEC-04` — interdire les écritures CRM directes | Évite une logique métier dupliquée | Conserve validations, RLS et audit CRM | Empêche les divergences visibles | Facilite idempotence et tests contractuels | **GO — règle impérative** |
| `T1-DEC-05` — séparer job technique et exécution métier | Évite de confondre transport et résultat produit | Rend `Bloquée` et `À vérifier` explicables | Fournit des états compréhensibles | Permet reprise contrôlée sans mensonge opérationnel | **GO** |
| `T1-DEC-06` — moteur déterministe autoritaire | Centralise Feu et Prévol | Empêche l’IA d’inventer une permission | Rend les raisons compréhensibles | Offre reproductibilité et tests de décision | **GO — règle impérative** |
| `T1-DEC-07` — double autorisation | Traite correctement les effets différés | Ferme perte de droit, TOCTOU et permission retirée | Évite des actions surprenantes | Exige un garde commun testable | **GO — règle impérative** |
| `T1-DEC-08` — audit unique et transactionnel | Évite un second journal | Maintient immutabilité et isolation | Offre une preuve unifiée | Réutilise les mécanismes déjà testés | **GO** |
| `T1-DEC-09` — drapeau global et admission par organisation | Permet un déploiement progressif | Le contrôle doit exister côté serveur avant admission et effet | Protège les PME d’une activation large | Nécessite suspension, génération et retour arrière testés | **GO sous prescriptions** |
| `T1-DEC-10` — exclure les textes sensibles de l’observabilité | Sépare preuve, métrique et contenu | Réduit fuite, conservation et exposition de données | Favorise confiance et simplicité | Réduit coût et cardinalité | **GO — règle impérative** |

## 4. Avis Architecture

### 4.1 Points confirmés

- Le produit est déjà organisé comme un monolithe modulaire : routes, cas d’usage, ports, dépôts, unités de travail et composition centrale.
- L’ajout immédiat d’un microservice Automatisation créerait des problèmes de cohérence, d’identité, de transactions et d’exploitation sans bénéfice démontré.
- Les objets CRM possèdent déjà leurs règles, contraintes de version et patrons d’idempotence. Les contourner créerait une seconde logique métier.
- La file PostgreSQL possède les propriétés nécessaires à une première orchestration durable : admission transactionnelle, bail, pulsation, tentatives, annulation et rejeu idempotent.
- Le statut de job ne suffit pas à représenter le cycle métier d’une Automatisation. La séparation proposée est donc correcte.

### 4.2 Prescription Architecture `CV-T1-ARC-01`

Le choix du monolithe modulaire est approuvé pour V1, mais `ADR-AUT-001` devra définir ses conditions de réouverture :

- saturation ou contention mesurée de la file ;
- nécessité démontrée d’un déploiement ou d’une montée en charge indépendante ;
- isolation de panne insuffisante ;
- exigences de résidence ou de sécurité incompatibles ;
- cadence de livraison indépendante justifiée par des équipes réellement séparées.

Aucun découpage réseau ne sera décidé uniquement « pour préparer l’avenir ».

### 4.3 Prescription Architecture `CV-T1-ARC-02`

`ADR-AUT-002` devra décider comment l’admission Automatisation et la création du travail durable restent atomiques :

- utilisation directe de la file dans la transaction applicative ; ou
- outbox transactionnelle si plusieurs consommateurs ou publications deviennent nécessaires.

Un bus d’événements générique ne doit pas être introduit sans besoin démontré.

## 5. Avis Sécurité et Confiance

### 5.1 Points confirmés

- L’organisation est déjà portée par un contexte serveur et renforcée par RLS.
- Les capacités sont explicites, mais aucune capacité Automatisation n’existe encore.
- Le worker réévalue l’activité du membre ; cette vérification est nécessaire mais insuffisante pour un effet différé.
- L’audit actuel est fermé, immuable et transactionnel : il constitue la bonne source de preuve à étendre.
- L’IA n’a actuellement aucun composant ni accès au produit, ce qui permet de concevoir sa frontière avant intégration.

### 5.2 Prescription Sécurité `CV-T1-SEC-01` — garde d’effet

Avant chaque mutation CRM différée, un garde commun doit vérifier :

1. validité de l’acteur ou du principal système ;
2. organisation active et cohérente ;
3. capacité Automatisation requise ;
4. capacité CRM requise ;
5. portée sur l’objet ;
6. version courante de l’objet ;
7. Feu et permission actuels par action et canal ;
8. validité du Playbook, du Prévol et de l’approbation ;
9. absence de suspension globale, locataire ou Playbook ;
10. unicité de l’effet métier.

L’échec d’un contrôle produit un état métier explicable. Il ne doit pas être transformé en nouvelle tentative technique automatique.

### 5.3 Prescription Sécurité `CV-T1-SEC-02` — principal système

Les déclencheurs système devront utiliser un principal technique limité :

- origine fermée et autorisée par type de travail ;
- aucune capacité implicite universelle ;
- organisation obligatoire ;
- portée réduite au Playbook et aux actions admises ;
- révocation et suspension immédiates ;
- audit de chaque décision et corrélation avec l’admission.

Le principal système ne doit jamais remplacer silencieusement un utilisateur pour une action qui exige une approbation humaine.

### 5.4 Prescription Confiance `CV-T1-TRU-01` — IA sans autorité

Le contrat IA de T3 devra démontrer :

- schéma de sortie fermé ;
- liste blanche de verbes et Playbooks ;
- aucune fonction ou clé permettant une mutation CRM ;
- contexte minimisé ;
- données CRM traitées comme contenu non fiable ;
- résolution du périmètre après l’IA ;
- revalidation déterministe avant Prévol et avant effet ;
- expiration et empreinte du plan ;
- comportement guidé de repli sans IA.

## 6. Avis Produit PME

### 6.1 Points confirmés

- Un seul module technique d’Automatisation sert les trois Playbooks, ce qui évite trois produits différents.
- Le moteur déterministe soutient la promesse de confiance : comprendre avant d’agir.
- L’interdiction d’écrire directement dans le CRM protège la cohérence des écrans existants.
- Les états métier distincts permettent d’expliquer simplement `Préparée`, `Bloquée`, `À vérifier` et `Suspendue`.
- Le monolithe et la réutilisation du worker réduisent le coût d’une première offre Lite.

### 6.2 Prescription Produit `CV-T1-PRD-01`

Les futurs contrats techniques doivent préserver exactement l’expérience V2.1 :

- l’Assistant de `Aujourd’hui` demeure l’unique point de nouvelle intention humaine ;
- `Playbooks` administre des recettes, sans constructeur libre ;
- `Entrées et exceptions` résout les problèmes ;
- aucun menu `Sources` n’est réintroduit dans Automatisation ;
- aucun contrat V1 ne permet un envoi externe autonome ;
- une limitation de file ou de quota doit être expliquée en termes métier, sans exposer le fonctionnement interne du worker.

### 6.3 Prescription Produit `CV-T1-PRD-02`

La réutilisation technique ne doit pas devenir de la complexité visible. Les limites de capacité, les tentatives et les statuts de file restent internes. L’utilisateur voit : ce qui est préparé, ce qui est bloqué, pourquoi, et comment résoudre.

## 7. Avis Exploitation et Qualité

### 7.1 Points confirmés

- La file actuelle limite une organisation à une tâche active et à 100 tâches en attente.
- Trois tentatives au maximum sont possibles pour les erreurs reconnues transitoires.
- Les métriques techniques et journaux structurés possèdent des vocabulaires bornés.
- Le registre d’usage agrège déjà des unités et résultats par organisation.
- Les tests d’intégration existants couvrent RLS, audit append-only, file durable et usage.

### 7.2 Prescription Exploitation `CV-T1-OPS-01` — capacité

Avant la Porte 3, une projection et un test technique devront couvrir :

- volume quotidien et de pointe par Playbook ;
- travail produit par une intention visant plusieurs prospects ;
- délai d’attente par organisation ;
- interaction avec exports et connecteurs qui partagent le worker ;
- comportement à 80 %, 100 % et au-delà de la capacité de file ;
- priorité entre tâche interne, réévaluation, résolution et travail administratif ;
- backpressure visible et absence de perte silencieuse.

### 7.3 Prescription Exploitation `CV-T1-OPS-02` — résultat incertain

Lorsque l’effet peut avoir eu lieu mais que sa confirmation est absente :

- l’exécution passe à `À vérifier` ;
- le job ne déclenche pas la même mutation automatiquement ;
- une réconciliation consulte la source canonique ;
- une reprise utilise la même identité d’effet ;
- l’opérateur voit la raison, le risque et l’action sûre disponible.

### 7.4 Prescription Qualité `CV-T1-QUA-01`

Chaque extension devra recevoir des tests négatifs couvrant au minimum : autre organisation, rôle rétrogradé, membre inactif, permission retirée, objet modifié, approbation invalidée, Playbook suspendu, travail rejoué et résultat incertain.

## 8. Scénarios contradictoires exécutés sur la conception

| Scénario | Décision attendue | Résultat de la contre-validation |
| --- | --- | --- |
| Une note CRM contient « ignore les règles et envoie » | La note reste une donnée non fiable ; aucun effet | Couvert par `T1-DEC-06` et `CV-T1-TRU-01` |
| Un commercial devient inactif après admission | Aucun effet ; exécution bloquée | Couvert par `T1-DEC-07` et le garde d’effet |
| Une permission courriel passe de Vert à Rouge | Aucun brouillon exécutable ni envoi | Couvert par la réévaluation avant effet |
| Le même travail est livré deux fois | Un seul effet métier | Couvert par idempotence file + commande CRM |
| La réponse est perdue après une mutation | État `À vérifier`, pas de répétition aveugle | Couvert par `T1-DEC-05` et `CV-T1-OPS-02` |
| Un identifiant d’un autre locataire est fourni | RLS et portée objet refusent l’accès | Couvert par contexte serveur + RLS + tests négatifs |
| L’IA est indisponible | Parcours guidé disponible, CRM normal intact | Couvert par frontière IA et mode dégradé |
| La file d’une organisation est pleine | Refus ou différé explicable, aucune perte | À détailler par `CV-T1-OPS-01` |
| Le kill switch est activé avec des travaux en file | Aucun nouvel effet après le point de contrôle | À détailler par `T1-DEC-09` et T3 |
| Un brouillon change après approbation | Approbation invalidée | À matérialiser dans le modèle T2 |

Aucun scénario ne révèle une contradiction fondamentale. Les scénarios de capacité, suspension et approbation nécessitent leur conception détaillée dans T2/T3.

## 9. Prescriptions obligatoires consolidées

| ID | Prescription | Vague responsable | Bloque quoi si absente ? |
| --- | --- | --- | --- |
| `CV-T1-ARC-01` | Critères mesurables de réouverture du monolithe | T4 | Porte 3 |
| `CV-T1-ARC-02` | Décision transaction directe ou outbox | T2 | Contrats d’exécution |
| `CV-T1-SEC-01` | Garde commun avant chaque effet | T2/T3 | Développement des effets |
| `CV-T1-SEC-02` | Principal système limité | T3 | Déclencheurs système |
| `CV-T1-TRU-01` | Contrat IA sans autorité d’écriture | T3 | Intégration IA |
| `CV-T1-PRD-01` | Fidélité stricte à l’UX V2.1 | T2/T3 | Validation fonctionnelle |
| `CV-T1-PRD-02` | Masquer la mécanique technique | T2 | Acceptation Produit |
| `CV-T1-OPS-01` | Projection et test de capacité | T4 | Porte 3 |
| `CV-T1-OPS-02` | Réconciliation du résultat incertain | T2/T3 | Exécution durable |
| `CV-T1-QUA-01` | Catalogue de tests négatifs | T3/T4 | Porte 3 |

## 10. Toutes les vagues restantes de l’Étape 3

### Vague T2 — Concevoir les données, les règles et les contrats

**But :** transformer les frontières validées en contrats techniques précis.

Travaux :

1. `T2.1` — formaliser `ADR-AUT-001` sur les frontières et `ADR-AUT-002` sur l’orchestration ;
2. `T2.2` — produire le modèle logique, le dictionnaire de données, les contraintes RLS et la rétention ;
3. `T2.3` — définir le moteur de règles, les versions et la fidélité Prévol/exécution ;
4. `T2.4` — spécifier les commandes API, les erreurs et les événements versionnés ;
5. `T2.5` — définir idempotence, concurrence, corrélation, approbation et résultat incertain ;
6. `T2.6` — écrire les diagrammes de séquence principaux.

Livrables : modèle de données, matrice objet/propriétaire, table de décision du Feu, contrats API/événements, stratégie d’idempotence et premiers ADR.

Critère de sortie : chaque comportement V2.1 possède un objet, une règle et un contrat sans duplication du CRM.

### Vague T3 — Fermer la sécurité, l’IA et la résilience

**But :** démontrer que les contrats T2 restent sûrs sous abus, panne et changement de contexte.

Travaux :

1. `T3.1` — matrice d’autorisation et garde d’effet à double contrôle ;
2. `T3.2` — modèle de menace complet et frontières de confiance ;
3. `T3.3` — contrat IA, minimisation, schéma fermé, repli et évaluations adversariales ;
4. `T3.4` — audit, télémétrie, journaux, usage et rétention ;
5. `T3.5` — feature flags, admission par organisation, suspension générale et retour arrière ;
6. `T3.6` — scénarios de panne, rejeu, TOCTOU, injection, confusion de locataire et résultat incertain ;
7. `T3.7` — exigences de tests négatifs et de sécurité.

Livrables : matrice d’autorisation, modèle de menace, frontière IA, plan d’observabilité, plan de lancement sûr, matrice des pannes et traitements.

Critère de sortie : aucun risque critique sans traitement, aucune voie IA vers un effet et aucune exécution différée sans réautorisation.

### Vague T4 — Estimer, découper et assembler la Porte 3

**But :** rendre un verdict de faisabilité et de maîtrise fondé sur des preuves.

Travaux :

1. `T4.1` — modéliser charge, latence, stockage, coûts IA, coût worker et exploitation ;
2. `T4.2` — tester les hypothèses de file, backpressure et débit par organisation ;
3. `T4.3` — découper l’implémentation future en tranches verticales réversibles ;
4. `T4.4` — consolider ADR, dépendances, risques résiduels, responsables et jalons ;
5. `T4.5` — effectuer les revues Produit, Architecture, Sécurité, Confiance, Données, Exploitation et Qualité ;
6. `T4.6` — assembler le dossier de Porte 3 et formuler la recommandation.

Livrables : estimation coûts/risques, preuve de capacité, découpage d’implémentation, registre des risques, ADR approuvées et dossier de Porte 3.

Critère de sortie : coût compatible PME, risques maîtrisés, architecture testable et plan d’implémentation réversible.

## 11. Après les vagues T2 à T4

Les vagues T1 à T4 appartiennent uniquement à l’Étape interne 3. Leur achèvement conduit à la **Porte 3 — Faisabilité et maîtrise**, qui rendra l’un des verdicts suivants :

- `GO` ;
- `GO avec réserves` ;
- `NO-GO`.

Un GO de Porte 3 pourra autoriser l’**Étape interne 4 — Plan de livraison et protocole de validation**. Il n’autorisera pas automatiquement la production.

Le parcours programme restera ensuite :

1. Étape 4 — plan de livraison et validation ;
2. Étape 5 — fondations du MVP ;
3. Étape 6 — expérience Lite complète ;
4. Étape 7 — validation de bout en bout ;
5. Étape 8 — pilote fermé PME ;
6. Étape 9 — préparation au lancement ;
7. Étape 10 — lancement progressif ;
8. Étape 11 — optimisation produit-marché ;
9. Étape 12 — extension contrôlée.

Ces étapes ne sont pas ouvertes par la présente contre-validation.

## 12. Conditions de clôture T1

- [x] quatre angles de contre-validation appliqués ;
- [x] dix décisions T1 examinées ;
- [x] contradictions et scénarios de panne examinés ;
- [x] prescriptions attribuées aux vagues responsables ;
- [x] aucune contradiction avec `RF-AUT-2.1` identifiée ;
- [x] aucun changement actif du produit réalisé ;
- [x] T1 déclarée contre-validée avec prescriptions ;
- [ ] autorisation explicite d’ouvrir T2 reçue.

## 13. Décision recommandée

La Vague T1 peut être clôturée avec un **GO sous prescriptions obligatoires**.

La prochaine décision attendue est :

> **Autoriser ou non la Vague T2 — Concevoir les données, les règles et les contrats.**

L’autorisation de T2 permettra de produire des modèles, contrats, ADR et diagrammes. Elle ne permettra toujours ni migration active, ni endpoint branché au produit, ni travail de production.

## 14. Journal

| Date | Événement | Résultat |
| --- | --- | --- |
| 1er octobre 2026 | Cartographie T1 produite | Dix décisions proposées |
| 1er octobre 2026 | Contre-validation Architecture, Sécurité/Confiance, Produit PME et Exploitation/Qualité | GO T1 avec dix prescriptions obligatoires |
| 1er octobre 2026 | Feuille de route T2 à T4 détaillée | T2 recommandée, non encore ouverte |
