# Fonctionnalités transitoires avant CRM V1

Ce registre empêche les fonctions historiques du générateur de devenir des dépendances durables du CRM. Elles restent disponibles uniquement pour préserver le fonctionnement actuel pendant la migration.

| Fonction transitoire | État actuel | Remplacement CRM V1 | Suppression prévue |
| --- | --- | --- | --- |
| Recherche Google multi-zone, multi-page et objectif jusqu’à 500 résultats | Route `POST /api/leads/search` et champs `target`, `max_tiles`, `max_pages` marqués `deprecated` dans OpenAPI | Recherche Google explicite limitée à 20 résultats, sans pagination ni balayage multi-zone | Bascule vers le module de recherche Google V1 |
| Export Excel des résultats Google bruts | Route `POST /api/leads/export` marquée `deprecated` dans OpenAPI | Export des seules données internes du CRM, avec provenance et permissions | Activation du module d’import/export CRM V1 |

## Règles de migration

- Ne pas ajouter de nouvelle fonctionnalité aux routes transitoires.
- Limiter les corrections à la sécurité, aux régressions et à la continuité de service.
- Ne pas réutiliser `ExcelLeadExporter` pour les futurs exports CRM.
- Développer les remplacements derrière de nouveaux cas d’utilisation et de nouveaux contrats API.
- Supprimer les façades, tests et contrôles historiques uniquement après validation des parcours CRM équivalents.

Le test d’intégration `test_legacy_search_and_export_remain_marked_as_deprecated` protège ce statut jusqu’à la suppression effective des routes.
