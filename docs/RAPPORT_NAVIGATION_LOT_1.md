# NAV-L1 — Navigation globale

Références : [plan des trois lots](PLAN_IMPLEMENTATION_NAVIGATION_HYBRIDE.md), [architecture validée](PROPOSITION_NAVIGATION_RESPONSIVE_MENUS.md).

Statut : **validé — verrou frontend vert et recette applicative utilisateur PASS le 26 septembre 2026**.

## Réalisation

La navigation combine cinq accès quotidiens et trois groupes : Acquisition, Données et audit, Administration. Le menu utilisateur contient le rôle, Compte et Déconnexion ; le manuel et le changement d’organisation demeurent séparés. Les libellés de navigation sont localisés en français et anglais. Sans organisation, la langue de navigation reprend la préférence publique existante.

La page sans organisation propose désormais un lien Compte. Le composant de changement d’organisation conserve son traitement des erreurs, sa désactivation pendant la requête et la redirection vers une route autorisée ; ses annonces sont traduites.

Plateforme et Audit plateforme restent deux liens distincts, chacun conditionné par sa propre capacité. Les droits ne sont jamais déduits du nom du rôle.

| Destination | Capacité existante |
| --- | --- |
| Tableau de bord | `dashboard:read:self` |
| Mes tâches | `tasks:read` |
| Prospects | `prospects:read` |
| Pipeline | `pipeline:read` |
| Opportunités | `opportunities:read` |
| Recherche d’établissements | `google:search` |
| Sources et acquisitions | `providers:read` |
| Quotas et usage | `usage:read:self` |
| Conservation et imports | `retention:read` |
| Historique des imports | `imports:read` |
| Exports CSV | `exports:create:self` |
| Journal d’activité | `audit:read` |
| Organisation | `organization:read` |
| Membres | `members:read` |
| Plateforme | `platform:organizations:read` |
| Audit plateforme | `platform:audit:read` |
| Compte | Session authentifiée, sans capacité supplémentaire |

Les destinations organisationnelles nécessitent aussi une organisation active selon le registre des routes inchangé. Les liens sont filtrés avant regroupement. Les groupes vides disparaissent et les groupes à un lien gardent un comportement de panneau.

Les catégories utilisent des disclosures HTML natives avec des liens ordinaires. Échap ferme la couche de catégorie et rend le focus à son déclencheur. La navigation place le focus au contenu. Les menus se ferment à la sortie du focus, au clic extérieur et au changement de route, d’utilisateur ou de capacités. Les ouvertures de liens avec Ctrl/Cmd conservent le comportement navigateur.

## Fichiers

- `client/src/app/navigationModel.js` : classement des routes autorisées et repères actifs ;
- `client/src/app/NavigationDisclosure.jsx` et `navigation.css` : groupes et présentation ;
- `client/src/app/AuthenticatedLayout.jsx` : intégration de la navigation et du compte ;
- `client/src/features/auth/NoOrganizationPage.jsx` : accès Compte ;
- `client/src/features/organizations/OrganizationSwitcher.jsx` : annonces FR/EN ;
- tests du modèle, du layout et du routeur ;
- `scripts/navigation_lot1_browser.mjs` : rejeu navigateur avec session synthétique et interception de toutes les API.

## Vérifications

| Contrôle | Résultat |
| --- | --- |
| ESLint frontend | PASS |
| Build Vite | PASS ; avertissement non bloquant de bundle supérieur à 500 kB |
| Suite frontend complète | PASS : 204 tests dans 47 fichiers, aucun échec ni test ignoré |
| Navigateur : catégories, focus, 1440/1280/390 px, EN, plateforme et compte sans organisation | PASS, API simulées |
| En-tête à 1440 px avec noms longs | PASS, aucun chevauchement détecté |
| axe sur l’en-tête fermé | PASS, aucune violation détectée dans ce périmètre |

Commandes reproductibles :

```powershell
npm --prefix client run lint
npm --prefix client test -- --reporter=verbose
npm --prefix client run build
npm --prefix client run preview -- --host 127.0.0.1 --port 4178 --strictPort
# Dans un second terminal, avec Playwright disponible :
node scripts/navigation_lot1_browser.mjs <chemin-du-module-playwright>
```

La première exécution complète, silencieuse pendant plus de dix minutes, a été interrompue sans verdict exploitable. La relance avec rapport détaillé a réussi en 593,97 secondes. Le lint final et le build ont également réussi. Aucun verrou backend n’a été exécuté pour ce lot exclusivement frontend.

## Recette applicative à jouer

1. Sur un compte organisationnel, parcourir les cinq accès directs et les trois groupes, puis vérifier l’entrée active.
2. Avec un compte à capacités réduites, vérifier la disparition des seuls liens non autorisés et l’absence de groupes vides.
3. Avec un compte plateforme, ouvrir séparément Plateforme et Audit plateforme selon les capacités accordées.
4. Ouvrir le menu utilisateur, vérifier le rôle et accéder à Compte ; vérifier aussi Compte depuis l’écran sans organisation.
5. Changer d’organisation avec un compte multi-organisation et vérifier les liens recalculés et la route d’arrivée.
6. Rejouer en anglais ; vérifier Échap, Tab, le clic extérieur, les liens Ctrl/Cmd et le manuel.

Résultat consigné le 26 septembre 2026 : **NAV-L1-01 à NAV-L1-07 sont PASS**. Les preuves applicatives confirment les catégories Acquisition / Données et audit / Administration, le repère actif sur Prospects, Pipeline et Recherche Google, le menu Compte, les destinations Plateforme et Audit plateforme sans organisation active, ainsi que le maintien des pages métier. La recette réelle de NAV-L1 est donc close.

## Limites et suite

Le lot 2 finalisera la barre inférieure, l’inertie du contenu arrière, le piège de focus du panneau compact, Retour et les comportements du clavier mobile. Le lot 1 maintient une présentation compacte de base pour les groupes, avec un seuil provisoire de 1400 px.

Automatisation demeure absente jusqu’à son activation produit. Le lot 3 portera les changements d’ergonomie de Recherche Google. Les tests navigateur du présent lot n’ont pas appelé le backend réel ; la recette utilisateur de l’application reste à effectuer avant clôture fonctionnelle du lot.
