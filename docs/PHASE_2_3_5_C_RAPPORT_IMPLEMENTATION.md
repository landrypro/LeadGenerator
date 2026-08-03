# Phase 2.3.5-C — Rapport d’implémentation des membres et invitations

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Lot | 2.3.5-C — Membres et invitations |
| Date | 3 août 2026 |
| Statut | Implémenté ; validation produit locale attendue |
| Migration SQL | Aucune |
| Révision Alembic | `20260802_0005 (head)` |

## 1. Résultat livré

Le lot C active `/app/admin/users` et rend consommables les contrats backend de 2.3.3 :

- liste des membres paginée par curseur, dédupliquée et limitée à l’organisation de la session ;
- lecture seule avec `members:read` et édition uniquement avec `members:manage` ;
- modification ciblée du rôle et de l’état avec la version exacte ;
- confirmation accessible avant désactivation ou retrait du rôle Administrateur ;
- traitement explicite des conflits de version et de la protection du dernier Administrateur actif ;
- invalidation immédiate de l’interface lorsque l’utilisateur modifie sa propre appartenance ;
- onglet Invitations uniquement avec `invitations:read` ;
- création, renvoi et révocation uniquement avec `invitations:manage` ;
- identifiants idempotents par intention, conservés après résultat ambigu et renouvelés après modification métier ;
- aucune donnée locataire, clé idempotente ou jeton d’invitation dans les stockages Web.

Le backend, RLS et les fonctions SQL ne changent pas. L’organisation reste déduite du cookie de session ; aucun
`organization_id` n’est accepté par les adaptateurs frontend.

## 2. Membres

La page présente nom affiché, courriel, rôle, état, date d’arrivée et date de modification. Le bouton « Charger la
suite » n’apparaît qu’en présence d’un `next_cursor`. Un rechargement remplace la page ; une pagination ajoute les
éléments en les dédupliquant par `membership_id`.

L’éditeur n’envoie que les champs réellement modifiés avec la version lue. Une commande identique reste désactivée.
Sur `membership_version_conflict`, le brouillon est conservé et l’utilisateur choisit de recharger la liste ; la
mutation n’est jamais rejouée. Sur `last_active_administrator`, la ligne reste intacte et le message indique qu’un
autre Administrateur actif est requis.

Après une auto-modification réussie, le client purge immédiatement session et CSRF puis remplace l’URL par `/login`.
Il ne dépend pas d’une prochaine requête `401` pour constater l’expiration du cookie décidée par le serveur.

## 3. Invitations et idempotence

La liste représente uniquement les invitations actionnables retournées par l’API. Elle affiche destinataire, rôle,
état, livraison et expiration sans prétendre fournir un historique complet.

La création mémorise un `invitation_request_id` et le corps normalisé de l’intention. Un échec réseau ou
`invitation_outcome_unknown` permet un retry explicite avec exactement le même identifiant et le même corps. Une
modification du courriel ou du rôle abandonne cette intention et crée un nouvel UUID.

Chaque renvoi suit la même règle avec son `resend_request_id`. Deux invitations distinctes peuvent être traitées en
parallèle, mais une double commande sur la même invitation est neutralisée. Le `Retry-After` d’un `429` est conservé
dans l’erreur applicative et affiché en secondes. Une révocation exige un dialogue accessible et envoie un corps JSON
vide conformément au contrat strict du backend.

Les intentions ambiguës survivent à un changement d’onglet au sein de la page, mais sont volontairement abandonnées
lorsque la route ou l’organisation est quittée : elles ne doivent jamais traverser un contexte locataire.

## 4. Résilience des états

Les lectures partagent un hook paginé qui :

- expose chargement initial, actualisation, chargement de suite, vide et erreur ;
- annule la requête au démontage ;
- ignore une réponse de séquence ancienne ;
- ne relance automatiquement aucune lecture ou mutation ;
- réconcilie les réponses serveur au lieu de reconstruire les ressources.

Les mutations possèdent des verrous synchrones, en complément des états visuels React. Elles neutralisent donc les
doubles clics avant même le prochain rendu. Les contrôleurs actifs sont annulés lors d’un changement de route ou
d’organisation et une réponse tardive ne réinjecte pas d’état.

## 5. Tests ajoutés

Les scénarios couvrent notamment :

- route et navigation par `members:read` ;
- lecture seule du Gestionnaire et absence de l’onglet Invitations ;
- pagination, curseur, déduplication et annulation au démontage ;
- version exacte, seuls champs modifiés et confirmation sensible ;
- dernier Administrateur sans modification locale ;
- conflit sans écrasement ni rejeu ;
- auto-modification et retour immédiat à la connexion ;
- création avec UUID stable après résultat inconnu ;
- nouvel UUID après modification du formulaire ;
- conservation de l’intention pendant un changement d’onglet ;
- neutralisation de la double soumission ;
- renvoi idempotent et opérations indépendantes par invitation ;
- confirmation avant révocation ;
- mode invitations en lecture seule ;
- commandes HTTP, CSRF, corps JSON vide et absence d’`organization_id` ;
- propagation de `Retry-After` dans l’erreur contrôlée.

## 6. Preuves automatisées

Matrice exécutée le 3 août 2026 :

| Contrôle | Résultat |
| --- | --- |
| ESLint | vert, zéro avertissement |
| Vitest | 18 fichiers, 83 tests réussis |
| Build Vite | vert, 63 modules transformés |
| Ruff | vert |
| Ruff format | 142 fichiers conformes |
| mypy | 110 fichiers, aucune anomalie |
| pytest | 133 réussis, 17 ignorés faute d’activation de la matrice d’infrastructure |
| Alembic current | `20260802_0005 (head)` |
| Alembic check | aucune opération de migration détectée |

Les 17 tests d’infrastructure restent une barrière explicite du lot final 2.3.5-E et du déploiement ; ils ne sont pas
masqués comme une validation réelle du présent lot frontend.

## 7. Revue experte 1 — Sécurité et cohérence transactionnelle

- Toutes les ressources sont inférées depuis la session et les routes n’envoient jamais d’organisation choisie.
- Les UUID sont opaques, injectables en test, uniquement en mémoire et jamais journalisés.
- Les résultats ambigus conservent le couple identifiant/corps ; les modifications métier créent une nouvelle intention.
- Les réponses serveur restent l’autorité pour versions, dernier Administrateur, sessions et état de livraison.
- L’auto-modification purge l’interface dès la réponse réussie et ne laisse aucune capacité obsolète visible.

Risque résiduel accepté : la sécurité finale continue de dépendre du backend, de la rotation des sessions et de RLS,
déjà couverts par 2.3.3. Le frontend ne cherche pas à reproduire ces décisions.

## 8. Revue experte 2 — UX, accessibilité et exploitation

- Les droits insuffisants suppriment les actions au lieu de présenter de faux boutons désactivés.
- Les confirmations sensibles utilisent un dialogue annoncé, piègent le focus utile, acceptent Échap et restaurent le focus.
- Une intention ne bloque que sa propre ressource ; le reste de la page demeure utilisable.
- Les erreurs métier utilisent les codes stables et conservent les saisies utiles.
- Le responsive transforme les lignes en cartes sans supprimer d’information.

Risques résiduels acceptés : les contrôles axe globaux, le zoom 200 % et la fermeture des 17 `skip` appartiennent au
verrou final E. Le rendu multi-rôle réel doit encore être accepté localement par le responsable produit.

## 9. Procédure de validation locale

1. Confirmer `/api/health/ready` à `ready`, Mailpit à `http://127.0.0.1:8025`, puis démarrer le frontend.
2. Se connecter comme Gestionnaire et ouvrir `/app/admin/users` : vérifier la liste sans bouton Modifier ni onglet Invitations.
3. Se connecter comme Commercial et confirmer que la route Membres est absente et qu’un lien profond produit un `403`.
4. Se connecter comme Administrateur : ouvrir Membres, modifier un Commercial vers Gestionnaire et vérifier le succès.
5. Désactiver un membre ou retirer un rôle Admin : vérifier la confirmation avant l’appel.
6. Tenter de désactiver/rétrograder le dernier Administrateur actif : vérifier le refus sans changement visuel de la ligne.
7. Modifier sa propre appartenance : vérifier le retour immédiat à `/login`, puis se reconnecter avec les nouveaux droits.
8. Ouvrir Invitations, inviter un nouveau courriel et vérifier le message dans Mailpit.
9. Renvoyer une invitation après le délai autorisé et vérifier que l’ancien lien est remplacé par le nouveau.
10. Révoquer une invitation, confirmer le dialogue et vérifier la disparition de la liste actionnable.
11. Pour le conflit de membre, garder l’éditeur ouvert dans une session, modifier la même ligne dans une autre, puis
    soumettre la première : vérifier le conflit, l’absence de rejeu et le rechargement explicite.
12. Vérifier les stockages navigateur : aucune session, invitation, clé idempotente ou ressource CRM ne doit apparaître.

## 10. Critères d’acceptation du lot C

Le lot C peut être accepté si les matrices Admin/Manager/Sales, les mutations sensibles, la protection du dernier
Administrateur, l’auto-invalidation, Mailpit, le renvoi et la révocation correspondent aux comportements ci-dessus.

Après validation, le prochain lot est **2.3.5-D — Plateforme**.
