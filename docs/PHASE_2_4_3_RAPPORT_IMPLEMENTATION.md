# Phase 2.4.3 — Rapport d’implémentation de la consultation de l’audit

| Élément | Valeur |
| --- | --- |
| Date | 9 août 2026 |
| Statut technique | Implémenté — verrou local complet vert, 180 tests sans skip |
| Statut produit | Recette utilisateur cumulée 2.4.1–2.4.3 conforme |
| Migration | Aucune nouvelle migration ; schéma `20260809_0007` conservé |

## Résultat livré

L’audit transactionnel produit par 2.4.1 et 2.4.2 est maintenant consultable dans deux périmètres structurellement
séparés : l’organisation active et la plateforme. Les routes, capacités, unités de lecture, contextes RLS, clients
React et chemins d’interface sont distincts. Aucun paramètre fourni par le navigateur ne choisit l’organisation ou la
portée.

- `GET /api/audit-events` exige une organisation active et `audit:read` ;
- `GET /api/platform/audit-events` exige `platform:audit:read` ;
- `/app/audit` est visible pour Admin et Manager, jamais pour Sales ;
- `/app/platform/audit` est réservé à l’Administrateur de plateforme ;
- les réponses portent `Cache-Control: no-store` et n’exposent ni courriel, ni secret, ni contenu Google ;
- la période vaut trente jours par défaut et reste limitée à quatre-vingt-dix jours ;
- la pagination par `(occurred_at, id)` utilise un curseur HMAC opaque lié à la portée, l’organisation et tous les
  filtres ;
- les détails affichés proviennent d’une liste blanche et aucun JSON brut n’est rendu ;
- les filtres, événements et curseurs restent uniquement dans la mémoire React.

La cible `organization_id` des nouveaux événements plateforme liés au provisioning et aux invitations initiales est
désormais renseignée prospectivement. Aucun historique existant n’est modifié.

## Architecture et sécurité

Le domaine définit les filtres et projections sans dépendance SQLAlchemy. Deux ports de lecture et deux fabriques
d’unité de travail séparent locataire et plateforme. L’adaptateur PostgreSQL applique filtres, ordre et pagination
sous RLS. La lecture plateforme vide explicitement `app.organization_id` avant de poser
`app.audit_scope = platform`, ce qui renforce l’isolation même en présence d’une connexion réutilisée.

Le lecteur effectue une jointure contrôlée sur le nom affiché actuel de l’acteur. L’UUID reste la référence
historique et le courriel n’entre jamais dans la projection. Un acteur système n’expose aucun identifiant utilisateur.
Les erreurs de curseur ou de filtres produisent `422`, l’absence de capacité `403` et l’indisponibilité PostgreSQL
`503`, toujours sous le format d’erreur protégé existant.

## Interface utilisateur

Un socle partagé fournit filtres, chronologie et détail repliable, tandis que les hooks et clients HTTP restent
séparés par portée. Les périodes rapides 7, 30 et 90 jours ainsi qu’une période personnalisée sont disponibles. Le
chargement progressif ne calcule aucun total et **Actualiser** démarre une nouvelle lecture cohérente.

Les actions et types d’entité utilisent des catalogues centralisés préparés pour `fr-CA` et `en-CA`. Une action ou
une version inconnue reçoit un libellé sûr et masque ses métadonnées. Le locataire affiche les dates dans le fuseau de
l’organisation ; la plateforme utilise UTC.

## Preuves automatisées

Contrôles exécutés avec succès :

- Ruff sur le backend ;
- mypy sur 125 fichiers source ;
- pytest hors infrastructure : **140 tests réussis** ;
- pytest complet avec PostgreSQL, Redis et Mailpit réels : **180 tests réussis en 27,84 s, zéro test ignoré** ;
- contrôle JUnit `junit-no-skips` : conforme ;
- ESLint sans avertissement ;
- tests frontend : **132 tests réussis dans 31 fichiers**, dont les vingt états axe ;
- `npm audit --audit-level=high` : aucune vulnérabilité élevée ;
- build Vite : 77 modules compilés, artefacts JS et CSS produits.

Le lancement Vitest monolithique a épuisé les ressources de la machine locale et provoqué deux délais d’attente non
reproductibles. La suite complète a donc été rejouée en quatre groupes déterministes couvrant les 31 fichiers et les
132 tests, tous verts. Azure conserve la commande canonique monolithique et reste la preuve d’intégration attendue.

Le verrou local complet a ensuite été exécuté par le responsable produit avec l’infrastructure Docker pilotée depuis
WSL et les tests lancés sous PowerShell. PostgreSQL, RLS, Redis, Mailpit et les workflows transactionnels sont verts.
Le rapport JUnit contient 180 succès et le contrôle automatique confirme l’absence de test ignoré. La recette produit
est également conforme. Par décision produit, le passage Azure est reporté à la clôture globale de la phase 2.4 ;
il ne bloque pas le démarrage de 2.4.4 mais reste obligatoire avant tout déploiement.

## Preuve de recette fonctionnelle

Le responsable produit a exécuté et validé la recette cumulée le 9 août 2026. La preuve HTTP fournie contient une
chronologie locataire ordonnée de manière antéchronologique et couvre notamment : activation et modification
d’organisation, création, livraison, acceptation et révocation d’invitations, changement de rôle et changement
d’organisation active.

La réponse observée respecte le contrat : fenêtre UTC explicite de trente jours, `next_cursor` nul en fin de lecture,
acteurs identifiés uniquement par UUID interne et nom affiché, métadonnées limitées aux clés autorisées, aucun
courriel, secret, contact ou contenu Google. Le responsable produit confirme également la conformité des parcours
fonctionnels prévus par la recette.

## Trois critiques expertes

### 1. Isolation et moindre privilège

Point fort : l’autorisation applicative, les routes distinctes et RLS se répètent sans faire confiance au client. Le
lecteur SQL charge explicitement les seules colonnes du contrat de réponse, en plus du nom affiché joint. Risque
résiduel : une évolution du contrat pourrait élargir cette projection. Décision : conserver les tests contractuels
d’absence de courriel et de contenu Google et revoir explicitement la liste à chaque ajout au modèle d’audit.

### 2. Intégrité historique et confidentialité

Point fort : aucune donnée rétroactive n’est inventée et les métadonnées sont limitées par politique. Compromis : le
nom affiché de l’acteur est son nom actuel, pas nécessairement celui de la date de l’événement. L’interface et les
spécifications le documentent ; figer un nom aurait dupliqué une donnée personnelle et accru les obligations de
conservation.

### 3. Performance et expérience produit

Point fort : fenêtre bornée, index existants, pagination par clé et absence de `count(*)` rendent la charge
prévisible. Limite : il n’existe ni recherche libre, ni export, ni temps réel. C’est volontaire pour réduire la
surface de fuite et conserver un journal opérationnel. Toute extension devra partir de mesures réelles et d’une
revue de conformité.

## Deux revues de code

### Revue architecture Clean/SOLID

Les dépendances vont de la présentation vers les cas d’utilisation, puis vers des ports ; le domaine reste isolé de
FastAPI, React et SQLAlchemy. Les responsabilités écriture, lecture, pagination et présentation sont distinctes. Les
deux portées ne reposent pas sur une option booléenne transversale contrôlable par le client. Aucun défaut bloquant
n’a été identifié.

### Revue sécurité, concurrence et exploitation

Le curseur est signé, canonique et non interchangeable ; l’ordre est total ; `limit + 1` évite le total exact ; les
dates sont normalisées en UTC ; les appels obsolètes React sont annulés ou ignorés ; aucune donnée n’est conservée
dans le navigateur. La correction de cible plateforme reste dans la transaction auditée. La preuve PostgreSQL locale
est clôturée et la recette fonctionnelle est signée. Le passage Azure est volontairement suivi comme verrou final
transversal de la phase 2.4.

## Recette locale

1. Démarrer PostgreSQL, Redis, le backend et le frontend, puis vérifier `/api/health/ready`.
2. Produire plusieurs mutations réussies et au moins un refus ou conflit.
3. Ouvrir `/app/audit` comme Admin, Manager puis Sales et vérifier la matrice d’accès.
4. Tester période, action, entité, acteur, détails, **Charger la suite** et **Actualiser**.
5. Ouvrir `/app/platform/audit` comme Administrateur de plateforme et confirmer l’absence de lignes locataires.
6. Exécuter `scripts/Test-AuditLocal.ps1` pour chaque portée autorisée.
7. Vérifier le réseau (`no-store`, aucun courriel) et les stockages navigateur (aucun audit, filtre ou curseur).
8. Suivre la recette cumulée de la section 22 des spécifications 2.4.3 et consigner les preuves.

## Conclusion

Le code de 2.4.3 est cohérent avec les seize décisions validées et ne nécessite aucune migration supplémentaire. Il
a franchi la recette utilisateur cumulée 2.4.1–2.4.3 et est validé localement. Le GO de 2.4.4 est autorisé ; le
passage Azure reste obligatoire au verrou final de la phase 2.4.
