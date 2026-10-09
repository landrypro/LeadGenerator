# Fiche d’exécution — recette fonctionnelle Automatisation AUT-COR-01 à AUT-COR-08

> Document préparé pour l’exécution humaine après le verrou qualité. Aucun scénario
> ci-dessous n’autorise l’activation d’une organisation cliente ni l’envoi externe.

> **Exécution navigateur locale — 5 octobre 2026 :** campagne partielle exécutée par
> l’assistant sur l’organisation de démonstration. Résultat provisoire :
> `PASS_AVEC_RESERVE` pour la coque et les états vides ; parcours de préparation
> d’un plan en échec d’affichage ; scénarios nécessitant des rôles, fixtures ou
> commandes mutantes non exécutés.

## 1. Périmètre et décision attendue

Cette fiche couvre la coque Automatisation, les états vides, les lectures, le Prévol,
le cycle de vie, les entrées/exceptions et l’observabilité/rollback :

- `AUT-COR-01` / `R01–R03` : coque et sous-navigation ;
- `AUT-COR-02` / `R04–R06` : états honnêtes et indisponibilité ;
- `AUT-COR-03` / `R07–R09b` : contrats, droits et isolation ;
- `AUT-COR-04` / `R09c–R11` : Prévol persistant sans effet ;
- `AUT-COR-05` / `R12–R14` : activation, suspension et reprise ;
- `AUT-COR-06` / `R15–R17` : exceptions et résolution ;
- `AUT-COR-07` / `R18–R20` : observabilité, flags et retour arrière.
- `AUT-COR-08` / `R21–R24` : administration du flag organisationnel, version et audit.

Décision finale : `PASS`, `PASS_AVEC_RESERVE`, `FAIL` ou `BLOCKED`. Un `BLOCKED`
doit préciser le prérequis manquant ; il ne vaut pas validation.

## 2. Préconditions de recette

### Verrou qualité préalable

| Contrôle | Résultat communiqué | Preuve |
|---|---|---|
| Build Vite | PASS | sortie du verrou qualité |
| Recette navigateur 4.6 | PASS — 44 parcours, axe conforme | `test-results/phase-4-6/browser-axe.json` |
| Sources navigateur / artefact Vite | conforme | sortie du verrou qualité |
| Diff Git | conforme, avertissements LF/CRLF non bloquants | sortie du verrou qualité |
| Nettoyage des services de test | effectué | sortie du verrou qualité |

Le verrou qualité local est donc **VERT**. Il ne remplace pas la recette
fonctionnelle humaine ci-dessous et n’autorise aucune activation Automation.

| Élément | Valeur à renseigner | Contrôle |
|---|---|---|
| Environnement | préproduction jetable / local isolé | URL et date |
| SHA / image |  | concordance avec le verrou qualité |
| Tête Alembic | `20261006_0042` attendue | `alembic current` |
| Organisation A | synthétique, active | UUID non affiché dans les captures publiques |
| Organisation B | synthétique, distincte | utilisée pour l’isolation |
| Sales | membre actif affecté à un cas | identifiant de session de recette |
| Gestionnaire | portée organisationnelle | identifiant de session de recette |
| Administrateur | gestion des Playbooks et exceptions | identifiant de session de recette |
| Plateforme | sans organisation active | vérifie l’absence d’élévation implicite |
| Flags initiaux | `AUTOMATION_ENABLED=false`, `AUTOMATION_ROLLOUT_MODE=off` | capture de configuration sans secret |
| Fournisseurs externes | désactivés ou simulateurs/Mailpit | aucune clé réelle |
| Données | fixtures synthétiques uniquement | sauvegarde/restauration jetable |

Les trois lots de navigation `NAV-L1`, `NAV-L2` et `NAV-L3` sont des prérequis
déjà validés. La recette Automation vérifie seulement que leur navigation globale
reste intacte et que la sous-navigation Automatisation s’y insère sans doublon.

Avant `R10–R17`, préparer trois fixtures :

1. Playbook `new_prospect` avec version immuable et Prévol de configuration à
   `subject_count=0` ;
2. Playbook admissible avec Prévol complet, frais et non vide, uniquement si le
   parcours d’activation doit être exercé ;
3. exceptions `owner_unavailable` et `effect_uncertain`, avec corrélations et
   versions connues.

Si la fixture complète n’existe pas, exécuter la partie refus sûr de `R12` et
marquer la partie activation `BLOCKED_FIXTURE`, jamais `PASS`.

## 3. Règles de preuve

Créer un dossier de campagne hors dépôt, par exemple :
`test-results/recette-aut-cor-20261005/`.

Chaque preuve doit contenir l’ID du scénario, la date, l’environnement et le
résultat. Ne jamais y copier mot de passe, cookie, bearer, adresse complète, texte
libre de l’assistant ou UUID métier non nécessaire.

Nommage recommandé :

```text
AUT-COR-R01-ui-fr.png
AUT-COR-R09b-sales-admin.json
AUT-COR-R13-audit.txt
AUT-COR-R18-metrics.txt
AUT-COR-R20-rollback.json
```

## 4. Feuille d’exécution

| ID | Action courte | Résultat attendu | Statut | Preuve / réserve |
|---|---|---|---|---|
| R01 | ouvrir Aujourd’hui | titre, limite V1 et assistant visibles |  |  |
| R02 | parcourir les trois surfaces desktop | titre, fil et actif cohérents |  |  |
| R03 | ouvrir le tiroir mobile | inertie, Échap, hors panneau et focus corrects |  |  |
| R04 | ouvrir Playbooks sans configuration | cartes honnêtes, aucun faux compteur/interrupteur |  |  |
| R05 | ouvrir Exceptions sans données | état vide distinct d’une erreur |  |  |
| R06 | couper le service de lecture | erreur récupérable, pas d’état vide trompeur |  |  |
| R07 | session Sales | lecture self, aucune commande de gestion |  |  |
| R08 | session Gestionnaire/Admin avec flag accordé | commandes visibles seulement si capacité + flag |  |  |
| R09 | forger organisation / changer de tenant | `403`/`404`, aucune fuite |  |  |
| R09a | paramètres inconnus ou invalides | `422`, `no-store`, pas de repli silencieux |  |  |
| R09b | comparer Sales et Gestionnaire | projection et portée conformes |  |  |
| R09c | Prévol puis rejeu de clé | même résultat, audit, zéro effet CRM |  |  |
| R10 | Prévol admissible | version, expiration et compteurs cohérents |  |  |
| R11 | modifier règle/snapshot/capacité | Prévol obsolète, activation refusée |  |  |
| R12 | activation avec Prévol à zéro sujet | `409`, aucune écriture métier |  |  |
| R13 | suspendre puis rejouer | génération, état et idempotence corrects |  |  |
| R14 | reprendre après suspension | `preflight_required`, aucune reprise implicite |  |  |
| R15 | claim puis resolve `owner_unavailable` | décision fermée, audit, aucun effet CRM |  |  |
| R16 | code libre puis abandon contrôlé | `422` sans écriture, abandon audité |  |  |
| R17 | reconcile `effect_uncertain` | pas de retry aveugle, état `in_progress` |  |  |
| R18 | consulter audits + métriques + logs | événements allow-listés, aucune PII |  |  |
| R19 | fr-CA/en-CA, zoom 200 %, clavier | utilisable, focus et libellés corrects |  |  |
| R20 | passer flags off et rollback | commandes refusées, Playbooks suspendus, données conservées |  |  |
| R21 | ouvrir Administration > Automatisation en admin | état de l’organisation active, état global et version lisibles |  |  |
| R22 | ouvrir la même route en Gestionnaire/Sales | lien absent et API `403`, aucune élévation |  |  |
| R23 | activer ou suspendre avec confirmation | version incrémentée, génération de suspension cohérente, audit présent |  |  |
| R24 | rejouer avec une version périmée | `409 automation_settings_version_conflict`, aucun changement |  |  |

### Exécution constatée — campagne locale du 5 octobre 2026

| ID / contrôle | Statut | Constat et preuve |
|---|---|---|
| R01 | **PASS** | `Aujourd’hui` affiche le titre, l’identifiant `IMP-A5`, l’assistant en lecture seule, la limite de 500 caractères et les suggestions guidées. |
| R02 | **PASS** | Les routes `today`, `playbooks` et `exceptions` sont accessibles ; titres, fil d’Ariane et surface active sont cohérents. |
| R03 | **PASS_AVEC_RESERVE** | Rejoué le 6 octobre 2026 dans le navigateur local en disposition responsive (viewport d’environ 792×397). Le tiroir s’ouvre avec le focus sur sa fermeture, les groupes Acquisition / Données et audit / Administration exposent leurs sous-liens, Échap ferme le tiroir, un clic hors panneau le ferme aussi et le focus revient au bouton Menu. Le verrouillage de défilement pendant l’ouverture n’a pas été mesuré séparément. |
| R04 | **PASS** | Les trois cartes Playbooks sont visibles. L’absence de configuration est explicitement indiquée ; aucun compteur, interrupteur ou état d’activation fictif n’est affiché. |
| R05 | **PASS** | L’écran Entrées et exceptions indique une absence de données confirmée, distingue les états suivis et précise qu’une erreur de chargement serait affichée séparément. |
| R06 | **NON EXÉCUTÉ** | Aucune coupure artificielle du service de lecture n’a été injectée. |
| Préparation d’un plan | **FAIL — défaut d’environnement et d’affichage** | La saisie et l’envoi sont possibles, mais l’environnement garde l’assistant désactivé par défaut. La réponse d’erreur produit un bandeau rouge visuellement vide, puis aucun plan. Le backend reste sain (`/api/health/ready` = `200`). |
| R07–R09b | **BLOCKED** | Aucun changement de session Sales/Gestionnaire/Administrateur, de tenant ou de paramètres invalides n’a été autorisé dans cette campagne navigateur. |
| R09c–R17 | **BLOCKED_FIXTURE** | Configuration active, Prévol complet, exceptions synthétiques et comptes de commande non disponibles dans l’organisation de démonstration. |
| R18–R20 | **NON EXÉCUTÉ** | Audit/métriques, accessibilité multi-locale complète et rollback contrôlé exigent une campagne dédiée avec preuves et flags isolés. |

#### Analyse de l’échec « Préparer un plan »

Le parcours appelle bien `POST /api/automation/intent-plans`. Le service répond
dans l’environnement courant, mais l’assistant est verrouillé par les valeurs de
Pré-Phase 5 (`AUTOMATION_ENABLED=false` et
`AUTOMATION_ASSISTANT_ENABLED=false`, valeurs par défaut lorsque ces variables ne
sont pas injectées au conteneur API). Cette réponse de verrouillage est attendue
tant qu’un environnement de recette isolé n’a pas ouvert explicitement les flags.

Un défaut frontend indépendant masque toutefois le diagnostic :
`AutomationTodayPage.jsx` rend `<ErrorBanner message={error} />`, alors que
`ErrorBanner` attend son texte dans `children`. Le bandeau est donc présent mais
vide. La correction minimale à valider est :

```jsx
<ErrorBanner>{error}</ErrorBanner>
```

Cette correction doit être accompagnée d’un test vérifiant qu’une réponse `409`
(`assistant_disabled`) ou `503` affiche le message lisible et ne crée aucun effet
CRM/externe. Les tests unitaires backend Automatisation exécutés pendant cette
campagne sont verts : **31 PASS, 7 ignorés** ; les tests frontend ciblés de la
page Aujourd’hui sont également verts ; un test dédié couvre désormais le rendu
de `ErrorBanner` avec une erreur API.

### Correctifs appliqués après la campagne

| Correctif | Statut | Vérification |
|---|---|---|
| Rendu du message d’erreur dans `AutomationTodayPage` | **APPLIQUÉ** | `ErrorBanner` reçoit désormais le texte via `children`. |
| Test de refus de préparation (`409`/erreur lisible) | **APPLIQUÉ** | 3 tests `AutomationTodayPage` passent avec Vitest. |
| Transmission des flags Automation par Compose | **APPLIQUÉ** | `compose.yaml` transmet les flags à l’API et au worker ; valeurs par défaut conservées à `false`. |
| Rejeu navigateur avec assistant désactivé | **PASS** | Après rechargement, le bandeau affiche maintenant `L’assistant est désactivé.` ; aucun plan ni effet CRM/externe n’est produit. |
| Rejeu navigateur avec assistant activé | **PASS_AVEC_RESERVE** | Rejoué le 6 octobre 2026 sur le backend local issu du dépôt courant (`127.0.0.1:8002`) et Vite (`localhost:5174`). L’origine `http://localhost:5174` a été ajoutée à la configuration CORS puis le backend a été relancé. La suggestion `Cadrer mes prospects ouverts` produit un plan lisible (`0` élément trouvé, `0` retenu) avec les garde-fous `read only`, `server resolved scope` et `no provider tools`; la section « Ce qui n’a pas été fait » confirme `no crm write`, `no preflight`, `no job` et `no external send`. Le bouton `Préparer ce plan` affiche ensuite « Plan marqué comme prêt dans cet écran. Aucune donnée ni tâche n’a été créée. » Réserve d’infrastructure : l’image Docker API reste antérieure aux capacités Automation (import de `AUTOMATION_CAPABILITIES_BY_ROLE` absent dans `/app/backend`) et sa reconstruction est toujours bloquée par le délai réseau Docker Hub (`node:22-alpine` / `python:3.12-slim`). La validation produit est donc acquise sur le runtime local courant, pas encore sur l’image Docker reconstruite. |

**Test complémentaire exécuté le 6 octobre 2026 :** la suggestion `Étudier un rééquilibrage` produit également un plan `11` éléments trouvés / `11` retenus, avec les mêmes garde-fous et la confirmation « Aucune donnée ni tâche n’a été créée » après `Préparer ce plan`. Les journaux backend confirment `POST /api/automation/intent-plans` en `200 OK`.

### Ajout AUT-COR-08 — administration du commutateur organisationnel

La route `/app/admin/automation` est désormais exposée dans le groupe
**Administration** uniquement pour la capacité `automation:settings:manage`, attribuée
au rôle administrateur. Elle lit l’état de l’organisation active et expose une
confirmation explicite pour activer ou suspendre Automation. La mutation est
tenant-bound, protégée par CSRF/origine de confiance et contrôle de version ; elle
ne crée ni Playbook actif, ni Prévol, ni tâche, ni envoi externe.

Le backend persiste cette mutation via la fonction PostgreSQL SECURITY DEFINER
`app_private.set_automation_organization_settings(boolean, integer, text)`. Toute
transition effective ajoute `automation.organization_settings_changed` au journal
d’audit avec les versions et la génération de suspension. Le rejeu d’un état déjà
présent est idempotent et n’ajoute pas d’événement inutile.

### Correctif exécuté le 6 octobre 2026 — erreur 503 à la suspension

Le premier clic de confirmation retournait `503 Les paramètres Automation sont indisponibles.`.
La reproduction SQL, réalisée dans une transaction annulée, a identifié une résolution de
signature PostgreSQL impossible : la fonction de paramètres appelait `app_private.append_audit_event`
avec le littéral `1` en `integer`, alors que le contrat d’audit exige `smallint`.

Le correctif est livré dans la migration `20261006_0042` (et dans le corps de la migration
d’origine pour les installations neuves) : le schéma-version est désormais transmis explicitement
comme `1::smallint`. La migration a été appliquée jusqu’à `20261006_0042`, puis la recette
navigateur a été rejouée : suspension confirmée avec état `Non disponible`, version 2,
génération 1 et audit présent ; réactivation confirmée avec état `Disponible pour cette
organisation`, version 3 et génération 1. Aucun Playbook, tâche ou envoi externe n’a été créé.

Le contrôle ciblé est donc **PASS**. Le rejeu R24 (version périmée) reste à exécuter séparément.

**Rejeu navigateur complémentaire — 6 octobre 2026 :** l’organisation était
initialement activée en version 5, génération 2. La suspension confirmée a
produit la version 6, génération 3, puis la réactivation confirmée a produit la
version 7, génération 3. Les deux transitions ont affiché le succès dans
l’interface et ont créé les deux événements d’audit attendus. **PASS.**

**Correctif navigation — 6 octobre 2026 :** après suspension, la disponibilité
effective est relue côté session et l’entrée globale **Automatisation** ainsi que
ses surfaces `Aujourd’hui`, `Playbooks` et `Entrées et exceptions` disparaissent
de la navigation et sont refusées en accès direct. L’entrée
**Administration > Automatisation** reste disponible pour réactiver le service.
Le contrôle frontend ciblé (20 tests) et le contrat `GET /api/automation/availability`
passent. Le rejeu navigateur après redémarrage du backend source a été effectué :
la navigation et l’état relus après rechargement sont conformes ; le contrôle
responsive détaillé reste couvert par R03 ci-dessous.

**Rejeu fonctionnel complémentaire — 6 octobre 2026 :** depuis
`Administration > Automatisation`, la suspension confirmée a produit l’état
`Non disponible`, la version `12` et la génération `6`. Pendant cette suspension,
le menu global **Automatisation** a disparu tandis que le lien
`Administration > Automatisation` est resté disponible. La réactivation confirmée a
restauré `Disponible pour cette organisation`, l’état `Activée`, la version `13`
et le menu global. Le contrôle R23 est donc **PASS** pour l’interface et les
compteurs de version ; la présence de l’événement d’audit n’a pas été relue dans
la présente passe navigateur.

Le parcours mobile R03 est **PASS_AVEC_RESERVE** : la navigation catégorisée,
Échap, le clic hors panneau et le retour de focus ont été observés ; le verrouillage
de défilement reste à confirmer par une mesure responsive dédiée. Les écrans
Playbooks et Entrées/exceptions ont été rejoués : les cartes Playbooks affichent
explicitement l’absence de configuration de Playbook et l’écran Exceptions expose
une absence de données confirmée, sans la confondre avec une erreur de chargement.
L’activation du commutateur d’organisation ne crée pas à elle seule de fixtures de
Playbooks ; les scénarios R09c–R17 restent donc conditionnés à ces fixtures.

**R24 — version périmée, 6 octobre 2026 :** deux vues de la même organisation ont
été ouvertes. Après une suspension confirmée dans la première vue (version `13`
vers `14`, génération `6` vers `7`), la seconde vue a rejoué la suspension avec
son `If-Match` périmé (`13`). L’interface a refusé la commande et affiché
« La configuration a changé. Rechargez la page avant de réessayer. » ; aucun
compteur n’a été modifié par la seconde commande. **PASS UI** ; le code HTTP `409`
et le code d’erreur JSON restent à capturer séparément côté réseau. L’organisation a été
réactivée ensuite depuis la vue fraîche (version `15`, génération `7`) et la page
Aujourd’hui a été restaurée.

## 5.1 Connexion aux données CRM réelles — prérequis avant la suite de recette

Les trois surfaces Automation utilisent désormais des projections bornées des
tables CRM canoniques, en lecture seule et dans le tenant de la session :

| Surface | Donnée réelle affichée | Contrat | Garde-fou |
|---|---|---|---|
| Aujourd’hui | compteurs de prospects ouverts, tâches à échéance/en retard, opportunités ouvertes, puis cinq priorités au maximum | `GET /api/automation/today` | aucun contact, aucune écriture CRM, périmètre commercial limité à ses affectations |
| Playbooks | volume courant des prospects/opportunités correspondant à chaque recette (`new_prospect`, `proposal_pending`, `forgotten_opportunity`) | `GET /api/automation/playbooks` → `live_scopes` | un volume CRM ne crée pas de configuration Playbook ni de Prévol fictif |
| Entrées et exceptions | libellé et stade du prospect/opportunité lié à une exception persistée | `GET /api/automation/exceptions` | une absence d’exception reste une absence confirmée ; aucune exception n’est fabriquée à partir d’un simple compteur |

Le lecteur PostgreSQL ouvre une transaction `snapshot_readonly` et applique la
portée organisationnelle ou personnelle avant toute agrégation. Les résultats
sont donc un instantané de la base CRM au moment de la lecture, non une copie ou
une seconde liste métier.

Contrôles techniques effectués le 6 octobre 2026 :

- `tests/test_automation_read_api.py` : **9 PASS**, dont le contrat `GET /api/automation/today` et la portée commerciale `self` ;
- tests Vitest Automation ciblés (`AutomationTodayPage`, `AutomationSupplementaryPages`) : **10 PASS** ;
- `npm --prefix client run build` : **PASS** ;
- Ruff (`check` et `format --check`) sur le lecteur et le routeur : **PASS**.

À rejouer dans le navigateur lorsque le backend contenant ces changements est
redémarré : vérifier que les nombres et priorités changent après une modification
CRM autorisée, qu’un Sales ne voit pas les objets d’un autre membre, et que les
cartes Playbooks restent explicitement « non configurées » lorsque seules les
données CRM existent. Aucun test ne doit créer une tâche, un prospect, une
opportunité, un Prévol ou un envoi externe.

**Rejeu navigateur — 6 octobre 2026 : PASS.** Après activation des flags globaux
et reconnexion de `demo2` sur « Entreprise Démonstration A » :

- **Aujourd’hui** a affiché `11` prospects ouverts, `2` tâches à échéance, `2`
  tâches en retard et `45` opportunités ouvertes, avec cinq priorités CRM
  lisibles (dont `OPP-07 Manager perdue`, `Test OPP-14` et `Test OPP-15`) ;
- **Playbooks** a affiché les volumes réels `9` (nouveau prospect), `2`
  (proposition en attente) et `44` (occasion oubliée), tout en conservant l’état
  « Prévol et activation non disponibles » puisque aucune configuration
  Playbook n’a été créée ;
- **Entrées et exceptions** a affiché l’absence confirmée de données, avec les
  états suivis, sans transformer cette absence en erreur ni inventer une
  exception.

Aucune écriture CRM, tâche, Prévol ou communication externe n’a été déclenchée
pendant ce rejeu.

## 5. Contrôles API et preuves AUT-COR-07

Les commandes mutantes doivent toujours porter `Origin` de confiance, CSRF,
`If-Match` lorsque requis et une clé d’idempotence. Les exemples ci-dessous sont
des gabarits ; remplacer les variables par des valeurs de recette, jamais par des
secrets committés.

### R18 — événements bornés

1. Ouvrir chaque surface et relever la télémétrie `surface_opened`.
2. Exécuter un Prévol ou une commande d’exception synthétique.
3. Lire `/internal/metrics` avec le bearer interne depuis un poste autorisé.
4. Vérifier seulement les labels `event`, `operation`, `outcome` et l’absence de
   nom, UUID, phrase libre ou contenu CRM.
5. Comparer avec l’audit organisationnel : corrélation, version, état avant/après
   et acteur sont présents côté audit, pas dans les labels Prometheus.

Événements acceptés :
`automation.surface_opened.v1`, `automation.playbook_preflighted.v1`,
`automation.playbook_state_changed.v1`, `automation.exception_resolved.v1` et
`automation.first_value_reached.v1`.

### R19 — accessibilité

- répéter `R01–R05` en `fr-CA` puis `en-CA` ;
- tester 200 % de zoom, orientation portrait/paysage et clavier seul ;
- vérifier nom accessible, focus visible, fermeture du tiroir et absence de
  défilement horizontal ;
- conserver une capture par surface et une note sur tout écart.

### R20 — rollback contrôlé

1. Capturer l’état initial du Playbook, sa version et sa génération.
2. Positionner `AUTOMATION_ENABLED=false` et `AUTOMATION_ROLLOUT_MODE=off`.
3. Suspendre avec le motif fermé `rollback` si un Playbook était actif.
4. Rejouer une tentative de Prévol/activation : elle doit être refusée.
5. Vérifier `prepare_enabled=false`, génération augmentée et absence de nouveau
   prospect, tâche, job, pipeline ou message.
6. Vérifier que Prévols, exceptions et audits existants sont conservés.

## 6. Critères bloquants et décision

Bloquant immédiat : fuite inter-organisation, activation malgré flag off, effet CRM
ou externe, perte d’audit, retry aveugle, PII dans la télémétrie, contournement de
version/idempotence ou impossibilité de suspendre.

| Décision | Condition |
|---|---|
| `PASS` | tous les scénarios applicables sont PASS et les preuves sont référencées |
| `PASS_AVEC_RESERVE` | uniquement réserve d’infrastructure explicitement acceptée, aucun P0 en échec |
| `BLOCKED` | fixture, service, compte ou preuve obligatoire indisponible |
| `FAIL` | résultat contraire à l’attendu ou garde-fou contournable |

## 7. Sign-off

| Rôle | Nom | Date | Décision | Commentaire |
|---|---|---|---|---|
| QA / recette |  |  |  |  |
| Produit |  |  |  |  |
| Sécurité |  |  |  |  |
| Données |  |  |  |  |

La recette ne vaut pas autorisation de mise en production. Toute activation pilote
réelle nécessite une décision séparée après le verrou qualité, les preuves de cette
fiche et la revue des réserves.
