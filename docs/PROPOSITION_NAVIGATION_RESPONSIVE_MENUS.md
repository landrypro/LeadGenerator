# Proposition d’évolution — navigation hybride et expérience responsive

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Nature | Proposition fonctionnelle et UX |
| Version | 4 — proposition hybride consolidée, lots 1 et 2 implémentés |
| Statut | GO de conception accordé ; lots 1 et 2 couverts automatiquement, recette applicative finale différée |
| Date | 25 septembre 2026 |
| Périmètre | Navigation principale, menus, changement d’organisation, responsive, Recherche Google mobile et extension future Automatisation |
| Mise en œuvre | Lots 1 et 2 implémentés ; lot 3 planifié : voir le [plan des trois lots](PLAN_IMPLEMENTATION_NAVIGATION_HYBRIDE.md) |

## 1. Objet du document

Ce document propose une navigation hybride pour Marketteo CRM. Elle conserve un accès direct aux fonctions commerciales les plus fréquentes et regroupe les fonctions secondaires dans des menus cohérents.

La proposition répond à quatre objectifs :

1. supprimer l’encombrement créé par les quinze destinations placées au même niveau ;
2. préserver la rapidité d’accès aux tâches quotidiennes ;
3. rendre la navigation utilisable sur ordinateur, tablette, mobile, au clavier et avec les technologies d’assistance ;
4. adapter la Recherche Google mobile en donnant la priorité aux résultats et aux actions utiles.

La navigation actuelle comprend :

- Tableau de bord ;
- Usage ;
- Conservation et imports ;
- Historique des imports ;
- Exports ;
- Sources et acquisitions ;
- Pipeline ;
- Opportunités ;
- Mes tâches ;
- Prospects ;
- Recherche Google ;
- Organisation ;
- Membres ;
- Journal d’activité ;
- Compte.

La recette du prototype V2 a validé la direction UX. Les lots 1 de navigation globale et 2 de responsive ont ensuite été implémentés ; leur périmètre, leurs preuves et le lot suivant sont tracés dans le [plan d’implémentation](PLAN_IMPLEMENTATION_NAVIGATION_HYBRIDE.md), le [rapport NAV-L1](RAPPORT_NAVIGATION_LOT_1.md) et le [rapport NAV-L2](RAPPORT_NAVIGATION_LOT_2.md).

## 2. Problème produit

Le problème ne se limite pas au manque de place dans l’en-tête. La navigation doit trouver un équilibre entre deux exigences :

- réduire le bruit visuel et accueillir de futures fonctions ;
- ne pas ajouter une action à chaque accès aux écrans utilisés plusieurs fois par jour.

L’objectif produit est donc :

> Réduire l’encombrement de la navigation sans augmenter le temps nécessaire pour atteindre les fonctions quotidiennes de chaque rôle.

### 2.1 Constats observables

- Les quinze liens horizontaux occupent presque toute la largeur disponible.
- Les traductions, le zoom et les noms longs réduisent encore l’espace utile.
- Sur écran réduit, le panneau de navigation peut entrer en concurrence visuelle avec les paramètres de la Recherche Google.
- Les utilisateurs n’ont pas tous les mêmes droits ni les mêmes destinations principales.
- Sur mobile, afficher simultanément les paramètres, la carte, les indicateurs et les résultats surcharge la page.

### 2.2 Risque à éviter

Une navigation entièrement catégorisée serait visuellement plus propre, mais elle pourrait ralentir les utilisateurs intensifs. « Mes tâches », « Prospects », « Pipeline » et « Opportunités » ne doivent pas être systématiquement enfouis sans preuve que ce coût est acceptable.

## 3. Niveaux de décision

Le document distingue les exigences fermes des choix à tester.

| Niveau | Contenu |
| --- | --- |
| **Exigence ferme** | Absence de chevauchement, contenu arrière inerte, droits respectés, accès clavier, focus maîtrisé, reflow, traductions et ordre stable. |
| **Option préférée** | Navigation hybride avec raccourcis directs et menus secondaires. |
| **Extension réservée** | Une entrée future pour l’expérience Automatisation, invisible jusqu’au franchissement de ses conditions d’activation. |
| **Hypothèse à tester** | Composition exacte des raccourcis, barre mobile inférieure, ordre des menus, liste compacte des résultats et position secondaire de la carte. |
| **Décision différée** | Seuils responsive définitifs, libellés finaux et descriptions dans les sous-menus. |

## 4. Principes de conception

1. Les tâches fréquentes restent directement accessibles.
2. Les fonctions secondaires sont regroupées selon un vocabulaire métier compréhensible.
3. Les positions communes restent stables entre les rôles et les organisations.
4. Une même commande conserve le même comportement quel que soit le rôle.
5. Le sélecteur d’organisation reste distinct du compte utilisateur.
6. Les catégories ne changent pas d’ordre selon les habitudes individuelles.
7. La navigation mobile privilégie les destinations quotidiennes.
8. Le mode compact s’active avant tout chevauchement.
9. La page active et son espace sont identifiables sans dépendre uniquement de la couleur.
10. Le serveur reste l’autorité pour les droits, même lorsqu’une destination est masquée dans l’interface.

## 5. Architecture hybride proposée

### 5.1 Navigation sur grand écran

La navigation principale combine cinq accès directs et trois groupes secondaires.

```text
Tableau de bord | Mes tâches | Prospects | Pipeline | Opportunités
Acquisition ▼ | Données et audit ▼ | Administration ▼
```

Les accès directs correspondent à l’hypothèse actuelle sur les fonctions commerciales les plus fréquentes. Cette hypothèse doit être vérifiée par rôle avant d’être figée.

### 5.2 Groupes secondaires

| Groupe | Destinations | Finalité |
| --- | --- | --- |
| **Acquisition** | Recherche d’établissements, Sources et acquisitions | Trouver de nouvelles entreprises et gérer leurs canaux d’origine. |
| **Données et audit** | Quotas et usage, Conservation et imports, Historique des imports, Exports CSV, Journal d’activité | Suivre les volumes techniques, importer, exporter, conserver et consulter la traçabilité. |
| **Administration** | Organisation, Membres | Administrer l’espace de travail et ses accès. |

Arborescence proposée :

```text
Acquisition
├── Recherche d’établissements
└── Sources et acquisitions

Données et audit
├── Quotas et usage
├── Conservation et imports
├── Historique des imports
├── Exports CSV
└── Journal d’activité

Administration
├── Organisation
└── Membres
```

« Données et audit » contient désormais cinq destinations. Ce volume reste acceptable pour un panneau vertical, à condition de conserver des libellés explicites et un ordre stable. Si de nouveaux écrans de pilotage sont ajoutés, le groupe devra être réévalué avant de dépasser six destinations ; une séparation entre « Gestion des données » et « Pilotage et audit » pourra alors être testée.

### 5.3 Contexte et utilisateur

La partie droite de l’en-tête contient trois zones distinctes :

```text
Organisation active | Aide | Utilisateur
```

| Zone | Contenu |
| --- | --- |
| **Organisation active** | Nom de l’organisation et changement d’organisation lorsque plusieurs choix sont accessibles. |
| **Aide** | Manuel utilisateur et assistance disponible. |
| **Utilisateur** | Identité, rôle, Compte et Déconnexion. |

Le changement d’organisation ne doit pas être enfoui uniquement dans le menu utilisateur. Il modifie les données, les droits et parfois la navigation ; son importance justifie un contrôle identifiable.

### 5.4 Stabilité selon les rôles

- Une destination non autorisée n’est pas affichée.
- Les destinations restantes conservent leur ordre relatif.
- Un groupe vide est masqué.
- Un groupe contenant une seule destination continue d’ouvrir son panneau ; son comportement ne devient pas un lien direct selon le rôle.
- Les raccourcis directs communs conservent autant que possible le même emplacement.
- La composition ne doit pas être réordonnée automatiquement selon l’historique personnel.

Si les tests démontrent qu’une famille de rôles possède un besoin très différent, une variante stable par famille de rôles pourra être étudiée. Elle ne devra pas changer au gré de l’usage individuel.

### 5.5 Extension future « Automatisation »

L’architecture réserve une extension pour le volet Automatisation Marketteo. Cette réservation prépare son intégration future sans ajouter immédiatement une destination visible.

#### Décision de principe

| Élément | Décision proposée |
| --- | --- |
| Place dans l’architecture | Réservée dès la conception de la navigation. |
| Affichage dans l’application actuelle | Aucun menu visible tant que les conditions d’activation ne sont pas remplies. |
| Nombre d’entrées globales | Une seule entrée pour l’expérience Automatisation. |
| Structure interne | Une expérience guidée, et non cinq nouveaux modules dans la navigation globale. |
| Libellé provisoire | « Automatisation », avec « Aujourd’hui » comme page d’arrivée. |
| Placement retenu après recette du prototype V2 | Immédiatement après « Tableau de bord » sur grand écran et dans l'ordre du panneau « Plus » ; l'entrée reste masquée avant activation. |

La structure interne envisagée est :

```text
Automatisation
├── Aujourd’hui
├── Boîte d’entrée
└── Playbooks
```

Les autres capacités du noyau Lite ne deviennent pas des destinations globales indépendantes :

- le Passeport de prise en charge apparaît dans les prospects, les recommandations et les détails d’une automatisation ;
- le Feu relationnel apparaît au voisinage des actions auxquelles il s’applique ;
- le Prévol appartient au parcours d’essai et d’activation d’un playbook ;
- les preuves et événements détaillés restent accessibles depuis le playbook concerné et le Journal d’activité.

#### Placement retenu sur grand écran

La recette du prototype V2 retient une entrée directe **Automatisation** immédiatement après **Tableau de bord**. Ce placement rend la capacité visible dès son activation, tout en conservant « Aujourd’hui » comme page d’arrivée interne :

```text
Tableau de bord | Automatisation | Mes tâches | Prospects | Pipeline | Opportunités
Acquisition ▼ | Données et audit ▼ | Administration ▼
```

L’entrée reste entièrement masquée tant que les conditions d’activation ne sont pas remplies. Le placement ne constitue donc pas une annonce « bientôt disponible ».

Les deux variantes étudiées avant cette décision sont conservées ci-dessous comme historique de conception.

**Variante A — accès quotidien direct**

```text
Tableau de bord | Mes tâches | Aujourd’hui | Prospects | Pipeline | Opportunités
Acquisition ▼ | Données et audit ▼ | Administration ▼
```

Cette variante convient si « Aujourd’hui » devient une destination très fréquente pour les commerciaux et responsables.

**Variante B — espace secondaire regroupé**

```text
Tableau de bord | Mes tâches | Prospects | Pipeline | Opportunités
Automatisation ▼ | Acquisition ▼ | Données et audit ▼ | Administration ▼
```

Cette variante préserve les raccourcis actuels et donne accès à l’ensemble de l’expérience par un groupe dédié.

La mise en œuvre devra vérifier l’espace disponible aux seuils responsive. Si l’ensemble ne tient pas, l’en-tête bascule au mode compact défini dans ce document ; l’ordre retenu ne doit pas provoquer de compression ou de chevauchement.

#### Placement mobile futur

Au premier lancement, la barre mobile retenue reste :

```text
Accueil | Tâches | Prospects | Pipeline | Plus
```

Automatisation apparaît immédiatement après Tableau de bord dans l'ordre du panneau « Plus ». Si les mesures démontrent ensuite que « Aujourd’hui » devient la principale porte d’entrée quotidienne, elle pourra être candidate à la barre inférieure :

```text
Aujourd’hui | Tâches | Prospects | Pipeline | Plus
```

La composition de la barre reste stable pour une même famille de rôles et ne change pas selon l’historique personnel.

#### Conditions d’activation du menu

L’entrée Automatisation devient visible uniquement lorsque :

1. le parcours `prospect → recommandation → playbook → Prévol → action` fonctionne de bout en bout ;
2. la page Aujourd’hui possède un état utile dès la première visite ;
3. au moins un playbook apporte une valeur observable ;
4. les droits de consultation, préparation, activation, approbation et suspension sont définis ;
5. les libellés `fr-CA` et `en-CA` sont validés ;
6. les parcours ordinateur, tablette, mobile et clavier sont testés ;
7. les états vides, bloqués, suspendus et sans organisation sont conçus ;
8. les critères de la porte produit Automatisation autorisent son exposition.

Aucune entrée désactivée « Bientôt disponible » n’est prévue avant ces conditions. Elle occuperait de l’espace et créerait une promesse produit avant que l’expérience soit exploitable.

## 6. Comportement sur grand écran

### 6.1 En-tête

L’en-tête contient :

- le logo Marketteo ;
- les raccourcis directs ;
- les trois groupes secondaires ;
- le sélecteur d’organisation ;
- l’aide ;
- le menu utilisateur.

Si l’ensemble ne tient pas sans compression, la navigation passe au mode compact. Les éléments ne doivent ni se réduire jusqu’à devenir illisibles, ni se superposer, ni passer sur une seconde ligne.

### 6.2 Sous-menus

Les groupes secondaires s’ouvrent au clic. Ils utilisent des boutons de divulgation et des listes de liens ordinaires.

Un panneau se ferme lors de :

- la sélection d’une destination ;
- l’activation d’Échap ;
- un clic ou toucher à l’extérieur ;
- l’ouverture d’un autre groupe.

Après une fermeture sans navigation, le focus revient au bouton déclencheur. Après sélection d’une destination, le focus est placé au début du contenu principal, idéalement sur son titre.

### 6.3 Descriptions

Les descriptions dans les sous-menus sont optionnelles. Elles seront conservées uniquement si les tests montrent qu’elles améliorent la compréhension sans ralentir le balayage visuel.

## 7. Responsive

Les seuils sont provisoires. La décision finale doit tenir compte de `fr-CA`, `en-CA`, des noms longs, du zoom et de la largeur réellement disponible.

### 7.1 Grand écran

À partir d’environ 1 280 px, si tout tient correctement :

- afficher la navigation hybride complète ;
- conserver le sélecteur d’organisation et les fonctions personnelles à droite ;
- ne pas réafficher les quinze liens indépendants.

### 7.2 Tablette et petit ordinateur

Lorsque la navigation hybride ne tient plus :

- conserver le logo ;
- afficher un bouton « Menu » ;
- afficher le nom de la section courante lorsque l’espace le permet ;
- conserver un accès compact au sélecteur d’organisation et à l’utilisateur ;
- ouvrir un tiroir dont la largeur maximale suit une règle équivalente à `min(22rem, 100vw)`.

Le tiroir :

- possède un fond opaque ;
- passe au-dessus des panneaux fonctionnels ;
- est accompagné d’un voile ;
- possède son propre défilement ;
- rend le contenu arrière inerte ;
- bloque le défilement de la page ;
- se ferme avec son bouton, Échap, le voile ou une destination ;
- restaure correctement le focus.

Le tiroir présente d’abord les raccourcis directs, puis les groupes secondaires. L’organisation, l’aide, le compte et la déconnexion occupent une zone clairement séparée.

### 7.3 Mobile

L’option préférée à prototyper est une barre inférieure avec quatre destinations fréquentes et un accès « Plus » :

```text
Accueil | Tâches | Prospects | Pipeline | Plus
```

« Plus » ouvre un panneau plein écran comprenant :

```text
Navigation                                      ×

Opportunités

Acquisition                                    ▼
  Recherche d’établissements
  Sources et acquisitions

Données et audit                               ▼
  Quotas et usage
  Conservation et imports
  Historique des imports
  Exports CSV
  Journal d’activité

Administration                                ▼
  Organisation
  Membres

Organisation active
Aide
Compte
Déconnexion
```

La barre inférieure doit respecter la zone sûre du système, ne pas masquer les actions de page et rester cohérente en portrait et paysage.

Cette barre est une hypothèse à comparer au menu plein écran seul. Elle sera retenue uniquement si elle réduit le temps d’accès aux tâches fréquentes sans créer de confusion.

### 7.4 Règles communes aux panneaux

- Une seule couche modale peut être active à la fois.
- Échap ou Retour ferme d’abord la couche supérieure.
- Le contenu arrière n’est ni cliquable, ni focalisable, ni défilable.
- Le changement de largeur ferme proprement une couche devenue incompatible avec le nouveau mode.
- Le focus revient au déclencheur après annulation.

## 8. Recherche Google sur mobile

La Recherche Google constitue un chantier distinct de la navigation globale. Les décisions de l’un ne doivent pas imposer sans test la présentation de l’autre.

### 8.1 Priorité produit

Après une recherche, la priorité est de consulter, comparer, sélectionner et ajouter des établissements. La carte et les indicateurs sont secondaires sur mobile, sauf preuve contraire issue des tests.

### 8.2 État initial

Avant toute recherche, la page affiche :

1. le titre et l’état de l’API ;
2. une invitation à définir les paramètres ;
3. le bouton « Définir les paramètres » ;
4. une information compacte sur la consommation Google.

La carte vide n’occupe pas l’espace principal.

### 8.3 Après une recherche

L’ordre recommandé est :

1. résumé de la recherche appliquée ;
2. actions « Modifier » et « Voir la carte » ;
3. résultats temporaires ;
4. barre d’action liée à la sélection ;
5. informations de consommation détaillées.

Le résumé affiche :

- le type d’entreprise ;
- le pays ou la région ;
- la ville ou le quartier ;
- le rayon ;
- l’inclusion ou non des entreprises de zone de service.

### 8.4 Brouillon et recherche appliquée

Deux états sont distingués :

| État | Définition |
| --- | --- |
| **Brouillon** | Valeurs en cours de modification dans le panneau de paramètres. |
| **Recherche appliquée** | Valeurs ayant réellement produit les résultats visibles. |

Le bouton « Rechercher » applique le brouillon. « Annuler » restaure les valeurs de la dernière recherche appliquée. Le résumé de page affiche toujours les paramètres correspondant aux résultats visibles.

Si le panneau est fermé avec des modifications non appliquées, celles-ci ne doivent pas remplacer silencieusement le résumé de la recherche. Le comportement de conservation ou d’abandon du brouillon doit être explicite dans le prototype.

### 8.5 Panneau de paramètres

Le bouton « Modifier » ouvre un panneau plein écran ou une feuille mobile contenant :

- le type d’entreprise ;
- le pays ou la région ;
- la ville ou le quartier ;
- les coordonnées avancées ;
- le rayon ;
- l’option des entreprises de zone de service ;
- l’information sur l’appel Google ;
- « Annuler » et « Rechercher ».

L’action principale reste accessible avec le clavier virtuel ouvert, sans masquer le champ actif. Retour ou Échap ferme d’abord ce panneau selon la règle définie pour le brouillon.

### 8.6 Résultats

L’option préférée est une liste compacte avec détails extensibles, à comparer aux cartes lors du prototype.

```text
☐ Nom de l’établissement
   Adresse · Distance · Statut                   >
```

Le détail peut contenir :

- type ;
- adresse ou mention de zone de service ;
- distance ou état « non vérifiable » ;
- statut ;
- Place ID lorsqu’il doit être consultable ;
- lien Google Maps ;
- nom interne CRM ;
- action d’ajout.

La sélection multiple affiche une barre persistante :

```text
3 établissements sélectionnés       Ajouter au CRM
```

Le prototype doit préciser :

- la portée de « Tout sélectionner » ;
- le maintien ou non de la sélection pendant un filtrage ;
- le comportement après ajout partiel ;
- l’emplacement du nom interne CRM ;
- l’ordre de lecture sémantique.

### 8.7 Carte et indicateurs

La carte est accessible par une action explicite ou une vue secondaire. Lorsqu’elle est visible :

- l’attribution Google Maps reste présente ;
- toute information essentielle existe aussi sous forme textuelle ;
- l’utilisateur peut entrer et sortir de la carte au clavier ;
- le focus n’est pas déplacé automatiquement dans la carte.

Les compteurs Google sont regroupés dans une zone compacte. Ils ne doivent pas repousser les premiers résultats sous la ligne de flottaison sans justification métier.

## 9. Libellés recommandés

Les libellés doivent rester compréhensibles hors de leur contexte immédiat.

| Libellé actuel | Recommandation de navigation | Commentaire |
| --- | --- | --- |
| Tableau de bord | Tableau de bord ou Accueil | À comparer selon la compréhension utilisateur. |
| Mes tâches | Mes tâches | Accès direct proposé. |
| Prospects | Prospects | Accès direct proposé. |
| Pipeline | Pipeline | Accès direct proposé. |
| Opportunités | Opportunités | Accès direct sur grand écran. |
| Recherche Google | Recherche d’établissements | Plus orienté tâche ; Google reste visible pour l’attribution. |
| Sources et acquisitions | Sources d’acquisition | Plus explicite qu’un simple « Sources ». |
| Usage | Quotas et usage | Distingue les rapports techniques d’une facturation commerciale. |
| Conservation et imports | Conservation et imports | Éviter un raccourci ambigu. |
| Historique des imports | Historique des imports | Conserver le contexte. |
| Exports | Exports CSV | Précise le format et évite la confusion avec un export Google. |
| Journal d’activité | Journal d’activité | Éviter « Activité », trop générique. |
| Organisation | Organisation | Inchangé. |
| Membres | Membres | Inchangé. |
| Compte | Compte | Placé dans le menu utilisateur. |

Les libellés finaux doivent être évalués en `fr-CA` et en `en-CA`, dans les menus, les fils d’Ariane, les titres et les annonces des lecteurs d’écran.

## 10. Autorisations et changement d’organisation

- Le serveur contrôle chaque accès.
- Les destinations incompatibles avec les capacités de la session sont masquées.
- Une ouverture directe d’URL interdite produit une page 403 contrôlée.
- Le changement d’organisation affiche un état de transition unique avant de rendre la nouvelle navigation.
- Aucun contenu ni menu de l’organisation précédente ne réapparaît pendant la transition.
- Le nom de l’organisation active reste visible ou accessible sans ambiguïté.
- Un nom long est tronqué visuellement, avec son contenu complet accessible.
- L’organisation active n’est jamais transportée comme autorité dans l’URL.
- « Quotas et usage » est affiché seulement avec la capacité de lecture d’usage ; la portée personnelle ou organisationnelle reste déterminée par les capacités de la session.
- « Exports CSV » est affiché seulement avec une capacité de création d’export ; les portées et jeux de données accessibles restent contrôlés dans la page et par le serveur.

## 11. Accessibilité

### 11.1 Modèle sémantique

- La navigation principale utilise un repère `nav` nommé.
- Un lien d’évitement permet d’atteindre le contenu principal.
- Les destinations restent des liens ordinaires.
- Les groupes utilisent des boutons avec état développé ou réduit et relation avec leur panneau.
- La destination courante est annoncée comme page active.
- Les accordéons mobiles sont composés de titres, boutons et régions identifiables.
- Les panneaux modaux rendent le contenu arrière inerte.

### 11.2 Clavier et focus

- Tab et Maj+Tab parcourent les commandes et les liens.
- Entrée ou Espace ouvre un bouton de groupe.
- Échap ferme la couche supérieure.
- Après annulation, le focus revient au déclencheur.
- Après navigation, le focus atteint le titre principal ou le début du contenu.
- Le focus reste visible.
- La carte ne crée pas de piège clavier.

### 11.3 Affichage

- Les zones tactiles mesurent au moins 44 × 44 px.
- La page fonctionne à 200 % de zoom.
- Le reflow est vérifié à l’équivalent de 320 CSS px, notamment à 400 % sur une fenêtre de 1 280 px.
- La page active ne dépend pas uniquement de la couleur.
- Le contraste forcé et l’espacement personnalisé du texte sont vérifiés.
- Les animations respectent la préférence de réduction des mouvements.

## 12. Largeurs et contextes à vérifier

Les prototypes doivent être testés au minimum à :

- 320, 360, 390 et 430 CSS px ;
- 768 et 1 024 CSS px ;
- 1 280 et 1 440 CSS px ;
- portrait et paysage ;
- zoom 200 % ;
- reflow équivalent à 320 CSS px ;
- `fr-CA` et `en-CA` ;
- nom long d’organisation ;
- nom long d’utilisateur ;
- clavier virtuel ouvert.

Le passage d’un mode à l’autre ne doit pas scintiller après le chargement des traductions ou de la session.

## 13. Mesures de succès

| Indicateur | Cible initiale proposée |
| --- | --- |
| Trouver une destination sans aide | Au moins 90 % des essais. |
| Temps d’accès aux destinations fréquentes | Aucun ralentissement significatif par rapport à l’existant. |
| Erreurs de groupe | Moins de 10 % des essais. |
| Débordement ou chevauchement | Aucun dans les contextes testés. |
| Parcours réalisable au clavier | 100 % des actions prévues. |
| Destination affichée sans autorisation | Aucune. |
| Recherche mobile menée jusqu’aux résultats | Au moins 90 % des essais. |
| Sélection multiple et ajout | Réalisables sans défilement horizontal. |

Les cibles pourront être ajustées avant la recette, mais les décisions ne doivent pas reposer uniquement sur l’impression visuelle.

## 14. Critères d’acceptation proposés

### 14.1 Navigation

- Les quinze destinations restent accessibles sous réserve des droits.
- Les cinq destinations directes sont atteignables en une action sur grand écran.
- Les groupes secondaires ont un comportement identique pour tous les rôles.
- Le sélecteur d’organisation, l’aide et le compte ne sont pas dupliqués.
- La page active est identifiable visuellement et sémantiquement.
- Aucune navigation horizontale ne déborde ou ne passe sur deux lignes.

### 14.2 Responsive

- Le mode compact s’active avant tout chevauchement.
- Le tiroir tablette recouvre correctement les panneaux fonctionnels.
- La barre mobile ne masque aucune action de page.
- Le panneau « Plus » reste utilisable sans défilement horizontal.
- Le contenu arrière ne reçoit ni focus ni action tactile.
- Échap, Retour et la restauration du focus suivent les règles définies.
- Le comportement reste correct dans toutes les largeurs et langues prévues.

### 14.3 Recherche Google

- Le résumé correspond toujours aux résultats affichés.
- Le brouillon ne remplace pas silencieusement la recherche appliquée.
- Les premiers résultats sont visibles sans que la carte occupe l’essentiel de l’écran.
- Les paramètres restent utilisables avec le clavier virtuel.
- La sélection multiple affiche son nombre et son action principale.
- La liste ne requiert aucun défilement horizontal.
- La carte est accessible au clavier et ses informations essentielles sont également textuelles.
- L’attribution Google Maps reste conforme.

### 14.4 Autorisations

- Un groupe vide est absent.
- Les destinations communes conservent leur ordre relatif.
- Le changement d’organisation met à jour le contexte et la navigation de manière atomique.
- Une URL interdite produit un refus contrôlé côté interface et côté serveur.

### 14.5 Extension Automatisation

- Aucun menu Automatisation n’est visible avant la satisfaction des conditions d’activation.
- Une seule entrée globale donne accès à l’expérience Automatisation.
- Aujourd’hui, Boîte d’entrée et Playbooks restent réunis dans cet espace.
- Passeport, Feu relationnel et Prévol apparaissent dans leurs contextes d’usage plutôt que comme menus globaux.
- L’apparition de l’entrée respecte les capacités de la session et le contexte d’organisation.
- L’ajout futur ne provoque aucun débordement de l’en-tête ni déplacement imprévisible des destinations principales.
- Sur mobile, l’entrée apparaît d’abord dans « Plus » avant toute promotion éventuelle vers la barre inférieure.

## 15. Validation avant spécification

### 15.1 Données à recueillir

- fréquence de visite de chaque destination par famille de rôles ;
- transitions les plus courantes entre les pages ;
- proportion d’utilisation mobile et tablette ;
- fréquence des changements d’organisation ;
- fréquence des recherches Google et des sélections multiples ;
- fréquence de consultation des quotas et rapports d’usage ;
- fréquence de création, suivi et téléchargement des exports CSV ;
- fréquence projetée puis observée de la page Aujourd’hui, de la Boîte d’entrée et des Playbooks ;
- transitions entre Aujourd’hui, Mes tâches, Prospects, Pipeline et Opportunités.

### 15.2 Études à conduire

1. réaliser un tri de cartes avec des commerciaux, gestionnaires et administrateurs ;
2. effectuer un test d’arborescence sur les principales destinations ;
3. comparer la navigation actuelle, une navigation entièrement catégorisée et la navigation hybride ;
4. tester les scénarios « consulter mes tâches », « retrouver un prospect », « accéder au pipeline », « consulter son usage », « préparer un export CSV », « changer d’organisation » et « ouvrir le Journal d’activité » ;
5. tester sur mobile une recherche Google, la modification des paramètres, la sélection multiple et l’accès à la carte ;
6. lorsque le prototype Automatisation existe, comparer les libellés « Automatisation » et « Aujourd’hui » ainsi que les variantes de placement direct et regroupé ;
7. vérifier que les utilisateurs comprennent Passeport, Feu relationnel et Prévol sans les rechercher comme modules autonomes.

### 15.3 Mesures comparatives

- taux de réussite sans aide ;
- temps pour atteindre la destination ;
- nombre de clics ou touchers ;
- erreurs de groupe ;
- retours arrière ;
- capacité à identifier les paramètres ayant produit les résultats ;
- temps nécessaire pour sélectionner et ajouter plusieurs établissements ;
- temps nécessaire pour trouver un rapport d’usage et comprendre sa portée ;
- temps nécessaire pour créer puis retrouver un export CSV.

## 16. Décisions restant à valider

1. les cinq accès directs sur grand écran ;
2. le nom « Données et audit » ;
3. la place du Journal d’activité ;
4. la barre mobile inférieure et ses quatre destinations ;
5. le comportement du panneau « Plus » ;
6. le libellé « Recherche d’établissements » ;
7. la liste compacte ou les cartes pour les résultats ;
8. la place de la carte après la recherche ;
9. la conservation ou l’abandon d’un brouillon de paramètres à la fermeture ;
10. les seuils responsive définitifs ;
11. la présence de descriptions dans les sous-menus ;
12. le libellé global « Automatisation » ou « Aujourd’hui » ;
13. la variante de placement sur grand écran ;
14. la promotion éventuelle d’Aujourd’hui dans la barre mobile ;
15. le raccourci à remplacer si la navigation directe doit conserver un maximum de cinq destinations ;
16. les libellés « Quotas et usage » et « Exports CSV » ;
17. l’ordre des cinq destinations de « Données et audit » ;
18. le seuil à partir duquel « Données et audit » doit être séparé en deux groupes.

## 17. Séquence recommandée

### Étape 1 — Socle de navigation

- corriger le modèle de superposition dans les maquettes ;
- séparer navigation, organisation, aide et compte ;
- définir les comportements clavier et responsive ;
- préparer la mesure des visites et transitions.

### Étape 2 — Architecture de l’information

- recueillir les fréquences et transitions ;
- conduire le tri de cartes et le test d’arborescence ;
- comparer la navigation catégorisée et la navigation hybride ;
- valider les libellés français et anglais.

### Étape 3 — Recherche Google mobile

- prototyper le brouillon et la recherche appliquée ;
- comparer liste compacte et cartes ;
- comparer résultats prioritaires et carte prioritaire ;
- valider la sélection multiple.

### Étape 4 — Spécification et recette

- consigner les décisions issues des tests ;
- produire les spécifications détaillées ;
- définir les cas de recette par rôle, langue et largeur ;
- planifier l’implémentation seulement après validation.

### Extension conditionnelle — Automatisation

- réserver la place dans les maquettes et le modèle de navigation sans afficher d’entrée inactive ;
- suivre la conception du noyau Lite et ses portes de validation ;
- prototyper l’espace unique Automatisation lorsque les parcours sont suffisamment définis ;
- comparer les variantes de libellé et de placement ;
- activer le menu uniquement après satisfaction des huit conditions d’activation de la section 5.5.

## 18. Hors périmètre

Cette proposition ne modifie pas :

- les règles métier des modules ;
- les capacités accordées aux rôles ;
- les routes applicatives ;
- les règles de facturation ou d’appel Google ;
- les données conservées ;
- le contenu fonctionnel des pages en dehors des adaptations de présentation décrites ;
- la conception métier, les règles d’autonomie et l’implémentation du volet Automatisation, qui restent régies par leurs documents dédiés.
