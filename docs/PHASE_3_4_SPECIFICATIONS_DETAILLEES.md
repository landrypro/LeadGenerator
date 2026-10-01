# Phase 3.4 — Opportunités

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3 — Cœur CRM |
| Incrément | 3.4 — Opportunités |
| Version | 1.8 — contrats 3.4-C détaillés |
| Prérequis | 3.2 et 3.3 clôturés avec réserves ; tête Alembic `20260910_0020` ; verrou local 3.4-A vert |
| Statut | Phase 3.4 clôturée avec réserves transférées à la recette finale de la phase 4 ; GO produit du 23 septembre 2026 (UTC) |
| Date | 10 septembre 2026 |
| Résultat visé | Opportunités internes avec montant, devise, probabilité, échéance, responsable, issue et lien explicite avec le pipeline |

## 1. Objectif

L’incrément 3.4 permet de suivre les affaires commerciales portées par un prospect sans transformer Marketteo en outil
de facturation. Une opportunité représente une estimation interne : elle possède son propre cycle de vente, un montant,
une devise, une probabilité, une date de conclusion prévue et un responsable.

Un même prospect peut porter plusieurs opportunités. Le pipeline du prospect décrit la relation commerciale globale,
tandis que l’étape d’une opportunité décrit une affaire précise. Leur rapprochement est visible et contrôlé, mais aucune
modification d’opportunité ne déplace silencieusement le prospect dans le Kanban.

## 2. Périmètre

### 2.1 Inclus

- création de plusieurs opportunités CRM pour un prospect actif ;
- nom interne, montant estimé, devise ISO 4217, probabilité, date de conclusion prévue et responsable ;
- six étapes d’opportunité : découverte, qualification, proposition, négociation, gagnée et perdue ;
- transitions contrôlées, issue gagnée/perdue, motifs de perte et réouverture ;
- calcul serveur de la valeur pondérée sans stockage redondant ;
- version optimiste, idempotence et historique métier append-only ;
- section Opportunités sur la fiche prospect et vue portefeuille filtrable ;
- synthèse par devise sur la fiche, la liste et le Kanban ;
- intégration des événements d’opportunité dans la chronologie commerciale 3.3 ;
- action explicite d’alignement avec le pipeline 3.2 ;
- RLS, capacités, audit minimisé, métriques, journaux structurés et écrans bilingues.

### 2.2 Hors périmètre

- devis, factures, taxes, paiements, produits, lignes de commande et comptabilité ;
- conversion monétaire, taux de change et agrégation de devises différentes ;
- prévisions avancées, objectifs, commissions ou tableaux de bord analytiques ;
- automatisations selon le montant, la date, l’étape ou la probabilité ;
- synchronisation avec un ERP, une plateforme de paiement ou un calendrier externe ;
- création d’une table ou d’une fiche client distincte ;
- import ou export d’opportunités dans 3.4 ;
- déplacement automatique du prospect dans le Kanban ;
- génération d’une opportunité depuis Google, un import CSV, une activité ou une tâche.

## 3. Vocabulaire et séparation des états

- **Prospect** : établissement CRM suivi dans le pipeline global à neuf étapes.
- **Opportunité** : affaire commerciale interne et facultative liée à un prospect.
- **Étape d’opportunité** : avancement propre à une affaire parmi six codes système.
- **Issue** : état terminal `won` ou `lost` d’une opportunité.
- **Valeur pondérée** : montant multiplié par la probabilité, calculé à la lecture.
- **Alignement pipeline** : action utilisateur distincte qui demande une transition 3.2 compatible.
- **Conversion logique** : présence d’au moins une opportunité gagnée ; aucune copie vers une nouvelle table client.

L’étape `opportunity` du Kanban ne constitue pas une opportunité et ne crée aucun enregistrement. Réciproquement, créer
une opportunité ne modifie pas `prospects.stage_code`. Cette séparation évite qu’une affaire perdue masque une autre
affaire encore ouverte pour le même prospect.

## 4. Données commerciales

### 4.1 Nom et montant

Le nom interne est obligatoire, normalisé comme les autres textes courts du CRM et limité à 160 caractères. Il ne doit
pas être prérempli avec un nom Google affiché en direct.

Le montant estimé est obligatoire, strictement positif et stocké en `NUMERIC(19,4)`. Les API échangent le montant sous
forme de chaîne décimale canonique afin d’éviter toute conversion binaire flottante. Les séparateurs localisés sont une
responsabilité d’affichage ; le JSON utilise toujours le point décimal.

La devise est un code ISO 4217 de trois lettres majuscules validé côté serveur par une liste contrôlée. `CAD` est la
valeur initiale proposée. Modifier la devise exige de confirmer simultanément le montant correspondant ; Marketteo ne
convertit jamais automatiquement une valeur.

### 4.2 Probabilité et valeur pondérée

La probabilité est un entier de 0 à 100. Pour une étape ouverte, l’utilisateur peut la modifier explicitement. Les
valeurs initiales proposées par l’interface sont : découverte 10, qualification 25, proposition 50 et négociation 75.
Elles sont des valeurs de saisie et non des automatismes persistants liés aux changements d’étape.

Une opportunité gagnée impose 100 et une opportunité perdue impose 0. La valeur pondérée est calculée côté serveur avec
une arithmétique décimale : `montant × probabilité / 100`. Elle est arrondie à quatre décimales et n’est pas stockée.

### 4.3 Échéance

`expected_close_on` est une date civile obligatoire, sans heure. Elle est interprétée selon le calendrier de
l’organisation et évite les heures locales ambiguës. À la création, elle ne peut pas précéder la date courante de
l’organisation. Une opportunité ouverte dont l’échéance est dépassée devient « En retard », sans transition ni rappel
automatique.

Une date dépassée peut être conservée lors d’une mise à jour d’un autre champ afin de ne pas bloquer la correction d’un
dossier ancien. La modification explicite de l’échéance d’une opportunité ouverte doit toutefois choisir la date du jour
ou une date future.

### 4.4 Responsable

Le responsable est une appartenance active de l’organisation. Un Administrateur ou un Gestionnaire peut choisir tout
membre actif. Un Commercial crée une opportunité pour lui-même et ne peut pas changer son responsable.

La désactivation ultérieure du responsable ne réaffecte rien. L’opportunité reste lisible, indique « Responsable
désactivé » et doit être réassignée par un Administrateur ou un Gestionnaire avant toute modification métier, sauf sa
consultation.

## 5. Cycle de vie

### 5.1 Étapes système

| Code | Libellé `fr-CA` | Libellé `en-CA` | Probabilité proposée | État |
| --- | --- | --- | ---: | --- |
| `discovery` | Découverte | Discovery | 10 | Ouvert |
| `qualification` | Qualification | Qualification | 25 | Ouvert |
| `proposal` | Proposition | Proposal | 50 | Ouvert |
| `negotiation` | Négociation | Negotiation | 75 | Ouvert |
| `won` | Gagnée | Won | 100 | Terminal |
| `lost` | Perdue | Lost | 0 | Terminal |

Les codes, l’ordre et les libellés sont fixes en 3.4. La personnalisation du catalogue d’étapes reste hors périmètre.

### 5.2 Graphe de transition

Le parcours normal autorise l’avance ou le retour d’une étape entre `discovery`, `qualification`, `proposal` et
`negotiation`. `proposal` et `negotiation` peuvent passer à `won`. Toute étape ouverte peut passer à `lost`.

Les sauts entre étapes ouvertes, le passage direct de découverte à gagnée et une transition depuis un état terminal
sont refusés par la route normale avec une erreur stable, sans écriture partielle.

### 5.3 Perte et réouverture

Le passage à `lost` exige l’un des motifs suivants :

| Code | `fr-CA` | `en-CA` |
| --- | --- | --- |
| `no_need` | Aucun besoin confirmé | No confirmed need |
| `no_budget` | Budget insuffisant | Insufficient budget |
| `no_response` | Absence de réponse | No response |
| `competitor` | Concurrent retenu | Competitor selected |
| `timing` | Échéancier incompatible | Timing mismatch |
| `scope_mismatch` | Offre hors périmètre | Scope mismatch |
| `invalid_or_duplicate` | Affaire invalide ou en double | Invalid or duplicate opportunity |
| `other` | Autre | Other |

`other` exige une note de 1 à 500 caractères, rendue comme texte. Les autres motifs acceptent une note facultative dans
la même limite. Une opportunité gagnée ne demande aucun motif libre.

Seuls Administrateur et Gestionnaire peuvent rouvrir une opportunité terminale. `won` revient à `negotiation` ; `lost`
revient à sa dernière étape ouverte, ou à `discovery` si l’historique est incomplet. La réouverture exige un motif codé
parmi `entered_in_error`, `customer_reengaged`, `additional_information` et `other` ; `other` exige une note.

`closed_at` est fixé en UTC lors du passage à `won` ou `lost`, puis remis à `NULL` lors d’une réouverture. L’historique
terminal demeure append-only.

## 6. Lien avec le pipeline prospect

Les correspondances servent à expliquer l’alignement, pas à déclencher une écriture automatique :

| Étape d’opportunité | Étape Kanban suggérée |
| --- | --- |
| `discovery` ou `qualification` | `opportunity` |
| `proposal` | `proposal_sent` |
| `negotiation` | `negotiation` |
| `won` | `won` |
| `lost` | `lost` seulement si aucune autre opportunité n’est ouverte ou gagnée |

Après une transition d’opportunité, l’interface peut proposer « Aligner le pipeline ». Cette action utilise strictement
les routes, capacités, versions, motifs et règles de graphe de 3.2. Elle n’est jamais cochée implicitement, ne contourne
aucune transition interdite et produit sa propre entrée d’historique.

Une opportunité gagnée produit une conversion logique dérivée : `has_won_opportunity = true`. Le prospect reste dans
sa table d’origine, ses données ne sont pas copiées et aucun objet client n’est créé. Les vues peuvent afficher le
badge « Client gagné » indépendamment de l’alignement actuel du Kanban.

Une opportunité ne peut être créée que pour un prospect non archivé. Les étapes terminales du prospect n’interdisent
pas la consultation de son historique. La création sur un prospect `won` ou `lost` exige d’abord sa réouverture selon
le parcours 3.2 afin d’éviter une affaire active invisible dans un portefeuille terminal.

## 7. Acteurs et capacités

| Capacité | Administrateur | Gestionnaire | Commercial |
| --- | --- | --- | --- |
| `opportunities:read` | Oui, organisation | Oui, organisation | Oui, propres opportunités |
| `opportunities:create` | Oui | Oui | Oui, pour lui-même |
| `opportunities:update` | Oui | Oui | Oui, si responsable actif |
| `opportunities:close` | Oui | Oui | Oui, si responsable actif |
| `opportunities:reopen` | Oui | Oui | Non |

La lecture de la section synthétique d’un prospect reste disponible avec `prospects:read`, mais les montants, noms et
détails des opportunités exigent `opportunities:read`. Pour un Commercial, l’API applique le filtre de responsabilité ;
masquer un bouton dans React n’est jamais considéré comme un contrôle d’autorisation.

## 8. Modèle de données cible

### 8.1 `opportunities`

| Champ | Type / contrainte |
| --- | --- |
| `id` | UUID, clé primaire |
| `organization_id` | UUID, obligatoire, clé locataire |
| `prospect_id` | UUID, FK composite vers le prospect de la même organisation |
| `owner_membership_id` | UUID, appartenance de la même organisation |
| `name` | texte normalisé, 1 à 160 caractères |
| `amount` | `NUMERIC(19,4)`, strictement positif |
| `currency_code` | `CHAR(3)`, ISO 4217 majuscule |
| `probability` | petit entier entre 0 et 100 |
| `stage_code` | l’un des six codes système |
| `expected_close_on` | `DATE`, obligatoire |
| `loss_reason_code` | motif contrôlé seulement pour `lost` |
| `loss_reason_note` | texte facultatif, 1 à 500 caractères |
| `closed_at` | UTC, obligatoire seulement pour `won` ou `lost` |
| `created_by` | UUID de l’acteur interne |
| `version` | entier positif de verrou optimiste |
| `created_at`, `updated_at` | UTC |

Les contraintes SQL garantissent la cohérence des probabilités terminales, du motif de perte et de `closed_at`.
L’unicité du nom n’est pas imposée : deux affaires distinctes peuvent porter le même intitulé.

### 8.2 `opportunity_events`

| Champ | Type / contrainte |
| --- | --- |
| `id` | UUID, clé primaire et résultat stable d’idempotence |
| `organization_id`, `prospect_id`, `opportunity_id` | clés composites locataires |
| `actor_id` | UUID interne |
| `event_type` | `created`, `updated`, `stage_changed` ou `reopened` |
| `from_stage`, `to_stage` | codes facultatifs selon l’événement |
| `from_version`, `resulting_version` | séquence positive |
| `changed_fields` | objet JSON fermé de codes de champs, sans valeurs métier |
| `reason_code`, `reason_note` | seulement lorsque le parcours l’exige |
| `idempotency_key` | texte opaque de 1 à 128 caractères, UUID recommandé, unique par organisation et type de commande |
| `occurred_at` | UTC |

L’événement métier permet la chronologie sans recopier les montants, noms ou responsables dans l’audit technique. La
note de motif reste une donnée métier soumise à la conservation du prospect et n’est jamais copiée dans les journaux.

### 8.3 Index, RLS et privilèges

- index `(organization_id, prospect_id, stage_code, expected_close_on, id)` ;
- index `(organization_id, owner_membership_id, stage_code, expected_close_on, id)` ;
- index partiel des opportunités ouvertes et échues ;
- index des événements `(organization_id, opportunity_id, occurred_at DESC, id DESC)` ;
- RLS activée et forcée sur les deux tables ;
- clés étrangères composites empêchant tout rattachement inter-organisation ;
- privilèges applicatifs limités à `SELECT`, `INSERT` et `UPDATE` nécessaires ; aucun `DELETE` métier ;
- événements append-only : aucun privilège `UPDATE` ou `DELETE` pour le rôle applicatif.

## 9. API proposée

| Méthode et route | Capacité | Usage |
| --- | --- | --- |
| `GET /api/prospects/{prospect_id}/opportunities` | `opportunities:read` | Opportunités visibles du prospect, paginées |
| `POST /api/prospects/{prospect_id}/opportunities` | `opportunities:create` | Créer une opportunité |
| `GET /api/opportunities` | `opportunities:read` | Portefeuille filtré et paginé |
| `GET /api/opportunities/{opportunity_id}` | `opportunities:read` | Détail et actions autorisées |
| `PATCH /api/opportunities/{opportunity_id}` | `opportunities:update` | Nom, montant/devise, probabilité, échéance ou responsable |
| `POST /api/opportunities/{opportunity_id}/stage-transitions` | `opportunities:close` ou `update` | Transition normale ou terminale |
| `POST /api/opportunities/{opportunity_id}/reopen` | `opportunities:reopen` | Réouverture contrôlée |
| `GET /api/opportunities/{opportunity_id}/events` | `opportunities:read` | Historique métier paginé |

Les créations et mutations contiennent `idempotency_key`. Toute modification d’un état existant contient également la
`version` lue. Les listes utilisent un curseur signé lié aux filtres, au tri, à l’organisation et à l’acteur visible.
Les réponses portent `Cache-Control: no-store, max-age=0`.

Le montant JSON est une chaîne, par exemple `"12500.0000"`. La réponse expose `weighted_amount` sous la même forme.
Elle ne contient aucun champ Google réhydraté.

### 9.1 Erreurs stables

| HTTP | Code | Situation |
| ---: | --- | --- |
| 403 | `opportunity_action_forbidden` | capacité ou responsabilité insuffisante |
| 404 | `opportunity_not_found` | ressource absente ou invisible |
| 409 | `opportunity_version_conflict` | version obsolète |
| 409 | `opportunity_idempotency_conflict` | même clé, autre commande |
| 409 | `opportunity_owner_inactive` | responsable désactivé ou réaffectation requise |
| 409 | `opportunity_parent_archived` | prospect parent archivé, mutation interdite |
| 422 | `opportunity_command_invalid` | champ, montant, devise, date ou motif invalide |
| 422 | `opportunity_transition_invalid` | graphe non respecté |
| 422 | `opportunity_pipeline_alignment_invalid` | alignement 3.2 impossible |

Une ressource d’une autre organisation ne produit jamais un code qui confirmerait son existence.

## 10. Transactions, concurrence et idempotence

Chaque commande suit l’ordre suivant :

1. authentifier la session et résoudre l’organisation active ;
2. vérifier origine, CSRF, type JSON et capacité ;
3. verrouiller le prospect puis l’opportunité dans cet ordre ;
4. vérifier organisation, archivage, responsable, version et commande idempotente ;
5. appliquer les invariants et incrémenter la version ;
6. créer l’événement métier et l’audit minimisé ;
7. valider une seule transaction PostgreSQL.

Un rejeu strict restitue le même résultat sans nouvel événement. Une clé réutilisée avec un corps différent retourne
`409`. Deux modifications concurrentes de la même version produisent exactement un succès et un conflit. Une erreur
d’événement ou d’audit annule la modification métier.

L’alignement du pipeline est une commande 3.2 séparée dans la V1. Une défaillance de cet alignement ne revient pas sur
la transition d’opportunité déjà confirmée ; l’interface explique l’écart et permet de réessayer avec la version actuelle
du prospect. Aucun enchaînement client ne doit présenter les deux commandes comme une transaction unique.

## 11. Interface utilisateur

### 11.1 Fiche prospect

Une section « Opportunités » affiche les affaires visibles, leur étape, montant/devise, valeur pondérée, échéance,
responsable et état de retard. Elle propose la création selon les capacités et un lien vers le détail. Une synthèse
affiche le nombre d’opportunités ouvertes et les totaux regroupés par devise.

La chronologie commerciale reçoit les événements « Opportunité créée », « Opportunité modifiée », « Étape
d’opportunité modifiée », « Opportunité gagnée/perdue » et « Opportunité rouverte ». Les valeurs financières et les
notes de perte ne sont affichées que dans le détail autorisé, pas dans le résumé de chronologie.

### 11.2 Portefeuille des opportunités

La navigation ajoute « Opportunités ». La vue liste filtre par texte interne, étape, responsable, devise, échéance,
retard et prospect. Le tri initial est échéance croissante, puis mise à jour décroissante, puis UUID. Le changement de
filtre invalide le curseur précédent.

Les totaux et valeurs pondérées sont regroupés par devise. Il est interdit d’afficher un total unique mélangeant CAD,
USD ou toute autre devise sans conversion explicite, laquelle est hors périmètre.

### 11.3 Kanban et liste des prospects

Une carte Kanban ou une ligne prospect peut afficher un indicateur borné : nombre d’opportunités ouvertes, prochaine
échéance et totaux par devise. Le détail est chargé par l’API CRM, jamais depuis Google. Si plus de trois devises sont
présentes, l’interface affiche un résumé et renvoie vers la fiche au lieu d’élargir la carte.

Toutes les actions existent au clavier. Les dialogues de perte et de réouverture utilisent des listes de motifs
compréhensibles, le focus est restauré et les confirmations sont annoncées par `aria-live`. La couleur n’est jamais le
seul indicateur d’étape ou d’issue.

## 12. Audit et observabilité

Actions d’audit proposées :

- `opportunity.created` ;
- `opportunity.updated` ;
- `opportunity.stage_changed` ;
- `opportunity.reopened`.

L’audit contient les identifiants internes, codes d’étape, code de devise, code de motif, version et noms des champs
modifiés. Il exclut nom d’opportunité, montant, note, alias du prospect, courriel, téléphone, identités affichées et tout
contenu Google.

Les journaux JSON utilisent un schéma fermé : opération, résultat, code d’étape, code d’erreur, durée et `request_id`.
Les métriques proposées sont :

- `opportunity_command_total{operation,result}` ;
- `opportunity_transition_total{from_stage,to_stage,result}` ;
- `opportunity_conflict_total{operation}` ;
- `opportunity_portfolio_request_total{result}` ;
- histogrammes de durée des commandes et lectures.

Les six étapes et les opérations forment des ensembles bornés. Devise, responsable, prospect et opportunité ne sont
jamais des étiquettes de métrique.

## 13. Sécurité, conservation et conformité

- l’organisation active vient exclusivement de la session serveur ;
- toute mutation exige origine approuvée, CSRF valide et JSON ;
- RLS et clés composites assurent l’isolation locataire ;
- les filtres de responsabilité d’un Commercial sont vérifiés côté serveur ;
- aucune donnée 3.4 n’est écrite dans `localStorage`, `sessionStorage`, IndexedDB ou Cache API ;
- tous les textes sont normalisés, bornés et rendus comme texte ;
- aucune donnée Google ne préremplit nom, montant, devise, probabilité, échéance ou motif ;
- l’opportunité suit la conservation et l’archivage logique du prospect parent ;
- un prospect archivé rend ses opportunités en lecture seule et les retire des portefeuilles actifs ;
- aucune suppression physique ou route de suppression d’opportunité n’est livrée ;
- les données financières CRM sont exportables ultérieurement seulement selon une liste blanche et les droits.

## 14. Tests et critères d’acceptation

1. Un prospect actif accepte plusieurs opportunités distinctes sans collision de nom.
2. Nom, montant, devise, probabilité, échéance et responsable respectent les limites applicatives et SQL.
3. Les montants transitent comme décimaux exacts ; aucune opération ne passe par un flottant binaire.
4. La valeur pondérée est exacte à quatre décimales et les devises différentes ne sont jamais additionnées.
5. Les six étapes et le graphe autorisent uniquement les transitions documentées.
6. Gagnée impose 100, Perdue impose 0 et Perdue refuse une commande sans motif valide.
7. La réouverture restaure la bonne étape ouverte, exige un motif et reste interdite au Commercial.
8. Une échéance passée est signalée sans transition automatique ; le rendu suit le fuseau de l’organisation.
9. Un responsable désactivé reste visible, bloque les mutations et ne reçoit aucune nouvelle opportunité.
10. Deux commandes concurrentes produisent un succès et un `409` ; un rejeu strict ne double ni événement ni audit.
11. Opportunité, événement et audit sont atomiques, y compris lorsqu’une insertion est forcée en échec.
12. Créer ou déplacer une opportunité ne modifie jamais implicitement le pipeline du prospect.
13. L’alignement explicite respecte la version et le graphe 3.2 ; une incompatibilité est expliquée sans perte d’état.
14. Administrateur, Gestionnaire et Commercial respectent capacités, responsabilité et isolation inter-organisation.
15. Interface clavier, axe, bilinguisme, `no-store`, CSRF et absence de stockage navigateur sont conformes.
16. Ruff, format Ruff, mypy, pytest PostgreSQL/RLS réel, Alembic, ESLint, Vitest/axe, build et verrou global sont verts sans skip.

## 15. Migration, compatibilité et retour arrière

La migration proposée `20260910_0020` :

1. crée `opportunities` et `opportunity_events` avec contraintes et clés composites ;
2. crée les index de portefeuille, responsabilité, échéance et chronologie ;
3. active et force RLS sur les deux tables ;
4. accorde les privilèges minimaux au rôle applicatif ;
5. ne transforme aucune étape Kanban existante et ne crée aucune opportunité historique artificielle.

Le déploiement applique la migration avant le backend 3.4. Le frontend masque ses écrans tant que les routes et
capacités ne sont pas disponibles. Un retour arrière applicatif retire les points d’entrée sans supprimer les données.
En staging ou production, toute correction de schéma est additive ; un downgrade destructeur n’est permis que sur une
base éphémère explicitement dédiée aux tests.

## 16. Séquence d’implémentation proposée

### 16.1 — 3.4-A Domaine et persistance

- domaine Opportunité, montants décimaux, étapes et invariants ;
- capacités et matrice de rôles ;
- migration `20260910_0020`, modèles, RLS, privilèges et dépôts ;
- tests unitaires, SQL, contraintes et isolation réelle.

La traduction technique complète est disponible dans
[`PHASE_3_4_A_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_A_SPECIFICATIONS_DETAILLEES.md). Le lot est implémenté et validé
techniquement dans [`PHASE_3_4_A_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_A_RAPPORT_IMPLEMENTATION.md).

### 16.2 — 3.4-B Cas d’utilisation et API

- création, modification, transitions, issues et réouverture ;
- portefeuille, détail, historique, agrégats par devise et valeur pondérée ;
- concurrence, idempotence, audit, métriques et erreurs stables ;
- tests API, transactionnels et multi-organisation.

La traduction technique complète est disponible dans
[`PHASE_3_4_B_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_B_SPECIFICATIONS_DETAILLEES.md). Sa rédaction est terminée ; elle
est implémentée et techniquement validée dans
[`PHASE_3_4_B_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_B_RAPPORT_IMPLEMENTATION.md).

### 16.3 — 3.4-C Interface et intégrations CRM

- section et formulaire sur la fiche prospect ;
- portefeuille des opportunités ;
- événements dans la chronologie et synthèse sur liste/Kanban ;
- action explicite d’alignement pipeline ;
- écrans `fr-CA` / `en-CA`, clavier, axe et tests React.

La traduction technique complète est disponible dans
[`PHASE_3_4_C_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_C_SPECIFICATIONS_DETAILLEES.md). Son implémentation a été
autorisée explicitement le 10 septembre 2026 ; le verrou global reste requis avant la clôture du sous-lot.

### 16.4 — 3.4-D Recette et verrou

- migration reconstruite sur PostgreSQL réel ;
- recette fonctionnelle regroupée des montants, issues, concurrence, rôles et pipeline ;
- documentation utilisateur et rapport d’implémentation ;
- régression 3.1 à 3.3 et verrou qualité global sans skip.

Le protocole détaillé est disponible dans
[`PHASE_3_4_D_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_D_SPECIFICATIONS_DETAILLEES.md), avec la recette regroupée
[`RECETTE_FONCTIONNELLE_3_4_OPPORTUNITES.md`](RECETTE_FONCTIONNELLE_3_4_OPPORTUNITES.md) et le modèle de rapport
[`PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md).

## 17. Seize décisions validées

1. Un prospect actif peut porter plusieurs opportunités ; aucune unicité n’est imposée sur leur nom.
2. Une opportunité exige nom interne, montant strictement positif, devise, probabilité, échéance et responsable actif.
3. Le montant utilise `NUMERIC(19,4)` et une chaîne décimale JSON ; `CAD` est proposé initialement et la devise est validée par une liste ISO 4217 serveur.
4. La probabilité est un entier de 0 à 100 ; la valeur pondérée est dérivée côté serveur, jamais stockée, et les devises ne sont jamais additionnées entre elles.
5. Les six codes fixes sont `discovery`, `qualification`, `proposal`, `negotiation`, `won` et `lost`.
6. Les étapes ouvertes avancent ou reculent d’un cran ; proposition et négociation peuvent gagner ; toute étape ouverte peut perdre.
7. Perdue exige l’un des huit motifs définis ; Gagnée et Perdue sont terminales et seuls Administrateur ou Gestionnaire peuvent les rouvrir avec motif.
8. L’échéance est une date civile obligatoire ; un dépassement crée un indicateur de retard sans transition, rappel ou automatisation.
9. Le responsable est une appartenance active ; sa désactivation ne réaffecte rien et bloque les mutations jusqu’à réaffectation humaine.
10. Administrateur et Gestionnaire gèrent toutes les opportunités ; Commercial lit et gère seulement celles dont il est responsable et ne peut pas les rouvrir.
11. Étape d’opportunité et étape Kanban restent indépendantes ; tout alignement du prospect est une seconde action explicite soumise aux règles 3.2.
12. Une opportunité gagnée représente une conversion logique dérivée sans créer ni copier une fiche client.
13. Toute mutation est versionnée, idempotente et atomique avec son événement métier et son audit minimisé.
14. La fiche prospect, le portefeuille, la chronologie, la liste et le Kanban affichent uniquement des synthèses autorisées et regroupées par devise.
15. RLS, clés composites, CSRF, `no-store`, absence de stockage navigateur, textes bilingues et exclusion totale des contenus Google sont obligatoires.
16. 3.4 sera clôturé après migration réelle, recette opportunités/pipeline, tests de concurrence et d’isolation, zéro skip, documentation et verrou qualité global vert ; les réserves antérieures restent dues en 3.6.

## 18. Décision de sortie

Les seize décisions de la section 17 ont été validées explicitement par le responsable produit le 10 septembre 2026.
La séparation opportunité/pipeline, la visibilité du Commercial, les règles financières, la conversion logique, les
contrats de concurrence et les exigences de qualité sont désormais stabilisés.

Le GO du 10 septembre 2026 a permis **3.4-A — Domaine et persistance**. Le socle est livré dans le rapport
[`PHASE_3_4_A_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_A_RAPPORT_IMPLEMENTATION.md). PostgreSQL réel, Alembic, 289 tests
backend et 162 tests frontend sont verts sans skip.

Le GO explicite du 10 septembre 2026 a autorisé l’implémentation de **3.4-B — Cas d’utilisation et API**, désormais
documentée dans [`PHASE_3_4_B_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_B_SPECIFICATIONS_DETAILLEES.md). Les commandes,
les lectures, l’historique, la pagination signée, les agrégats, l’audit et les métriques sont présents sans migration
additionnelle. Le verrou qualité local est vert ; voir
[`PHASE_3_4_B_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_B_RAPPORT_IMPLEMENTATION.md).

Le GO documentaire du 10 septembre 2026 a ensuite permis de détailler **3.4-C — Interface et intégrations CRM** dans
[`PHASE_3_4_C_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_C_SPECIFICATIONS_DETAILLEES.md). Les parcours de la fiche, du
portefeuille, de la chronologie, de la liste, du Kanban et de l’alignement explicite y sont stabilisés, avec leurs
contrats bilingues, clavier, axe et tests React. L’implémentation et la recette sont retracées dans les rapports 3.4-C
et 3.4-D.

Le verrou global sur `20260922_0021` est vert et le responsable produit a donné le GO de clôture de 3.4 le
23 septembre 2026 (UTC). Les preuves et réserves transférées figurent dans
[`PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md). La spécification de la phase 4 est
ouverte dans [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md).
