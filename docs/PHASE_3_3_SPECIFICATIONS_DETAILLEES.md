# Phase 3.3 — Activités, tâches et rappels

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3 — Cœur CRM |
| Incrément | 3.3 — Activités, tâches et rappels |
| Version | 1.8 — 3.3 clôturé avec réserves après recette et verrou global vert |
| Prérequis | 3.2 implémenté et verrou local vert avec réserves `SEC-01` et `AUD-01` reportées à 3.6 |
| Statut | 3.3-A à 3.3-E implémentés ; clôture avec réserves, contrôles restants transférés à la recette finale 3.6 |
| Date | 10 septembre 2026 |
| Résultat visé | Chronologie commerciale, notes et interactions déclaratives, tâches, échéances, rappels internes et prochaine action |

## 1. Objectif

L’incrément 3.3 transforme le pipeline en outil de travail quotidien. Un membre doit pouvoir comprendre ce qui s’est
passé avec un prospect, consigner une interaction, préparer la prochaine action, suivre ses tâches et voir les retards
sans quitter Marketteo.

La chronologie métier n’est pas le journal d’audit. Elle est destinée aux équipes commerciales et contient les
informations utiles au suivi. L’audit reste une preuve technique minimisée, append-only et séparée. Une activité ou une
tâche ne déplace jamais automatiquement un prospect dans le pipeline.

## 2. Périmètre

### 2.1 Inclus

- chronologie unifiée d’un prospect : activités manuelles, événements de tâches et transitions de pipeline ;
- notes internes en texte simple ;
- appels, courriels et réunions déclaratifs, sans fonction d’envoi ni de téléphonie ;
- création, assignation, modification, réalisation, annulation et réouverture de tâches ;
- échéance obligatoire, priorité, rappel facultatif, report de rappel et indicateur de retard ;
- vue globale « Mes tâches » et vue organisation pour les rôles autorisés ;
- prochaine action dérivée et visible sur la fiche prospect, la liste et le Kanban ;
- nouveaux écrans et messages 3.3 disponibles en `fr-CA` et `en-CA` ;
- version optimiste, idempotence, RLS, audit, métriques, tests et documentation.

### 2.2 Hors périmètre

- envoi de courriel, appel téléphonique, SMS, réunion ou invitation calendrier ;
- notification externe par courriel, SMS, push navigateur ou application mobile ;
- synchronisation Google Calendar, Microsoft 365, téléphonie ou boîte courriel ;
- pièces jointes, contenu HTML, dictée, transcription ou enregistrement d’appel ;
- tâches récurrentes, séquences commerciales, automatisations et règles de relance ;
- commentaires collaboratifs en temps réel, mentions et abonnements ;
- opportunités, montants et prévisions, livrés en 3.4 ;
- résolution de lieux et bilinguisme complet des écrans existants, livrés en 3.5.

## 3. Vocabulaire et principes

Une **activité** est un fait commercial saisi volontairement : note interne, appel, courriel ou réunion. Elle peut
décrire un événement passé ou immédiat, mais jamais une action future. Une **tâche** décrit une action à réaliser et
porte une échéance. Un **rappel** est un signal interne attaché à une tâche ; il n’est ni un message envoyé au prospect
ni une preuve de consentement.

La **chronologie commerciale** agrège des sources métier sans les recopier : activités, événements de tâches et
transitions 3.2. Le **journal d’activité** existant conserve sa fonction d’audit technique et réglementaire. Les deux
vues ne doivent pas être confondues dans l’interface.

## 4. Activités commerciales

### 4.1 Types contrôlés

| Code stable | Libellé initial | Données particulières |
| --- | --- | --- |
| `note` | Note interne | Résumé et note ; aucune direction ni issue |
| `call` | Appel déclaré | Direction, issue et canal téléphonique facultatif |
| `email` | Courriel déclaré | Direction, issue et canal courriel facultatif |
| `meeting` | Réunion déclarée | Issue et contact facultatif |

Les codes restent en anglais dans l’API et la base. Les libellés visibles sont livrés en `fr-CA` et `en-CA` dès 3.3 ;
la phase 3.5 généralisera la préférence linguistique aux écrans antérieurs. Une activité `call` ou `email` exige une
direction `inbound` ou `outbound`. Une note n’accepte aucune direction.

Issues initiales :

- appel : `connected`, `voicemail`, `no_answer`, `wrong_number`, `other` ;
- courriel : `sent`, `received`, `bounced`, `other` ;
- réunion : `completed`, `no_show`, `cancelled`, `other`.

Le résumé contient de 1 à 160 caractères et la note facultative au plus 4 000 caractères. Les contenus sont normalisés,
conservés et rendus comme texte simple. Aucun HTML, Markdown actif, lien enrichi ou fichier n’est accepté. `occurred_at`
doit être horodaté avec fuseau et ne peut pas être dans le futur au-delà d’une tolérance d’horloge de cinq minutes.

### 4.2 Immutabilité et correction

Une activité publiée n’est ni éditée ni supprimée. Une erreur est corrigée par une nouvelle activité liée à l’originale
avec `corrects_activity_id` et un motif contrôlé : `incorrect_time`, `incorrect_type`, `incorrect_content`, `duplicate`
ou `other`. Le motif `other` exige une note de correction de 1 à 500 caractères.

La chronologie montre l’original comme corrigé et la nouvelle version comme correction active. Cette règle préserve
l’historique sans obliger l’utilisateur à conserver une information fausse comme vérité courante.

### 4.3 Contacts, canaux et permission

Une activité peut référencer un contact et, pour `call` ou `email`, un canal direct existant du même prospect. Le
serveur enregistre un instantané contrôlé de la permission du canal au moment de la déclaration : `allowed`, `unknown`
ou `restricted`.

La déclaration d’une interaction passée reste possible lorsque la permission est inconnue ou restreinte afin de ne pas
masquer un fait historique. L’interface affiche alors un avertissement explicite et exige une confirmation. Cette saisie
n’autorise aucun contact futur, ne modifie jamais la permission et ne déclenche aucun envoi. Les activités entrantes
restent déclarables quel que soit l’état de permission.

## 5. Tâches et rappels

### 5.1 Cycle de vie d’une tâche

Une tâche appartient obligatoirement à un prospect et contient :

- un titre de 1 à 160 caractères et une description facultative de 2 000 caractères maximum ;
- un responsable membre actif de l’organisation ;
- une priorité parmi `low`, `normal`, `high` et `urgent` ;
- une échéance obligatoire ;
- un rappel facultatif ;
- un statut parmi `open`, `completed` et `cancelled` ;
- une version positive et les horodatages de création et de mise à jour.

La création produit `open`. La réalisation produit `completed` avec auteur et date. L’annulation produit `cancelled`
avec un motif contrôlé. Une tâche terminée ou annulée peut être rouverte avec la capacité appropriée, la version courante
et un motif. Aucune route ne supprime physiquement une tâche.

### 5.2 Concurrence et historique

Toute modification transmet la version lue. Deux commandes portant la même version ne peuvent pas réussir toutes les
deux ; la seconde reçoit `409 task_version_conflict`. Création, réalisation, annulation, réouverture, accusé de rappel
et report sont idempotents.

Chaque mutation ajoute dans la même transaction un événement métier append-only contenant l’action, les versions,
l’acteur et les champs contrôlés qui ont changé. Les titres, descriptions et notes ne sont jamais recopiés dans l’audit
technique.

### 5.3 Échéances et fuseau horaire

Les instants sont stockés en UTC. L’interface les affiche dans le fuseau IANA de l’organisation et indique ce fuseau à
côté du champ. L’API exige un ISO 8601 avec décalage ; une date locale inexistante ou ambiguë lors d’un changement
d’heure est refusée avec un code stable plutôt que corrigée silencieusement.

Une nouvelle échéance doit être future. Une tâche ouverte est `overdue` lorsque son échéance UTC est passée. `overdue`
est un état calculé par le serveur, jamais une valeur persistée ni fournie par le navigateur.

### 5.4 Rappels internes

`reminder_at` est facultatif et initialement antérieur ou égal à l’échéance. Lorsque cet instant est atteint et que la
tâche est encore ouverte, elle apparaît dans « Mes rappels ». Le membre peut :

- accuser réception, ce qui masque le rappel sans terminer la tâche ;
- reporter le rappel à une date future de sept jours maximum ;
- terminer ou ouvrir la tâche.

Le calcul se fait à la lecture depuis PostgreSQL ; aucun worker, cron, courriel ou push n’est requis en 3.3. Ce choix
évite les notifications perdues et reste correct avec plusieurs instances API. Un rappel terminé, annulé, archivé ou
lié à un prospect archivé n’est jamais présenté comme actif.

## 6. Prochaine action et intégration au pipeline

La prochaine action d’un prospect est la tâche `open` dont l’échéance est la plus proche, avec départage par priorité
décroissante puis identifiant. Elle est dérivée côté serveur grâce à un index dédié ; elle n’est pas dupliquée dans la
table `prospects`.

La fiche, la liste des prospects et la carte Kanban montrent seulement le titre court, l’échéance, le responsable et
l’état `à venir`, `aujourd’hui` ou `en retard`. La description reste sur la fiche de tâche. Un changement de tâche ne
modifie jamais `stage_code`, et une transition de pipeline ne crée jamais automatiquement une tâche.

## 7. Acteurs et capacités

| Capacité | Administrateur | Gestionnaire | Commercial |
| --- | :---: | :---: | :---: |
| `activities:read` | Oui | Oui | Oui |
| `activities:create` | Oui | Oui | Oui |
| `activities:correct:self` | Oui | Oui | Oui |
| `activities:correct:any` | Oui | Oui | Non |
| `tasks:read` | Oui | Oui | Oui |
| `tasks:create` | Oui | Oui | Oui |
| `tasks:update:assigned` | Oui | Oui | Oui |
| `tasks:manage` | Oui | Oui | Non |

Administrateur et Gestionnaire peuvent assigner et gérer toute tâche de l’organisation. Commercial crée par défaut une
tâche pour lui-même et ne peut mettre à jour, terminer, annuler ou rouvrir qu’une tâche qui lui est assignée. Tous les
membres actifs voient les activités et tâches de l’organisation afin de permettre la collaboration commerciale.

Un responsable désactivé reste visible dans l’historique. Ses tâches ouvertes ne sont pas réassignées automatiquement ;
elles sont signalées aux Administrateurs et Gestionnaires jusqu’à réaffectation. L’administrateur de plateforme n’a
aucun accès implicite aux activités ou tâches d’une organisation.

## 8. Modèle de données cible

### 8.1 `prospect_activities`

- `id`, `organization_id`, `prospect_id`, `actor_id` ;
- `contact_id` et `contact_channel_id` facultatifs ;
- `activity_type`, `direction`, `outcome_code` ;
- `summary`, `note`, `occurred_at`, `created_at` ;
- `permission_state_snapshot` facultatif ;
- `corrects_activity_id`, `correction_reason_code` et `correction_reason_note` facultatifs ;
- `idempotency_key_hash` et `command_fingerprint`.

La table est append-only. Les clés composites incluant `organization_id` empêchent toute référence croisée entre
organisations. Une contrainte interdit les combinaisons type/direction/issue invalides.

### 8.2 `prospect_tasks`

- `id`, `organization_id`, `prospect_id`, `created_by_id`, `assignee_id` ;
- `title`, `description`, `priority`, `status` ;
- `due_at`, `reminder_at`, `reminder_acknowledged_at`, `reminder_snoozed_until` ;
- `completed_at`, `completed_by_id`, `cancelled_at`, `cancelled_by_id` ;
- `version`, `created_at`, `updated_at`.

Les index couvrent la prochaine action, les tâches d’un responsable, les retards, les rappels dus et la pagination. Les
contraintes garantissent la cohérence statut/horodatages.

### 8.3 `prospect_task_events`

- `id`, `organization_id`, `prospect_id`, `task_id`, `actor_id` ;
- `event_type`, `from_status`, `to_status`, `from_version`, `resulting_version` ;
- `changed_fields`, ensemble fermé sans contenu libre ;
- `reason_code`, `occurred_at`.

Cette table est append-only et alimente la chronologie métier. Elle ne remplace pas l’audit transactionnel.

La migration `20260905_0016` succède à `20260904_0015`. Elle crée les trois tables, contraintes, index, politiques
RLS forcées, privilèges minimaux et nouvelles capacités. La migration additive `20260905_0017` ajoute les clés
d’idempotence et empreintes de commande des tâches et de leurs événements. Elles ne transforment aucune donnée
historique en activité ou tâche.

## 9. API proposée

| Méthode et route | Capacité | Usage |
| --- | --- | --- |
| `GET /api/prospects/{prospect_id}/timeline` | `activities:read` | Chronologie unifiée, filtrée et paginée |
| `POST /api/prospects/{prospect_id}/activities` | `activities:create` | Déclarer une note ou interaction |
| `POST /api/activities/{activity_id}/corrections` | correction propre ou globale | Ajouter une correction append-only |
| `GET /api/tasks` | `tasks:read` | Tâches de l’organisation, personnelles ou filtrées |
| `GET /api/tasks/{task_id}` | `tasks:read` | Détail d’une tâche visible |
| `POST /api/prospects/{prospect_id}/tasks` | `tasks:create` | Créer une tâche idempotente |
| `PATCH /api/tasks/{task_id}` | mise à jour assignée ou gestion | Modifier titre, description, responsable, priorité, échéance ou rappel |
| `POST /api/tasks/{task_id}/complete` | mise à jour assignée ou gestion | Terminer avec version et idempotence |
| `POST /api/tasks/{task_id}/cancel` | mise à jour assignée ou gestion | Annuler avec version et motif |
| `POST /api/tasks/{task_id}/reopen` | mise à jour assignée ou gestion | Réouvrir avec version et motif |
| `POST /api/tasks/{task_id}/reminder/acknowledge` | mise à jour assignée ou gestion | Accuser réception du rappel |
| `POST /api/tasks/{task_id}/reminder/snooze` | mise à jour assignée ou gestion | Reporter le rappel |
| `GET /api/reminders/due` | `tasks:read` | Rappels actifs du membre connecté |

La chronologie accepte les filtres `kind`, `activity_type`, `actor_id`, `occurred_from` et `occurred_to`. La liste des
tâches accepte `scope=mine|organization`, statuts, priorités, responsable, prospect, retard et intervalle d’échéance.
Les limites sont 25 par défaut et 100 maximum.

Les curseurs sont opaques, signés, liés à l’organisation, au prospect et à l’empreinte des filtres. Toutes les réponses
privées portent `Cache-Control: no-store`. Les mutations exigent JSON, origine approuvée, CSRF, version lorsque requise
et clé d’idempotence. Les erreurs utilisent les contrats `401`, `403`, `404`, `409`, `422` et `503` existants.

## 10. Chronologie commerciale

Chaque élément retourné porte `kind`, `occurred_at`, `actor`, un sous-type stable et les données métier autorisées :

- `activity` : type, direction, issue, résumé, note et état de correction ;
- `task_event` : action, statut, responsable, échéance et champs changés ;
- `stage_transition` : étapes source/cible et motif contrôlé.

L’ordre est `occurred_at DESC`, puis `id DESC`. Les transitions existantes sont lues depuis
`prospect_stage_transitions` et ne sont pas recopiées dans `prospect_activities`. Un filtre ou changement d’organisation
invalide le curseur.

## 11. Interface utilisateur

La fiche prospect reçoit deux zones :

1. **Chronologie** avec filtres, pagination, formulaire rapide « Ajouter une note » et menu « Déclarer une activité » ;
2. **Tâches** avec prochaine action, tâches ouvertes et actions de création, réalisation, report et annulation.

La navigation principale ajoute **Mes tâches**. Cette page propose les vues `En retard`, `Aujourd’hui`, `À venir`,
`Terminées` et, pour Administrateur/Gestionnaire, `Organisation`. Un compteur de rappels dus est affiché dans la
navigation, mais aucune notification système n’est envoyée.

Le formulaire d’activité indique clairement « Déclaration uniquement — aucun message ou appel n’est envoyé ». Lorsqu’un
canal `unknown` ou `restricted` est choisi, un dialogue explique la permission et demande confirmation avant la seule
inscription historique.

Toutes les actions sont accessibles au clavier. Les dialogues gèrent le focus, les statuts utilisent `aria-live`, les
dates affichent le fuseau, les priorités et retards ne reposent pas seulement sur la couleur, et les tests axe couvrent
les parcours principaux dans les deux langues.

## 12. Audit et observabilité

Actions d’audit ajoutées :

- `prospect.activity_created` et `prospect.activity_corrected` ;
- `prospect.task_created`, `prospect.task_updated`, `prospect.task_completed` ;
- `prospect.task_cancelled`, `prospect.task_reopened` et `prospect.task_reminder_changed`.

Les métadonnées d’audit contiennent seulement type/direction/issue contrôlés, versions, statut, code de motif et liste
fermée des champs modifiés. Elles excluent résumé, note, description, nom du prospect, valeur du canal et toute donnée
Google. La mutation métier, son événement de chronologie et son audit sont validés dans la même transaction.

Journaux JSON : résultat, action, type contrôlé, conflit, durée et `request_id`, sans identifiant métier ni contenu libre.
Métriques à cardinalité bornée :

- `crm_activity_command_total{type,result}` ;
- `crm_task_command_total{action,result}` ;
- `crm_task_version_conflict_total` ;
- `crm_timeline_request_total{result}` ;
- durées des commandes et lectures.

## 13. Sécurité, conservation et conformité

- RLS activée et forcée sur les trois tables ; l’organisation vient exclusivement de la session serveur ;
- les clés étrangères composites interdisent de lier un prospect, contact, canal ou membre d’une autre organisation ;
- un prospect archivé est en lecture seule et exclu des listes de tâches actives et rappels ;
- activités, tâches et événements suivent la conservation du prospect parent ; aucun effacement physique indépendant
  n’est exposé en 3.3 et un hold sur le prospect protège l’ensemble ;
- les textes libres sont bornés, normalisés et rendus sans interprétation ;
- aucun contenu n’est écrit dans `localStorage`, `sessionStorage`, IndexedDB ou Cache API ;
- aucune activité n’est créée automatiquement depuis Google, un import ou une transition de pipeline ;
- aucune déclaration d’activité ne crée une permission de contact ou une provenance de données.

## 14. Atomicité, erreurs et indisponibilité

Chaque commande écrit dans une transaction PostgreSQL unique : ressource, événement métier, idempotence et audit. Une
erreur sur l’une de ces écritures annule tout. Les ressources d’une autre organisation répondent comme absentes.

Codes spécifiques proposés :

- `activity_validation_failed`, `activity_correction_forbidden` ;
- `task_validation_failed`, `task_version_conflict`, `task_assignee_invalid` ;
- `task_transition_invalid`, `reminder_time_invalid` ;
- `prospect_archived_read_only` et `crm_activity_service_unavailable`.

Le frontend recharge la ressource après `409`, conserve le formulaire non sensible en mémoire React pendant l’erreur et
ne réessaie jamais automatiquement une mutation avec une nouvelle clé.

## 15. Tests et critères d’acceptation

1. Les quatre types d’activités acceptent seulement les combinaisons direction/issue définies et refusent le futur.
2. Une note est rendue comme texte, bornée et absente des logs, métriques et métadonnées d’audit.
3. Une correction ajoute une nouvelle activité liée sans modifier ni supprimer l’originale.
4. Un appel ou courriel sur canal inconnu/restreint exige confirmation, conserve l’instantané et ne change pas la permission.
5. Une activité entrante reste déclarable et aucune activité n’envoie de message ni ne déplace le pipeline.
6. Une tâche respecte responsable actif, priorité, échéance future, statut et contraintes de rappel.
7. Le retard et les rappels dus sont calculés côté serveur en UTC et affichés dans le fuseau de l’organisation.
8. Accusé, report, réalisation, annulation et réouverture respectent version, idempotence et cycle de vie.
9. Deux mises à jour concurrentes d’une tâche donnent exactement un succès et un `409` sans écriture partielle.
10. Commercial gère ses tâches assignées et corrige ses activités ; Administrateur/Gestionnaire gèrent l’organisation.
11. Un membre désactivé reste historique, ne peut agir et ses tâches ouvertes sont signalées pour réaffectation.
12. La chronologie fusionne activités, événements de tâches et transitions sans doublon, dans un ordre et une pagination stables.
13. La prochaine action est la première tâche ouverte attendue et disparaît des vues actives avec un prospect archivé.
14. Deux organisations ne voient ni ne référencent leurs activités, tâches, événements, responsables, contacts ou canaux.
15. Les parcours `fr-CA`/`en-CA`, clavier, focus, lecteurs d’écran, fuseaux, retards et avertissements passent les tests React/axe.
16. Ruff, format Ruff, mypy, pytest PostgreSQL/RLS réel, Alembic, ESLint, Vitest/axe, build et verrou local sont verts sans skip.

## 16. Migration, compatibilité et retour arrière

La migration 3.3 est additive. Elle crée tables, index, contraintes, capacités, politiques RLS et privilèges. Elle ne
modifie pas les activités historiques car aucune activité 3.3 n’existe encore. La chronologie réemploie directement
l’historique de pipeline 3.2.

Le déploiement applique la migration avant le backend. Le frontend n’affiche les nouveaux écrans qu’après disponibilité
des routes. Un retour arrière applicatif masque les formulaires et tâches mais conserve les données append-only. En
staging ou production, toute correction de schéma est additive ; le downgrade destructeur reste réservé aux
environnements éphémères.

## 17. Séquence d’implémentation proposée

L’incrément produit 3.3 est réalisé en cinq sous-lots techniques successifs.

### 17.1 — 3.3-A Socle backend

- domaine des activités, tâches, événements et rappels ;
- capacités et matrice de rôles ;
- migration `20260905_0016`, contraintes, index, privilèges et RLS ;
- ports applicatifs et dépôts PostgreSQL de base.

Sortie obligatoire : tests domaine, migration aller, `current`, `check`, RLS et isolation réels verts.

### 17.2 — 3.3-B Cas d’utilisation et API

- commandes transactionnelles d’activités et de tâches ;
- lecture de chronologie, listes de tâches et rappels dus ;
- concurrence, versions, idempotence, curseurs et erreurs stables ;
- événements métier, audit minimisé, métriques et journaux structurés.

Sortie obligatoire : Ruff, format Ruff, mypy et tests backend ciblés, transactionnels et multi-organisation verts.

### 17.3 — 3.3-C Chronologie et activités

- chronologie intégrée à la fiche prospect ;
- ajout de note et déclaration d’appel, courriel ou réunion ;
- correction append-only et avertissement lié à la permission du canal ;
- écrans et messages nouveaux en `fr-CA` et `en-CA`.

Sortie obligatoire : ESLint, Vitest, tests React/axe, tests API ciblés et build frontend verts.

### 17.4 — 3.3-D Tâches, rappels et prochaine action

- création et cycle de vie des tâches ;
- vue « Mes tâches », rappels dus, accusé et report ;
- prochaine action sur la fiche prospect, la liste et le Kanban ;
- gestion des conflits, responsables désactivés, retards et fuseaux horaires.

Sortie obligatoire : tests backend/frontend ciblés, concurrence, fuseaux, accessibilité et régression Kanban verts.

### 17.5 — 3.3-E Recette, documentation et verrou final

- rapport d’implémentation et revue de cohérence ;
- documentation technique et utilisateur actualisée ;
- document unique de recette fonctionnelle 3.3 ;
- régression complète et verrou qualité local sans skip.

La recette fonctionnelle est exécutée une seule fois après 3.3-E sur l’ensemble des parcours 3.3. Les tests automatisés
sont néanmoins obligatoires après chaque sous-lot : un sous-lot rouge bloque le démarrage du suivant. Aucune
fonctionnalité partielle n’est exposée en production avant la validation globale de 3.3.

## 18. Seize décisions validées

1. 3.3 couvre quatre activités déclaratives : `note`, `call`, `email` et `meeting` ; aucun envoi, appel ou calendrier n’est intégré.
2. Les activités publiées sont append-only ; toute correction crée une nouvelle activité liée et conserve l’originale.
3. La chronologie unifie activités, événements de tâches et transitions 3.2 sans dupliquer les transitions en base.
4. Les activités futures sont interdites : une action à venir est toujours représentée par une tâche.
5. Déclarer un contact sur canal inconnu ou restreint reste possible avec avertissement et instantané, sans modifier la permission.
6. Une tâche appartient à un prospect, porte une échéance obligatoire et suit uniquement `open`, `completed` ou `cancelled`.
7. Toutes les dates sont stockées en UTC, affichées dans le fuseau IANA de l’organisation et les heures ambiguës sont refusées.
8. Les rappels sont internes et calculés à la lecture ; aucun worker ou canal de notification externe n’est livré en 3.3.
9. Accusé de rappel et report de sept jours maximum sont permis sans terminer la tâche.
10. La prochaine action est dérivée de la première tâche ouverte ; elle n’est pas dupliquée dans `prospects`.
11. Administrateur et Gestionnaire gèrent toutes les tâches ; Commercial gère ses tâches assignées et ses propres corrections.
12. Un membre désactivé reste visible dans l’historique et ses tâches sont signalées, sans réaffectation automatique.
13. Toute mutation est versionnée lorsqu’elle modifie un état, idempotente et atomique avec événement métier et audit.
14. Activités et tâches suivent la conservation du prospect parent ; un prospect archivé est en lecture seule et sans rappel actif.
15. RLS, clés composites locataires, CSRF, `no-store`, bilinguisme des nouveaux écrans, absence de stockage navigateur et minimisation des logs/audits sont obligatoires.
16. 3.3 peut être clôturé avec réserves après migration réelle, recette renseignée, zéro skip et verrou qualité vert ; tout contrôle fonctionnel non exécuté reste nommé, non réputé validé et transféré à la recette finale 3.6 avec `SEC-01` et `AUD-01`. Ces réserves demeurent bloquantes avant la préproduction.

## 19. Décision de sortie

Les seize décisions de la section 18 ont été validées par le responsable produit le 5 septembre 2026. Le découpage en
cinq sous-lots 3.3-A à 3.3-E, les tests automatisés après chaque sous-lot et la recette fonctionnelle regroupée à la fin
ont été validés le même jour. Toute modification qui ajoute un canal externe, une automatisation, une suppression
physique, une transition automatique du pipeline ou une permission implicite nécessite une nouvelle décision produit
et conformité.

Le sous-lot **3.3-C — Chronologie et activités** est implémenté. La fiche prospect charge la chronologie en parallèle
avec le profil et propose les quatre activités déclaratives en `fr-CA` et `en-CA`. Le formulaire n’envoie aucun message ;
pour un appel ou un courriel, il peut associer un canal existant, affiche son avertissement de permission et l’API fige
l’instantané de cette permission. Une correction ajoute une nouvelle activité liée sans modifier l’original. Le détail des
contrôles est consigné dans [`PHASE_3_3_C_RAPPORT_IMPLEMENTATION.md`](PHASE_3_3_C_RAPPORT_IMPLEMENTATION.md).

Le sous-lot **3.3-D — Tâches, rappels et prochaine action** est implémenté. Les tâches sont créées pour un membre
actif, portent une échéance UTC et peuvent être terminées, annulées, rouvertes, accusées ou reportées dans la limite de
sept jours. La vue « Mes tâches » charge en parallèle les tâches ouvertes et les rappels dus. La prochaine action reste
dérivée de la première tâche ouverte et est restituée par l’API sur la fiche, la liste et le Kanban. Les tâches affectées à
un membre désactivé restent lisibles et signalées, sans réaffectation automatique. Les migrations et la recette
fonctionnelle globale sont volontairement reportées à 3.3-E. Le détail est consigné dans
[`PHASE_3_3_D_RAPPORT_IMPLEMENTATION.md`](PHASE_3_3_D_RAPPORT_IMPLEMENTATION.md).

Le sous-lot **3.3-E — Recette, documentation et verrou final** est terminé. La tête Alembic attendue est
`20260905_0019`, le pipeline Azure et le verrou local utilisent cette même révision, et la recette regroupée est publiée
dans [`RECETTE_FONCTIONNELLE_3_3_ACTIVITES_TACHES_RAPPELS.md`](RECETTE_FONCTIONNELLE_3_3_ACTIVITES_TACHES_RAPPELS.md).
Le verrou global est vert avec 274 tests backend et 162 tests frontend, sans échec ni test ignoré. La clôture avec
réserves est prononcée le 10 septembre 2026 ; les contrôles fonctionnels non exécutés sont transférés à la recette
finale 3.6. Le détail est consigné dans [`PHASE_3_3_E_RAPPORT_IMPLEMENTATION.md`](PHASE_3_3_E_RAPPORT_IMPLEMENTATION.md).

La migration locale a atteint `20260905_0019 (head)` et `alembic check` n’a détecté aucune opération. Le verrou global
du 10 septembre 2026 est vert. `TASK-02`, `TASK-05`, `TASK-06`, `PERM-01`, `ISO-01`, `SEC-3.3` et l’audit minimisé
3.3 restent des réserves explicites à rejouer en 3.6 avant la préproduction.
