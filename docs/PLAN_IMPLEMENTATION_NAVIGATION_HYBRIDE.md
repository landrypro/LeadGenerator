# Navigation hybride — lots d’implémentation

Référence UX : [proposition validée](PROPOSITION_NAVIGATION_RESPONSIVE_MENUS.md), prototype V2 et [recette validée](../prototypes/navigation-hybride/RECETTE_PROTOTYPE_V2.md).

La recette applicative consolidée est préparée dans le [kit Relooking UX — lots 1 à 3](RECETTE_RELOOKING_UX_NAVIGATION_LOTS_1_2_3.md).

Le GO de conception est acquis. Les lots 1 et 2 sont implémentés et couverts automatiquement. La recette applicative réelle des changements responsive sera exécutée par l’utilisateur à la fin des travaux. Le lot 3 reste planifié.

| Lot | Périmètre | État |
| --- | --- | --- |
| NAV-L1 — Navigation globale | Catégories, capacités réelles, Plateforme/Audit plateforme, organisation, aide et compte | Validé sur application réelle le 26 septembre 2026 |
| NAV-L2 — Responsive | En-tête compact finalisé, panneau modal, barre inférieure, inertie, clavier, focus et Retour | Validé sur application réelle le 26 septembre 2026, y compris NAV-L2-COR-01 |
| NAV-L3 — Recherche mobile | Paramètres brouillon/appliqués, résultats, carte secondaire, sélection et ajout CRM | Validé sur application réelle le 26 septembre 2026 |

## NAV-L1 — Navigation globale

Conserver les URL, la résolution des routes et les contrôles d’accès existants. Construire la navigation à partir de `navigationRoutes(session)` : aucune matrice de rôles propre au prototype ne devient une règle applicative.

| Zone | Destinations dans l’ordre |
| --- | --- |
| Accès directs | Tableau de bord, Mes tâches, Prospects, Pipeline, Opportunités |
| Acquisition | Recherche d’établissements, Sources et acquisitions |
| Données et audit | Quotas et usage, Conservation et imports, Historique des imports, Exports CSV, Journal d’activité |
| Administration | Organisation, Membres |
| Plateforme | Plateforme, Audit plateforme, selon leurs capacités indépendantes |
| Contexte | Organisation active/changement, Manuel, utilisateur avec rôle, Compte et Déconnexion |

Les groupes vides sont masqués. Un groupe avec une seule destination reste un groupe. Les pages de création/détail prospect conservent le repère Prospects. Les menus se ferment avec Échap, à la sortie du focus, au clic extérieur et après navigation. Un changement de contexte ferme les menus et recalcule les destinations. Compte reste accessible sans organisation. Le changement d’organisation conserve le composant existant, son état d’attente, ses erreurs et la redirection vers une route autorisée.

Automatisation ne reçoit aucune route ni entrée visible. Son emplacement futur reste réservé après Tableau de bord. Aucun changement de capacité serveur n’est prévu.

Critères de recette :

- `NAV-L1-01` : ordre direct et catégories conformes, labels FR/EN ;
- `NAV-L1-02` : seuls les liens autorisés par la session sont exposés, groupes vides absents ;
- `NAV-L1-03` : Plateforme et Audit plateforme indépendants, Compte sans organisation ;
- `NAV-L1-04` : repère actif sur la page et son groupe, fermeture/clavier et liens avec Ctrl/Cmd préservés ;
- `NAV-L1-05` : changement d’organisation, attente/erreur et recalcul des menus ;
- `NAV-L1-06` : accès Compte, identité/rôle, Manuel et Déconnexion ;
- `NAV-L1-07` : Automatisation absente, pages métier et routes inchangées.

Validation : tests navigation/routage/contexte, suite frontend, lint, build et contrôle navigateur ciblé. Le verrou backend complet n’est pas proportionné à ce lot exclusivement frontend ; les modifications backend présentes dans l’espace de travail relèvent d’autres travaux. La compatibilité provisoire du panneau a été remplacée par le comportement final de NAV-L2.

## NAV-L2 — Responsive

Dépend de NAV-L1. Les seuils retenus sont : navigation complète à partir de 1 400 px, en-tête compact et bouton Menu de 601 à 1 399 px, barre inférieure jusqu’à 600 px. Une largeur logique de 600 à 640 px couvre notamment le repli attendu à 200 % d’une fenêtre courante de 1 200 à 1 280 px. Le panneau est un dialogue modal natif : le contenu arrière devient inerte, Échap et le bouton de fermeture rendent le focus au déclencheur, et Retour consomme l’état d’ouverture sans changer de page.

La barre stable présente, dans cet ordre, les raccourcis autorisés parmi `Accueil | Tâches | Prospects | Pipeline`, puis `Plus`. Les absences sont déterminées par les capacités réelles de la session. Organisation et compte restent dans l’en-tête ; le Manuel est aussi disponible dans le panneau. Le panneau utilise `100dvh`, reste défilable avec un clavier virtuel et respecte les zones sûres. Une rotation conserve un contenu et une fermeture accessibles ; le passage à la largeur desktop ferme le panneau. La barre réserve l’espace inférieur du contenu et reste sous la superposition des paramètres Google pour ne pas masquer ceux-ci ni leurs actions.

Recette automatisée : 1440/1400/1280/1024/768/640/600/390/360/320 px, noms longs, FR/EN, capacités réduites, profil Plateforme sans organisation, orientation paysage, dialogue modal/inertie, Retour, Échap, zones sûres, absence de chevauchement Google et axe. La recette avec clavier virtuel et appareils réels reste volontairement différée à la campagne applicative finale. Aucun accès ne doit disparaître sans alternative, aucun contenu arrière ne doit recevoir le focus quand le panneau est ouvert.

## NAV-L3 — Recherche mobile

Dépend de NAV-L2. Donner la priorité aux résultats ; ouvrir les paramètres séparément, distinguer brouillon et recherche appliquée, préserver les saisies au redimensionnement et purger les données au changement d’organisation. Conserver l’autocomplétion et les coordonnées existantes, les quotas et les contraintes de données Google. Carte secondaire, sélection partielle, barre d’action accessible et saisie explicite du nom CRM.

Recette : rechercher, modifier/annuler, sélectionner/ajouter, erreur/récupération, absence de résultats, quota et interruption ; aucune recherche implicite facturable, aucune copie automatique du nom Google. Valider les parcours réels et l’accessibilité après intégration.

## Traçabilité et progression

Chaque lot reçoit un bilan des fichiers, contrôles et résultats avant de passer au suivant. Les preuves du prototype restent historiques et ne remplacent pas la recette applicative. Un retour arrière du lot 1 consiste à rétablir le rendu de navigation précédent sans migration de données.

Le [rapport du lot 1](RAPPORT_NAVIGATION_LOT_1.md) consigne la navigation globale. Le [rapport du lot 2](RAPPORT_NAVIGATION_LOT_2.md) consigne le responsive et ses preuves : 207 tests frontend dans 47 fichiers, lint, build et parcours navigateur ciblé réussis. Le [rapport du lot 3](RAPPORT_NAVIGATION_LOT_3.md) consigne les preuves ciblées de la recherche mobile. La recette applicative réelle des trois lots demeure à effectuer.
