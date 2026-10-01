# Rapport d’implémentation — NAV-L3 Recherche mobile

| Élément | Valeur |
| --- | --- |
| Date | 25 septembre 2026 |
| État | Validé ; verrou automatisé et recette applicative verte |
| Recette réelle | PASS le 26 septembre 2026 |

## Résultat

La recherche Google sur mobile donne désormais priorité aux résultats. Les paramètres s’ouvrent dans un panneau modal : le brouillon est distinct de la dernière recherche appliquée. Fermer le panneau conserve le brouillon ; **Annuler** restaure la recherche appliquée. Échap, Retour et fermeture ramènent le focus au déclencheur et le contenu arrière est inerte.

Après une recherche, le résumé appliqué précède les résultats ; la carte et les métriques sont secondaires et ne s’affichent qu’à la demande. La sélection prend en charge l’état partiel et l’ajout CRM exige toujours un nom interne explicite : aucun nom Google n’est recopié, aucune écriture ne part si ce nom manque. Un changement d’organisation efface résultats temporaires et sélection.

## Fichiers principaux

- `client/src/features/lead-search/LeadGeneratorPage.jsx` : état brouillon/appliqué, historique, inertie et changement d’organisation ;
- `components/SearchSidebar.jsx` et `MobileSearchSummary.jsx` : panneau et résumé mobile ;
- `components/ResultsCard.jsx`, `LeadTable.jsx`, `hooks/useProspectAdds.js` : sélection, focus et ajout CRM ;
- `hooks/useLeadSearch.js` : annulation/purge des résultats ;
- `scripts/navigation_lot3_browser.mjs` : parcours Chromium synthétique.

## Preuves

| Contrôle | Résultat |
| --- | --- |
| ESLint | PASS, zéro avertissement |
| Tests ciblés recherche | PASS — 19 tests |
| Build Vite | PASS — 117 modules transformés |
| Parcours Chromium | PASS — brouillon/appliqué, inertie, carte secondaire, sélection et CRM |
| axe WCAG 2 A/AA | PASS — zéro violation dans le parcours mobile |

Le build conserve la réserve non bloquante connue : bundle JavaScript de 527,53 kB minifié, au-dessus du seuil informatif Vite de 500 kB.

## Recette applicative

Résultat consigné le 26 septembre 2026 : **NAV-L3-01 à NAV-L3-11 sont PASS**. La campagne réelle couvre les appareils mobiles, les libellés fr-CA/en-CA, les paramètres et coordonnées, la séparation brouillon/recherche appliquée, les résultats et leur filtre, les états sans résultat et erreur/récupération, la carte secondaire, les sélections unitaire et globale, ainsi que l’ajout CRM avec nom interne explicite.

Les preuves confirment en particulier qu’aucun nom Google n’est recopié comme nom CRM, que la barre d’action de sélection reste disponible au-dessus de la navigation inférieure et que l’erreur de liaison serveur demeure récupérable sans perte du résultat déjà appliqué.
