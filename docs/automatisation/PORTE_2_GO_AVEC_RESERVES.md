# Porte 2 — GO avec réserves

| Élément | Décision |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Porte | Porte 2 — Désirabilité et clarté |
| Date | 1er octobre 2026 |
| Décideur | Responsable Produit |
| Verdict | **GO AVEC RÉSERVES** |
| Effet | Clôture de l’Étape interne 2 et autorisation de l’Étape interne 3 — Conception technique |
| Limite | **Aucun GO de production, de développement ou d’activation réelle** |
| Référence fonctionnelle | [Étape 2 — Conception fonctionnelle et UX](./ETAPE_2_CONCEPTION_FONCTIONNELLE_UX.md) |
| Prototype de référence | [Prototype cliquable V2.1](./PROTOTYPE_CLIQUABLE_ETAPE_2_V2.html) |
| Recette | [Recette V2.1 et sessions PME post-production](./RECETTE_ET_RECHERCHE_VAGUE_C.md) |
| Référence fonctionnelle | [`RF-AUT-2.1` — référence figée](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) |
| Étape ouverte | [Étape 3 — Architecture, données et sécurité](./ETAPE_3_ARCHITECTURE_DONNEES_SECURITE.md) |

## 1. Décision exécutive

La Porte 2 reçoit un **GO avec réserves**.

Cette décision constate que la conception fonctionnelle et UX est suffisamment définie pour devenir l’entrée officielle de la conception technique. Elle ferme l’Étape interne 2 et autorise l’ouverture de l’**Étape interne 3 — Architecture, données et sécurité**.

Les comportements approuvés sont figés dans la [référence fonctionnelle `RF-AUT-2.1`](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md). Toute évolution matérielle doit désormais recevoir une nouvelle version avant d’être transmise à l’architecture.

Elle ne constitue pas un GO de production. Elle n’autorise ni le développement du moteur dans l’application active, ni une migration, ni l’activation d’un connecteur, ni l’utilisation de données réelles, ni un envoi externe. Ces autorisations dépendront des portes techniques, de sécurité, de qualité et de production ultérieures.

## 2. Constats approuvés

| ID | Constat de Porte 2 | Preuve ou référence | Statut |
| --- | --- | --- | --- |
| `P2-CONST-01` | La recette fonctionnelle du prototype V2.1 est validée. | Contrôles `REC-B-01`, `REC-B-16` et `REC-IA-01` à `REC-IA-06` consignés dans la [recette V2.1](./RECETTE_ET_RECHERCHE_VAGUE_C.md). | **Validé** |
| `P2-CONST-02` | L’Assistant IA d’`Aujourd’hui` est l’unique point d’entrée d’une nouvelle intention utilisateur. | Saisie libre, prévisualisation du plan et absence d’un second champ générique dans Playbooks ou Entrées et exceptions, visibles dans le [prototype V2.1](./PROTOTYPE_CLIQUABLE_ETAPE_2_V2.html). | **Validé** |
| `P2-CONST-03` | Les trois Playbooks — Nouveau prospect, Proposition en attente et Occasion oubliée — ainsi que le traitement des entrées et exceptions sont représentés et validés fonctionnellement. | [Rapport de validation de la Vague B](./RAPPORT_VALIDATION_VAGUE_B.md) et prototype V2.1. | **Validé** |
| `P2-CONST-04` | La V1 ne réalise aucun envoi externe autonome. Toute communication externe demeure préparée, explicable et soumise à une approbation humaine. | Limite V1 affichée dans le prototype et contrôles `REC-B-07`, `REC-B-11` et `REC-B-20`. | **Validé comme invariant de conception** |
| `P2-CONST-05` | Les sessions d’observation auprès des PME sont reportées après la mise en production. | [Protocole Vague C](./RECETTE_ET_RECHERCHE_VAGUE_C.md), conservé comme réserve post-production. | **Report accepté — réserve `P2-RSV-01`** |
| `P2-CONST-06` | La preuve Azure du socle 4.6 est reportée à la fin de la Phase 5. | [Analyse croisée](./ANALYSE_CROISEE_ETAPE_2_PHASES_1_A_4.md) et décision `P2-PRE3-01`. | **Report accepté — réserve `P2-RSV-02`** |

## 3. Périmètre désormais autorisé

Le GO de Porte 2 autorise exclusivement la **conception technique** nécessaire à l’Étape interne 3 :

- architecture logique et découpage des composants ;
- modèle de données et stratégie de réutilisation des objets CRM canoniques ;
- contrats conceptuels d’API, d’événements et d’idempotence ;
- modèles d’états des playbooks, exécutions, brouillons, approbations, suspensions et exceptions ;
- modèle de menace, isolation par organisation et matrice des capacités ;
- règles techniques garantissant le mode `Préparer` et l’absence d’envoi externe autonome ;
- stratégie d’observabilité, d’audit, de reprise et de mise en quarantaine ;
- hypothèses de volume, latence, coût et rétention ;
- plan de réalisation, de test, de déploiement contrôlé et de retour arrière, sans l’exécuter.

## 4. Ce que la décision n’autorise pas

La Porte 2 n’autorise pas :

- un déploiement ou une mise en production ;
- le développement branché sur le produit actif ;
- une migration ou une modification des données de production ;
- l’activation réelle de Meta, LinkedIn ou d’un autre connecteur ;
- l’exposition publique d’un webhook ou d’une nouvelle API ;
- un envoi de courriel, de message social ou de toute communication externe ;
- une modification autonome du pipeline, d’un responsable ou du Feu relationnel ;
- une affirmation commerciale selon laquelle la désirabilité PME ou la chaîne Azure finale serait déjà prouvée.

## 5. Réserves acceptées et conditions de levée

### `P2-RSV-01` — Validation PME post-production

| Élément | Engagement |
| --- | --- |
| Risque accepté | La compréhension sans accompagnement, la désirabilité et l’adoption PME ne sont pas encore démontrées par observation. |
| Responsable | Produit et Design |
| Moment d’exécution | Après une mise en production qui aura été autorisée par les portes ultérieures, et avant tout élargissement au-delà du périmètre initial contrôlé. |
| Preuve de levée | Sessions PME exécutées selon le protocole Vague C, résultats consignés et absence de défaut critique ou élevé non traité. |
| Mesure de protection | Tout défaut critique ou élevé suspend l’élargissement ; le produit est corrigé et les scénarios affectés sont rejoués. |

### `P2-RSV-02` — Preuve Azure du socle 4.6

| Élément | Engagement |
| --- | --- |
| Risque accepté | La preuve Azure rattachée à la révision finale du socle 4.6 n’est pas encore archivée. |
| Responsable | Ingénierie et Qualité |
| Moment d’exécution | À la fin de la Phase 5, avant son verdict final. |
| Preuve de levée | Pipeline Azure vert sur la révision de clôture, résultats et artefacts de test archivés et traçables. |
| Mesure de protection | L’absence de cette preuve bloque la clôture de la Phase 5 et toute affirmation de chaîne CI finale prouvée. |

## 6. Invariants transférés à l’Étape interne 3

La conception technique doit conserver les décisions Produit suivantes :

1. un seul point d’entrée IA pour toute nouvelle intention humaine : l’Assistant d’`Aujourd’hui` ;
2. trois Playbooks guidés, sans constructeur libre de workflows en V1 ;
3. Playbooks comme surface de contrôle et Entrées et exceptions comme surface de résolution ;
4. aucun registre parallèle de prospects, tâches, opportunités, permissions ou audit ;
5. IA limitée à l’interprétation, au résumé et à la préparation d’un plan explicable ;
6. règles de permissions, d’opposition et de Feu relationnel déterministes ;
7. approbation humaine obligatoire avant toute communication externe ;
8. aucun changement silencieux du pipeline, du responsable ou du Feu relationnel ;
9. capacité de suspendre, reprendre, expliquer et auditer chaque effet ;
10. séparation stricte des organisations, données minimisées et journalisation proportionnée.

Toute proposition technique qui contredit un de ces invariants doit revenir en revue Produit avant d’être retenue.

## 7. Conditions de sortie de l’Étape interne 3

L’Étape interne 3 devra produire au minimum :

- une architecture traçable vers les écrans et décisions V2.1 ;
- un modèle de données sans duplication du CRM ;
- des contrats d’effets, d’idempotence, d’approbation et de suspension ;
- une matrice des menaces, capacités et frontières de confiance ;
- des choix documentés pour la résilience, l’audit, la télémétrie et les coûts ;
- un registre des décisions techniques et des risques résiduels ;
- un dossier de Porte 3 permettant un verdict distinct.

La prochaine décision sera la **Porte 3 — Faisabilité et maîtrise**. Elle seule pourra autoriser l’étape suivante. Elle ne devra pas être confondue avec un GO de production.

## 8. Formule officielle de décision

> **Porte 2 — GO avec réserves.** La recette fonctionnelle V2.1, le point d’entrée IA unique, les trois Playbooks et le traitement des exceptions sont validés. La V1 demeure sans envoi externe autonome. Les sessions PME sont reportées après la production et la preuve Azure 4.6 à la fin de la Phase 5. Cette décision autorise uniquement l’Étape interne 3 de conception technique ; elle ne constitue pas un GO de production.

## 9. Journal

| Date | Décision | Effet |
| --- | --- | --- |
| 1er octobre 2026 | Porte 2 prononcée `GO avec réserves` | Étape interne 2 clôturée ; Étape interne 3 autorisée dans son seul périmètre de conception technique |
| 1er octobre 2026 | `P2-RSV-01` acceptée | Sessions PME maintenues après la production et obligatoires avant élargissement du périmètre initial |
| 1er octobre 2026 | `P2-RSV-02` acceptée | Preuve Azure 4.6 obligatoire à la fin de la Phase 5 |
| 1er octobre 2026 | Étape interne 3 ouverte | Architecture, données et sécurité deviennent le chantier actif ; aucun GO de développement ou de production |
