# Phase 2.3.5-A — Rapport d’implémentation du routage et du shell

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Lot | 2.3.5-A — Routage et shell |
| Date | 2 août 2026 |
| Statut | Implémenté et validé localement par le responsable produit |
| Validation produit | 3 août 2026 |
| Migration SQL | Aucune |
| Révision Alembic | `20260802_0005 (head)` |

## 1. Résultat livré

Le lot A introduit le socle de navigation authentifié sans modifier les contrats HTTP ni les données :

- routes canoniques `/login`, `/accept-invitation`, `/app/search` et `/app/account` ;
- chemins Organisation, Membres et Plateforme réservés mais non activés avant leurs lots B, C et D ;
- redirections par `replaceState`, navigation utilisateur par `pushState` et prise en charge de `popstate` ;
- véritable page `404`, sans retour silencieux vers Recherche ;
- page `403` lorsqu’une capacité manque ou qu’aucune organisation active n’autorise la route ;
- shell monté seulement après restauration complète de la session ;
- navigation filtrée par les capacités reçues du serveur ;
- page Compte strictement en lecture seule ;
- menu mobile avec fermeture par `Échap`, restitution du focus et lien d’évitement ;
- titres d’onglet dynamiques ;
- intégration de Recherche dans le shell sans modifier ses appels Google, sa carte ou ses résultats.

## 2. Règles de routage du lot A

| Contexte | Destination de `/` |
| --- | --- |
| Session absente | `/login` |
| Organisation active avec `google:search` | `/app/search` |
| Session valide sans recherche autorisée | `/app/account` |
| Aucun rôle plateforme et aucune organisation | état restreint « Aucune organisation accessible » |

Pendant le lot A, un Administrateur de plateforme sans organisation est dirigé vers Compte. La destination
`/app/platform/organizations` sera activée avec 2.3.5-D, lorsque la page Plateforme sera complète. Cette activation
progressive évite d’exposer un écran vide ou partiellement fonctionnel.

## 3. Sécurité et confidentialité

- le shell ne déduit aucun droit depuis un libellé de rôle ; il consomme uniquement `capabilities` ;
- le serveur demeure l’autorité et continue de contrôler chaque route API ;
- aucune action privilégiée n’est rendue pendant l’état `loading` ;
- CSRF, cookie, UUID utilisateur, UUID d’appartenance et UUID d’organisation ne sont pas affichés ;
- aucune donnée de session n’est écrite dans `localStorage` ou `sessionStorage` ;
- les routes non livrées sont absentes du registre actif et de la navigation ;
- une route inconnue conserve son URL et affiche `404` ;
- un refus d’accès ne déclenche pas le composant fonctionnel protégé.

## 4. Durcissement découvert par le verrou qualité

La passe pytest a révélé qu’une variante Base64 URL non canonique d’une signature de curseur pouvait produire les
mêmes octets décodés. La signature HMAC restait mathématiquement valide malgré la modification textuelle du dernier
caractère.

Le décodeur de `HmacCursorCodec` :

- utilise maintenant une validation Base64 stricte ;
- réencode les octets et exige une représentation canonique identique ;
- refuse explicitement les alias fondés sur les bits de remplissage ;
- possède un test de non-régression dédié.

Cette correction ne change ni le format émis ni les curseurs valides existants.

## 5. Preuves automatisées

### Frontend

| Contrôle | Résultat |
| --- | --- |
| ESLint | vert, zéro avertissement |
| Vitest | 43 réussites dans 11 fichiers |
| Build Vite | vert, 51 modules transformés |
| Tests de routage/shell/Compte | 19 scénarios dédiés |

Les tests couvrent redirections, liens profonds, retour/avance, 403, 404, navigation filtrée, absence de privilèges
pendant le chargement, page Compte sans secret, déconnexion, lien d’évitement et fermeture clavier du menu mobile.

### Backend et migration

| Contrôle | Résultat |
| --- | --- |
| Alembic `current` | `20260802_0005 (head)` |
| Alembic `check` | aucune opération nouvelle |
| Ruff check | vert |
| Ruff format | 142 fichiers conformes |
| mypy | 110 fichiers, aucune erreur |
| pytest | 133 réussites, 17 ignorés |

Les 17 scénarios ignorés exigent les services réels PostgreSQL, Redis et Mailpit. Leur exécution sans `skip` reste le
verrou obligatoire de 2.3.5-E avant 2.4 ; elle ne bloque pas l’acceptation fonctionnelle locale du lot A.

### Navigateur local

- `/` redirigé vers `/login` sans boucle ;
- titre final `Connexion — Prospect CRM` ;
- formulaire de connexion présent dans une région accessible ;
- aucune erreur console.

## 6. Revue critique 1 — Architecture et sécurité

Points jugés satisfaisants :

- le registre central sépare chemins réservés et pages réellement activées ;
- la règle d’accès est pure, testable et indépendante de l’affichage ;
- les redirections initiales synchronisent explicitement l’historique et l’état React ;
- Recherche demeure responsable uniquement de son état métier ; le shell porte identité et navigation ;
- le durcissement du curseur ferme une ambiguïté de représentation au niveau de la frontière de confiance.

Limite assumée : la route Plateforme finale n’est pas activée en A. L’activer sans les clients API et les états
d’erreur de D serait moins sûr que la destination Compte actuelle.

## 7. Revue critique 2 — UX et accessibilité

Points jugés satisfaisants :

- liens natifs conservant ouverture dans un nouvel onglet et navigation sans rechargement au clic normal ;
- `aria-current`, navigation nommée, fil d’Ariane et lien d’évitement ;
- menu mobile contrôlable au clavier et respect de `prefers-reduced-motion` ;
- fond mobile retiré de l’arbre accessible pour éviter deux commandes homonymes ;
- page Compte sans faux formulaire ni fonction annoncée avant sa livraison.

Limites restantes : axe automatisé, contrôle complet à 320 px et zoom 200 % appartiennent au verrou final E. Une
validation visuelle authentifiée par le responsable produit est demandée ci-dessous.

## 8. Procédure de validation locale

1. Démarrer PostgreSQL, Redis et le backend puis confirmer `/api/health/ready` à `ready`.
2. Démarrer le frontend avec `cd client` puis `npm.cmd run dev`.
3. Ouvrir `http://localhost:5173/` et se connecter.
4. Confirmer l’URL `/app/search`, le bandeau Prospect CRM, Recherche Google, Compte, organisation active et identité.
5. Effectuer une recherche contrôlée et vérifier que carte, résultats, attribution et export désactivé sont inchangés.
6. Ouvrir Compte et vérifier nom, courriel, organisation, rôle et absence de formulaire de modification.
7. Ouvrir une URL inexistante, par exemple `/route-inconnue`, et confirmer la page `404`.
8. Avec un rôle dépourvu d’une capacité, ouvrir directement la route correspondante et confirmer le `403`.
9. Réduire la fenêtre sous 850 px, ouvrir Menu, puis utiliser `Échap` et vérifier le retour du focus au bouton Menu.
10. Tester retour/avance entre Recherche et Compte.
11. Se déconnecter et confirmer le retour à `/login`.

## 9. Critères d’acceptation du lot A

Le responsable produit peut accepter 2.3.5-A si :

- le shell et la page Compte correspondent au parcours attendu ;
- aucune régression Google n’est observée ;
- les redirections, 403 et 404 sont compréhensibles ;
- le parcours clavier mobile est utilisable ;
- l’état transitoire Plateforme vers Compte jusqu’au lot D est accepté.

Le responsable produit a validé ce parcours le 3 août 2026. Le lot suivant est **2.3.5-B — Organisation active**.
