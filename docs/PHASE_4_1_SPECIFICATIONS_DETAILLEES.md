# Phase 4.1 — Tableau de bord

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 4.1 — Tableau de bord |
| Version | 0.5 — résultat du verrou qualité technique 4.1 |
| Statut | Implémentation 4.1 réalisée ; verrou qualité technique VERT le 23 septembre 2026 ; recette fonctionnelle prévue en fin de phase 4 (lot 4.6) |
| Date | 23 septembre 2026 (UTC) |
| Contrat parent | [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md) |
| Socle existant | Pipeline 3.2, activités/tâches 3.3, opportunités 3.4, RLS et session organisation |

## 1. Résultat attendu et périmètre

Le tableau de bord permet de comprendre l’activité commerciale à partir des données CRM internes déjà autorisées :
répartition des prospects, tâches à traiter, activités réalisées, progression du pipeline et opportunités par devise.
Il n’ajoute aucune écriture métier. Les cartes et tableaux affichent un même calcul serveur, quelle que soit la langue
ou la taille d’écran. Le Commercial voit son périmètre personnel ; l’Administrateur et le Gestionnaire voient leur
organisation et peuvent filtrer par Commercial actif ou désactivé.

Les valeurs chiffrées de consommation Google par utilisateur/organisation figurent dans le périmètre global de la
phase 4. En 4.1, seul un compteur déjà fiable et consultable peut être affiché ; l’historique et les seuils de coût
requièrent le contrat 4.4. Une valeur absente est présentée comme indisponible, jamais comme zéro.
Le quota Redis existant réserve des recherches par jour UTC et expire à la remise à zéro : il ne prouve ni un historique
d'usage ni un nombre d'appels réellement effectués ou facturés. `DASH-09` reste indisponible tant qu'une source de
lecture autorisée ne documente pas explicitement son unité, sa période, son fuseau, son attribution et sa fiabilité.

## 2. Dictionnaire des indicateurs

Toutes les valeurs sont calculées côté serveur dans l’organisation active. `P` désigne l’intervalle de dates civiles
choisi dans son fuseau IANA ; `as_of` désigne l’instant UTC du cliché de lecture cohérent. Les bornes de période sont
inclusives dans l’interface et traduites en intervalle d’instants `[début inclus, lendemain de fin exclu)` pour les
événements. Aucun événement postérieur à `as_of` ne contribue au résultat.

| ID | Indicateur | Population, calcul et source |
| --- | --- | --- |
| `DASH-01` | Prospects actifs par étape | Nombre de prospects non archivés, groupés par `stage_code` courant, y compris les étapes terminales ; source `prospects`. C’est une photographie à `as_of`, sans filtre de période historique. |
| `DASH-02` | Tâches dues aujourd’hui | Tâches `open` dont `due_at` tombe dans le jour courant de l’organisation ; source `prospect_tasks`. Une tâche sans responsable explicite reste visible seulement dans le périmètre collectif autorisé. |
| `DASH-03` | Tâches en retard | Tâches `open` avec `due_at < début du jour courant` dans le fuseau de l’organisation ; exclut `completed` et `cancelled`. Le nombre d’échéances déjà passées aujourd’hui peut être présenté séparément, sans les confondre avec les jours antérieurs. |
| `DASH-04` | Activités par période | Nombre d’activités métier actives par type `call`, `meeting`, `email`, `note`, selon le `occurred_at` de leur version active dans `P`. Les versions corrigées ne sont pas comptées une deuxième fois ; voir la règle ci-dessous. Le texte des notes n’est pas copié. |
| `DASH-05` | Passage entre étapes | Pour les seules paires de progression définies en section 3, compter la première sortie de la première entrée dans l’étape pendant `P` ; sources append-only `prospect_stage_transitions` et création des prospects pour l’entrée initiale en `new`. Les sorties vers `lost` sont séparées. |
| `DASH-06` | Opportunités par issue | Nombre courant d’opportunités `open` (quatre étapes ouvertes), `won` et `lost`. Les issues historiques par période sont un indicateur distinct et utilisent `closed_at` ou les événements, afin de ne pas mélanger stock et flux. |
| `DASH-07` | Montant et valeur pondérée | Somme des opportunités ouvertes du périmètre, groupée par `currency_code`, en `NUMERIC` décimal. Valeur pondérée = somme des calculs serveur par opportunité, arrondis conformément au contrat 3.4. Aucune ligne combinant deux devises. |
| `DASH-08` | Ventilation par Commercial | Les mêmes mesures, groupées selon la table d’attribution de la section 5 ; la source de responsabilité est nommée dans chaque réponse. Réservée à la lecture organisationnelle autorisée. |
| `DASH-09` | Usage Google | Compteur technique seulement si sa source, sa période, son fuseau, son unité et son attribution sont qualifiés. Une réservation de quota n’est pas présentée comme un appel facturé. Sinon, statut `unavailable` sans valeur numérique. Aucune donnée d’établissement Google n’est exposée ; historique et seuils relèvent de 4.4. |

Une carte indique si sa mesure est une **photographie** (`DASH-01`, `02`, `03`, `06`, `07`) ou un **flux de période**
(`DASH-04`, `05`). Les dates de filtre ne changent pas silencieusement une photographie en historique. Les
opportunités perdues ne diminuent pas le montant brut des opportunités ouvertes : elles n’en font simplement pas partie.

Pour `DASH-04`, les activités et leurs corrections forment une chaîne par `correction_of_activity_id`. Une chaîne
contribue au plus une fois : sa dernière version créée au plus tard à `as_of` est la version active. Si plusieurs
corrections concurrentes existent, l’ordre `created_at`, puis `id` départage les versions de façon déterministe.
Le type et la date de cette version active déterminent sa période et sa ventilation par type. L’auteur de l’activité
initiale reste l’attributaire commercial, même si un autre membre effectue la correction ; l’originale et les versions
intermédiaires restent dans la chronologie, sans augmenter l’indicateur. Une correction ultérieure peut donc rectifier
un chiffre historique ; la réponse affiche `as_of` pour permettre ce rapprochement.

## 3. Cohorte du passage entre étapes

La V1 mesure uniquement les sorties de progression `new → qualifying`, `qualifying → qualified`,
`qualified → contacted`, `contacted → opportunity`, `opportunity → proposal_sent`,
`proposal_sent → negotiation`, `proposal_sent → won` et `negotiation → won`. Le raccourci direct
`proposal_sent → won` a sa propre ligne et le même dénominateur que `proposal_sent → negotiation` ;
ces deux taux ne sont pas additionnés. Les retours vers une étape antérieure et les sorties vers `lost`
ne sont pas des progressions. `won` et `lost` ne créent pas de cohorte de départ.

Pour une étape de départ `A`, la cohorte `C(A,P)` contient chaque prospect distinct dont **la première entrée dans A
pendant P** survient entre le début de `P` et l’instant d’observation. La création d’un prospect en `new` est une
entrée, même sans transition enregistrée ; un retour ou une réouverture vers `new` est une entrée horodatée par la
transition. Un prospect déjà dans `A` au début de `P` n’entre pas dans la cohorte, sauf s’il quitte puis rejoint `A`
pendant `P`. Une seule première entrée par prospect et par étape est retenue dans `P`.

L’instant d’observation vaut `min(as_of, fin exclusive de P)` et est retourné comme `observed_until` en UTC. Pour
chaque membre, **sa première sortie de cette entrée dans A**, si elle survient avant cet instant, fixe l’issue :
progression directe vers `B`, perte directe vers `lost`, ou autre sortie. Une progression après un retour ultérieur
dans `A` n’est pas attribuée une seconde fois à cette cohorte. Le numérateur `advanced` d’une paire `A → B` est le
nombre de membres dont cette première sortie est `A → B`. Le taux est `advanced / cohort × 100`, avec numérateur
et dénominateur affichés ; `cohort = 0` produit `rate_percent = null` et « Données insuffisantes ».
Les premières sorties `A → lost` sont comptées séparément dans `stage_losses`, sans entrer dans `advanced`.

La fenêtre d’observation d’une cohorte se termine à la fin de `P`, même si certains prospects restent dans `A` :
une progression postérieure n’en modifie pas le taux. L’interface nomme cette mesure « passage direct dans la
période » et indique « observée jusqu’au [date et heure locales] » tant que `P` n’est pas terminée. Le champ
`window_complete` signifie seulement que la fenêtre est terminée, pas que tous les prospects ont quitté `A`.

## 4. Périodes, fuseau et précision

La proposition validée `P4-02` offre jour, semaine et mois. Le calendrier suit la locale pour l’affichage, mais le
fuseau d’interprétation est celui de l’organisation active. La semaine est lundi–dimanche ; une date passée ou une
plage explicite ne doit pas être automatiquement remplacée par la période courante. L’API échange des dates ISO
`YYYY-MM-DD` et retourne le fuseau utilisé, les bornes UTC calculées et `as_of`. Les événements à la borne de début
sont inclus, ceux au lendemain de la fin sont exclus. Les changements d’heure d’été/hiver sont couverts par test.
Les dates futures peuvent faire partie du jour, de la semaine ou du mois courant, mais un `start_on` postérieur à la
date locale courante est refusé. Les événements de flux sont coupés à `as_of` ; une période en cours ne donne jamais
un taux calculé avec des événements futurs. Les photographies restent celles de `as_of` et affichent leur propre date
de référence, indépendamment de la période choisie.

Les montants sont transmis sous chaînes décimales avec le code de devise, comme en 3.4. Le formatage localisé est
limité à l’interface. Un montant inconnu n’est jamais additionné ou converti dans une autre devise.

## 5. Autorisations et isolation

| Rôle | Lecture personnelle | Lecture équipe/organisation | Choix d’un autre responsable |
| --- | --- | --- | --- |
| Commercial actif | Oui, pour son périmètre autorisé | Non | Non |
| Gestionnaire actif | Oui | Oui, dans son organisation | Oui, membre de son organisation |
| Administrateur actif | Oui | Oui, dans son organisation | Oui, membre de son organisation |

Le serveur distingue `dashboard:read:self` et `dashboard:read:organization`. Les trois rôles actifs disposent de la
première capacité ; seuls Gestionnaire et Administrateur actifs disposent de la seconde. Le filtre d’un autre membre
et la ventilation `DASH-08` exigent `dashboard:read:organization`. Le tableau de bord applique la matrice suivante,
qui peut être plus restrictive que la lecture collective des listes de pipeline, d’activités et de tâches existantes :

| Indicateur | Ligne retenue pour `self` ou un membre filtré | Attribution pour `DASH-08` |
| --- | --- | --- |
| `DASH-01`, `DASH-05` | `prospects.owner_id` égal à l’appartenance visée, évalué à `as_of` ; exclure les non assignés | Responsable **courant** du prospect ; `null` pour non assigné |
| `DASH-02`, `DASH-03` | `prospect_tasks.assigned_membership_id` égal à l’appartenance visée | Responsable **courant** de la tâche ; `null` pour non assignée |
| `DASH-04` | `prospect_activities.actor_id` de l’activité initiale égal à l’utilisateur de l’appartenance visée | Auteur initial de la chaîne, relié à son appartenance dans l’organisation ; `null` si cette attribution est impossible |
| `DASH-06`, `DASH-07` | `opportunities.owner_membership_id` égal à l’appartenance visée | Responsable **courant** de l’opportunité |
| `DASH-09` | Compteur qualifié attribué au `user_id` de l’appartenance visée | Utilisateur relié à son appartenance, seulement si la source est qualifiée |

La vue organisationnelle inclut les éléments sans responsable dans une ligne `owner_membership_id: null` ; ils ne sont
attribués à aucun Commercial. Un Gestionnaire ou Administrateur peut filtrer une appartenance désactivée de sa propre
organisation pour expliquer ses données historiques et ses tâches encore ouvertes. Une appartenance désactivée ne peut
plus demander sa vue personnelle. Les activités sont attribuées à leur auteur initial, même si le prospect a un autre
responsable. Pour les transitions historiques, le responsable courant du prospect est utilisé faute d’instantané de
responsabilité sur chaque événement : une réaffectation peut donc modifier une ventilation historique. Le tableau de
bord doit l’indiquer et ne pas présenter `DASH-08` comme une performance historique figée.

La permission de lecture du tableau de bord est contrôlée côté serveur pour chaque sous-requête, en plus de RLS.
Une requête Commercial qui envoie un identifiant tiers ou demande la portée organisationnelle est refusée sans
divulguer ses mesures. Le contexte d’organisation vient de la session, jamais d’un paramètre libre. Chaque réponse
utilise un cliché de lecture cohérent pour éviter que ses cartes reflètent des mutations à des instants différents.
Une appartenance désactivée perd l’accès après le contrôle de session courant. Aucune réponse du tableau de bord
n’est mise en cache dans le navigateur.

## 6. Contrat API proposé

La lecture agrégée proposée est `GET /api/dashboard/summary`. La requête fournit **soit** un preset
`period=day|week|month` (période locale courante), **soit** les deux dates explicites `start_on` et `end_on`
(`YYYY-MM-DD`) ; elle ne mélange pas ces formes. Une date explicite passée reste choisie. Un paramètre manquant,
une combinaison contradictoire, `end_on < start_on` ou `start_on` dans le futur local répond `422` avec le champ en
cause. La plage explicite est limitée à **93 jours civils inclusifs** ; le serveur répond `422` sur `end_on` au-delà
de ce plafond. Les presets ne dépassent pas un mois. La réponse contient un point par étape, type, issue ou devise,
sans série temporelle quotidienne. Le rafraîchissement est manuel par « Actualiser » ; le chargement initial et un
changement de filtres appliqués déclenchent une lecture. Ces bornes pourront être révisées après profilage.

La portée demandée est `scope=self|organization|owner`. `self` cible l’appartenance courante ; `organization` couvre
toute l’organisation ; `owner` exige `owner_membership_id` et cible cette appartenance, active ou désactivée, dans
l’organisation courante. Un filtre `owner_membership_id` avec une autre portée répond `422`. `organization` et
`owner` exigent `dashboard:read:organization` ; `self` exige `dashboard:read:self`. Une portée non autorisée est
refusée sans résultat. Le client fournit explicitement `scope` pour éviter toute portée implicite différente selon
le rôle. Un identifiant d’une autre organisation ne révèle pas son existence.

Réponse structurée attendue :

```json
{
  "period": {
    "start_on": "2026-09-01", "end_on": "2026-09-30", "timezone": "America/Toronto",
    "start_at_utc": "2026-09-01T04:00:00Z",
    "end_at_utc_exclusive": "2026-10-01T04:00:00Z"
  },
  "as_of": "2026-09-23T02:00:00Z",
  "scope": {"kind": "self", "owner_membership_id": "11111111-1111-4111-8111-111111111111"},
  "attribution": {
    "prospects_by_stage": "prospects.owner_id",
    "tasks": "prospect_tasks.assigned_membership_id",
    "activities_by_type": "prospect_activities.actor_id (initiale)",
    "stage_passage": "prospects.owner_id_current",
    "stage_losses": "prospects.owner_id_current",
    "opportunities": "opportunities.owner_membership_id",
    "pipeline_by_currency": "opportunities.owner_membership_id",
    "google_usage": "unavailable"
  },
  "prospects_by_stage": [{"stage_code": "new", "count": 3}],
  "tasks": {"due_today": 2, "overdue": 1},
  "activities_by_type": [{"type": "call", "count": 4}],
  "stage_passage": [{
    "from_stage": "new", "to_stage": "qualifying", "cohort": 5, "advanced": 2,
    "rate_percent": "40.00", "observed_until": "2026-09-23T02:00:00Z", "window_complete": false
  }],
  "stage_losses": [{"from_stage": "new", "cohort": 5, "lost": 1}],
  "opportunities": {"open": 2, "won": 1, "lost": 0},
  "pipeline_by_currency": [{"currency_code": "CAD", "amount": "1250.5000", "weighted_amount": "625.2500"}],
  "owner_breakdown": null,
  "google_usage": {"status": "unavailable", "reason": "source_not_qualified", "used": null,
                   "unit": null, "start_at_utc": null, "end_at_utc_exclusive": null,
                   "timezone": null, "source": null}
}
```

Cet exemple illustre la forme, pas une donnée de production. `DASH-08` est `null` hors portée `organization` ; pour
la portée organisationnelle, `owner_breakdown` est une liste de lignes portant `owner_membership_id` (UUID ou `null`)
et les champs `prospects_by_stage`, `tasks`, `activities_by_type`, `stage_passage`, `stage_losses`, `opportunities` et
`pipeline_by_currency`, sans ventilation imbriquée. Le compteur Google par membre y figure seulement si sa source
est qualifiée. Les sommes des lignes, y compris la ligne non assignée, se rapprochent des totaux organisationnels.
Le champ `attribution` nomme la source
pour chaque famille de mesure, même lorsque la ventilation n’est pas autorisée. `DASH-09` est toujours présent :
`unavailable` conserve `used: null` ; `available` exige `used`, `unit`, les bornes UTC, `timezone` et `source`, pour
la portée demandée. Une période de quota UTC ne doit pas être présentée comme une période métier locale.

L’API peut séparer les lectures lorsque les profils de charge le justifient, mais une même mesure conserve exactement
la définition et le contrôle d’accès ci-dessus. Les réponses utilisent `Cache-Control: no-store, max-age=0`. Le
`request_id` reste disponible sur les erreurs ; aucune valeur personnelle ou contenu Google n’est écrit dans les
journaux de calcul.

## 7. Interface et accessibilité

La page du tableau de bord affiche successivement le périmètre et la période, les indicateurs principaux, la
répartition du pipeline, les tâches à traiter, puis les activités et la progression. Un tableau textuel accompagne
chaque visualisation éventuelle ; le montant porte toujours sa devise. Une carte est un lien vers une liste CRM
filtrée seulement si le filtre cible a exactement la même portée. Les liens ne donnent pas accès à des éléments
interdits par les règles de la liste destination.

Les états chargement, erreur, période vide, compteur indisponible et absence de permission sont distincts. Le
changement de locale met à jour intitulés, dates et nombres sans changer la période métier ; le changement
d’organisation relance les lectures avec le nouveau contexte et efface immédiatement l’ancien affichage. Le parcours
`Tab` suit l’ordre visuel, les valeurs ont des libellés lisibles par lecteur d’écran et restent utilisables à 200 %.

## 8. Scénarios de recette chiffrés

Ces scénarios préparent la recette fonctionnelle de fin de phase 4 (lot 4.6). Les tests automatiques de l’incrément
4.1 relèvent de son verrou qualité ; ils ne constituent pas à eux seuls le verdict de recette fonctionnelle.

| ID | Jeu et action | Résultat attendu |
| --- | --- | --- |
| `DASH-01-A` | Organisation A : 3 prospects `new`, 2 `qualifying`, 1 archivé ; organisation B : 4 `new` | A affiche `new=3`, `qualifying=2` ; B n’apparaît pas et l’archivé est exclu |
| `DASH-02-A` | Dans A, 2 tâches ouvertes dues aujourd’hui, 1 ouverte hier, 1 terminée hier, 1 annulée aujourd’hui | `due_today=2`, `overdue=1` ; terminée et annulée exclues |
| `DASH-04-A` | Dans `P`, 2 appels, 1 rendez-vous et 1 note ; 1 appel juste avant la borne de début | `call=2`, `meeting=1`, `note=1` ; l’appel hors période est exclu |
| `DASH-05-A` | 5 prospects entrent en `new` dans `P`, 2 sortent d’abord vers `qualifying`, 1 sort d’abord vers `lost`, 2 restent ; un sixième était déjà `new` avant `P` | Cohorte 5, avancés 2, pertes 1, taux `40.00 %` ; le sixième n’entre pas dans la cohorte |
| `DASH-05-B` | Un prospect entre en `qualifying` dans `P`, retourne en `new`, puis rejoint `qualifying` et avance vers `qualified` ; un autre entre en `new` le dernier jour de `P` et avance seulement le lendemain | La première sortie du premier est un retour : `advanced=0` pour sa cohorte `qualifying` ; l’avancée du second ne modifie pas le taux de `P` |
| `DASH-04-B` | A déclare un appel dans `P` ; B le corrige en réunion hors de `P`, puis en appel dans `P` | Une seule activité active est comptée en `call` dans `P`, attribuée à A ; les corrections de B ne créent ni doublon ni transfert de performance |
| `DASH-07-A` | Deux affaires ouvertes : `1 000 CAD` à 50 % et `2 000 USD` à 25 % ; une affaire CAD perdue | Lignes distinctes `1 000/500 CAD` et `2 000/500 USD` ; la perdue ne contribue pas aux montants ouverts |
| `DASH-SEC-A` | Commercial A demande le filtre de Commercial B, puis une autre organisation | Refus sans données ni agrégat de B ; la version organisationnelle est accessible seulement à Admin/Gestionnaire |
| `DASH-SCOPE-B` | Prospect de A et tâche assignée à B, activité rédigée par B sur ce prospect, opportunité de A, plus un prospect et une tâche non assignés ; B est ensuite désactivé | La vue personnelle de A compte son prospect et son opportunité, pas la tâche ou l’activité de B ; la vue organisationnelle garde tous les éléments et une ligne non assignée ; Admin peut filtrer B désactivé |
| `DASH-OWNER-HIST` | Un prospect avance dans `P` puis passe du responsable A au responsable B après `P` | Le total organisationnel de `DASH-05` reste identique ; la ventilation courante attribue la cohorte à B et affiche l’avertissement sur les réaffectations |
| `DASH-API-A` | Requête avec `period=month` et dates explicites, puis `scope=owner` sans `owner_membership_id`, puis une période en cours | Les deux premières répondent `422` sur le champ fautif ; la dernière retourne les bornes UTC, `as_of` et `observed_until <= as_of` |
| `DASH-09-A` | Seules les réservations de quota Redis du jour UTC sont disponibles | `google_usage.status=unavailable`, `used=null` ; aucun total d’appels facturés n’est inféré |
| `DASH-TZ-A` | Une activité juste avant et une juste après minuit local lors d’un changement d’heure | Chaque activité appartient à une seule journée selon `America/Toronto` ; aucune duplication ou omission |
| `DASH-I18N-A` | Même session en `fr-CA`, puis `en-CA`, clavier et zoom 200 % | Valeurs identiques, libellés et formatages localisés, ordre de focus et lecteur d’écran conformes |

Les tests automatiques emploient PostgreSQL réel pour RLS et agrégats sensibles, des tests de calcul pur pour dates et
décimaux et des tests UI pour langue, focus et états. Un test de navigateur vérifie qu’aucune réponse de tableau de
bord ou contenu Google n’est conservé dans les stockages persistants.

## 9. Décision produit et conditions du GO 4.1

Le responsable produit a approuvé les choix de conception de ce contrat, puis donné le GO d’implémentation le
23 septembre 2026. Les règles validées sont les suivantes :

| ID | Décision validée |
| --- | --- |
| `P4.1-01` | Portées `self`, `organization` et `owner`, capacités distinctes et attribution par indicateur selon la section 5 ; les ventilations historiques suivent le responsable courant lorsque l’événement ne porte pas d’instantané. |
| `P4.1-02` | Activités corrigées comptées une seule fois d’après leur version active, avec attribution à l’auteur initial. |
| `P4.1-03` | Passage direct dans la période : première entrée, première sortie, paires de progression et pertes séparées selon la section 3. |
| `P4.1-04` | Périodes en dates civiles du fuseau de l’organisation, coupure à `as_of`, photographies distinctes des flux et montants séparés par devise. |
| `P4.1-05` | Formes de requête exclusives, portée explicite, bornes UTC et états de disponibilité définis dans le contrat API de la section 6. |
| `P4.1-06` | `DASH-09` affiche `unavailable` jusqu’à qualification d’une source d’usage ; les réservations Redis ne sont pas assimilées à des appels facturés. |

Le GO d’implémentation 4.1 a été donné le 23 septembre 2026. Les choix d’exécution sont les suivants :

1. limiter la plage à 93 jours, sans série temporelle détaillée, et utiliser un rafraîchissement manuel ;
2. conserver l’endpoint unique et les agrégats serveur dans un cliché de lecture `REPEATABLE READ READ ONLY` ;
3. ajouter `dashboard:read:self` et `dashboard:read:organization` à la matrice d’identité et afficher la
   responsabilité courante dans les deux langues.

La qualification d’une source Google reste optionnelle pour le GO 4.1 : sans source admissible, `DASH-09` demeure
`unavailable` et sa mesure chiffrée relève du lot 4.4. Le verrou qualité local exécuté par le responsable produit le
23 septembre 2026 est **VERT** : migrations PostgreSQL reconstruites jusqu’à `20260922_0021`, contrôle Alembic sans
nouvelle opération, Ruff et format, mypy, 313 tests backend et 193 tests frontend réussis sans skip, audit npm sans
vulnérabilité, ESLint, build Vite et contrôles des sources navigateur et de l’artefact conformes. La sortie finale du
script conserve le libellé historique « 3.4 », mais le passage inclut les tests backend et frontend du tableau de
bord 4.1. La recette fonctionnelle reste regroupée en fin de phase 4, au lot 4.6 ; son verdict reste ouvert.
