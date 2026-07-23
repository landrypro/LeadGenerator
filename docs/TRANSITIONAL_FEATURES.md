# Registre des fonctionnalités transitoires

## Verrou de conformité terminé le 22 juillet 2026

| Fonction historique | État après la phase 1 | Protection |
| --- | --- | --- |
| Recherche Google multi-zone et multi-page | Retirée du contrat HTTP et de la composition applicative | Le nouveau port ne possède qu’une opération `search` sans jeton de pagination. |
| Objectif pouvant atteindre 500 résultats | Retiré | `pageSize` vaut 20 et la limite est répétée dans le client Google, le cas d’usage et le schéma de réponse. |
| Téléphone et site Web dans la liste | Retirés | Le masque Google, le candidat applicatif et le schéma HTTP ne définissent aucun contact. |
| `POST /api/leads/search` | Route absente | Le seul chemin public est `POST /api/google/places/search`. |
| `POST /api/leads/export` | Route absente | Le bouton reste visible mais toujours désactivé, sans action frontend. |
| Contenu orienté extraction dans l’interface | Retiré | L’écran présente une recherche temporaire d’établissements pour Prospect CRM. |

L’ancien adaptateur Excel reste momentanément présent uniquement comme code non monté pour conserver le test de neutralisation des formules. Il n’est injecté dans aucun conteneur, n’est accessible par aucune route et ne doit pas être utilisé pour les futurs exports CRM. Son remplacement se fera par une liste blanche de données internes dans le module d’import/export.

## Invariants à préserver

- une action utilisateur produit exactement un POST Text Search ;
- aucun `nextPageToken` n’est demandé ou suivi ;
- aucun contenu Google n’est persisté ou exporté ;
- les réponses Google sont `no-store` ;
- les clés restent côté serveur ;
- la carte reste protégée par un jeton court à usage unique ;
- l’attribution `Google Maps` reste visible dans le conteneur des résultats.
