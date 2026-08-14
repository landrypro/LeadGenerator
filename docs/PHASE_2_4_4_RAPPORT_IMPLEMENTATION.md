# Phase 2.4.4 - Rapport d'implementation

| Metadonnee | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Increment | 2.4.4 - Suspension, reactivation et historique |
| Date | 13 aout 2026 |
| Statut | Implemente, controles locaux verts |
| Migration | `20260813_0008` |
| Spec source | `PHASE_2_4_4_SPECIFICATIONS_DETAILLEES.md` |

## 1. Resultat livre

L'increment livre les operations plateforme versionnees et idempotentes de suspension et reactivation d'organisation,
ainsi que l'ouverture de l'historique complet des invitations membre.

La suspension bloque l'organisation sans suppression. La reactivation restaure l'acces aux membres encore actifs, sans
reactiver les membres desactives ni les invitations terminales.

## 2. Backend

- ajout des commandes domaine `ChangeOrganizationStatusCommand` et `ValidatedChangeOrganizationStatus` ;
- validation stricte des raisons, versions, references externes et empreintes idempotentes ;
- ajout de la capacite `platform:organizations:manage` ;
- ajout du use case `ChangeOrganizationStatusUseCase` pour `suspend` et `reactivate` ;
- ajout des routes :
  - `POST /api/platform/organizations/{organization_id}/suspend` ;
  - `POST /api/platform/organizations/{organization_id}/reactivate` ;
- ajout du contrat `state` sur `GET /api/organization/invitations` ;
- extension de la lecture invitations : `open`, `active`, `expired`, `accepted`, `revoked`, `all` ;
- audit plateforme `organization.suspended` et `organization.reactivated` ;
- non-creation d'audit lors d'un rejeu idempotent.

## 3. PostgreSQL

La migration `20260813_0008` ajoute :

- la table `organization_status_operations` ;
- contraintes de raison, operation, empreinte, version et reference externe ;
- RLS forcee, limitee a la plateforme ;
- la fonction privee `app_private.platform_change_organization_status(...)`.

La fonction verrouille l'operation, gere le rejeu, refuse le contenu divergent, verifie la version, applique uniquement
les transitions `active -> suspended` et `suspended -> active`, puis retourne la vue plateforme existante.

## 4. Frontend

- ajout des appels `suspendOrganization` et `reactivateOrganization` ;
- ajout des boutons plateforme selon statut et capacite ;
- confirmation avec raison obligatoire et reference externe optionnelle ;
- conservation d'une intention par action en memoire uniquement ;
- filtre invitations `En cours` / `Tout l'historique` ;
- absence d'action sur les invitations terminales.

## 5. Tests executes

| Controle | Resultat |
| --- | --- |
| `pytest -q` | 161 passed, 23 skipped |
| `ruff check backend ...` | vert |
| `mypy backend` | vert |
| `npm run lint` | vert |
| `npm test` | 31 fichiers, 133 tests passed |
| `npm run build` | vert |
| `alembic heads` | `20260813_0008 (head)` |

Les tests ignores restent les tests d'infrastructure conditionnels deja presents dans le projet. Le verrou zero skip
reste reserve au verrou final 2.4.5 avec environnement PostgreSQL/Redis de recette complet.

## 6. Critique experte - premier passage

Le choix de conserver `ProvisioningResponse` pour la suspension/reactivation reduit le risque de rupture UI, mais il
lie encore la vue plateforme au concept d'invitation initiale. C'est acceptable pour 2.4.4, car l'ecran plateforme
existant est centre sur ce contrat. A moyen terme, une vue `PlatformOrganizationDetail` autonome sera plus nette.

L'idempotence est materialisee en base, pas seulement dans l'application. C'est le bon niveau de protection. La table
stocke cependant un resultat minimal et relit la vue courante au rejeu ; si l'organisation change apres l'operation,
le rejeu montrera la vue actuelle. Ce compromis est acceptable car le contrat utilisateur porte sur l'absence de double
mutation, pas sur une photographie historique complete.

## 7. Critique experte - second passage

Le blocage Google repose sur la relecture de session et la notion `MembershipIdentity.is_active`, qui combine
appartenance active et organisation active. C'est solide pour les appels authentifies. Le test manuel doit toutefois
confirmer qu'une session ouverte avant suspension perd bien sa capacite apres relecture serveur.

L'historique des invitations expose l'etat courant fiable et ne reconstruit pas les transitions passees. C'est prudent.
Il manque volontairement les dates terminales fines dans la reponse publique ; si le QA demande "quand exactement a ete
revoquee/acceptee", il faudra enrichir le modele de sortie dans une iteration dediee.

## 8. Revue code - angle architecture

Le changement respecte les couches existantes : domaine pour validation, use case pour orchestration, port pour contrat,
adaptateur PostgreSQL pour details SQL et route FastAPI pour transport. Les actions audit sont toujours construites par
la politique centrale, et non depuis une charge HTTP libre.

Point de vigilance : `platform:organizations:create` et `platform:organizations:manage` coexistent. C'est volontaire
pour separer provisioning et exploitation, mais les tests et les futures interfaces devront continuer a distinguer ces
deux intentions.

## 9. Revue code - angle securite/exploitation

La suspension n'est pas un simple bouton : la capacite locataire disparait quand l'organisation n'est plus active. Les
routes Google exigent une appartenance active et ne peuvent donc plus appeler le fournisseur apres suspension.

Les donnees sensibles restent absentes de l'audit. La reference externe est courte, formattee et optionnelle. La raison
est codee. Aucun filtre, curseur ni `operation_id` n'est persiste dans le navigateur.

## 10. Recette locale conseillee

1. Lancer la migration `20260813_0008`.
2. Se connecter comme Administrateur de plateforme.
3. Ouvrir `Organisations`.
4. Suspendre une organisation active avec raison `Administration`.
5. Verifier que le statut devient `Suspendue`.
6. Se connecter comme membre de cette organisation.
7. Verifier l'absence d'acces locataire et l'impossibilite de faire une recherche Google.
8. Revenir plateforme et reactiver l'organisation.
9. Verifier que les membres actifs retrouvent l'acces.
10. Ouvrir l'audit plateforme et verifier les evenements `organization.suspended` et `organization.reactivated`.
11. Ouvrir `Membres et invitations`.
12. Basculer de `En cours` vers `Tout l'historique`.
13. Confirmer que les invitations acceptees/revoquees/expirees apparaissent sans action disponible.

## 11. Decision restante

Le passage Azure et la recette de deploiement externe restent volontairement reportes au verrou final 2.4.5, conformement
a la decision produit prise avant 2.4.4.
