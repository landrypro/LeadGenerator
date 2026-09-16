# Améliorations pré-2.6 — Identité des prospects et marque

## Décision

Avant l'incrément 2.6, Marketteo sépare explicitement trois notions :

1. le **nom Google**, affiché uniquement dans les résultats temporaires de recherche ;
2. le **`place_id`**, référence Google persistante, visible et non modifiable ;
3. le **nom interne CRM**, choisi et saisi par l'utilisateur, persistant et modifiable.

Le nom Google n'est jamais envoyé à la route de création du prospect et n'est pas utilisé automatiquement comme nom interne.

## Contrat applicatif

L'ajout depuis Google reçoit un jeton de sélection et une liste de vingt éléments maximum :

```json
{
  "selection_token": "jeton-à-ne-pas-journaliser",
  "items": [
    {
      "place_id": "référence-google",
      "internal_alias": "Nom choisi par l'organisation"
    }
  ]
}
```

Le serveur vérifie chaque `place_id` contre le jeton de sélection. Un `place_id` déjà présent dans l'organisation retourne le prospect existant et ne modifie pas silencieusement son nom interne.

## Recherche et consultation

- le tableau Google affiche le `place_id` avec le nom Google temporaire ;
- l'ajout reste inaccessible tant que le nom interne est vide ;
- la liste des prospects recherche aussi par `place_id` ;
- la liste et la fiche présentent le `place_id` séparément du nom interne ;
- seul le nom interne est modifiable.

## Conformité Google

Google autorise la conservation d'un Place ID et recommande de le rafraîchir lorsqu'il a plus de douze mois. Les autres contenus Places restent soumis aux restrictions de mise en cache et de stockage. La présente évolution ne change ni l'attribution Google Maps, ni la limite d'une requête Text Search, ni le maximum de vingt résultats, ni l'absence de contacts et de pagination.

Références :

- [Google Maps Platform — Places API Policies](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Maps Platform — Place IDs](https://developers.google.com/maps/documentation/places/web-service/place-id)

## Migration de marque

Les libellés visibles passent de « Prospect » ou « Prospect CRM » à **Marketteo** ou **Marketteo CRM**. Les identifiants techniques historiques restent stables dans cet incrément : nom du paquet frontend, cookie de session, schéma PostgreSQL, noms Compose et chemins du dépôt. Leur renommage nécessiterait une migration dédiée et n'apporte aucune valeur fonctionnelle immédiate.

## Limites et suivi

- les prospects Google historiques qui portent encore un alias généré doivent être renommés manuellement ; le système ne peut pas reconstruire un nom d'établissement depuis le `place_id` sans un nouvel affichage Google explicite ;
- un mécanisme contrôlé de rafraîchissement des Place IDs âgés de plus de douze mois devra être spécifié séparément, avec estimation de coût et tests de conformité ;
- la disponibilité juridique de la marque Marketteo demeure une validation commerciale distincte.
