# Rapport de validation Produit — Vague B

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Étape | Étape interne 2 — Vague B |
| Date | 1er octobre 2026 |
| Référentiel | [Vague B — Produit testable](./VAGUE_B_PRODUIT_TESTABLE.md) |
| Artefact revu | [Prototype cliquable V2.1](./PROTOTYPE_CLIQUABLE_ETAPE_2_V2.html) |
| Suite de validation | [Recette V2.1 validée et protocole des sessions PME post-production](./RECETTE_ET_RECHERCHE_VAGUE_C.md) |
| Décision de sortie | [Porte 2 — GO avec réserves](./PORTE_2_GO_AVEC_RESERVES.md) |
| Référence active | [`RF-AUT-2.1` — référence fonctionnelle figée](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) |
| Avis Produit | **Favorable : recette prototype V2.1 validée** |
| Décision | Ajustements Produit intégrés : Assistant d’Aujourd’hui comme point d’entrée utilisateur unique et suppression de la surface Sources |

## 1. Objet de la revue

Cette revue vérifie que la Vague B traduit de façon compréhensible les décisions de la Vague A dans un prototype testable. Elle porte sur la clarté fonctionnelle et la cohérence Produit ; elle ne constitue pas une validation d’implémentation technique ou d’envoi externe.

## 2. Éléments confirmés

Le prototype V2 couvre les attendus fonctionnels suivants :

- navigation Automatisation intégrée et ses trois surfaces : Aujourd’hui, Playbooks, Entrées et exceptions ; le diagnostic de source est contextuel ;
- Assistant IA encadré dans Aujourd’hui comme unique point d’entrée d’une nouvelle intention utilisateur ; Playbooks et Exceptions restent des surfaces de contrôle et de résolution ;
- trois recettes guidées : Nouveau prospect, Proposition en attente et Occasion oubliée ;
- liens de conception vers les objets CRM canoniques, sans fiche, tâche ou opportunité parallèle ;
- Feu relationnel par action/canal, distinct d’une tâche interne ou d’une exception opérationnelle ;
- traitement visible du responsable inactif, de la source déconnectée, du doublon et de la quarantaine ;
- Prévol, activation en mode `Préparer`, suspension et reprise ;
- approbation externe qui devient invalide après modification du brouillon ;
- refus explicite des actions de configuration, de suspension ou d’approbation pour le rôle `sales` ;
- absence explicite d’envoi externe automatique et de modification silencieuse du pipeline.

## 3. Verdict Produit

Le responsable Produit considère le prototype correct à ce stade. La proposition demeure Lite, compréhensible et compatible avec le socle CRM jusqu’à la Phase 4.6.

La validation confirme que les mécanismes différenciants — point d’entrée IA unique, Passeport, Prévol, Feu relationnel et exceptions explicables — sont suffisamment représentés pour préparer les tests de désirabilité et de compréhension.

## 4. Réserves conservées

Au moment de la revue, cette validation favorable ne clôturait pas encore la Vague B. Les preuves ou obligations suivantes ont ensuite été acceptées, transférées ou conservées par la Porte 2 :

| Réserve | Prochaine preuve | Destination |
| --- | --- | --- |
| Navigation clavier et rendu mobile | Vérification dans un navigateur utilisable | Vague B |
| Compréhension sans accompagnement | Sessions PME, mesures et observations | Vague C post-production — réserve Produit acceptée |
| Cycles de vie, erreurs et télémétrie | Revue Produit, Ingénierie, Confiance, Sécurité, Qualité et Données | Vague B / Porte 2 |
| Contrats techniques, contrôles d’effet et acteur système | Conception d’architecture et modèle de menace | Étape 3 |
| Preuve Azure 4.6 liée au SHA final | Pipeline de clôture vert | Fin de la Phase 5 |

## 5. Décision de suite

La recette V2.1 est validée par le responsable Produit. Les sessions PME sont différées après la mise en production et demeurent une réserve explicite. La [Porte 2](./PORTE_2_GO_AVEC_RESERVES.md) a ensuite reçu un `GO avec réserves` : l’Étape 3 de conception technique est autorisée, tandis que la production reste soumise aux portes techniques, de sécurité et de qualité ultérieures.

## 6. Journal

| Date | Événement | Effet |
| --- | --- | --- |
| 1er octobre 2026 | Revue Produit du prototype V2 | Avis favorable initial ; réserves de test et de porte conservées |
| 1er octobre 2026 | Point d’entrée utilisateur unifié | Toute nouvelle intention humaine commence dans l’Assistant d’Aujourd’hui ; les déclencheurs système restent autonomes |
| 1er octobre 2026 | Recette V2.1 validée | Parcours fonctionnel approuvé ; sessions PME transférées après la mise en production et preuve de désirabilité maintenue comme réserve explicite |
| 1er octobre 2026 | Porte 2 prononcée `GO avec réserves` | Sortie de la Vague B actée ; conception technique autorisée ; aucun GO de production |
| 1er octobre 2026 | Référence `RF-AUT-2.1` figée | Les résultats validés de la Vague B deviennent le contrat versionné transmis à l’architecture |
