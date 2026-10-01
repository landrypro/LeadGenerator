# Recette fonctionnelle — prototype Navigation hybride V2

## 1. Objectif

Cette recette sert à décider si la navigation hybride et le parcours mobile de Recherche d'établissements peuvent devenir la base d'une future implémentation Marketteo.

Elle évalue une **maquette autonome** : aucune réussite ne valide les API, les permissions réelles, Google Places, la persistance ou l'accessibilité complète de l'application.

## 2. Artefacts et sécurité

- Prototype : [index.html](index.html)
- Guide : [README.md](README.md)
- Registre à renseigner : [RECETTE_PROTOTYPE_V2_REGISTRE.csv](RECETTE_PROTOTYPE_V2_REGISTRE.csv)
- Données : entièrement fictives.
- Effets : aucun appel d'API, aucune écriture CRM, aucun quota Google consommé.

Ouvrir `index.html` dans un navigateur récent, actualiser la page avec `Ctrl+F5`, puis utiliser **Réinitialiser** avant `NAV-V2-01`.

## 3. Mode de consignation

Utiliser uniquement les statuts suivants dans le registre :

- `PASS` : résultat conforme et expérience acceptable ;
- `PASS_WITH_RESERVE` : conforme, mais amélioration souhaitée ;
- `FAIL` : résultat différent ou expérience inacceptable ;
- `BLOCKED` : contrôle impossible ;
- `NOT_RUN` : contrôle non exécuté.

Les contrôles `DÉCISION` conditionnent l'adoption de la proposition. Un seul `FAIL` sur ces contrôles empêche le GO en l'état. Les contrôles `AMÉLIORATION` peuvent devenir des réserves priorisées.

Dans « Commentaire », noter brièvement : **ce qui gêne**, **où**, et **la correction attendue**. Une capture est utile seulement si elle montre clairement le problème ; elle ne doit contenir aucune donnée réelle.

## 4. Parcours de bout en bout

### NAV-V2-01 — Navigation ordinateur en français

**Niveau : DÉCISION**

1. Choisir `Ordinateur · 1440 px`, `Administrateur`, `Français Canada`, Automatisation masquée.
2. Repérer les accès directs : Tableau de bord, Mes tâches, Prospects, Pipeline et Opportunités.
3. Ouvrir successivement Acquisition, Données et audit et Administration.
4. Vérifier que Recherche d'établissements, Sources d'acquisition, Quotas et usage, Conservation et imports, Historique des imports, Exports CSV, Journal d'activité, Organisation et Membres sont retrouvables.

**Attendu :** les destinations quotidiennes sont immédiatement visibles ; les autres sont regroupées sans ambiguïté ; aucun chevauchement n'apparaît.

### NAV-V2-02 — Repère de catégorie active

**Niveau : DÉCISION**

1. Ouvrir `Acquisition → Recherche d'établissements`.
2. Ouvrir de nouveau le menu de navigation.
3. Refaire le contrôle depuis `Données et audit → Quotas et usage`.

**Attendu :** la page active et sa catégorie sont identifiables ; il est possible de comprendre sa position sans mémoriser le chemin.

### NAV-V2-03 — Tablette et tiroir

**Niveau : DÉCISION**

1. Choisir `Tablette · 1024 px`.
2. Ouvrir Menu, développer une catégorie, puis fermer avec `Échap`.
3. Appuyer sur `Tab`.

**Attendu :** le menu remplace proprement la barre complète ; le contenu arrière n'est pas actionnable pendant l'ouverture ; après fermeture, le focus revient au bouton Menu et reste visible.

### NAV-V2-04 — Navigation mobile et variante

**Niveau : DÉCISION**

1. Choisir `Mobile · 390 px` et `Barre inférieure + Plus`.
2. Parcourir Accueil, Tâches, Prospects, Pipeline et Plus.
3. Descendre en bas d'une page et vérifier que la barre ne cache aucune action.
4. Refaire à `320 px`.
5. Choisir `Menu seul — comparaison` et comparer le nombre d'actions nécessaires pour atteindre Tâches puis Recherche d'établissements.

**Attendu :** aucun débordement horizontal ni chevauchement ; les cibles tactiles sont confortables ; la variante préférée est évidente et peut être justifiée dans le commentaire.

### GSRCH-V2-01 — Première recherche

**Niveau : DÉCISION**

1. À `390 px`, revenir au profil Administrateur et à la barre inférieure.
2. Ouvrir `Plus → Acquisition → Recherche d'établissements`.
3. Choisir `Définir les paramètres`.
4. Conserver `plombier`, `Canada`, `Québec`, `15 km` et les zones de service incluses.
5. Lancer Rechercher.

**Attendu :** les paramètres s'ouvrent dans une vue mobile lisible ; l'action principale est facile à trouver ; quatre résultats fictifs apparaissent avec un résumé de la recherche appliquée.

### GSRCH-V2-02 — Brouillon et annulation

**Niveau : DÉCISION**

1. Choisir Modifier.
2. Remplacer Québec par Montréal et modifier le rayon.
3. Choisir Annuler.

**Attendu :** la recherche appliquée et ses résultats restent ceux de Québec ; le brouillon annulé n'est pas appliqué ; le focus revient à Modifier.

### GSRCH-V2-03 — Sélection et nom CRM explicite

**Niveau : DÉCISION**

1. Sélectionner un seul résultat.
2. Vérifier l'état partiel de « Sélectionner les résultats disponibles ».
3. Choisir Ajouter au CRM sans saisir de nom interne.
4. Dans le détail ouvert automatiquement, saisir `Prospect recette Québec`.
5. Relancer Ajouter au CRM.

**Attendu :** la sélection reste visible ; l'absence du nom CRM bloque l'ajout et place le focus sur le bon champ ; le nom Google n'est jamais recopié automatiquement ; après ajout fictif, le résultat est marqué et exclu de la sélection globale.

### GSRCH-V2-04 — Carte secondaire

**Niveau : AMÉLIORATION**

1. Choisir Voir la carte.
2. Fermer avec `Échap`.

**Attendu :** la carte est clairement secondaire, associée à la zone appliquée et ne détourne pas du parcours résultats ; le focus revient à Voir la carte.

### GSRCH-V2-05 — États dégradés et récupération

**Niveau : DÉCISION**

Dans `Atelier V2 — état simulé`, contrôler successivement :

1. Chargement, puis Interrompre ;
2. Aucun résultat, puis Modifier les paramètres ;
3. Erreur réseau, puis Réessayer ;
4. Quota atteint, puis Quotas et usage ;
5. Recherche interrompue, puis Réessayer.

**Attendu :** chaque état est compréhensible sans connaissance technique, propose une prochaine action cohérente et ne laisse pas croire qu'une écriture CRM a eu lieu.

### STATE-V2-01 — Conservation et séparation des états

**Niveau : DÉCISION**

1. Relancer une recherche et sélectionner un résultat.
2. Passer de `390 px` à `320 px`, puis à `1440 px`.
3. Vérifier que recherche et sélection sont conservées.
4. Changer d'organisation pour `Studio Rivage`.

**Attendu :** le redimensionnement ne réinitialise rien ; le changement d'organisation efface immédiatement résultats et sélections de l'espace précédent et l'explique avant l'action.

### ROLE-V2-01 — Profil Commercial

**Niveau : DÉCISION**

1. Choisir `Commercial`.
2. Examiner toutes les catégories et les destinations accessibles.

**Attendu :** Membres, Conservation et imports, Historique des imports et Journal d'activité ne sont pas proposés ; le reste du menu demeure cohérent. Cette matrice est illustrative : noter toute différence souhaitée pour les droits réels.

### ROLE-V2-02 — Plateforme et Sans organisation

**Niveau : DÉCISION**

1. Choisir `Plateforme` : vérifier que Plateforme, Audit plateforme et Compte sont proposés et que le sélecteur d'organisation est absent.
2. Choisir `Sans organisation` : vérifier que Compte demeure accessible, que l'état vide explique la situation et qu'aucun changement d'organisation n'est proposé.

**Attendu :** aucun écran métier d'organisation ne fuite dans ces deux états ; une sortie compréhensible existe toujours.

**Constat initial :** échec signalé en recette, car Audit plateforme était absent de la première version du prototype.

### ROLE-V2-02-R1 — Rejeu du profil Plateforme

**Niveau : DÉCISION**

1. Actualiser le prototype avec `Ctrl+F5`.
2. Choisir `Plateforme` à `1440 px` : vérifier la présence distincte de Plateforme et Audit plateforme.
3. Ouvrir Audit plateforme et vérifier que son titre apparaît dans le contenu.
4. Refaire à `390 px` depuis Menu.
5. Passer en anglais et vérifier les libellés Platform et Platform audit.

**Attendu :** les deux destinations Plateforme sont accessibles sur ordinateur et mobile, dans les deux langues ; Compte reste accessible et le sélecteur d'organisation reste absent.

### I18N-V2-01 — Parcours anglais

**Niveau : DÉCISION**

1. Choisir `Administrateur`, puis `English Canada`.
2. Refaire NAV-V2-02, GSRCH-V2-01 et GSRCH-V2-05.

**Attendu :** commandes, titres, catégories, messages et libellés accessibles sont en anglais ; aucun texte essentiel n'est tronqué à 320 px. Les noms d'organisations et les données fictives peuvent rester en français.

### AUTO-V2-01 — Extension future Automatisation

**Niveau : AMÉLIORATION**

1. Revenir en français et vérifier qu'Automatisation est absente lorsque l'extension est masquée.
2. Choisir `Automatisation en maquette`.
3. Examiner sa place à 1440 px puis à 390 px.
4. Ouvrir Aujourd'hui, Boîte d'entrée et Playbooks.

**Attendu :** une seule entrée globale apparaît immédiatement après Tableau de bord sur grand écran et dans l'ordre du panneau Plus sur mobile ; la barre inférieure reste `Accueil | Tâches | Prospects | Pipeline | Plus` ; l'écran annonce explicitement qu'il s'agit d'une extension future et ne laisse croire à aucune automatisation active.

### A11Y-V2-01 — Clavier, zoom et couches

**Niveau : DÉCISION**

1. Revenir à 390 px et recharger la page.
2. Sans souris, utiliser `Tab`, `Maj+Tab`, `Entrée` et `Échap` pour ouvrir le menu, naviguer, ouvrir les paramètres puis annuler.
3. Vérifier la visibilité du focus et son retour au déclencheur après chaque fermeture.
4. Mettre le navigateur à 200 % et répéter l'ouverture du menu et des paramètres.

**Attendu :** aucun piège clavier ; l'ordre est logique ; le contenu arrière ne prend pas le focus pendant une fenêtre ; aucun contrôle essentiel ne devient inaccessible. Le lecteur d'écran et le clavier virtuel mobile restent des contrôles séparés avant implémentation.

## 5. Questions de synthèse

Après le dernier contrôle, répondre dans le registre :

1. Préférez-vous **Barre inférieure + Plus** ou **Menu seul** sur mobile, et pourquoi ?
2. Une destination a-t-elle été difficile à retrouver ?
3. La hiérarchie Acquisition / Données et audit / Administration vous paraît-elle naturelle ?
4. Les paramètres de recherche prennent-ils trop ou pas assez de place ?
5. L'action d'ajout au CRM et l'exigence du nom interne sont-elles suffisamment claires ?
6. Quel état dégradé mérite une meilleure explication ?
7. L'emplacement futur d'Automatisation vous paraît-il correct ?
8. Quel est le principal irritant restant avant implémentation ?

## 6. Critères de décision

### Résultat de la recette

Recette utilisateur achevée le **25 septembre 2026** :

- 14 scénarios validés directement à `PASS` ;
- `ROLE-V2-02` a révélé l'absence d'Audit plateforme dans la première version ;
- la correction a été rejouée avec succès sous `ROLE-V2-02-R1` ;
- les huit questions de synthèse ont reçu une réponse ;
- aucune réserve ouverte ni aucun irritant bloquant n'est déclaré.

L'échec initial reste inscrit dans le registre pour assurer la traçabilité. Il est clos et remplacé, pour la décision finale, par le rejeu `ROLE-V2-02-R1` à `PASS`.

### Décisions issues de la revue

- La variante mobile retenue est **Barre inférieure + Plus**.
- La hiérarchie des catégories, l'espace des paramètres, l'ajout CRM et les états dégradés sont acceptés sans réserve nouvelle.
- Aucune destination difficile à retrouver ni irritant principal n'est signalé à ce stade.
- Lorsqu'elle sera activée, Automatisation se placera immédiatement après Tableau de bord / Dashboard ; elle restera dans Plus sur mobile tant qu'une promotion dans la barre inférieure n'est pas justifiée par l'usage.

La direction peut recevoir un **GO de conception** si :

- tous les contrôles `DÉCISION` sont `PASS` ou `PASS_WITH_RESERVE` ;
- aucune réserve ne concerne une action inaccessible, une navigation incompréhensible, une confusion d'organisation ou une copie implicite du nom Google ;
- la variante mobile préférée est identifiée ;
- les améliorations retenues sont consignées avant le découpage d'implémentation.

Ce GO autorise seulement la préparation de l'implémentation progressive. Il ne vaut ni recette de l'application ni validation WCAG.

### Verdict

**GO de conception accordé.** Le prototype V2 devient la référence UX pour préparer la spécification technique et le découpage d'implémentation. La recette de l'application réelle et sa validation d'accessibilité resteront obligatoires après développement.
