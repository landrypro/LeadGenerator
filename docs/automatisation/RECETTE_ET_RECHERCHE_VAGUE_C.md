# Recette prototype V2.1 et sessions PME post-production — Vague C

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Entrée | [Rapport de validation Produit — Vague B](./RAPPORT_VALIDATION_VAGUE_B.md) |
| Prototype évalué | [Prototype cliquable V2.1](./PROTOTYPE_CLIQUABLE_ETAPE_2_V2.html) |
| Objectif | Observer en production contrôlée la clarté, l’utilisabilité, la désirabilité et l’adoption PME |
| Statut | **Recette V2.1 validée** par le responsable Produit le 1er octobre 2026 ; sessions PME réservées après la mise en production |
| Décision de sortie | [Porte 2 — GO avec réserves](./PORTE_2_GO_AVEC_RESERVES.md) |
| Référence fonctionnelle | [`RF-AUT-2.1` — référence figée](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) |

## 1. Règle de lecture

La recette manuelle confirme que le prototype s’exprime correctement dans un navigateur réel. Les sessions PME vérifient ensuite si le produit est compris sans accompagnement. Une réussite de recette ne vaut pas encore une preuve de désirabilité ; une opinion positive ne remplace pas l’observation des tâches.

Par décision Produit du 1er octobre 2026, le protocole V2.1 est gelé mais les sessions PME sont différées après la mise en production. Cette décision transforme la recherche utilisateur en **réserve explicite de validation post-production** : elle ne constitue ni une preuve de désirabilité acquise, ni une validation rétroactive du parcours.

La validation Produit de la recette V2.1 couvre le point d’entrée unique dans `Aujourd’hui`, la saisie d’une intention, la prévisualisation du plan et de son périmètre, les garde-fous avant effet, ainsi que la séparation avec le catalogue `Playbooks`. Les contrôles `REC-B-01`, `REC-B-16` et `REC-IA-01` à `REC-IA-06` sont déclarés validés. Cette validation fonctionnelle n’exécute aucune session PME et ne lève donc pas la réserve de désirabilité post-production.

## 2. Recette manuelle Vague B — 20 minutes

### 2.1 Préparation

- ouvrir le prototype V2 dans un navigateur moderne sur poste et mobile ou émulateur mobile ;
- commencer en rôle `Responsable` ;
- réinitialiser la démo avant chaque parcours ;
- consigner la version du navigateur, le format d’écran et tout comportement inattendu ;
- ne pas utiliser de donnée personnelle réelle : les données du prototype sont fictives.

### 2.2 Parcours et critères

| ID | Action | Résultat attendu | Preuve à inscrire |
| --- | --- | --- | --- |
| `REC-B-01` | Ouvrir le prototype sur poste | Automatisation est active après Tableau de bord ; Aujourd’hui, Playbooks et Entrées et exceptions sont accessibles | Capture ou verdict Oui/Non |
| `REC-B-02` | Réduire à un format mobile puis ouvrir `Plus` | Automatisation est la première entrée de `Plus` et aucun contenu n’est tronqué | Format testé + verdict |
| `REC-B-03` | Utiliser Tab, Entrée, Échap et Shift+Tab | Navigation visible, boutons accessibles, modales fermables par Échap | Blocage éventuel |
| `REC-B-04` | Ouvrir Aujourd’hui | Les cartes Nouveau prospect, Proposition en attente et Occasion oubliée sont visibles | Oui/Non |
| `REC-B-05` | Préparer la tâche d’Acme | La carte devient préparée ; le Feu Jaune courriel demeure visible | Oui/Non |
| `REC-B-06` | Ouvrir le Passeport Acme | Origine, permission, responsable, prochaine action et explication sont lisibles | Oui/Non |
| `REC-B-07` | Examiner Boreal puis approuver | L’approbation est visible ; aucun envoi n’est proposé ou simulé | Oui/Non |
| `REC-B-08` | Modifier le brouillon Boreal après approbation | L’approbation devient à renouveler | Oui/Non |
| `REC-B-09` | Ouvrir Proposition en attente | La tâche de suivi est proposée sans déplacement automatique de l’opportunité | Oui/Non |
| `REC-B-10` | Ouvrir Occasion oubliée | Une revue interne est proposée sans fermeture automatique | Oui/Non |
| `REC-B-11` | Ouvrir Playbooks et lancer les trois Prévols | Chaque Prévol affiche des volumes, blocages et zéro envoi externe | Oui/Non |
| `REC-B-12` | Suspendre puis reprendre Nouveau prospect | L’état évolue ; tâches et historique restent annoncés comme conservés | Oui/Non |
| `REC-B-13` | Ouvrir Entrées et exceptions | Responsable inactif, quarantaine, doublon et source déconnectée sont distingués | Oui/Non |
| `REC-B-14` | Résoudre le responsable indisponible | Réattribution explicite, sans tirage aléatoire ni changement du Feu | Oui/Non |
| `REC-B-15` | Examiner la source Meta déconnectée | Données existantes consultables, nouvelles entrées indisponibles, diagnostic explicable | Oui/Non |
| `REC-B-16` | Ouvrir l’exception Meta déconnectée | Le diagnostic est explicable et l’accès aux réglages d’intégration est contextuel, sans écran Sources dans Automatisation | Oui/Non |
| `REC-B-17` | Passer le rôle à `Commercial` | Prévol, suspension, réattribution et approbation sont refusés sans changement d’état | Oui/Non |
| `REC-B-18` | Cliquer un lien CRM de conception | Un message indique l’ouverture future de l’objet CRM canonique ; aucune fiche parallèle | Oui/Non |
| `REC-B-19` | Réinitialiser la démo | États, rôles, libellés et boutons reviennent à leur état initial | Oui/Non |
| `REC-B-20` | Vérifier l’ensemble des écrans | Aucun libellé ne laisse croire à un envoi externe automatique ou à une garantie juridique | Oui/Non |

### 2.3 Verdict de recette

| Résultat | Décision |
| --- | --- |
| 20 réussites, aucun défaut critique/élevé | Recette Vague B validée ; figer V2.1 et conserver les sessions PME dans le plan post-production |
| Défaut critique ou élevé | Corriger le prototype puis rejouer les cas affectés |
| Défaut moyen ou faible | Consigner, prioriser avant la Porte 2 selon fréquence et impact |
| Environnement non exploitable | Documenter l’environnement, changer de navigateur ou de poste ; ne pas interpréter l’absence de preuve comme une réussite |

Un défaut est **critique** s’il suggère un envoi non autorisé, contourne une opposition, brouille le Feu relationnel ou empêche tout parcours principal. Il est **élevé** s’il entraîne un abandon probable, une confusion majeure sur Prévol/Préparer ou rend la suspension introuvable.

### 2.4 Résultat consigné — recette initiale

Le 1er octobre 2026, le commanditaire a confirmé la validation des contrôles `REC-B-01` à `REC-B-20` du prototype V2. Cette validation couvre la version contrôlée avant l’ajout de l’entrée conversationnelle et avant le retrait de la surface Sources. Les garde-fous déjà validés restent acquis ; `REC-B-01` et `REC-B-16` doivent être rejoués sur la V2.1 pour confirmer la navigation à trois surfaces et le diagnostic contextuel.

### 2.5 Complément de recette — entrée « Demander à l’IA »

| ID | Action | Résultat attendu | Preuve à inscrire |
| --- | --- | --- | --- |
| `REC-IA-01` | Saisir « Combien de prospects sont en cours ? » | Le plan affiche la demande, un volume/périmètre estimé et aucune action directe | Capture ou verdict Oui/Non |
| `REC-IA-02` | Saisir « Répartis les prospects en cours entre mon équipe » | La proposition explique les critères et exige une revue avant toute réattribution | Oui/Non |
| `REC-IA-03` | Utiliser les exemples et `Ajuster ma demande` | Le texte est inséré, le plan est lisible et le focus revient au champ | Oui/Non |
| `REC-IA-04` | Cliquer `Préparer ce plan` | Un retour confirme qu’aucun objet CRM, Feu, pipeline ou envoi externe n’a changé | Oui/Non |
| `REC-IA-05` | Ouvrir le prototype sur mobile | Le bouton `Demander à l’IA` donne accès au même champ sans masquer la navigation | Format testé + verdict |
| `REC-IA-06` | Parcourir Playbooks puis Entrées et exceptions | Aucun second champ d’intention ou bouton générique de création n’est proposé ; la nouvelle demande commence dans Aujourd’hui | Oui/Non |

## 3. Sessions PME post-production — Vague C

Les sessions sont conduites après la mise en production, sur un périmètre contrôlé et avec des données de démonstration ou des organisations pilotes consentantes. Elles ne doivent pas exposer un prospect réel à une action externe autonome.

### 3.1 Échantillon recommandé

Prévoir 5 à 7 participants appartenant à des PME B2B, répartis autant que possible entre :

- un responsable commercial ou dirigeant qui choisit les règles de suivi ;
- un commercial qui traite les prospects et opportunités au quotidien ;
- une personne attentive aux permissions, à la qualité des données ou à la conformité.

Ne pas collecter de liste de prospects, d’accès CRM, de messages réels ni de données confidentielles durant la session. Le prototype suffit.

### 3.2 Hypothèses à confirmer

| ID | Hypothèse | Succès observable | Signal d’échec |
| --- | --- | --- | --- |
| `H-C-01` | La promesse est comprise rapidement | Le participant reformule « chaque prospect pris en charge » sans aide | Il pense qu’il s’agit seulement d’un outil d’envoi de courriels |
| `H-C-02` | Le Prévol rassure | Il explique qu’aucune action réelle n’a encore eu lieu | Il pense que des tâches/courriels sont déjà partis |
| `H-C-03` | Préparer est compris | Il distingue tâche/brouillon préparé et communication envoyée | Il anticipe un envoi automatique |
| `H-C-04` | Le Feu aide la décision | Il distingue Vert, Jaune, Rouge et exception opérationnelle | Il assimile Vert à une garantie juridique ou une panne à Rouge |
| `H-C-05` | Les trois recettes sont utiles | Il associe chaque recette à une situation métier réelle | Il les perçoit comme trois noms pour le même automatisme |
| `H-C-06` | Le contrôle paraît suffisant | Il trouve suspension, Passeport et approbation sans aide | Il demande un bouton de contournement ou ne trouve pas l’arrêt |
| `H-C-07` | Le point d’entrée unique réduit l’hésitation | Pour une nouvelle demande, il commence spontanément dans l’Assistant d’Aujourd’hui | Il cherche d’abord où créer une automatisation dans Playbooks ou Exceptions |

### 3.3 Déroulé par participant — 35 à 45 minutes

1. Présenter le contexte, le caractère fictif des données et l’absence d’envoi réel.
2. Demander : « Vous venez d’adopter Marketteo. Que pensez-vous que cette section vous apporte ? »
3. Confier la tâche : « Demandez à Marketteo de sécuriser la prise en charge d’un nouveau prospect », sans indiquer où commencer.
4. Observer si le participant utilise l’Assistant d’Aujourd’hui, puis demander d’expliquer le plan et le Prévol avant d’activer Nouveau prospect en mode Préparer.
5. Présenter Acme, puis demander ce qui est permis et ce qui est encore à vérifier.
6. Présenter Boreal, demander le chemin avant une éventuelle communication, puis modifier le brouillon.
7. Demander de traiter une proposition silencieuse et une occasion oubliée.
8. Demander de trouver et de traiter le responsable inactif et la source déconnectée.
9. Demander de suspendre une recette et de trouver la raison d’un refus de capacité en rôle Commercial.
10. Recueillir la valeur perçue, les doutes, la recette préférée et ce qui manquerait pour adopter le module.

Le modérateur ne corrige pas pendant les tâches. Il peut demander « Que vous attendez-vous à ce qu’il se passe ? » et « Qu’est-ce qui vous fait dire cela ? ».

### 3.4 Mesures à relever

| Mesure | Mode de calcul | Seuil de lecture proposé |
| --- | --- | --- |
| Réussite sans aide | Participants qui achèvent une tâche sans indice / participants | 80 % ou plus sur les tâches critiques |
| Temps à première valeur | Démarrage → compréhension du Prévol + activation Préparer | Médiane sous 10 minutes |
| Compréhension du Feu | Bonne explication des trois états et de l’exception | 80 % ou plus |
| Confusion d’autonomie | Participants pensant qu’un message part seul | 0 toléré sur la version à la Porte 2 |
| Suspension trouvable | Participants qui suspendent sans aide | 80 % ou plus |
| Point d’entrée trouvé | Participants commençant une nouvelle intention dans Aujourd’hui sans indice | 80 % ou plus ; aucun point de création concurrent observé |
| Valeur perçue | Réponse qualitative et note 1–5 volontaire | Tendance et verbatims, pas une preuve isolée |

### 3.5 Fiche d’observation

```text
Participant : P-__       Rôle : __       Secteur : __       Session : __

Tâche                   Réussite sans aide   Temps   Hésitation / citation
Nouveau prospect        Oui / Non            __      ______________________
Prévol + Préparer       Oui / Non            __      ______________________
Feu / Passeport         Oui / Non            __      ______________________
Approbation             Oui / Non            __      ______________________
Proposition en attente  Oui / Non            __      ______________________
Occasion oubliée        Oui / Non            __      ______________________
Suspension              Oui / Non            __      ______________________

Problème observé : __
Gravité : Critique / Élevée / Moyenne / Faible
Recommandation : __
```

## 4. Décision après les sessions post-production

| Constat | Décision |
| --- | --- |
| Aucun défaut critique/élevé et seuils principaux atteints | Lever la réserve de validation PME et poursuivre le déploiement progressif |
| Défaut critique ou élevé confirmé | Suspendre l’élargissement, corriger le produit et rejouer la recette et le test affecté |
| Question technique non résolue | Transférer avec identifiant et risque à l’Étape 3 |
| Besoin hors noyau Lite | Consigner dans le backlog d’évolution, sans étendre la V1 par défaut |

## 5. Journal d’exécution

| Date | Élément | Résultat | Décision |
| --- | --- | --- | --- |
| 1er octobre 2026 | Recette prototype V2.1 | **Validée par le responsable Produit** | `REC-B-01`, `REC-B-16` et `REC-IA-01` à `REC-IA-06` validés ; sessions PME maintenues après la mise en production |
| 1er octobre 2026 | Porte 2 | **GO avec réserves** | Étape 3 de conception technique autorisée ; sessions PME maintenues comme réserve post-production ; aucun GO de production |
| À renseigner | Session PME P-01 |  |  |
| À renseigner | Session PME P-02 |  |  |
| À renseigner | Synthèse Vague C |  |  |
