# Phase 4.4 — Quotas et rapports d’usage

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 4.4 — Quotas et rapports d’usage |
| Version | 0.2 — décisions produit validées |
| Statut | Décisions `P4.4-01` à `P4.4-08` et GO d’implémentation validés ; implémentation réalisée, verrou qualité complet à exécuter |
| Date | 24 septembre 2026 (UTC) |
| Contrat parent | [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md) |
| Prérequis | Tableau de bord 4.1, worker 4.2 et exports/imports 4.3 implémentés ; verrou qualité 4.3 VERT |

## 1. Résultat attendu et périmètre

Le lot 4.4 fournit des compteurs techniques explicables par utilisateur et organisation, applique les limites serveur
avant les appels Google coûteux et rend l’usage consultable sans exposer les requêtes ni les données retournées. Le
rapport distingue toujours :

1. une **réservation de quota**, qui protège un budget avant l’appel ;
2. une **tentative d’appel amont**, qui prouve que Marketteo a commencé une requête vers un fournisseur ;
3. son **résultat technique** connu (`succeeded`, `failed` ou `indeterminate`) ;
4. une **limite serveur**, qui protège la plateforme mais ne crée aucun droit commercial ;
5. une éventuelle consommation facturée, qui reste `unavailable` tant qu’aucune source officielle de facturation
   n’est intégrée et rapprochée.

La V1 couvre les opérations Google déjà présentes et les volumes de plateforme utiles à l’exploitation du produit :
recherches Text Search, autocomplétion et résolution de lieu, cartes statiques, exports CSV et imports CSV confirmés.
Les métriques Prometheus et les journaux structurés restent des outils d’exploitation sans identifiants utilisateur ;
ils ne deviennent pas la source des rapports métier. PostgreSQL porte l’historique durable et Redis conserve son rôle
de décision atomique en temps réel.

Sont hors périmètre : prix, devise de facturation, taxes, crédits, plans SaaS, dépassement payant, factures, paiement,
répartition comptable d’une session Google, estimation d’un coût à partir d’un simple nombre de requêtes et
modification libre des seuils depuis l’interface. Ces sujets relèvent de la phase 5 ou d’un contrat fournisseur
ultérieur. Le lot ne collecte aucun texte recherché, résultat Google, `place_id`, adresse, coordonnée, jeton, clé API,
adresse IP ou contenu de fichier.

## 2. État du socle et écarts à fermer

Le socle actuel protège Text Search par un script Lua Redis atomique. Les limites par défaut sont de 20 réservations
par utilisateur et 100 par organisation et par jour UTC, avec un avertissement à 80 %. Une clé d’opération évite le
double comptage d’un même appel interne et toutes les clés expirent à la prochaine minuit UTC. Ce mécanisme résiste
aux courses concurrentes, mais son expiration empêche tout historique durable.

L’autocomplétion et la résolution de lieu partagent actuellement un limiteur anti-abus de 30 opérations par minute et
200 par jour et par utilisateur. La carte statique est protégée par un jeton court, lié au tenant et consommable une
seule fois. Ces protections ne prouvent pas une facturation et ne fournissent pas de total organisationnel durable.

Prometheus compte globalement certains appels `places_text_search` et `maps_static`, sans utilisateur ni organisation.
Il est adapté à l’alerte technique, pas à une restitution tenant. `DASH-09` de 4.1 retourne donc actuellement
`unavailable`. Les colonnes ou paramètres historiques portant un nom de quota ne sont pas automatiquement des sources
de vérité : la politique active est celle résolue côté serveur et son `policy_code` doit accompagner toute mesure.

Le lot ferme ces écarts en ajoutant un registre fermé des usages, une écriture durable avant chaque appel amont, des
agrégats journaliers tenant-scopés, une API de consultation et une présentation explicite des limites.

## 3. Dictionnaire fermé des usages V1

### 3.1 Opérations Google

| Code | Événement compté | Unité et attribution | Limite V1 |
| --- | --- | --- | --- |
| `google.places_text_search.quota` | Réservation acceptée ou refusée avant Text Search. | `reservation`, utilisateur et organisation ayant initié la recherche. | 20/utilisateur/jour UTC et 100/organisation/jour UTC ; avertissement unique à 80 %. |
| `google.places_text_search.request` | Tentative effectivement engagée vers Google Text Search. | `upstream_request`, même attribution. | Protégée par la réservation précédente ; aucun appel si la limite ou le registre durable est indisponible. |
| `google.places_autocomplete.request` | Requête d’autocomplétion effectivement engagée. | `upstream_request`, utilisateur et organisation. | Protection anti-abus existante : 30 opérations/minute et 200/jour/utilisateur, partagée avec la résolution ; pas de seuil de coût organisationnel en V1. |
| `google.places_details.request` | Résolution du lieu sélectionné effectivement engagée. | `upstream_request`, utilisateur et organisation. | Même protection anti-abus et jeton de sélection à usage unique. |
| `google.maps_static.request` | Récupération d’une carte statique effectivement engagée. | `upstream_request`, utilisateur et organisation ayant créé le cliché. | Jeton court, tenant-scopé et consommable une fois ; pas de seuil numérique distinct en V1. |

Une réponse Google en erreur compte comme tentative amont et porte `failed`. Une réservation refusée ne crée aucune
tentative amont. Une panne après l’écriture `attempted` et avant l’écriture du résultat produit `indeterminate` ; elle
n’est jamais transformée en succès. Les nombres de requêtes sont des unités techniques. Les sessions Autocomplete et
les règles de prix du fournisseur ne sont pas reconstruites ou estimées.

### 3.2 Opérations de plateforme

| Code | Source de vérité | Mesures publiées |
| --- | --- | --- |
| `platform.csv_export` | Transitions de `export_requests` et `export_artifacts` de 4.3 | demandes, prêts, échecs, expirés, lignes produites, champs/lignes omis et octets publiés ; aucune donnée du CSV |
| `platform.csv_import` | Confirmation de `csv_import_sessions` et création de `csv_import_runs` | lots confirmés, lignes examinées, créées, dupliquées, à revoir et mises en quarantaine ; aucun en-tête, mapping ou contenu brut |

Ces familles sont enregistrées dans le même registre 4.4, dans la transaction qui valide la transition métier. Le
registre ne copie que les nombres minimisés ; les tables 4.3 restent l’autorité du détail. Cette capture préserve les
agrégats après la purge normale des travaux ou artefacts. Une reprise de transaction utilise l’identifiant de la
demande ou du run et le type d’événement pour ne pas doubler les compteurs. Les limites d’export de 4.3 (50 000 lignes,
50 Mio, cinq demandes actives, 250 Mio et 24 h) et celles de l’import 3.1 restent leurs contrats d’autorité. Le rapport
4.4 les expose avec leur unité et leur version sans les modifier. Les métriques internes de file 4.2, les invitations,
connexions et lectures CRM restent réservées à l’exploitation et ne figurent pas dans le rapport utilisateur V1.

## 4. Modèle de mesure et cohérence

### 4.1 Registre durable

Une migration additive crée :

- `usage_operation_events`, journal append-only des événements Google et des transitions imports/exports retenues ;
- `usage_daily_counters`, agrégats UTC par organisation, utilisateur optionnel, code d’usage, résultat et jour ;
- une fonction privée d’enregistrement idempotent qui insère l’événement et incrémente les deux agrégats dans la
  même transaction.

Un événement contient uniquement `organization_id`, `actor_user_id`, `actor_membership_id`, `operation_id`,
`usage_code`, `event_kind`, `outcome`, `occurred_at`, `unit_count`, `policy_code`, les seuils appliqués si pertinents,
`reset_at` et une version de schéma. Les événements autorisés sont `quota_reserved`, `quota_rejected`,
`upstream_attempted`, `upstream_succeeded`, `upstream_failed`, `export_requested`, `export_ready`, `export_failed`,
`export_expired` et `import_confirmed`. Des colonnes numériques optionnelles fermées portent `row_count`,
`created_count`, `duplicate_count`, `review_count`, `quarantined_count`, `omitted_count` et `byte_count` seulement
pour les événements compatibles. L’unicité
`(organization_id, operation_id, event_kind)` rend les reprises inoffensives. Les quantités sont non négatives et les
codes sont contraints par liste blanche.

Les tables activent et forcent la RLS. Le rôle Web peut insérer au moyen d’une fonction bornée et lire selon les
capacités ; il ne peut ni mettre à jour ni supprimer un événement. Le rôle worker ne reçoit aucun droit sauf si un
futur type de travail enregistré produit explicitement un usage. Un rôle de maintenance non connectable effectue la
purge bornée. Les agrégats utilisateur utilisent l’identité à l’instant de l’opération ; une désactivation ultérieure
ne réattribue pas l’historique.

### 4.2 Ordre d’exécution et panne partielle

Pour Text Search :

1. le serveur valide session, organisation et capacité, puis crée l’`operation_id` interne ;
2. Redis réserve atomiquement le quota utilisateur et organisation avec un `operation_id` stable ;
3. le résultat de réservation est écrit durablement ; si une réservation acceptée ne peut pas être persistée,
   l’appel Google n’est pas lancé et la réponse est `503` ; la réservation Redis peut rester consommée jusqu’au reset,
   ce qui est un surcomptage sûr et visible comme incident ;
4. `upstream_attempted` est écrit avant l’ouverture de la requête Google ;
5. le succès ou l’échec technique est ajouté après la réponse ;
6. une tentative sans résultat après le délai de réconciliation apparaît comme `indeterminate`.

Autocomplete, Details et Static Maps commencent à l’étape 4 après leurs protections propres. Une indisponibilité du
registre durable bloque l’appel coûteux avec `503 usage_tracking_unavailable`. Elle ne désactive jamais silencieusement
un quota. Un refus Redis reste `429` avec `Retry-After` et sa portée `user` ou `organization`.

### 4.3 Idempotence interne et requêtes utilisateur

Chaque exécution serveur reçoit un `operation_id` opaque, créé avant la réservation et réutilisé par les seules
reprises internes de cette exécution. Redis et PostgreSQL dédupliquent ce même identifiant. Une double soumission
concurrente du navigateur reste bloquée par le verrou de recherche existant ; elle ne produit pas deux appels.

Une nouvelle requête HTTP reçue après la fin de la première est une nouvelle opération et peut consommer une nouvelle
unité. La V1 n’impose pas de clé d’idempotence au navigateur, car rejouer une réponse exigerait de conserver les
résultats Google et les jetons éphémères au-delà de leur cycle actuel. L’interface désactive le bouton pendant l’appel
et explique qu’une reprise après réponse perdue peut compter comme une nouvelle recherche. Une éventuelle idempotence
HTTP fera l’objet d’un contrat séparé définissant un cache fournisseur admissible et la régénération des jetons.

## 5. Périodes, agrégats et conservation

Le jour de quota Google est toujours `[00:00:00Z, 00:00:00Z le lendemain)`. L’interface affiche « UTC » et l’instant
`reset_at`; elle ne traduit pas ce jour en journée civile de l’organisation. Les périodes de rapport utilisent des
dates UTC inclusives et sont converties en intervalle `[start_at, end_at_exclusive)`.

La V1 accepte `today`, `last_7_days`, `last_30_days` ou des dates explicites couvrant au plus 93 jours. Le groupement
est journalier ; aucun regroupement horaire, minute par minute ou intervalle arbitraire n’est exposé. Le serveur fixe
`as_of` et n’inclut aucun événement postérieur. Les totaux organisationnels et utilisateur sont calculés dans un même
cliché cohérent ; la somme des membres, y compris les anciens membres conservés dans la période, se rapproche du total
organisationnel.

Les événements détaillés sont conservés 90 jours. Les agrégats journaliers minimisés sont conservés 400 jours afin de
mesurer une saison complète et de préparer la décision de seuil sans constituer un registre de facturation. La purge
est quotidienne, idempotente et bornée ; elle ne supprime ni les audits métier ni les données d’import/export. Une
suspension légale portant sur des données CRM ne prolonge pas automatiquement ces métriques techniques. Toute demande
de conservation différente doit être contractualisée avant implémentation.

La collecte qualifiée commence à l’activation de la migration 4.4. Aucun total historique n’est reconstruit depuis les
journaux ou Prometheus. Les imports et exports antérieurs peuvent faire l’objet d’un backfill organisationnel depuis
leurs tables encore présentes, avec `completeness=partial` et `reason=legacy_period`; ils ne sont pas attribués à un
membre lorsque l’acteur exact de la transition n’est pas démontrable. Aucun zéro n’est inventé pour la période
antérieure au début de collecte.

## 6. Limites, avertissements et changement de politique

Les valeurs 20/100/80 % sont conservées comme garde-fous serveur initiaux déjà déployés. Elles ne représentent ni un
forfait client ni une mesure de coût. `policy_code=server_default_v1` identifie cette politique. Un changement exige :

- une mesure des réservations, tentatives et échecs sur une période représentative ;
- une nouvelle valeur de `policy_code` et une configuration déployée ;
- un test de concurrence prouvant l’absence de dépassement ;
- une note de décision datée dans le rapport d’implémentation ;
- aucune modification rétroactive des événements historiques.

La source V1 de ces valeurs est la configuration serveur
`GOOGLE_SEARCH_USER_DAILY_LIMIT`, `GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT`,
`GOOGLE_SEARCH_QUOTA_WARNING_PERCENT` et `GOOGLE_SEARCH_QUOTA_POLICY_CODE`. La colonne historique
`organizations.google_search_daily_limit`, actuellement ignorée par le résolveur de politique, est renommée
`google_search_daily_limit_legacy` et conservée sans effet pendant la phase 4. Elle n’est ni affichée ni interprétée
comme une dérogation par organisation. Sa suppression ou sa conversion en véritable surcharge exige une décision
ultérieure, un audit de ses valeurs et un contrat de priorité entre politique globale et surcharge.

À 80 %, un avertissement est créé une seule fois par utilisateur et une seule fois par organisation et par jour UTC.
Il est visible dans l’interface au prochain chargement, sans courriel ni notification externe. À 100 %, le prochain
appel Text Search est refusé avant Google. L’organisation et l’utilisateur ont des compteurs indépendants ; le premier
plafond atteint détermine la portée du refus. Un Admin ne contourne pas les plafonds. Une désactivation globale de la
politique équivaut à un refus fermé des nouvelles recherches, pas à une consommation illimitée.

Les protections 30/minute et 200/jour de la sélection de lieu restent des limites anti-abus techniques. Elles sont
affichées comme telles et ne sont pas additionnées au quota Text Search. Static Maps reste borné par le jeton à usage
unique et par la recherche qui l’a créé. Des plafonds organisationnels distincts pour ces opérations nécessitent une
mesure 4.4 et une décision ultérieure.

## 7. Contrôle d’accès

| Action | Commercial | Gestionnaire | Administrateur | Admin plateforme |
| --- | --- | --- | --- | --- |
| Voir son usage et son quota courant | `usage:read:self` | `usage:read:self` | `usage:read:self` | Seulement avec appartenance active |
| Voir le total de l’organisation et la ventilation par membre | Non | `usage:read:organization` | `usage:read:organization` | Seulement avec appartenance active et capacité |
| Filtrer un membre actif ou désactivé de l’organisation | Non | Oui | Oui | Selon appartenance |
| Voir les paramètres techniques de la politique active | Valeurs applicables à soi | Valeurs applicables à l’organisation | Valeurs applicables à l’organisation | Outil opérateur distinct |
| Modifier un seuil | Non | Non | Non | Déploiement de configuration seulement en V1 |

Les capacités validées sont ajoutées à la matrice centrale. `self` utilise l’utilisateur authentifié et son
appartenance active ; le client ne fournit aucun identifiant d’acteur. `organization` et `owner` exigent la capacité
organisationnelle. Un membre d’un autre tenant retourne `404` lorsqu’un identifiant est adressé et ne révèle ni total,
ni existence, ni période d’activité. La consultation organisationnelle est auditée par un événement minimisé
`usage_report_viewed` portant seulement portée, bornes, groupement et code de rapport. Les lectures personnelles ne
créent pas un événement d’audit à chaque rafraîchissement.

## 8. Contrat API

### 8.1 Rapport historique

`GET /api/usage/report?period=last_30_days&scope=self&group_by=day`

Paramètres fermés :

- `period=today|last_7_days|last_30_days|custom` ;
- `start_on` et `end_on` obligatoires seulement avec `custom` ;
- `scope=self|organization|owner` ;
- `owner_membership_id` obligatoire seulement avec `owner` ;
- `group_by=day`, seule valeur V1.

Réponse structurée indicative :

```json
{
  "period": {
    "start_on": "2026-09-01",
    "end_on": "2026-09-24",
    "timezone": "UTC",
    "start_at_utc": "2026-09-01T00:00:00Z",
    "end_at_utc_exclusive": "2026-09-25T00:00:00Z"
  },
  "as_of": "2026-09-24T15:00:00Z",
  "scope": {"kind": "self", "owner_membership_id": null},
  "completeness": {"status": "complete", "reason": null, "last_recorded_at": "2026-09-24T14:58:00Z"},
  "google": {
    "billing": {"status": "unavailable", "reason": "billing_source_not_integrated", "amount": null},
    "totals": [
      {"code": "google.places_text_search.quota", "unit": "reservation", "accepted": 8, "rejected": 1},
      {"code": "google.places_text_search.request", "unit": "upstream_request", "attempted": 8,
       "succeeded": 7, "failed": 1, "indeterminate": 0}
    ]
  },
  "platform": {
    "csv_export": {"requested": 2, "ready": 2, "failed": 0, "rows": 42, "bytes": 8192},
    "csv_import": {"confirmed_runs": 1, "examined_rows": 30, "created": 25,
                   "duplicates": 2, "review": 1, "quarantined": 2}
  },
  "series": [],
  "owner_breakdown": null
}
```

Les valeurs absentes sont `null` avec un statut, jamais zéro par défaut. `completeness=partial` est permis seulement
avec un motif fermé (`result_pending`, `legacy_period`, `aggregation_delayed`) et les bornes affectées. Une panne au
moment de la lecture répond `503`; elle ne retourne pas un rapport vide. Les réponses portent
`Cache-Control: no-store, max-age=0`.

### 8.2 Quota courant

`GET /api/usage/current`

La réponse donne, pour Text Search, `used`, `remaining`, `limit`, `warning_threshold_percent`, `reset_at`, `timezone`,
`unit`, `policy_code` et `source`. Le personnel reçoit ses valeurs et les valeurs organisationnelles nécessaires pour
comprendre un refus, sans ventilation des autres membres. Le Gestionnaire et l’Admin peuvent demander
`scope=organization`. Si Redis est indisponible mais que l’agrégat durable du jour est lisible, le compteur historique
est retourné avec `enforcement_status=unavailable`; il ne prétend pas refléter les toutes dernières réservations. Si
les deux sources sont indisponibles, tous les nombres sont `null`.

Cette source qualifie `DASH-09` de 4.1 : le tableau de bord peut afficher `available` avec l’unité
`reservation`, la période UTC, `policy_code` et `source=usage_quota_v1`. Il ne renomme jamais cette valeur « appels
facturés » ou « coût Google ».

### 8.3 Erreurs

Les codes propres au lot sont `usage_query_invalid`, `usage_scope_forbidden`, `usage_owner_not_found`,
`usage_tracking_unavailable` et `usage_report_unavailable`. Les refus de quota conservent
`google_quota_exceeded` avec `Retry-After`. Les erreurs ne contiennent ni compteur d’un autre tenant, ni texte de
recherche, ni réponse fournisseur.

## 9. Interface et accessibilité

La page « Usage » présente dans cet ordre : période UTC, quota courant Text Search, avertissement éventuel, totaux
Google, volumes d’exports/imports, série journalière et, pour Gestionnaire/Admin, ventilation par membre. Chaque carte
nomme son unité. Les limites anti-abus sont séparées des quotas quotidiens et une note fixe indique que le rapport
n’est pas une facture.

Un tableau textuel accompagne tout graphique. Les états `loading`, `empty`, `partial`, `unavailable` et `error` sont
distincts. « Aucun usage observé » n’est affiché que pour une période complète et qualifiée ; sinon l’interface dit
« données indisponibles » ou « données partielles ». Le changement de langue `fr-CA`/`en-CA` ne change ni période,
ni valeur, ni unité. Le focus, les titres, l’ordre de lecture, les contrastes et le zoom 200 % suivent les règles du
tableau de bord 4.1.

L’avertissement à 80 % indique la portée, le nombre restant et la remise à zéro UTC. Le blocage à 100 % est expliqué
sur la page de recherche et sur la page Usage. Aucune interface d’augmentation de quota ou d’achat n’est affichée.

## 10. Confidentialité, audit et exploitation

Les journaux d’usage ne contiennent que des identifiants internes, codes fermés, horodatages et nombres. Sont interdits
dans les tables, audits, métriques, journaux et réponses : requête de recherche, réponse Google, nom ou adresse d’un
établissement, `place_id`, coordonnées, URL de carte, jeton de session ou sélection, empreinte de requête,
identifiant de corrélation externe, clé API,
nom de fichier et contenu CSV.

Prometheus conserve des labels bornés (`api`, `outcome`, `policy_code`) sans organisation ni utilisateur. Il supervise
les erreurs d’écriture, écarts de réconciliation, refus, avertissements et latence, mais ne sert pas aux rapports. Une
alerte opérateur se déclenche sur : échec d’écriture avant appel, événements `attempted` sans résultat au-delà de
30 minutes, écart négatif ou dépassement d’un plafond, retard d’agrégation supérieur à 15 minutes et purge absente
depuis 48 heures. Les alertes portent codes et nombres, jamais de contenu métier.

Le rapprochement quotidien vérifie : réservations acceptées ≥ tentatives Text Search ; tentatives = succès + échecs +
indéterminés ; totaux utilisateur ≤ total organisation ; aucune consommation acceptée au-delà du plafond. Un écart
n’est pas corrigé silencieusement : il crée un diagnostic codifié et rend la période `partial` si l’exactitude du
rapport est affectée.

## 11. Validation et scénarios d’acceptation

| ID | Scénario | Résultat attendu |
| --- | --- | --- |
| `USG-01` | 20 recherches concurrentes du même utilisateur, puis une 21e | 20 réservations et au plus 20 appels Google ; la 21e répond `429`, compteur utilisateur à 20. |
| `USG-02` | Cinq utilisateurs atteignent ensemble 100 recherches, puis un sixième appelle | Total organisation à 100 ; appel suivant refusé avant Google, même si son compteur personnel est inférieur à 20. |
| `USG-03` | Même `operation_id` rejoué par la couche serveur, puis double clic concurrent et nouvelle requête après fin | Reprise interne sans double débit ; double clic bloqué ; nouvelle requête séquentielle comptée comme nouvelle opération. |
| `USG-04` | Redis accepte, puis PostgreSQL devient indisponible avant l’appel | Aucun appel Google ; `503 usage_tracking_unavailable`; aucune limite contournée. |
| `USG-05` | Arrêt du processus après `upstream_attempted` et avant le résultat | La tentative devient `indeterminate` après 30 minutes et la période est explicable, jamais comptée comme succès. |
| `USG-06` | Avertissement atteint simultanément par plusieurs requêtes | Un seul avertissement utilisateur et organisation par période ; le compteur exact reste borné. |
| `USG-07` | Requête à 23:59:59Z puis à 00:00:00Z, organisation en `America/Toronto` | Deux jours UTC distincts ; remise à zéro et libellé UTC affichés sans conversion trompeuse. |
| `USG-08` | Commercial A demande son rapport, celui de B et le total de l’organisation | Son rapport réussit ; les deux autres sont refusés sans révéler les valeurs de B. |
| `USG-09` | Gestionnaire filtre un membre désactivé de son organisation puis un UUID d’un autre tenant | Historique autorisé pour le premier ; `404` indistinct pour le second. |
| `USG-10` | Appel Google échoue en 429/5xx ou délai dépassé | Tentative comptée, résultat `failed`, statut fournisseur séparé du refus de quota Marketteo. |
| `USG-11` | Autocomplete, Details et Static Maps utilisés dans une même recherche | Trois codes séparés ; aucune estimation de session facturée ou de prix. |
| `USG-12` | Export de 42 lignes et import de 30 lignes avec doublons/quarantaine | Totaux issus des registres 4.3, sans contenu de ligne ni double comptage lors d’un rejeu idempotent. |
| `USG-13` | Redis indisponible lors de `/api/usage/current` | Historique durable marqué comme non temps réel ou valeurs `null`; aucune valeur obsolète présentée comme quota disponible. |
| `USG-14` | Événements âgés de 91 jours et agrégats âgés de 401 jours | Détails de 91 jours purgés, agrégats encore valides jusqu’à 400 jours puis purgés par lots bornés. |
| `USG-15` | Rapport en `fr-CA` puis `en-CA`, navigation clavier et zoom 200 % | Valeurs/unités identiques, libellés traduits, tableaux accessibles et aucun stockage navigateur persistant. |

Les tests utilisent Redis et PostgreSQL réels pour concurrence, idempotence, RLS, migration, agrégation et purge ; une
horloge contrôlée pour minuit UTC et les délais ; des faux fournisseurs pour prouver qu’un refus n’ouvre aucun appel ;
et des tests UI pour capacités, états et accessibilité. Le verrou qualité exécute la reconstruction Alembic, les tests
sans skip, Ruff, format, mypy, audit npm, ESLint, Vitest, build et contrôle de l’artefact. La recette fonctionnelle reste
regroupée au lot 4.6.

## 12. Décisions validées par le responsable produit

| ID | Décision validée | Motif ou conséquence |
| --- | --- | --- |
| `P4.4-01` | PostgreSQL devient la source durable des rapports ; Redis reste la source atomique de décision du quota courant et Prometheus reste réservé à l’exploitation. | Historique tenant fiable sans transformer une métrique globale en donnée métier. |
| `P4.4-02` | Le registre V1 couvre les cinq opérations Google et les volumes d’exports/imports définis en section 3 ; aucune donnée de requête ou résultat n’est conservée. | Périmètre fermé, explicable et minimisé. |
| `P4.4-03` | Conserver Text Search à 20/utilisateur/jour UTC, 100/organisation/jour UTC et avertissement à 80 % ; conserver les protections existantes de lieu et carte sans inventer un quota commercial. | Garde-fous déjà éprouvés, révision seulement après mesure réelle. |
| `P4.4-04` | Rapports journaliers UTC sur 93 jours maximum ; événements détaillés 90 jours et agrégats 400 jours. | Charge bornée et période suffisante pour décider les seuils futurs. |
| `P4.4-05` | Commercial : soi ; Gestionnaire/Admin : soi, organisation et membre ; aucun rôle métier ne modifie les seuils dans l’interface V1. | Alignement avec 4.1 et séparation entre visibilité et configuration serveur. |
| `P4.4-06` | `operation_id` interne idempotent, verrou contre la double soumission concurrente, enregistrement durable avant appel, blocage fermé si Redis ou le registre requis est indisponible et état `indeterminate` après 30 minutes. | Aucun dépassement concurrent ni succès inventé lors d’une panne partielle, sans conserver les résultats Google pour rejouer une réponse HTTP. |
| `P4.4-07` | `/api/usage/report` et `/api/usage/current` alimentent la page Usage ; `DASH-09` affiche des réservations qualifiées, jamais des appels facturés ou un coût estimé. | Une seule définition serveur et vocabulaire non trompeur. |
| `P4.4-08` | Rapports non facturants, audit minimisé des vues organisationnelles, RLS forcée, purge bornée, rapprochement et verrou avec Redis/PostgreSQL réels. | Confidentialité, isolation tenant et preuves techniques avant recette 4.6. |

Les huit décisions `P4.4-01` à `P4.4-08`, puis le GO d’implémentation 4.4, ont été validés explicitement par le
responsable produit le 24 septembre 2026. Les valeurs initiales restent des protections techniques ; leur approbation
ne crée aucun plan, crédit ou engagement commercial.
