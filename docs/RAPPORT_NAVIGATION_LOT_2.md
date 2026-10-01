# Rapport d’implémentation — NAV-L2 Responsive

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | NAV-L2 — Responsive |
| Date | 25 septembre 2026 |
| État | Validé ; verrou automatisé et recette applicative verte |
| Recette réelle | PASS le 26 septembre 2026 |
| Prérequis | NAV-L1 implémenté et validé automatiquement |

## 1. Résultat

Le lot responsive est implémenté sans modifier les routes, les capacités serveur ni les règles métier. La navigation est désormais adaptée à trois situations d’espace réel :

- à partir de 1 400 px : navigation complète et catégories dans l’en-tête ;
- de 601 à 1 399 px : en-tête compact et ouverture par le bouton `Menu` ;
- jusqu’à 600 px : barre inférieure stable, complétée par `Plus`.

Le seuil mobile est fondé sur la largeur logique disponible. Le contrôle à 600/640 px couvre aussi le comportement attendu à un zoom de 200 % pour une fenêtre physique de 1 200/1 280 px. Les libellés longs, le français et l’anglais ont été contrôlés sans débordement horizontal.

## 2. Comportements livrés

### 2.1 Panneau modal

Le panneau compact utilise l’élément natif `<dialog>` avec `showModal()` :

- le contenu arrière est rendu inerte par le navigateur ;
- le focus initial va au bouton de fermeture ;
- Échap, le bouton de fermeture et un clic sur l’arrière-plan ferment le panneau ;
- le focus revient au bouton `Menu` ou `Plus` qui a déclenché l’ouverture ;
- un repli clavier est prévu pour les environnements de test qui ne prennent pas en charge `showModal()` ;
- les liens modifiés avec Ctrl/Cmd conservent le comportement ordinaire du navigateur.

Le panneau est limité à `100dvh`, défilable et protégé contre le débordement de défilement. Les marges haute et basse utilisent `env(safe-area-inset-*)`. En paysage ou avec un clavier virtuel réduisant le viewport dynamique, l’en-tête de fermeture reste collant et le contenu reste parcourable.

### 2.2 Retour et changements de contexte

L’ouverture ajoute une entrée d’historique sans changer l’URL. Le bouton Retour ferme donc d’abord le panneau. Une fermeture explicite consomme cette entrée ; une navigation depuis le panneau la retire avant de changer de route. L’avance navigateur ne rouvre pas le panneau.

Le panneau se ferme également lors d’un changement de route, d’organisation, de langue ou de capacités. Le passage à la largeur desktop le ferme et restitue le focus. La rotation dans un format compact conserve un panneau utilisable.

### 2.3 Barre mobile filtrée par droits

La barre suit l’ordre stable demandé :

1. Accueil ;
2. Tâches ;
3. Prospects ;
4. Pipeline ;
5. Plus.

Les quatre destinations sont présentes uniquement lorsque leur route est réellement autorisée par la session. `Plus` reste toujours disponible afin de donner accès aux autres destinations, y compris pour un profil Plateforme sans organisation. Sur une page qui n’appartient pas aux quatre raccourcis, `Plus` porte le repère actif.

L’organisation active ou son sélecteur, ainsi que le compte utilisateur, restent disponibles dans l’en-tête. Le Manuel est déplacé dans le pied du panneau sur mobile afin de préserver cet espace de contexte.

### 2.4 Coexistence avec Recherche Google

La hauteur de la barre, zone sûre comprise, est réservée sous le contenu et dans le panneau des paramètres. La barre globale utilise un niveau inférieur aux superpositions Google existantes : l’ouverture des paramètres et leurs actions restent donc au premier plan. Les pages conservent un espace inférieur suffisant pour que leurs dernières commandes ne soient pas masquées.

## 3. Fichiers concernés

| Fichier | Contribution |
| --- | --- |
| `client/src/app/AuthenticatedLayout.jsx` | Orchestration responsive, contexte, historique Retour, fermeture et focus |
| `client/src/app/MobileNavigationBar.jsx` | Barre mobile stable et filtrée par capacités |
| `client/src/app/NavigationDialog.jsx` | Dialogue modal natif, focus, Échap et repli de piège à focus |
| `client/src/app/NavigationDisclosure.jsx` | Fermeture mutualisée sans multiplier les écouteurs globaux |
| `client/src/app/navigationModel.js` | Sélection ordonnée des raccourcis mobiles autorisés |
| `client/src/app/navigation.css` | Seuils, zones sûres, viewport dynamique, orientation et empilement |
| `client/src/icons.jsx` | Icônes des raccourcis mobiles |
| `client/src/app/AuthenticatedLayout.test.jsx` | Tests du dialogue, de Retour, du focus et du filtrage |
| `client/src/app/navigationModel.test.js` | Ordre et filtrage du modèle mobile |
| `scripts/navigation_lot2_browser.mjs` | Parcours navigateur synthétique multi-format |
| `scripts/navigation_lot1_browser.mjs` | Compatibilité du contrôle NAV-L1 avec la barre NAV-L2 |

## 4. Preuves automatisées

| Contrôle | Résultat |
| --- | --- |
| Tests ciblés navigation/routage | 26 tests dans 3 fichiers : PASS |
| Suite frontend complète | 207 tests dans 47 fichiers : PASS |
| ESLint | PASS, zéro avertissement |
| Build Vite | PASS, 116 modules transformés |
| Navigateur Chromium synthétique | PASS sur 320, 360, 390, 600, 640, 768, 1024, 1280, 1400 et 1440 px |
| Accessibilité du panneau ouvert | axe WCAG 2 A/AA : zéro violation |
| Modalité réelle | `<dialog>:modal`, arrière-plan inerte et focus contenu dans le panneau : PASS |
| Retour / Échap | fermeture et restitution du focus : PASS |
| FR/EN et noms longs | PASS, aucun débordement horizontal |
| Droits réels | raccourcis réduits et profil Plateforme sans organisation : PASS |
| Orientation et Google | paysage, hauteur dynamique, espace inférieur et empilement : PASS |

Le build émet une réserve non bloquante déjà visible au niveau du bundle global : le fichier JavaScript produit atteint 520,00 kB minifié, au-dessus du seuil informatif de 500 kB de Vite. Le lot n’ajoute aucune dépendance d’exécution ; un découpage de bundle relève d’un chantier de performance séparé.

## 5. Recette applicative

Résultat consigné le 26 septembre 2026 : **NAV-L2-01 à NAV-L2-07 sont PASS**. Les preuves réelles couvrent l’en-tête complet et compact, le panneau modal, la navigation mobile, les pages Prospects/Pipeline/Journal d’activité, le rendu au zoom élevé et un iPhone avec barre inférieure. Aucun chevauchement bloquant ni perte d’accès n’a été signalé.

Les contrôles suivants ont été effectivement couverts :

- un téléphone iOS avec encoche ou zone d’accueil et un téléphone Android ;
- le clavier virtuel dans les paramètres Google, en portrait et paysage ;
- le zoom navigateur 200 % sur une fenêtre desktop réelle ;
- les comptes Sales, Manager, Admin, Plateforme et sans organisation ;
- Retour/Avance après plusieurs ouvertures, navigations et changements d’organisation ;
- les dernières actions de chaque page, afin de confirmer qu’aucune n’est cachée par la barre inférieure.

## 6. Verdict

Le verrou automatisé et la recette applicative de NAV-L2 sont **VERTS**, avec la réserve non bloquante de taille de bundle. NAV-L3 demeure à valider sur application réelle.
