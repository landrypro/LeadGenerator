# Phase 3.2 — Pipeline Kanban

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3 — Cœur CRM |
| Incrément | 3.2 — Pipeline Kanban |
| Version | 1.1 — implémentation réalisée |
| Prérequis | 3.1 clôturé avec réserve ; socle prospects 2.5 ; audit 2.4 ; durcissement 2.6 |
| Statut | Implémenté — recette fonctionnelle et verrou complet à exécuter |
| Date | 4 septembre 2026 |
| Résultat visé | Neuf étapes commerciales, transitions contrôlées, conflits de version, historique, audit et filtres |

## 1. Objectif

L’incrément 3.2 transforme le portefeuille de prospects en outil de pilotage commercial quotidien. Il permet de voir
chaque prospect dans une étape explicite, de le faire progresser selon des règles stables, d’identifier son responsable
et sa priorité, puis de retrouver l’historique exact des changements.

Le Kanban est une projection du portefeuille CRM. Il ne duplique ni les prospects ni leurs données de contact. Un
déplacement modifie l’étape du prospect dans une transaction unique, crée une entrée d’historique métier et écrit un
événement dans le journal d’audit append-only.

## 2. Périmètre

### 2.1 Inclus

- neuf étapes commerciales système et leur configuration visuelle par organisation ;
- vue Kanban par colonnes et vue liste filtrable du même portefeuille ;
- déplacement individuel contrôlé par bouton, clavier ou glisser-déposer ;
- contrôle de version optimiste et idempotence des commandes ;
- motifs structurés pour la perte et la réouverture d’un dossier terminal ;
- historique paginé des transitions d’un prospect ;
- filtres par étape, responsable, priorité, origine, étiquette et texte ;
- migration additive, RLS, capacités, audit, métriques, tests et documentation.

### 2.2 Hors périmètre

- activités, appels, notes, tâches, rappels et prochaine action, livrés en 3.3 ;
- opportunités, montants, probabilités et prévisions, livrés en 3.4 ;
- automatisations, règles de passage automatiques, séquences et notifications ;
- déplacement groupé, fusion de prospects et ordre manuel des cartes dans une colonne ;
- suppression d’une étape système ou création d’une dixième étape ;
- scoring par intelligence artificielle ou calcul automatique de probabilité ;
- restauration d’un prospect archivé et modification des règles de conservation.

## 3. Vocabulaire et séparation des états

Une **étape commerciale** décrit l’avancement de la relation. L’**archivage** décrit le cycle de conservation de la
donnée. `lost` et `archived` ne sont donc pas synonymes : un prospect perdu reste consultable dans le pipeline, tandis
qu’un prospect archivé est exclu du Kanban et suit les règles de conservation.

Le champ `stage_code` porte uniquement une étape commerciale pour les prospects actifs. La valeur historique
`archived` reste temporairement admise pour les lignes déjà archivées avant 3.2, mais elle n’est jamais proposée comme
colonne, cible de transition ou valeur d’une nouvelle commande.

## 4. Les neuf étapes commerciales

| Ordre initial | Code stable | Libellé français initial | Sens métier |
| ---: | --- | --- | --- |
| 1 | `new` | Nouveau | Prospect ajouté, pas encore examiné |
| 2 | `qualifying` | Qualification en cours | Besoin, territoire et adéquation en cours d’évaluation |
| 3 | `qualified` | Qualifié | Prospect jugé pertinent pour une démarche commerciale |
| 4 | `contacted` | Contact établi | Une prise de contact commerciale a été déclarée |
| 5 | `opportunity` | Opportunité détectée | Un besoin ou projet potentiel est identifié |
| 6 | `proposal_sent` | Proposition envoyée | Une proposition commerciale a été transmise |
| 7 | `negotiation` | Négociation | Les conditions de la proposition sont discutées |
| 8 | `won` | Gagné | La démarche commerciale est conclue positivement |
| 9 | `lost` | Perdu | La démarche est arrêtée avec un motif explicite |

Les codes sont immuables. Une organisation peut changer l’ordre d’affichage, la couleur et les libellés `fr-CA` et
`en-CA`, mais cette personnalisation ne change ni le sens système, ni les transitions autorisées, ni les rapports.
Les couleurs sont choisies dans une palette de jetons accessibles contrôlée par l’application ; aucun CSS libre n’est
accepté.

## 5. Règles de transition

### 5.1 Graphe normal

| Étape source | Cibles normales autorisées |
| --- | --- |
| `new` | `qualifying`, `lost` |
| `qualifying` | `new`, `qualified`, `lost` |
| `qualified` | `qualifying`, `contacted`, `lost` |
| `contacted` | `qualified`, `opportunity`, `lost` |
| `opportunity` | `contacted`, `proposal_sent`, `lost` |
| `proposal_sent` | `opportunity`, `negotiation`, `won`, `lost` |
| `negotiation` | `proposal_sent`, `won`, `lost` |
| `won` | Aucune transition normale |
| `lost` | Aucune transition normale |

Le retour à l’étape immédiatement précédente est permis afin de corriger une qualification ou une progression trop
rapide. Les sauts vers l’avant sont refusés, sauf `proposal_sent` vers `won`. Le passage vers `lost` est permis depuis
toute étape non terminale.

### 5.2 Passage à `lost`

Le motif est obligatoire et choisi parmi : `no_need`, `no_budget`, `no_response`, `competitor`, `timing`,
`outside_territory`, `invalid_or_duplicate` et `other`. Le motif `other` exige une note de 1 à 500 caractères. Cette
note est assainie et conservée dans l’historique métier, mais elle n’est jamais recopiée dans les journaux techniques,
les métriques ou les métadonnées d’audit.

### 5.3 Étapes terminales et réouverture

`won` et `lost` sont terminales. Leur réouverture exige la capacité `pipeline:reopen`, un motif structuré et la version
courante du prospect :

- `won` peut être rouvert vers `negotiation` ;
- `lost` revient à l’étape source de sa dernière transition vers `lost` ; en l’absence d’historique exploitable, la cible
  de repli est `qualifying` ;
- motifs de réouverture : `entered_in_error`, `customer_reengaged`, `additional_information` ou `other` ;
- `other` exige une note assainie de 1 à 500 caractères.

Un prospect archivé ne peut pas être déplacé ni rouvert dans 3.2.

## 6. Acteurs et capacités

| Capacité | Administrateur | Gestionnaire | Commercial |
| --- | :---: | :---: | :---: |
| `pipeline:read` | Oui | Oui | Oui |
| `pipeline:move` | Oui | Oui | Oui |
| `pipeline:history:read` | Oui | Oui | Oui |
| `pipeline:reopen` | Oui | Oui | Non |
| `pipeline:configure` | Oui | Non | Non |

En V1, l’assignation sert au pilotage et au filtrage ; elle ne restreint pas la visibilité ou le déplacement à son seul
responsable. Tout membre actif disposant de `pipeline:move` peut déplacer un prospect actif de son organisation.
L’administrateur de plateforme ne reçoit aucun accès implicite au pipeline d’une organisation.

## 7. Modèle de données cible

### 7.1 Configuration des étapes

La table `pipeline_stage_settings` contient :

- `id`, `organization_id` et `stage_code` ;
- `position` unique dans l’organisation ;
- `color_token` appartenant à la palette autorisée ;
- `labels`, objet JSON limité aux clés `fr-CA` et `en-CA` ;
- `version`, `created_at` et `updated_at`.

Une ligne existe pour chacun des neuf codes et chaque organisation. La migration initialise les organisations
existantes ; le provisioning crée les neuf lignes pour toute nouvelle organisation. Les étapes ne peuvent être ni
ajoutées, ni supprimées, ni désactivées.

### 7.2 Historique des transitions

La table append-only `prospect_stage_transitions` contient :

- `id`, `organization_id`, `prospect_id` et `actor_id` ;
- `from_stage_code`, `to_stage_code`, `from_version` et `resulting_version` ;
- `reason_code` et `reason_note` facultative selon la règle métier ;
- `idempotency_key_hash` et `command_fingerprint` ;
- `occurred_at`.

Une contrainte unique sur `(organization_id, prospect_id, resulting_version)` empêche deux histoires concurrentes
pour une même version. Une seconde contrainte garantit l’unicité de l’idempotence dans l’organisation. Aucune route ne
modifie ou ne supprime une transition.

### 7.3 Évolution de `prospects`

- la contrainte de `stage_code` accepte les neuf codes commerciaux ;
- `stage_changed_at` est ajouté, non nul, avec reprise initiale depuis `updated_at` ;
- `archived_at` reste la source de vérité de l’archivage ;
- les lignes historiques `stage_code = 'archived'` sont tolérées uniquement lorsque `archived_at IS NOT NULL` ;
- aucune conversion automatique d’un ancien prospect archivé vers `lost` ou `won` n’est effectuée.

La migration prévue succède à `20260826_0014`. Elle est additive et reconstruisible par Alembic. Toutes les nouvelles
tables portent RLS activée et forcée pour le rôle applicatif.

## 8. Atomicité, concurrence et idempotence

Une commande de transition transmet obligatoirement :

- la version lue du prospect ;
- une clé `Idempotency-Key` opaque, unique et bornée ;
- l’étape cible et, lorsque nécessaire, le motif et la note.

Dans une transaction PostgreSQL unique, le serveur :

1. relit le prospect sous RLS et vérifie qu’il n’est pas archivé ;
2. vérifie la capacité, la version et la transition ;
3. met à jour `stage_code`, `stage_changed_at`, `updated_at` et `version` ;
4. insère l’historique de transition ;
5. écrit l’événement d’audit ;
6. valide la transaction.

Deux commandes portant la même version ne peuvent pas réussir toutes les deux. La seconde reçoit `409` avec le code
`prospect_version_conflict` et les seules informations nécessaires au rafraîchissement : version et étape courantes.
Le rejeu strictement identique d’une clé d’idempotence retourne le résultat initial avec `replayed: true`. La même clé
avec une commande différente retourne `409 idempotency_conflict`.

## 9. API proposée

| Méthode et route | Capacité | Usage |
| --- | --- | --- |
| `GET /api/pipeline/stages` | `pipeline:read` | Configuration ordonnée des neuf étapes |
| `PATCH /api/pipeline/stages/{stage_code}` | `pipeline:configure` | Libellés, couleur et position avec version |
| `GET /api/pipeline/board` | `pipeline:read` | Colonnes, compteurs et première page filtrée |
| `POST /api/prospects/{prospect_id}/stage-transitions` | `pipeline:move` ou `pipeline:reopen` | Transition atomique et idempotente |
| `GET /api/prospects/{prospect_id}/stage-transitions` | `pipeline:history:read` | Historique paginé, du plus récent au plus ancien |
| `GET /api/prospects` | `prospects:read` | Vue liste avec filtres 3.2 étendus |

`GET /api/pipeline/board` retourne au plus 25 cartes par colonne et un curseur opaque par colonne lorsqu’il reste des
résultats. « Afficher plus » utilise la pagination filtrée de la colonne. La limite maximale d’une page est 50 cartes.
Toutes les réponses portent `Cache-Control: no-store`.

Les erreurs suivent le contrat existant : `401` authentification, `403` capacité, `404` ressource invisible ou absente,
`409` version/idempotence, `422` transition ou motif invalide et `503` indisponibilité. Chaque erreur contient un code
stable et un `request_id`.

## 10. Filtres et ordre d’affichage

La vue Kanban et la vue liste partagent les filtres suivants :

- recherche textuelle sur le nom interne CRM, le secteur et la ville CRM ;
- une ou plusieurs étapes ;
- responsable précis ou « non assigné » ;
- priorité minimale et maximale ;
- origine et étiquettes CRM ;
- date de dernière mise à jour.

Les filtres sont validés côté serveur, encodés dans l’URL et jamais conservés dans le stockage du navigateur. Les
curseurs sont opaques, liés à l’organisation et à l’empreinte des filtres ; changer un filtre invalide le curseur.

Dans une colonne, l’ordre stable est : priorité décroissante, date d’entrée dans l’étape croissante, puis identifiant.
Cela fait remonter les dossiers prioritaires et les plus anciens. Le réordonnancement manuel des cartes est exclu.

## 11. Interface Kanban

La navigation principale ajoute « Pipeline ». L’écran propose un basculement **Kanban / Liste**, un bandeau de filtres
et les neuf colonnes configurées. Une carte montre uniquement les données CRM utiles : nom interne, responsable,
priorité, étiquettes limitées, ancienneté dans l’étape et indicateur de source. Elle n’affiche aucune donnée Google
réhydratée ni canal de contact.

Le glisser-déposer affiche les cibles autorisées mais n’écrit rien avant confirmation du serveur. En cas de `409`, la
carte revient à sa position serveur, un message explique le conflit et le tableau se recharge. Une transition vers
`lost` ou une réouverture ouvre un dialogue de motif.

L’action reste entièrement disponible au clavier et par un menu « Changer d’étape ». Les colonnes ont des titres et
compteurs accessibles, les annonces utilisent une région `aria-live`, le focus revient sur la carte après succès ou
erreur et les couleurs ne sont jamais le seul porteur d’information.

## 12. Historique et audit

L’historique commercial est visible sur la fiche prospect et contient l’étape source, l’étape cible, l’auteur, la date
et le motif lorsque requis. La note de motif est visible seulement aux membres autorisés de l’organisation.

Deux nouvelles actions d’audit sont prévues :

- `prospect.stage_changed` ;
- `pipeline.stage_settings_updated`.

L’audit de transition contient uniquement les codes source/cible, le code de motif, les versions et l’identifiant du
prospect déjà porté par l’événement. Il exclut le nom du prospect, la note libre, les coordonnées, les contacts et toute
donnée Google. L’historique métier et l’audit sont validés dans la même transaction que le prospect.

## 13. Sécurité et isolation

- RLS protège configuration et historique par `organization_id` ;
- l’organisation active vient de la session serveur, jamais du corps ou des paramètres libres ;
- toutes les mutations exigent origine approuvée, CSRF, JSON et capacités ;
- les identifiants d’une autre organisation répondent comme une ressource absente ;
- les notes sont normalisées, bornées et rendues comme texte ;
- aucune donnée du pipeline n’est écrite dans `localStorage`, `sessionStorage`, IndexedDB ou Cache API ;
- les prospects archivés sont exclus du board au niveau SQL et non seulement masqués par React.

## 14. Observabilité

Les journaux JSON utilisent des événements à schéma fermé : résultat, code source/cible, conflit éventuel, durée et
`request_id`. Ils excluent identifiants utilisateur/organisation, alias, notes et données de contact.

Les métriques initiales sont :

- `pipeline_transition_total{from_stage,to_stage,result}` ;
- `pipeline_transition_conflict_total` ;
- `pipeline_board_request_total{result}` ;
- durée des transitions et chargements du board.

Les neuf codes forment une cardinalité bornée. Aucun identifiant métier ne devient une étiquette de métrique.

## 15. Tests et critères d’acceptation

1. Les neuf étapes sont présentes dans l’ordre initial pour une organisation existante et une nouvelle organisation.
2. La personnalisation d’un libellé, d’une couleur et d’une position ne change pas le code ni le graphe de transition.
3. Chaque transition autorisée réussit avec la bonne version ; chaque saut interdit retourne `422` sans écriture.
4. `lost` refuse une commande sans motif et `other` refuse une note absente ou hors limite.
5. `won` et `lost` refusent un déplacement normal ; leur réouverture respecte la capacité et le motif.
6. Deux transactions concurrentes sur la même version produisent exactement un succès et un `409`.
7. Un rejeu idempotent ne crée ni seconde transition ni second audit ; une charge différente avec la même clé échoue.
8. Mise à jour du prospect, historique et audit sont atomiques, y compris lorsqu’une insertion est forcée en échec.
9. Un prospect archivé ou d’une autre organisation ne peut ni apparaître sur le board ni être déplacé.
10. Les rôles respectent les cinq capacités définies, notamment l’interdiction de réouverture au Commercial.
11. Les filtres produisent les mêmes résultats en vue liste et Kanban ; les curseurs deviennent invalides après changement.
12. Le board respecte 25 cartes initiales par colonne, la pagination et l’ordre stable défini.
13. Le parcours clavier permet de déplacer une carte, saisir un motif, traiter un conflit et retrouver le focus.
14. Les tests axe ne détectent pas d’erreur critique ; libellés, statuts et focus ne dépendent pas de la couleur.
15. Audit, logs, métriques et réponses ne révèlent ni note libre, ni contact, ni contenu Google.
16. Ruff, format Ruff, mypy, pytest avec PostgreSQL/RLS réel, Alembic, ESLint, Vitest/axe, build et verrou local sont verts.

## 16. Migration, compatibilité et retour arrière

La migration 3.2 :

1. crée les tables de configuration et d’historique ;
2. initialise les neuf réglages pour chaque organisation ;
3. étend la contrainte `stage_code` et ajoute `stage_changed_at` ;
4. conserve les archives historiques sans les transformer en opportunités perdues ;
5. active et force RLS, puis accorde les droits minimaux au rôle applicatif.

Le déploiement applique la migration avant le backend 3.2. Le frontend n’utilise le nouveau board qu’après disponibilité
des routes. Le retour arrière applicatif masque le Kanban sans supprimer l’historique. Un downgrade destructeur des
transitions n’est autorisé qu’en environnement éphémère ; en staging ou production, le retour se fait par correction
additive.

## 17. Seize décisions validées

1. Le pipeline comporte exactement neuf codes système : `new`, `qualifying`, `qualified`, `contacted`, `opportunity`, `proposal_sent`, `negotiation`, `won` et `lost`.
2. `archived` n’est pas une étape commerciale ; les archives historiques sont conservées sans conversion automatique et restent hors du Kanban.
3. Une organisation peut modifier l’ordre, les couleurs contrôlées et les libellés bilingues, mais pas les codes, le nombre d’étapes ou le graphe.
4. Le graphe normal autorise les déplacements adjacents, le retour adjacent, toute étape non terminale vers `lost`, et `proposal_sent` vers `won`.
5. Le passage à `lost` exige l’un des huit motifs définis ; `other` exige une note assainie de 1 à 500 caractères.
6. `won` et `lost` sont terminales ; seuls Administrateur et Gestionnaire peuvent les rouvrir avec un motif structuré.
7. `won` se rouvre vers `negotiation` ; `lost` revient à son étape source précédente ou à `qualifying` si l’historique manque.
8. Toute transition exige version courante et `Idempotency-Key` ; concurrence et divergence d’idempotence retournent `409` sans écriture partielle.
9. Prospect, historique métier et audit append-only sont écrits dans la même transaction PostgreSQL.
10. Les capacités sont `pipeline:read`, `pipeline:move`, `pipeline:history:read`, `pipeline:reopen` et `pipeline:configure` selon la matrice de rôles définie.
11. En V1, le responsable est un filtre de pilotage, pas une frontière d’autorisation à l’intérieur de l’organisation.
12. Le board charge au plus 25 cartes par colonne, pagine jusqu’à 50 par requête et ordonne priorité décroissante puis ancienneté d’étape.
13. Les filtres couvrent texte, étapes, responsable/non assigné, priorité, origine, étiquettes et mise à jour ; ils vivent dans l’URL sans stockage navigateur.
14. Les déplacements groupés, l’ordre manuel des cartes, les automatisations et la prochaine action restent hors de 3.2.
15. RLS, CSRF, réponses `no-store`, accessibilité clavier, audit minimisé, logs fermés et métriques à cardinalité bornée sont obligatoires.
16. 3.2 ne sera clôturé qu’après migration reconstruite, tests de concurrence/RLS, recette Kanban accessible et verrou qualité complet vert ; les réserves staging/Azure restent bloquantes avant préproduction.

## 18. Décision de sortie

Les seize décisions de la section 17 ont été validées par le responsable produit le 4 septembre 2026. Le périmètre,
les transitions, les rôles, les contrats de concurrence, l’historique, les filtres et les exigences de qualité sont
désormais stabilisés.

L’implémentation est réalisée : domaine et migration `20260904_0015`, ports et cas d’utilisation, API sécurisée,
interface Kanban, capacités, audit et tests ciblés. Avant clôture, la recette fonctionnelle PostgreSQL/RLS et le verrou
qualité complet doivent être exécutés sur l’environnement de validation.
