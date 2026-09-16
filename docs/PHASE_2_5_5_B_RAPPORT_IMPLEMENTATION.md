# Incrément 2.5.5-B — Rapport d’implémentation

| Élément | Valeur |
|---|---|
| Statut | Implémenté ; recette PostgreSQL regroupée en attente de 2.5.5-E |
| Périmètre | Fiche prospect, contacts, canaux et permissions |
| Migration | Aucune : les tables et contraintes de 2.5.1–2.5.4 sont réutilisées |

## Résultat livré

La liste Prospects ouvre désormais une fiche CRM routable (`/app/prospects/:prospectId`). Elle permet, selon les
capacités de l’utilisateur connecté :

- de consulter et modifier le profil CRM déjà autorisé (alias, secteur, ville, priorité et étiquettes) ;
- de consulter et créer une personne de contact ;
- de consulter les canaux directs de l’établissement et les canaux rattachés à chaque contact ;
- d’ajouter un canal manuel à l’établissement ou à une personne (courriel, téléphone, LinkedIn, Facebook ou autre) ;
- d’autoriser ou de restreindre un canal direct lorsque la capacité correspondante est accordée.

L’autorisation d’un canal transmet sa provenance au backend : elle respecte donc la règle métier qui exige une base
légale et une provenance. Les restrictions restent disponibles uniquement selon les capacités `permissions:restrict`.

## API et architecture

Deux lectures applicatives sont ajoutées derrière les ports existants et protégées par le contexte locataire/RLS :

- `GET /api/prospects/{prospect_id}/channels` ;
- `GET /api/contacts/{contact_id}/channels`.

Elles exigent `contacts:read`, retournent `Cache-Control: no-store` et n’introduisent aucun stockage navigateur.
Les écritures utilisent les endpoints, protections CSRF et journalisation déjà introduits par 2.5.3.

## Hors périmètre maintenu

- aucune donnée descriptive Google n’est copiée ou affichée dans la fiche CRM ;
- aucune action commerciale, envoi de message, import de fichier ou Kanban n’est introduit ;
- aucune suppression physique n’est ajoutée ;
- la recette réelle PostgreSQL/RLS et le verrou qualité complet restent regroupés avec 2.5.5-E.

## Vérifications effectuées

- `pytest -q` : **196 passed, 29 skipped**. Windows a ensuite signalé un nettoyage temporaire pytest refusé ; ce
  message intervient après la réussite complète des tests et ne modifie pas leur résultat.
- Tests frontend ciblés : **7 passed** (routage, liste et fiche Prospect), avec le pool `forks` et sans parallélisme
  de fichiers, configuration nécessaire sur ce poste Windows.
- `ruff format --check backend/app` : vert.
- `ruff check backend/app` : vert.
- `mypy backend` : vert (**142 fichiers source**).
- `npm run lint` et `npm run build` : verts.

## Passage suivant

2.5.5-B est prêt pour **2.5.5-C — Fournisseurs et acquisitions**. La validation métier locale complète reste à
exécuter une seule fois après 2.5.5-E, conformément à la décision de recette regroupée.
