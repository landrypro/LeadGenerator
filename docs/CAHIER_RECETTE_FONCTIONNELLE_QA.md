# Prospect CRM — Cahier de recette fonctionnelle utilisateur

| Métadonnée | Valeur à renseigner |
| --- | --- |
| Version du document | 1.0 |
| Périmètre | CRM V1 livré jusqu’à 2.3.5-E |
| Environnement | Local / QA / préproduction : __________ |
| URL testée | __________ |
| Révision Git | __________ |
| Build Azure | __________ |
| Date de recette | __________ |
| Responsable QA | __________ |
| Navigateur et version | __________ |
| Système et résolution | __________ |
| Décision finale | GO / NO-GO / GO avec réserves |

## 1. Objet

Ce document permet à un testeur QA de vérifier, étape par étape, l’ensemble des fonctions actuellement livrées dans
Prospect CRM : authentification, invitations, organisations, rôles, membres, changement d’organisation,
administration plateforme, recherche Google limitée, carte, sécurité visible, accessibilité, responsive et qualité
d’exploitation.

La recette ne couvre pas les futurs modules Prospect, pipeline commercial, activités, opportunités, import CRM,
export CRM ou audit métier. Le bouton **Exporter Excel** est volontairement visible mais inaccessible.

## 2. Règles d’exécution

### 2.1 Statuts

- **PASS** : résultat obtenu exactement conforme à l’attendu ;
- **FAIL** : résultat différent, même si le parcours peut continuer ;
- **BLOCKED** : prérequis ou service indisponible empêchant le test ;
- **NOT RUN** : test non exécuté ;
- **N/A** : test explicitement hors de l’environnement, avec justification.

Un test ne peut être PASS sans preuve lorsque la colonne « preuve minimale » en demande une.

### 2.2 Sévérité des anomalies

| Sévérité | Définition | Décision |
| --- | --- | --- |
| Bloquante | fuite de secret, franchissement d’organisation, perte de données, contournement de rôle, facturation Google incontrôlée, impossibilité de se connecter | NO-GO |
| Majeure | fonction essentielle indisponible, mutation incohérente, erreur sans récupération, action inaccessible au clavier | NO-GO |
| Mineure | défaut visuel ou rédactionnel sans perte d’information ni d’action | Acceptation produit requise |

### 2.3 Précautions

- utiliser exclusivement des comptes et courriels de test ;
- ne jamais placer de mot de passe, cookie, CSRF, jeton d’invitation ou clé Google dans une capture ou un ticket ;
- ne jamais copier le lien Mailpit ailleurs que dans le navigateur de test ;
- ne pas modifier directement PostgreSQL pour faire réussir un scénario fonctionnel ;
- utiliser un suffixe unique `<RUN>`, par exemple `20260803-qa01`, pour éviter les collisions ;
- coordonner le scénario Google : il autorise au maximum **un Text Search et une Maps Static réels par campagne** ;
- ouvrir les outils développeur seulement pour les contrôles explicitement indiqués ; ne jamais recopier la valeur des
  cookies ou des en-têtes secrets.

## 3. Prérequis d’environnement

Le responsable de l’environnement, distinct du testeur si nécessaire, confirme avant la recette :

| Contrôle | Attendu | Statut |
| --- | --- | --- |
| PostgreSQL | disponible, migrations à `20260802_0005 (head)` | ___ |
| Redis | disponible | ___ |
| Mailpit | SMTP actif et interface accessible | ___ |
| Backend | `http://127.0.0.1:8000` | ___ |
| Frontend | `http://localhost:5173` | ___ |
| Readiness | `/api/health/ready` retourne `status: ready`, PostgreSQL `ok`, Redis `ok` | ___ |
| Clés Google | statut « API configurée » uniquement pour le scénario Google réel | ___ |
| Administrateur plateforme | compte de recette créé, mot de passe dans le coffre QA | ___ |
| Navigateurs | Chrome ou Edge récent ; Firefox recommandé en contrôle secondaire | ___ |

Commandes locales de référence :

```powershell
docker compose up -d --wait
docker compose run --rm database-role-provisioner
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:VOTRE_MOT_DE_PASSE@127.0.0.1:5432/prospect"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

Le backend et le frontend doivent ensuite être lancés selon le `README.md`. Mailpit est accessible par défaut sur
`http://127.0.0.1:8025`.

## 4. Jeu de données à construire pendant la recette

Ne créez pas ces données à l’avance, sauf les lignes marquées « préparée ». Leur création fait partie des tests.

| Référence | Valeur suggérée | Usage |
| --- | --- | --- |
| `PLATFORM` | `qa.platform.<RUN>@example.ca` | Administrateur plateforme sans appartenance locataire, préparé |
| `ORG-A` | `QA Alpha <RUN>` | organisation principale |
| `ORG-B` | `QA Bêta <RUN>` | deuxième organisation du compte Admin |
| `ORG-R` | `QA Renvoi <RUN>` | test du renvoi initial |
| `ORG-V` | `QA Révocation <RUN>` | test de révocation initiale |
| `ADMIN` | `qa.admin.<RUN>@example.ca` | Admin de ORG-A et ORG-B |
| `MANAGER` | `qa.manager.<RUN>@example.ca` | Gestionnaire de ORG-A |
| `SALES` | `qa.sales.<RUN>@example.ca` | Commercial de ORG-A |
| `SECOND-ADMIN` | `qa.admin2.<RUN>@example.ca` | deuxième Admin pour les scénarios sensibles |
| `NO-ORG` | `qa.noorg.<RUN>@example.ca` | compte accepté puis appartenance désactivée |
| `PENDING` | `qa.pending.<RUN>@example.ca` | invitation destinée au renvoi/révocation |

Les mots de passe doivent comporter entre 12 et 128 caractères et être différents des mots de passe réels. Ils sont
conservés uniquement dans le coffre ou la feuille de recette protégée.

## 5. Matrice des droits attendus

| Fonction | Plateforme seule | Admin | Gestionnaire | Commercial | Sans organisation |
| --- | --- | --- | --- | --- | --- |
| Plateforme | lecture/création/actions | non, sauf rôle plateforme distinct | non | non | non |
| Recherche Google | non | oui | oui | oui | non |
| Carte Google | non | oui | oui | oui | non |
| Organisation | non | lecture/édition | lecture | lecture | non |
| Membres | non | lecture/édition | lecture seule | non | non |
| Invitations membres | non | lecture/création/renvoi/révocation | non | non | non |
| Compte | oui | oui | oui | oui | état restreint/déconnexion |

## 6. Ordre conseillé de la campagne

Exécuter les sections dans cet ordre afin de réutiliser les données produites : environnement et pages publiques,
plateforme, invitation initiale, connexion et shell, organisation, membres, invitations de membres,
multi-organisation, Google, confidentialité, accessibilité, résilience, verrou automatisé.

## 7. Environnement et pages publiques

| ID | Pri. | Étapes | Résultat attendu |
| --- | --- | --- | --- |
| ENV-01 | P0 | 1. Ouvrir `/api/health/live`.<br>2. Ouvrir `/api/health/ready`. | `live` répond ; `ready` répond HTTP 200 avec PostgreSQL et Redis à `ok`. |
| ENV-02 | P0 | 1. Ouvrir l’application.<br>2. Ouvrir Mailpit.<br>3. Vérifier qu’aucune erreur serveur répétitive n’apparaît dans les terminaux. | Connexion affichée ; Mailpit accessible ; services stables. |
| LEG-01 | P1 | 1. Ouvrir `/conditions.html`.<br>2. Vérifier le titre, la date et les sections Google, export, compte et facturation.<br>3. Suivre le lien Confidentialité puis Retour à l’application. | Page lisible, liens fonctionnels, retour vers l’application. L’avertissement de validation juridique reste attendu avant commercialisation. |
| LEG-02 | P1 | 1. Ouvrir `/confidentialite.html`.<br>2. Vérifier les sections informations, conservation, Google, sécurité et droits.<br>3. Suivre les liens croisés. | Contenu cohérent avec 20 résultats, absence de contacts/export et conservation mémoire ; aucun lien cassé. |

## 8. Authentification, routage et compte

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| AUTH-01 | P0 | session fermée | 1. Ouvrir `/` puis `/app/search`.<br>2. Observer l’adresse. | Redirection vers `/login` ; aucun contenu CRM protégé n’est brièvement visible. |
| AUTH-02 | P0 | compte existant | 1. Saisir un courriel inexistant et un mauvais mot de passe.<br>2. Refaire avec le bon courriel et un mauvais mot de passe. | Même message générique « Courriel ou mot de passe incorrect » ; aucun indice sur l’existence du compte. |
| AUTH-03 | P0 | `PLATFORM` | 1. Se connecter.<br>2. Actualiser la page.<br>3. Ouvrir Mon compte. | Session restaurée après actualisation ; identité correcte ; aucun mot de passe affiché. |
| AUTH-04 | P0 | session ouverte | 1. Cliquer Se déconnecter.<br>2. Utiliser Retour navigateur.<br>3. Ouvrir directement une route protégée. | Retour à Connexion ; aucune page protégée accessible avec l’ancienne session. |
| AUTH-05 | P1 | `NO-ORG` préparé après MEM-04 | 1. Se connecter avec `NO-ORG`.<br>2. Observer les actions disponibles. | Écran « Aucune organisation accessible » ; seule la déconnexion est proposée. |
| ROUTE-01 | P1 | session locataire | 1. Vérifier le logo, le fil d’Ariane, les routes permises, le nom du compte et la déconnexion.<br>2. Ouvrir chaque lien. | Navigation cohérente ; route courante indiquée ; aucune route non autorisée dans le menu. |
| ROUTE-02 | P0 | `SALES` | 1. Ouvrir directement `/app/admin/users`.<br>2. Ouvrir `/app/platform/organizations`. | Page 403 contrôlée ; aucune liste membres/plateforme chargée ou visible. |
| ROUTE-03 | P1 | session ouverte | 1. Ouvrir `/app/inconnue`.<br>2. Cliquer Revenir à l’accueil. | Page 404 contrôlée puis destination autorisée. |
| ACCOUNT-01 | P1 | compte multi-organisation après MULTI-01 | 1. Ouvrir Mon compte.<br>2. Vérifier identité, rôle plateforme éventuel, organisations, rôles et badge Active. | Informations de session exactes, sans cookie, CSRF, jeton ni identifiant technique. |

## 9. Administration plateforme et provisioning

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| PLAT-01 | P0 | `PLATFORM` connecté, sans appartenance | 1. Ouvrir `/`.<br>2. Vérifier la destination et le menu.<br>3. Ouvrir la liste plateforme. | Destination `/app/platform/organizations` ; Plateforme et Compte visibles ; Recherche, Organisation et Membres absents. |
| PLAT-02 | P1 | page Plateforme | 1. Laisser chaque champ obligatoire vide.<br>2. Saisir un courriel invalide.<br>3. Vider le fuseau.<br>4. Tenter de soumettre. | Le navigateur empêche la soumission ; aucune organisation ni invitation créée. |
| PLAT-03 | P0 | page Plateforme | 1. Saisir `ORG-A`, `fr-CA`, `America/Toronto`, `ADMIN`.<br>2. Cliquer Créer l’organisation une fois.<br>3. Observer le message et la liste. | Un seul ORG-A en « Activation en cours » ; première invitation Active et livraison Envoyée ; formulaire remis à zéro. |
| PLAT-04 | P0 | PLAT-03 | 1. Ouvrir Mailpit.<br>2. Rechercher le message destiné à `ADMIN`.<br>3. Vérifier expéditeur, organisation, rôle et lien sans le publier. | Un message minimal, un seul lien, rôle Administrateur ; aucun mot de passe ni secret serveur. |
| PLAT-05 | P0 | créer `ORG-R`/`PENDING` | 1. Conserver l’ancien message fermé.<br>2. Cliquer Renvoyer une seule fois.<br>3. Ouvrir le nouveau message.<br>4. Essayer l’ancien lien, puis le nouveau. | Nouveau message reçu ; ancien lien refusé par le même état terminal générique ; nouveau lien valide. Aucun doublon d’organisation. |
| PLAT-06 | P0 | créer `ORG-V`/courriel unique | 1. Cliquer Révoquer.<br>2. Annuler le dialogue.<br>3. Refaire, confirmer.<br>4. Essayer le lien reçu. | Annulation sans effet ; confirmation rend l’invitation Révoquée ; lien refusé ; organisation reste en provisioning. |
| PLAT-07 | P0 | invitation ORG-A valide | 1. Accepter l’invitation selon INV-01.<br>2. Revenir comme `PLATFORM` et Actualiser. | ORG-A devient Active ; invitation Acceptée ; aucune action renvoi/révocation initiale n’est proposée. |
| PLAT-08 | P0 | `ADMIN` sans rôle plateforme | 1. Ouvrir le lien profond Plateforme.<br>2. Vérifier le menu. | 403 ; aucune donnée de provisioning ni action plateforme. |
| PLAT-09 | P2 | jeu assisté de 26 organisations | 1. Ouvrir Plateforme.<br>2. Noter la première page.<br>3. Cliquer Charger la suite.<br>4. Rechercher doublons et total global. | 25 éléments maximum sur la première page, suite ajoutée sans doublon ; aucun total global inventé. |

## 10. Acceptation des invitations

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| INV-01 | P0 | lien initial ORG-A pour nouveau `ADMIN` | 1. Ouvrir le lien Mailpit.<br>2. Vérifier que le fragment contenant le jeton disparaît immédiatement de l’adresse.<br>3. Vérifier organisation et rôle.<br>4. Saisir nom, mot de passe valide et confirmation.<br>5. Cliquer Créer le compte et accepter. | Aucun jeton dans l’URL visible après chargement ; compte créé ; ORG-A activée ; session ouverte dans ORG-A. |
| INV-02 | P1 | nouveau compte | 1. Saisir deux mots de passe différents.<br>2. Soumettre.<br>3. Corriger avec un mot de passe de moins de 12 caractères.<br>4. Soumettre. | Message de non-correspondance puis validation de longueur ; invitation non consommée. |
| INV-03 | P0 | INV-01 terminé | 1. Se déconnecter.<br>2. Réouvrir exactement le lien déjà accepté. | État terminal générique ; aucun second compte ni seconde appartenance. |
| INV-04 | P1 | aucun | 1. Ouvrir `/accept-invitation` sans jeton.<br>2. Tester séparément un lien expiré et un lien révoqué préparés. | Même présentation publique « Invitation non disponible » ; aucune information permettant de distinguer inconnu, expiré, révoqué ou utilisé. |
| INV-05 | P0 | compte `ADMIN` existant, première invitation ORG-B créée vers `ADMIN` | 1. Ouvrir le lien en étant déconnecté.<br>2. Se connecter dans la page d’invitation.<br>3. Cliquer Accepter l’invitation. | Aucun formulaire de nouveau compte ; appartenance ORG-B ajoutée ; session active dans ORG-B ; ORG-B activée. |
| INV-06 | P0 | invitation destinée à un compte existant | 1. Ouvrir le lien avec une session d’un autre compte.<br>2. Tenter de poursuivre.<br>3. Utiliser Se déconnecter puis le compte destinataire. | Le mauvais compte ne peut accepter ; aucune révélation supplémentaire ; le bon compte accepte. |

## 11. Organisation active

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| ORG-01 | P0 | comptes Admin, Manager, Sales | 1. Ouvrir Organisation avec chaque rôle.<br>2. Comparer les informations et actions. | Tous lisent nom, langue, fuseau, état et dates ; seul Admin voit le formulaire de modification. |
| ORG-02 | P0 | `ADMIN` dans ORG-A | 1. Modifier le nom avec un suffixe temporaire, la langue ou le fuseau.<br>2. Enregistrer.<br>3. Actualiser.<br>4. Restaurer les valeurs d’origine. | Succès annoncé ; valeurs persistantes ; version serveur prise en compte ; aucune autre organisation modifiée. |
| ORG-03 | P1 | `ADMIN` | 1. Vider le nom puis le fuseau.<br>2. Saisir un fuseau manifestement invalide.<br>3. Soumettre chaque variante. | Champs obligatoires bloqués ; valeur invalide refusée proprement ; aucune trace technique affichée. |
| ORG-04 | P1 | deux fenêtres `ADMIN` sur ORG-A | 1. Charger Organisation dans A et B.<br>2. Enregistrer une modification dans A.<br>3. Enregistrer une autre modification depuis B sans recharger.<br>4. Cliquer Recharger la version actuelle. | B reçoit un conflit explicite ; sa saisie n’est pas appliquée silencieusement ; rechargement contrôlé, aucun écrasement. |

## 12. Membres et rôles

Préparer `MANAGER`, `SALES`, `SECOND-ADMIN` et `NO-ORG` par la section 13, puis accepter leurs invitations.

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| MEM-01 | P0 | `MANAGER` actif | 1. Se connecter.<br>2. Ouvrir Membres.<br>3. Examiner chaque ligne. | Liste visible ; aucun bouton Modifier ; aucun onglet Invitations ; Organisation en lecture seule. |
| MEM-02 | P0 | `SALES` actif | 1. Se connecter.<br>2. Vérifier le menu.<br>3. Ouvrir le lien profond Membres. | Membres absent du menu ; lien profond 403 ; Recherche et Organisation disponibles. |
| MEM-03 | P0 | `ADMIN`, membre `SALES` | 1. Cliquer Modifier sur `SALES`.<br>2. Passer Commercial à Gestionnaire.<br>3. Enregistrer.<br>4. Reconnecter `SALES`, puis restaurer Commercial. | Succès ; nouveau rôle appliqué après renouvellement de session ; capacités cohérentes ; restauration réussie. |
| MEM-04 | P0 | `ADMIN`, membre `NO-ORG` actif | 1. Modifier `NO-ORG` vers Désactivé.<br>2. Annuler le dialogue.<br>3. Refaire et confirmer.<br>4. Utiliser la session ouverte de `NO-ORG` puis se reconnecter. | Annulation sans effet ; confirmation désactive ; ancienne session refusée ; connexion mène à « Aucune organisation accessible ». |
| MEM-05 | P0 | ORG-A ne possède momentanément qu’un Admin actif | 1. Modifier le dernier Admin vers Gestionnaire, ou le désactiver.<br>2. Confirmer. | Refus expliquant qu’un second Administrateur actif est requis ; ligne inchangée ; session conservée. |
| MEM-06 | P0 | `ADMIN` et `SECOND-ADMIN` actifs | 1. Depuis `ADMIN`, rétrograder son propre rôle après confirmation.<br>2. Observer la session.<br>3. Se reconnecter.<br>4. Faire restaurer Admin par `SECOND-ADMIN`. | Mutation réussie seulement avec second Admin ; session courante invalidée ; nouvelles capacités appliquées à la reconnexion. |
| MEM-07 | P2 | jeu assisté de plus de 25 membres | 1. Ouvrir Membres.<br>2. Cliquer Charger la suite.<br>3. Actualiser.<br>4. Vérifier doublons et ordre. | Pagination ajoute sans doublon ; Actualiser remplace la liste ; aucun total global inventé. |
| MEM-08 | P1 | deux fenêtres Admin | 1. Charger le même membre dans A et B.<br>2. Le modifier dans A.<br>3. Modifier la version ancienne dans B.<br>4. Recharger la liste depuis l’alerte. | Conflit de version explicite ; aucune mutation rejouée automatiquement ; saisie non appliquée silencieusement. |

## 13. Invitations de membres

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| MINV-01 | P0 | `ADMIN` dans ORG-A | 1. Ouvrir Membres puis Invitations.<br>2. Saisir `MANAGER`, rôle Gestionnaire.<br>3. Cliquer Créer l’invitation une fois.<br>4. Répéter pour `SALES`, `SECOND-ADMIN` et `NO-ORG` avec leurs rôles. | Une invitation actionnable par courriel ; état et livraison visibles ; succès annoncé ; aucune valeur technique affichée. |
| MINV-02 | P1 | invitation active | 1. Tenter de recréer la même invitation pour la même organisation.<br>2. Ne pas modifier le premier enregistrement. | Refus contrôlé « invitation déjà en attente » ou équivalent ; aucun doublon. |
| MINV-03 | P0 | MINV-01 | 1. Ouvrir Mailpit.<br>2. Vérifier destinataire, ORG-A, rôle et lien.<br>3. Vérifier qu’un seul message correspond à chaque création. | Courriel minimal et exact ; aucun mot de passe, cookie, CSRF, hash ou détail SMTP. |
| MINV-04 | P0 | invitation active non acceptée | 1. Conserver l’ancien lien.<br>2. Cliquer Renvoyer.<br>3. Ouvrir le nouveau message.<br>4. Tester ancien puis nouveau lien. | Nouveau lien valide ; ancien immédiatement invalide ; la liste représente l’invitation de remplacement. |
| MINV-05 | P0 | invitation active | 1. Cliquer Révoquer.<br>2. Vérifier focus et texte du dialogue.<br>3. Annuler.<br>4. Refaire et confirmer.<br>5. Tester le lien. | Annulation sans effet ; confirmation retire l’invitation de la liste actionnable ; lien refusé. |
| MINV-06 | P0 | invitations valides | 1. Accepter les invitations des comptes de la section 12.<br>2. Actualiser Membres et Invitations.<br>3. Vérifier rôles et absence des invitations acceptées dans la liste actionnable. | Membres actifs avec les rôles proposés ; invitations acceptées non présentées comme encore actionnables. |
| MINV-07 | P2 | environnement configuré pour atteindre la limite | 1. Déclencher des renvois jusqu’au `429` sans automatisation agressive.<br>2. Noter le message et le délai.<br>3. Attendre le délai puis réessayer une fois. | Message lisible avec `Retry-After` en secondes ; bouton récupérable ; aucune boucle automatique. |

## 14. Multi-organisation et isolation

Créer ORG-B depuis Plateforme vers le compte `ADMIN`, puis accepter selon INV-05.

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| MULTI-01 | P0 | `ADMIN` actif dans ORG-A et ORG-B | 1. Se connecter.<br>2. Vérifier le bandeau et Mon compte. | Sélecteur visible ; deux organisations et leurs rôles affichés ; une seule marquée Active. |
| MULTI-02 | P0 | MULTI-01 | 1. Dans ORG-A, ouvrir Organisation.<br>2. Choisir ORG-B.<br>3. Observer le bandeau, la page et Mon compte.<br>4. Revenir à ORG-A. | Contexte remplacé atomiquement ; données de ORG-B seulement ; ancien contexte ne réapparaît pas ; retour correct. |
| MULTI-03 | P0 | données différentes dans A et B | 1. Ajouter un membre uniquement dans ORG-A.<br>2. Lister les membres de A.<br>3. Basculer vers B et lister.<br>4. Tester une URL profonde déjà ouverte. | Le membre de A n’apparaît jamais dans B ; aucune donnée croisée pendant le chargement ou après retour navigateur. |
| MULTI-04 | P1 | outils développeur, session ORG-A | 1. Bloquer temporairement la requête `switch-organization` ou passer hors ligne.<br>2. Demander ORG-B.<br>3. Réactiver le réseau.<br>4. Actualiser. | Erreur contrôlée ; ORG-A reste active ; aucune interface hybride ; actualisation retrouve le contexte serveur. |
| MULTI-05 | P0 | résultat Google obtenu dans GOOG-03 | 1. Après l’unique recherche, basculer immédiatement d’organisation.<br>2. Revenir sur Recherche. | Résultats, carte, filtre, requêtes en vol et concession précédente sont purgés ; aucun contenu Google de l’autre organisation. |

## 15. Recherche Google et carte — scénario facturable borné

**Important :** GOOG-03 et GOOG-05 constituent ensemble l’unique Text Search réel de la campagne. Ne pas répéter en
cas de succès. Si le test échoue après que l’appel est parti, consigner l’incident avant toute nouvelle tentative.

| ID | Pri. | Précondition | Étapes | Résultat attendu |
| --- | --- | --- | --- | --- |
| GOOG-01 | P0 | `ADMIN`, `MANAGER` ou `SALES` ; clé configurée | 1. Ouvrir Recherche.<br>2. Vérifier le badge API configurée.<br>3. Vérifier les champs et compteurs à zéro. | Écran accessible seulement avec organisation active ; aucune requête au simple affichage. |
| GOOG-02 | P0 | GOOG-01 | 1. Laisser le type vide.<br>2. Tester latitude/longitude/rayon hors limites via saisie lorsque possible.<br>3. Ne pas valider de requête correcte. | Validation locale/serveur lisible ; compteurs restent à zéro ; aucun appel Google facturable. |
| GOOG-03 | P0 | coordinateur QA autorise l’appel | 1. Saisir `plombier`.<br>2. Utiliser latitude `46.8139`, longitude `-71.208`, rayon `15 km`.<br>3. Choisir l’option zone de service voulue.<br>4. Cliquer une seule fois Rechercher des établissements.<br>5. Attendre sans recliquer. | Exactement un Text Search ; maximum 20 résultats ; compteur d’appels à 1 ; aucune pagination automatique. |
| GOOG-04 | P0 | GOOG-03 | 1. Examiner plusieurs lignes.<br>2. Vérifier nom, adresse, distance, type, état et lien Google Maps lorsqu’ils existent.<br>3. Rechercher téléphone et site Web.<br>4. Examiner l’export et l’attribution. | Aucun téléphone ni site Web ; Exporter Excel visible mais désactivé ; attribution **Google Maps** visible ; aucun terme « générateur » ou « leads ». |
| GOOG-05 | P1 | GOOG-03 | 1. Utiliser le filtre local avec un nom ou une ville affichée.<br>2. Effacer le filtre.<br>3. Actualiser la page seulement après la preuve MULTI-05 si celle-ci est exécutée. | Filtre sans appel Google supplémentaire ; effacement restaure les lignes ; actualisation supprime résultats et carte. |
| GOOG-06 | P0 | GOOG-03, capacité carte | 1. Observer la carte produite après la recherche.<br>2. Vérifier le compteur Maps attendu.<br>3. Ne pas relancer automatiquement en cas d’échec. | Au plus une Maps Static ; carte liée aux résultats ; échec terminal lisible, sans seconde facturation automatique. |
| GOOG-07 | P0 | session Plateforme seule puis `NO-ORG` | 1. Ouvrir `/app/search` avec chaque profil.<br>2. Observer les compteurs Google Cloud si disponibles. | 403/état restreint ; zéro appel fournisseur. Le rôle plateforme n’accorde aucun accès implicite. |
| GOOG-08 | P1 | outils développeur | 1. Vérifier que `/api/leads/search` et `/api/leads/export` ne sont pas utilisés.<br>2. Tenter leur ouverture sans envoyer de données sensibles. | Routes historiques absentes (`404`/`405` selon méthode) ; aucune exportation possible. |

Alternative contrôlée à GOOG-03, à utiliser **à la place** du parcours manuel et non en supplément :

```powershell
.\scripts\Test-GoogleProtectionLocal.ps1 `
  -AdministratorEmail "qa.admin.<RUN>@example.ca" `
  -ConfirmGoogleCall RUN_ONE_GOOGLE_SEARCH `
  -FetchMap
```

## 16. Confidentialité et sécurité observables

| ID | Pri. | Étapes | Résultat attendu |
| --- | --- | --- | --- |
| SEC-01 | P0 | 1. Ouvrir DevTools > Application.<br>2. Examiner Local Storage, Session Storage, IndexedDB, Cache Storage et Service Workers après connexion, invitation, recherche et administration. | Aucun mot de passe, session, CSRF, jeton d’invitation, UUID idempotent, résultat Google, formulaire ou ressource CRM. |
| SEC-02 | P0 | 1. Parcourir toutes les routes.<br>2. Observer l’adresse après invitation et mutations.<br>3. Examiner les erreurs visibles. | Aucun cookie, CSRF, jeton, UUID idempotent, courriel sensible ou corps métier dans l’URL ; aucune trace Python/SQL/SMTP. |
| SEC-03 | P0 | 1. Dans Network, examiner sans copier les valeurs sensibles les réponses Auth, Google, carte et administration.<br>2. Vérifier les en-têtes de cache. | Réponses sensibles avec `Cache-Control: no-store` ; cookie de session `HttpOnly`; clés Google absentes des réponses. |
| SEC-04 | P1 | 1. Double-cliquer rapidement Connexion, Créer organisation, Créer invitation, Renvoyer et Rechercher dans des jeux de données dédiés.<br>2. Compter les effets. | Boutons occupés ; un seul effet métier ; aucun doublon ni double appel facturable. |
| SEC-05 | P0 | 1. Se connecter dans ORG-A.<br>2. Copier une URL d’administration et l’ouvrir avec un rôle inférieur.<br>3. Répéter entre ORG-A et ORG-B. | L’URL ne transporte aucune autorité ; serveur refuse selon session/capacité ; aucune donnée inter-organisation. |
| SEC-06 | P1 | 1. Observer Console pendant la campagne.<br>2. Filtrer erreurs et avertissements.<br>3. Vérifier le contenu sans recopier les secrets. | Aucun `console.log/debug`, rejet non géré, warning React ou donnée sensible. |

## 17. Accessibilité clavier et lecteur d’écran

Exécuter sans souris. Utiliser Tab, Maj+Tab, Entrée, Espace, Échap, Flèches, Home et End.

| ID | Pri. | Étapes | Résultat attendu |
| --- | --- | --- | --- |
| A11Y-01 | P0 | 1. Recharger une page authentifiée.<br>2. Appuyer Tab.<br>3. Activer « Aller au contenu principal ».<br>4. Continuer dans tout le bandeau. | Lien d’évitement visible au focus ; arrivée sur le contenu ; ordre logique et focus toujours visible. |
| A11Y-02 | P0 | 1. À largeur mobile, ouvrir Menu au clavier.<br>2. Vérifier le focus initial.<br>3. Appuyer Échap.<br>4. Réouvrir et fermer avec le bouton. | Focus dans la navigation ; Échap ferme ; focus revient au bouton Menu ; arrière-plan non actionnable. |
| A11Y-03 | P0 | 1. Ouvrir Membres comme Admin.<br>2. Focaliser l’onglet Membres.<br>3. Utiliser Droite/Gauche, Home/End.<br>4. Vérifier le panneau. | Un seul onglet dans l’ordre Tab ; flèches changent focus et panneau ; état sélectionné annoncé. |
| A11Y-04 | P0 | 1. Ouvrir un dialogue Révoquer ou modification sensible.<br>2. Parcourir avec Tab/Maj+Tab.<br>3. Appuyer Échap.<br>4. Refaire et déclencher une action occupée. | Titre/description annoncés ; focus piégé ; Échap annule hors traitement ; focus restitué ; aucun accès arrière-plan pendant traitement. |
| A11Y-05 | P0 | 1. Provoquer une erreur de connexion puis une erreur de formulaire/mutation.<br>2. Observer le focus et l’annonce. | Erreur reçoit le focus, est annoncée comme alerte et reste compréhensible sans couleur. |
| A11Y-06 | P1 | 1. Activer NVDA ou Narrateur.<br>2. Parcourir Connexion, Recherche, Membres/Invitations et Plateforme.<br>3. Vérifier titres, champs, états, boutons occupés et succès. | Noms accessibles corrects ; hiérarchie de titres logique ; succès poli ; aucune icône seule incompréhensible. |

## 18. Responsive, zoom et contraste

Tester au minimum Connexion, Invitation, Recherche, Compte, Organisation, Membres, Invitations, Plateforme, 403 et 404.

| ID | Pri. | Configuration et étapes | Résultat attendu |
| --- | --- | --- | --- |
| RESP-01 | P0 | 1. Régler 320 × 568 CSS px à 100 %.<br>2. Parcourir toutes les routes listées.<br>3. Ouvrir menus, dialogues, listes et formulaires.<br>4. Faire défiler verticalement. | Aucun défilement horizontal de page ; texte essentiel non tronqué ; toutes les actions accessibles ; aucun chevauchement. |
| RESP-02 | P0 | 1. Régler une fenêtre 1280 × 720.<br>2. Passer le zoom navigateur à 200 %.<br>3. Rejouer les routes et actions critiques. | Contenu reflué ; aucune action perdue ; ordre de lecture logique ; pas de superposition. |
| RESP-03 | P1 | 1. Tester largeur bureau normale.<br>2. Examiner focus, hover, disabled, succès et erreur.<br>3. Utiliser l’outil contraste du navigateur. | WCAG AA : 4,5:1 texte normal, 3:1 grand texte et composants/focus. Toute exception devient une anomalie. |
| RESP-04 | P1 | 1. Rejouer Connexion, Recherche et Administration dans un second navigateur.<br>2. Comparer interactions et mise en page. | Aucun défaut fonctionnel propre au navigateur ; variations typographiques mineures seulement. |

## 19. Résilience et erreurs contrôlées

| ID | Pri. | Étapes | Résultat attendu |
| --- | --- | --- | --- |
| RES-01 | P0 | 1. Après accord de l’exploitant, arrêter Redis ou PostgreSQL dans un environnement jetable.<br>2. Ouvrir readiness et tenter connexion/action.<br>3. Redémarrer le service. | Readiness non prête ; erreur utilisateur contrôlée sans trace ; récupération après redémarrage. |
| RES-02 | P1 | 1. Dans DevTools, passer hors ligne juste après une mutation idempotente dédiée.<br>2. Revenir en ligne.<br>3. Réessayer sans modifier le formulaire.<br>4. Vérifier les doublons. | Résultat incertain expliqué ; même intention réessayée explicitement ; un seul objet final ; aucune relance automatique. |
| RES-03 | P1 | 1. Commencer à remplir un formulaire sans soumettre.<br>2. Changer d’organisation ou se déconnecter.<br>3. Revenir. | Saisie et intention temporaires purgées ; aucune donnée de l’ancien contexte. |
| RES-04 | P0 | 1. Désactiver un membre pendant qu’il possède une session ouverte.<br>2. Depuis cette session, naviguer et lancer une action.<br>3. Se reconnecter. | Ancienne session invalidée ; aucune action après révocation ; droits recalculés à la reconnexion. |
| RES-05 | P1 | 1. Provoquer un conflit de version Organisation ou Membre.<br>2. Vérifier l’alerte.<br>3. Recharger explicitement. | Pas d’écrasement silencieux, pas de retry automatique, chemin de récupération clair. |

## 20. Verrou automatisé et Azure Pipelines

Cette section est exécutée par le QA technique ou l’exploitant, après arrêt des serveurs Vite locaux afin de permettre
à `npm ci` de remplacer ses binaires natifs.

### QUAL-01 — Verrou local complet

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-QualityGateLocal.ps1
```

Attendus obligatoires :

- Alembic à `20260813_0008 (head)`, downgrade contrôlé puis reconstruction et `alembic check` vert ;
- **185 tests pytest collectés, zéro échec, zéro skip** avec PostgreSQL, Redis et Mailpit réels ;
- Ruff, format Ruff et mypy verts ;
- `npm ci` et audit npm verts ;
- **133 tests Vitest réussis, zéro échec, zéro skip**, dont les états axe ;
- ESLint et build Vite verts ;
- contrôles sources navigateur, artefact et `git diff --check` verts ;
- message final `Verrou qualité local 2.4.5 : VERT`.

### QUAL-02 — Azure Pipelines

1. Pousser ou sélectionner exactement la même révision que celle testée localement.
2. Lancer Azure Pipelines.
3. Vérifier chaque étape et les deux rapports JUnit publiés.
4. Vérifier que l’artefact n’est publié qu’après toutes les barrières vertes.
5. Inscrire l’identifiant du passage et joindre son lien à la recette.

Résultat attendu : passage vert sans relance inexpliquée, zéro skip et aucune clé Google injectée.

## 21. Contrôles de fin de campagne

1. Se déconnecter de tous les comptes de recette.
2. Fermer les liens d’invitation encore ouverts.
3. Vérifier qu’aucune capture ne contient de secret.
4. Consigner les organisations et comptes créés pour nettoyage ultérieur ; ne rien supprimer directement en base.
5. Vérifier qu’un seul Text Search et au plus une Maps Static réels ont été consommés.
6. Compiler les résultats par sévérité.
7. Renseigner la décision finale.

## 22. Registre d’exécution

Copier une ligne par cas exécuté. Les identifiants attendus sont :

`ENV-01..02`, `LEG-01..02`, `AUTH-01..05`, `ROUTE-01..03`, `ACCOUNT-01`, `PLAT-01..09`, `INV-01..06`,
`ORG-01..04`, `MEM-01..08`, `MINV-01..07`, `MULTI-01..05`, `GOOG-01..08`, `SEC-01..06`,
`A11Y-01..06`, `RESP-01..04`, `RES-01..05`, `QUAL-01..02`.

| ID | Statut | Date/heure | Testeur | Preuve ou lien | Anomalie | Commentaire |
| --- | --- | --- | --- | --- | --- | --- |
| __________ | PASS / FAIL / BLOCKED / N/A | __________ | __________ | __________ | __________ | __________ |

## 23. Modèle d’anomalie

```text
Titre : [ID du test] Résumé précis
Sévérité : Bloquante / Majeure / Mineure
Révision et environnement :
Navigateur, version et résolution :
Compte/rôle utilisé (sans mot de passe) :
Organisation active :
Préconditions :
Étapes exactes de reproduction :
Résultat observé :
Résultat attendu :
Reproductibilité : x/y
Impact utilisateur/sécurité/facturation :
Preuves assainies :
Console ou request_id non sensible :
Contournement éventuel :
```

## 24. Rapport de synthèse et décision

| Mesure | Valeur |
| --- | --- |
| Cas prévus | 83 |
| PASS | ___ |
| FAIL | ___ |
| BLOCKED | ___ |
| NOT RUN | ___ |
| N/A justifiés | ___ |
| Anomalies bloquantes | ___ |
| Anomalies majeures | ___ |
| Anomalies mineures | ___ |
| Verrou local vert | Oui / Non |
| Azure vert, identifiant | __________ |
| Appel Google borné confirmé | Oui / Non |

### Critères de GO

Le GO exige simultanément :

- tous les cas P0 exécutés et PASS ;
- aucun défaut bloquant ou majeur ouvert ;
- aucun franchissement d’organisation ou de rôle ;
- verrou local et Azure verts sur la même révision ;
- zéro test ignoré dans le passage d’infrastructure obligatoire ;
- matrice clavier, responsive, zoom et contraste validée ;
- limites Google confirmées sans dépassement ;
- anomalies mineures documentées et explicitement acceptées par le responsable produit.

### Signatures

| Rôle | Nom | Décision | Date | Signature/commentaire |
| --- | --- | --- | --- | --- |
| Responsable QA | __________ | GO / NO-GO | __________ | __________ |
| Responsable produit | __________ | GO / NO-GO | __________ | __________ |
| Responsable technique | __________ | GO / NO-GO | __________ | __________ |
| Sécurité/exploitation | __________ | GO / NO-GO | __________ | __________ |

## 25. Références

- [`README.md`](../README.md)
- [`PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md)
