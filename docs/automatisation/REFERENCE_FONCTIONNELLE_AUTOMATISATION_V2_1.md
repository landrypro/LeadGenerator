# Référence fonctionnelle V2.1 — Automatisation Marketteo

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Identifiant de référence | `RF-AUT-2.1` |
| Version | **2.1** |
| Statut | **FIGÉE — référence d’entrée de l’Étape interne 3** |
| Date d’effet | 1er octobre 2026 |
| Autorité | Responsable Produit |
| Décision d’origine | [Porte 2 — GO avec réserves](./PORTE_2_GO_AVEC_RESERVES.md) |
| Portée | Comportements fonctionnels, règles UX, limites d’autonomie et exigences de preuve |
| Hors portée | Choix d’architecture, schémas physiques, technologies et implémentation |
| Dossier d’application | [Étape 3 — Architecture, données et sécurité](./ETAPE_3_ARCHITECTURE_DONNEES_SECURITE.md) |

## 1. Objet du gel

La présente référence fixe ce que l’architecture doit réaliser sans réinterpréter la décision Produit. Elle constitue le contrat fonctionnel d’entrée de l’**Étape interne 3 — Architecture, données et sécurité**.

La V2.1 est désormais la base de comparaison pour :

- l’architecture et le modèle de données ;
- les contrats d’API et d’événements ;
- le modèle de menace et les capacités ;
- les scénarios de qualité et de sécurité ;
- les futures démonstrations et recettes ;
- toute décision de portée ou d’autonomie.

La V2.1 n’est pas une autorisation de développement ou de production. Elle définit le comportement attendu lorsque les portes ultérieures autoriseront ces activités.

## 2. Artefact visuel de référence

Le prototype fonctionnel de référence est :

> **[Prototype cliquable Automatisation V2.1](./PROTOTYPE_CLIQUABLE_ETAPE_2_V2.html)**

| Propriété | Valeur figée |
| --- | --- |
| Nom de fichier conservé | `PROTOTYPE_CLIQUABLE_ETAPE_2_V2.html` |
| Désignation fonctionnelle | Prototype V2.1 |
| Taille | `42 030` octets |
| SHA-256 | `6993DEC8EAEF7EB0D46BDF9B2DC49B4BF6129D71C5E2A0FAAD3C171F8E0C918C` |

L’empreinte SHA-256 identifie les octets exacts approuvés. Une modification du fichier invalide cette empreinte et ne peut pas être présentée comme la référence V2.1 sans une décision de version explicite.

## 3. Sources normatives

La référence V2.1 consolide les sources suivantes :

1. [Étape 2 — Conception fonctionnelle et UX](./ETAPE_2_CONCEPTION_FONCTIONNELLE_UX.md) pour les parcours, exigences et limites de l’Assistant ;
2. [Vague A — Fondations de décision](./VAGUE_A_FONDATIONS_DECISION.md) pour le Feu relationnel, les capacités et la traçabilité vers le socle 4.6 ;
3. [Vague B — Produit testable](./VAGUE_B_PRODUIT_TESTABLE.md) pour les cycles de vie, les erreurs, les exceptions et les événements conceptuels ;
4. [Recette V2.1](./RECETTE_ET_RECHERCHE_VAGUE_C.md) pour la preuve fonctionnelle validée ;
5. [Porte 2](./PORTE_2_GO_AVEC_RESERVES.md) pour les réserves et les limites d’autorisation.

En cas d’ambiguïté, la présente référence et la décision de Porte 2 prévalent pour la portée fonctionnelle V2.1. Une contradiction non résolue doit être remontée à Produit ; elle ne peut pas être tranchée silencieusement par l’architecture.

## 4. Règles figées du Feu relationnel

### 4.1 Nature

Le Feu est un résultat déterministe calculé pour une action, un canal lorsqu’il y a communication, un prospect, un instant et une version de règles. Il n’existe aucun Feu global valable pour toutes les actions.

| Résultat | Sens V2.1 | Conséquence |
| --- | --- | --- |
| Vert | Action admissible selon les données et règles disponibles | Autoriser uniquement l’étape correspondant au niveau d’autonomie permis |
| Jaune | Preuve absente, contradictoire ou expirée, ou approbation encore requise | Vérifier, créer une tâche interne ou préparer sans envoyer |
| Rouge | Opposition ou interdiction déterministe | Bloquer, expliquer et journaliser |

La priorité est `Rouge > Jaune > Vert`. Ni l’IA, ni une approbation, ni un Playbook, ni une nouvelle source ne peuvent abaisser un Rouge.

### 4.2 Invariants

- Vert n’est jamais présenté comme une garantie juridique.
- L’inconnu ne produit jamais Vert.
- Le calcul est refait lorsque les données ou règles déterminantes changent.
- Les raisons principales et secondaires sont accessibles et versionnées.
- Une tâche interne n’exige pas une permission de contact et ne reçoit pas de couleur relationnelle.
- Un responsable inactif, une source déconnectée, une limite temporaire ou une panne crée une exception opérationnelle ; ces événements ne modifient pas artificiellement le Feu.
- Une opposition ne peut être levée depuis un Playbook ; elle suit le processus CRM de permission existant.

## 5. Mode `Préparer`

`Préparer` est le seul mode actif prévu au lancement V1.

Il peut :

- créer ou proposer des tâches internes admissibles ;
- préparer un brouillon lorsque le Feu et les règles le permettent ;
- créer une exception explicite ;
- demander une décision ou une approbation humaine ;
- conserver l’historique et la justification de la préparation.

Il ne peut pas :

- envoyer une communication externe ;
- déplacer silencieusement un prospect ou une opportunité dans le pipeline ;
- changer silencieusement un responsable ;
- modifier une permission ou contourner une opposition ;
- transformer une recommandation IA en effet métier direct.

Une approbation est liée au destinataire, au canal, au contenu, à la justification et aux versions du Playbook et des règles. Toute modification matérielle invalide l’approbation et exige une nouvelle lecture humaine.

## 6. Prévol

Le Prévol est une simulation déterministe sans effet métier réel. Il utilise les mêmes règles fonctionnelles que le mode actif et porte sur une version précise du Playbook.

Son résultat expose au minimum :

- la période et le périmètre simulés ;
- les volumes concernés ;
- les tâches, brouillons et actions internes qui seraient préparés ;
- les approbations nécessaires ;
- les blocages, conflits, doublons et exceptions ;
- la version du Playbook et la version des règles ;
- l’estimation de volume et, lorsqu’elle est disponible, de coût.

Le Prévol n’accorde aucune permission et ne produit aucune action CRM ou externe. Toute modification matérielle crée une nouvelle version et impose un nouveau Prévol avant activation.

## 7. Trois Playbooks guidés

La V2.1 contient exactement trois recettes guidées. Elle ne contient aucun constructeur libre de workflows.

| Playbook | Déclencheur fonctionnel | Résultat attendu | Garde-fous principaux |
| --- | --- | --- | --- |
| Nouveau prospect | Prospect admissible reçu d’une source autorisée et non résolu comme doublon exact | Un responsable et une prochaine action, ou une exception explicite | Admission canonique, doublons, source, responsable actif, Feu, volume et suspension |
| Proposition en attente | Opportunité ouverte à l’étape canonique `proposal`, sans réponse ou activité après le délai | Une tâche ou un rappel admissible, sans relance inappropriée ou dupliquée | Réponse, fermeture, opposition, attente convenue, tâche équivalente et fréquence |
| Occasion oubliée | Opportunité ouverte sans activité récente, prochaine action ou échéance selon les règles | Une revue humaine et une décision explicite | Fermeture, activité récente, prochaine action existante, attente et suspension |

Les Playbooks contrôlent des objets CRM canoniques. Ils ne créent aucun portefeuille parallèle et ne changent jamais silencieusement le pipeline.

## 8. Cycles de vie fonctionnels

### 8.1 Playbook et version

Le cycle de référence est :

`Brouillon` → `Prévol requis` → `Prévol en cours` → `Prêt à activer` → `Actif — Préparer` → `Suspendu` ou `Retiré`.

Un Prévol à revoir revient vers une configuration modifiée puis `Prévol requis`. La reprise d’un Playbook suspendu exige un nouveau Prévol si son contexte ou sa configuration est devenu obsolète. Les tâches, brouillons, décisions et historiques existants ne sont jamais supprimés par la suspension.

### 8.2 Admission et exécution

Une entrée est reçue, puis rejetée/quarantainée ou admise dans le CRM canonique. Une admission est évaluée avant de devenir une préparation, une exception ou un blocage. Une identité fonctionnelle rejouée ne doit produire aucun second effet métier.

Un résultat incertain devient `À vérifier` et n’est jamais répété automatiquement.

### 8.3 Brouillon et approbation

Le cycle couvre : `Non créé`, `Préparé`, `En approbation`, `Approuvé`, `Refusé`, `Expiré` et `Invalidé`. Une approbation n’est ni une permission de contact ni une dérogation au Feu Rouge.

### 8.4 Exception

Une exception peut être `Ouverte`, `En traitement`, `Résolue` ou `Abandonnée`. Sa cause initiale, sa corrélation et son historique demeurent traçables. Une résolution entraîne une nouvelle évaluation ; elle ne relance pas aveuglément l’action.

## 9. Capacités par rôle

Les seuls rôles techniques V1 restent `sales`, `manager` et `admin`. Confiance/Sécurité est un mandat porté par des capacités, pas un quatrième rôle.

| Capacité | `sales` | `manager` | `admin` |
| --- | --- | --- | --- |
| Voir ses cartes et exécutions | Oui, périmètre personnel | Oui | Oui |
| Voir l’organisation | Non | Oui | Oui |
| Configurer un Playbook | Non | Oui | Oui |
| Lancer un Prévol | Lecture des résultats pertinents seulement | Oui | Oui |
| Activer en `Préparer` | Non | Oui | Oui |
| Suspendre ou reprendre | Demande ou signalement | Oui | Oui |
| Gérer une exception | Actions assignées, selon droits CRM | Oui | Oui |
| Approuver une action externe | Non en V1 | Oui | Oui |

Une capacité Automatisation ne remplace jamais la capacité CRM exigée par l’effet. Les droits sont revérifiés côté serveur au moment de la décision et avant tout effet différé. Une perte d’appartenance, de portée ou de capacité ferme l’action.

## 10. Erreurs et exceptions

Toute erreur ou exception doit indiquer :

1. ce qui s’est passé ;
2. ce qui a été effectué ou non ;
3. la prochaine action permise ;
4. le détail ou la référence de diagnostic ;
5. l’état cible après résolution.

Le catalogue V2.1 couvre au minimum : source déconnectée, entrée non authentifiée, doublon exact, correspondance ambiguë, responsable indisponible, permission à vérifier, opposition, limite temporaire, capacité absente, approbation invalidée, résultat incertain et Playbook suspendu.

Principes figés :

- Rouge et Jaune restent réservés au Feu relationnel ;
- `Réessayer` n’est possible que lorsque l’identité d’exécution et l’absence d’effet sont certaines ;
- une reprise conserve la corrélation et l’historique ;
- une erreur technique ne devient jamais un succès, une couleur relationnelle ou une suppression silencieuse ;
- une attribution aléatoire n’est jamais utilisée pour masquer un responsable indisponible.

## 11. Exigences de traçabilité

Chaque action visible ou préparée doit être reliée à :

- l’organisation active et l’acteur réel ou système ;
- l’objet CRM canonique concerné ;
- le cas d’usage ou contrat d’effet ;
- les capacités Automatisation et CRM évaluées ;
- la version du Playbook, du Feu et des règles ;
- le résultat du Prévol applicable ;
- la décision d’approbation lorsqu’elle existe ;
- un identifiant de corrélation et une identité d’idempotence ;
- le résultat, l’exception ou le blocage ;
- l’événement d’audit proportionné.

Aucun prospect, tâche, opportunité, permission ou historique parallèle ne peut être créé pour faciliter l’Automatisation. La télémétrie exclut la phrase libre de l’utilisateur, les contenus de brouillon, les destinataires et les preuves brutes. Les événements et contrats sont versionnés.

## 12. Limites de l’Assistant IA

L’Assistant d’`Aujourd’hui` est l’unique point d’entrée d’une nouvelle intention humaine. Playbooks et Entrées et exceptions restent des surfaces de contrôle et de résolution.

L’Assistant peut :

- comprendre et reformuler une intention ;
- proposer un plan lisible et son périmètre ;
- estimer un volume ;
- expliquer les règles, capacités, blocages et approbations applicables ;
- préparer une étape soumise aux contrôles existants.

L’Assistant ne peut pas :

- créer un workflow libre ;
- produire directement un effet CRM ou externe ;
- décider d’une permission ou modifier le Feu ;
- contourner une capacité, une opposition, un Prévol ou une approbation ;
- inventer un objet, une donnée ou une action hors des recettes autorisées ;
- enregistrer la phrase libre dans la télémétrie produit.

Une demande ambiguë appelle une précision. Une demande incompatible est refusée avec une explication. En indisponibilité du modèle IA, le même point d’entrée fournit des intentions guidées déterministes. Les déclencheurs système déjà configurés continuent d’alimenter les Playbooks sans exiger une phrase utilisateur.

L'application `IMP-A5` confirmée le 3 octobre 2026 respecte cette référence sans la modifier : route dédiée
`/app/automation/today`, faux fournisseur déterministe, six intentions actives dans `P4-Lite`, plan non persisté et
limites locales avec échec fermé. Les deux Playbooks complémentaires, le Prévol créé depuis ce plan et OpenAI réel
restent hors de cette tranche.

## 13. Règle de versionnement

La référence `RF-AUT-2.1` ne doit jamais être modifiée silencieusement.

### 13.1 Changement matériel

Est matériel tout changement qui touche notamment :

- un invariant, une règle ou une priorité du Feu ;
- un effet permis en `Préparer` ou le niveau d’autonomie ;
- le contenu ou le caractère obligatoire du Prévol ;
- un déclencheur, paramètre, résultat ou arrêt d’un Playbook ;
- un état ou une transition de cycle de vie ;
- une capacité, un rôle ou une combinaison de droits ;
- une catégorie d’erreur, une stratégie de reprise ou d’idempotence ;
- une preuve, un événement ou une exigence de traçabilité ;
- le point d’entrée, les pouvoirs ou les limites de l’Assistant IA ;
- l’absence d’envoi externe autonome ;
- un objet CRM canonique ou la règle interdisant les registres parallèles.

### 13.2 Niveaux de version

| Changement | Version attendue | Exemple |
| --- | --- | --- |
| Correction éditoriale sans effet de comportement | `2.1.x` | Orthographe ou lien corrigé |
| Évolution fonctionnelle compatible avec les invariants V1 | `2.2` ou version mineure suivante | Nouvelle exception ou paramètre visible |
| Rupture d’invariant, nouveau niveau d’autonomie ou modification substantielle du parcours | `3.0` ou version majeure suivante | Envoi autonome ou constructeur libre |

### 13.3 Processus obligatoire

Avant toute modification matérielle :

1. créer une demande de changement identifiée ;
2. décrire la raison, les utilisateurs touchés, les règles affectées et les risques ;
3. produire les écarts par rapport à `RF-AUT-2.1` ;
4. obtenir l’approbation Produit et les contre-validations adaptées — Design, Ingénierie, Confiance/Sécurité et Qualité selon l’impact ;
5. attribuer une nouvelle version fonctionnelle avant l’implémentation ;
6. créer un nouvel artefact de prototype au lieu d’écraser le fichier V2.1 ;
7. exécuter un nouveau Prévol conceptuel, mettre à jour les critères d’acceptation et rejouer la recette touchée ;
8. consigner la décision, la date, le responsable, les migrations éventuelles et le plan de retour arrière.

Une modification du prototype, d’une règle normative ou d’un invariant sans nouvelle version approuvée est une non-conformité documentaire et ne peut pas servir de base à l’architecture.

## 14. Registre des versions

| Version | Date | Statut | Décision | Remplace |
| --- | --- | --- | --- | --- |
| `RF-AUT-2.1` | 1er octobre 2026 | **Figée et active** | Porte 2 — GO avec réserves | Prototype V2 et décisions préparatoires |

## 15. Formule officielle

> **La référence fonctionnelle `RF-AUT-2.1` est figée.** Le prototype V2.1, le Feu relationnel, le mode Préparer, le Prévol, les trois Playbooks, les cycles de vie, les capacités par rôle, les erreurs et exceptions, la traçabilité et les limites de l’Assistant IA constituent le contrat d’entrée de l’Étape interne 3. Toute modification matérielle exige une nouvelle version approuvée avant implémentation.
