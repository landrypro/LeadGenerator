# Phase 2.3.5-B — Rapport d’implémentation de l’organisation active

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Lot | 2.3.5-B — Organisation active |
| Date | 3 août 2026 |
| Statut | Implémenté et validé localement par le responsable produit |
| Validation produit | 3 août 2026 |
| Migration SQL | Aucune |
| Révision Alembic | `20260802_0005 (head)` |

## 1. Résultat livré

Le lot B rend le contexte multi-organisation utilisable depuis le shell livré en A :

- le sélecteur est masqué avec une seule appartenance et visible à partir de deux ;
- la commande transmet uniquement `membership_id` à `POST /api/auth/switch-organization` ;
- la session, le jeton CSRF, les capacités, l’organisation active et la navigation sont remplacés ensemble ;
- une erreur conserve le contexte actif et ne déclenche aucun rejeu automatique ;
- les écrans locataires sont remontés avec une clé d’organisation, ce qui purge leurs états en mémoire ;
- les recherches et cartes en vol sont annulées et les réponses tardives sont ignorées ;
- `/app/admin/organization` expose la fiche de l’organisation active ;
- Admin modifie nom, langue et fuseau avec contrôle de version ; Manager et Sales restent en lecture seule.

Le backend de 2.3.3 fournissait déjà les contrats nécessaires. Aucun endpoint, schéma SQL ou élargissement de
permission n’a été ajouté.

## 2. Rotation atomique du contexte

`AuthProvider` centralise la transition. Une seule promesse de commutation peut être active. La session courante
reste installée pendant l’appel. La réponse réussie configure d’abord le nouveau CSRF et installe ensuite la nouvelle
session React. Un compteur de génération invalide toute réponse arrivée après une déconnexion ou un remplacement de
session concurrent.

Le shell recalcule immédiatement ses routes depuis les capacités retournées. Si la route actuelle n’est plus
autorisée, l’utilisateur est redirigé par remplacement d’historique vers sa première page accessible. L’identifiant
d’organisation ne vient jamais du formulaire ni de l’URL : il reste déduit par le serveur depuis la session.

## 3. Purge des états locataires

Le composant de route authentifié porte comme clé l’identifiant de l’organisation active. Une rotation démonte donc
l’ancien écran et efface formulaires, résultats Google, carte et curseurs React. Les hooks de recherche, de carte et
d’organisation utilisent en plus `AbortController` et un numéro de séquence afin qu’une réponse ancienne ne puisse
pas réinjecter de données après le démontage.

Aucune session, donnée locataire, réponse Google, concession ou sélection d’organisation n’est écrite dans
`localStorage` ou `sessionStorage`.

## 4. Page Organisation

La lecture utilise `GET /api/organization`. La fiche présente nom, langue, fuseau, état et dates localisées avec
`Intl.DateTimeFormat`, tout en conservant des éléments `<time datetime="…">`.

Avec `organization:update`, le formulaire :

- n’envoie que les champs réellement modifiés et la version lue ;
- reste désactivé sans changement et neutralise une double soumission ;
- met à jour la fiche et le nom affiché dans le shell à partir de la réponse serveur ;
- conserve la saisie sur `organization_version_conflict` ;
- affiche les versions chargée et actuelle, puis propose un rechargement explicite ;
- ne rejoue jamais automatiquement la mutation et ne permet ni suspension ni suppression.

Sans capacité de modification, aucun faux bouton désactivé n’est affiché : la fiche est strictement en lecture seule.

## 5. Tests ajoutés

Les tests frontend couvrent notamment :

- visibilité du sélecteur selon le nombre d’appartenances ;
- envoi de `membership_id` et absence d’envoi d’`organization_id` ;
- rotation atomique du contexte et du CSRF ;
- fusion des commutations simultanées en un seul appel HTTP ;
- conservation de l’ancien contexte en cas d’erreur ;
- rejet d’une réponse tardive après déconnexion, y compris pendant une déconnexion serveur lente ;
- recalcul d’une route sûre après rotation ;
- démontage et annulation d’une recherche Google en vol ;
- lecture seule par capacité ;
- envoi des seuls champs modifiés avec la version ;
- neutralisation de la double soumission ;
- conflit de version sans perte de la saisie et rechargement explicite ;
- mise à jour du résumé d’organisation dans la session ;
- absence de stockage navigateur.

## 6. Preuves automatisées

Matrice exécutée le 3 août 2026 :

| Contrôle | Résultat |
| --- | --- |
| ESLint | vert, zéro avertissement |
| Vitest | 14 fichiers, 63 tests réussis |
| Build Vite | vert, 55 modules transformés |
| Ruff | vert |
| Ruff format | 142 fichiers conformes |
| mypy | 110 fichiers, aucune anomalie |
| pytest | 133 réussis, 17 ignorés faute d’activation de la matrice d’infrastructure |
| Alembic current | `20260802_0005 (head)` |
| Alembic check | aucune opération de migration détectée |

Une première exécution concurrente de lint, build et Vitest a saturé les workers Windows. La relance isolée de Vitest
a exécuté les tests sans erreur. Azure Pipelines exécute déjà ces étapes séquentiellement ; aucune faiblesse du
produit ni modification de la configuration CI n’a donc été masquée.

## 7. Revue experte 1 — Sécurité et concurrence

### Constats

- Le client n’accepte jamais un `organization_id` choisi par l’utilisateur.
- Le contexte précédent reste actif tant que la réponse serveur n’est pas complète.
- Un verrou de promesse empêche deux rotations facturables ou contradictoires.
- Le compteur de génération empêche une réponse tardive de ressusciter une session déconnectée.
- Le CSRF est remplacé avec la session et n’est pas conservé dans un stockage Web.

### Risque résiduel accepté

L’interface ne prouve pas l’isolation à elle seule. La sécurité continue de reposer sur la rotation du cookie, les
capacités serveur et RLS déjà testés dans les incréments précédents. Le lot B ne relâche aucune de ces barrières.

## 8. Revue experte 2 — UX, accessibilité et maintenabilité

### Constats

- Le sélecteur natif reste utilisable au clavier et annonce la progression et les erreurs.
- Une rotation réussie conserve la route si elle reste autorisée, sinon choisit une destination sûre.
- Les erreurs ne déplacent pas silencieusement l’utilisateur vers une autre organisation.
- La page Organisation sépare lecture, mutation et état de session ; ses appels résident dans un adaptateur API dédié.
- Les conflits demandent une décision humaine et ne détruisent pas le brouillon.

### Risques résiduels acceptés

- Le rendu authentifié multi-organisation doit encore être confirmé sur l’environnement local du responsable produit.
- Les contrôles axe globaux et la validation à 320 px/200 % appartiennent au verrou final 2.3.5-E.
- Les pages Membres et Plateforme restent volontairement absentes jusqu’aux lots C et D.

## 9. Procédure de validation locale

1. Confirmer `http://127.0.0.1:8000/api/health/ready` à `ready`, puis démarrer le frontend.
2. Se connecter avec un compte possédant deux appartenances actives.
3. Vérifier que le sélecteur apparaît dans le bandeau et affiche l’organisation active.
4. Lancer une recherche, changer d’organisation, puis confirmer que résultats et carte sont vidés.
5. Vérifier que le nom, le rôle, le menu et les capacités correspondent immédiatement à la nouvelle organisation.
6. Revenir à la première organisation et confirmer qu’aucun ancien résultat n’est restauré.
7. Ouvrir `/app/admin/organization` comme Admin, modifier un champ et vérifier la fiche ainsi que le nom du bandeau.
8. Ouvrir la même page comme Manager ou Sales et confirmer l’absence complète du formulaire.
9. Pour le conflit, ouvrir la page dans deux sessions Admin : modifier et enregistrer dans la seconde, puis soumettre
   un brouillon basé sur l’ancienne version dans la première. Confirmer que le brouillon reste visible et que le
   rechargement est explicitement proposé.
10. Couper temporairement le backend pendant une rotation et confirmer que l’ancienne organisation reste affichée.
11. Dans les outils du navigateur, confirmer que les stockages local et session ne contiennent aucune donnée CRM.

## 10. Critères d’acceptation du lot B

Le responsable produit peut accepter 2.3.5-B si le parcours multi-organisation, la purge des données, les permissions
de la page Organisation, l’échec contrôlé et le conflit de version correspondent aux comportements ci-dessus.

Le responsable produit a validé ce parcours le 3 août 2026. Le lot suivant est **2.3.5-C — Membres et invitations**.
