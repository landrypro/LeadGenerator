# IMP-A4 — Dossier de préparation

> **Statut :** implémentation en cours sur `codex/pre-phase-5-implementation` ; quatre décisions confirmées le 3 octobre 2026.
> **Portée :** raccorder l'API au parcours `Nouveau prospect`, consommer le job PostgreSQL avec un worker contrôlé et
> créer au plus une tâche CRM interne après une garde fraîche.
> **Limites maintenues :** flags désactivés par défaut, données synthétiques uniquement, aucune production, aucun appel
> IA, aucun envoi, aucun connecteur externe et aucune modification automatique du pipeline.

## 1. Objectif et backlog couvert

IMP-A4 rend exécutable, dans l'environnement local isolé, le chemin préparé par IMP-A1 à IMP-A3 :

```text
requête authentifiée
  → prospect canonique + Prévol + admission + job (une transaction)
  → commit
  → worker prospect_worker
  → seconde garde sur les données fraîches
  → tâche CRM canonique unique
  → admission et job terminaux
```

| Item | Résultat runtime attendu | Oracle principal |
|---|---|---|
| `AUT-4201` | l'API produit une admission et un job idempotents | même commande = même parcours, jamais un second effet |
| `AUT-4202` | le worker refait la garde juste avant l'écriture CRM | révocation ou suspension gagnante = aucune tâche |
| `AUT-4203` | une issue d'effet incertaine n'est pas rejouée aveuglément | recherche par clé puis `to_verify` si aucune preuve fiable |
| `AUT-4204` | une tâche interne unique est créée par le serveur | responsable actif, priorité normale, échéance `+24 h` |
| `AUT-4702` | le worker contrôlé fonctionne dans Docker/WSL | rôle DB dédié, bail, heartbeat et arrêt propres |
| `AUT-4703/04/05` | les preuves D2/D3 deviennent exécutables | garde, concurrence, suspension et reprise démontrées |

## 2. Point de départ vérifié

| Élément déjà disponible | Réutilisation IMP-A4 | Écart restant |
|---|---|---|
| `automation_admissions` et contrat IMP-A3 | identité, Prévol, décision, prospect, job et tâche finale | stocker durablement le responsable choisi ; garantir un seul job par admission |
| file PostgreSQL durable | claim, bail, heartbeat, annulation, retry et événements | enregistrer le handler `automation_new_prospect_prepare:1` |
| worker `backend.app.cli.worker` | processus séparé, rôle `prospect_worker`, contrôle de l'acteur humain | handler Automation et traitement spécifique des états d'admission |
| `CreateTaskUseCase` et dépôts CRM | validation du prospect, du responsable, idempotence, événement et audit | permettre une invocation serveur atomique sans donner des écritures larges au worker |
| flags, Prévol et décisions IMP-A1/A2 | première garde et données à relire | dépôt d'exécution et recalcul frais de la seconde garde |
| endpoint manuel `POST /api/prospects` | authentification, CSRF, tenant serveur et capability `prospects:create` | bloc Automation optionnel et réponse d'admission asynchrone |

Deux compléments de schéma sont nécessaires dans la migration IMP-A4 :

- `assigned_membership_id` dans `automation_admissions`, avec FK tenantisée vers `memberships`, car le choix humain
  strict ne peut pas être reconstruit depuis le job actuel ;
- unicité partielle de `(organization_id, job_id)` quand `job_id IS NOT NULL`, afin de prouver la relation un job ↔ une
  admission.

`created_at` de l'admission reste l'instant canonique `admitted_at` utilisé pour calculer l'échéance `+24 h`. Aucune
date fournie par le navigateur ne devient une autorité métier.

## 3. Périmètre proposé

### Inclus

- première intégration verticale sur la création manuelle de prospect ;
- extension stricte de la commande API avec une demande Automation explicite ;
- écriture atomique du prospect, du Prévol, de la décision, de l'admission et du job ;
- réponse `201` contenant le prospect et l'état d'admission, sans attendre le worker ;
- handler worker `automation_new_prospect_prepare:1` ;
- double garde et création idempotente de la tâche CRM ;
- transitions `prepared`, `blocked`, `cancelled` et `to_verify` ;
- RLS, privilèges minimaux, audit et métriques sans PII ;
- tests avec deux tenants, deux workers et données fictives.

### Exclus

- activation automatique pour Google, CSV, Meta ou Web/API ;
- création d'un principal métier `automation-system` ;
- attribution automatique, round-robin ou aléatoire ;
- UI complète du Passeport ;
- brouillon ou communication externe ;
- fournisseur IA réel ;
- activation d'un flag par défaut ou déploiement en production.

Les autres sources conserveront le même cas d'usage d'admission. Elles seront raccordées séparément après la preuve du
premier chemin manuel, sans créer de logique worker propre à chaque source.

## 4. Contrat API proposé

La création manuelle conserve `POST /api/prospects`. Un bloc optionnel et fermé déclenche le parcours Automation :

```text
CreateProspectRequest {
  internal_alias,
  automation?: {
    playbook_code: "new_prospect",
    assigned_membership_id,
    idempotency_key
  }
}
```

Règles :

- sans bloc `automation`, le comportement CRM actuel reste inchangé ;
- avec ce bloc, le serveur exige simultanément `prospects:create`, `automation:prepare:self` et `tasks:create` ;
- `organization_id`, acteur, membership demandeur, horodatage, corrélation et version du Playbook viennent du serveur ;
- les champs inconnus sont refusés ; la clé brute n'est ni journalisée ni persistée ;
- si les flags ne permettent pas la préparation, la requête n'écrit aucun prospect partiel : elle est refusée avant le
  commit avec un code métier stable ;
- un replay strict retourne le même prospect et la même admission ; une même clé avec une charge différente retourne
  `409 idempotency_conflict` ;
- la réponse n'attend pas la tâche : elle expose `admission_id`, `job_id`, `state=ready_to_prepare` et la corrélation.

La transaction applicative effectue : création canonique du prospect, calcul et persistance du Prévol et de sa décision,
création de l'admission avec le responsable désigné, puis enqueue du job. Le job n'est visible au worker qu'après commit.

## 5. Contrat du worker contrôlé

### 5.1 Identité et autorité

Le processus continue d'utiliser le rôle PostgreSQL `prospect_worker`. Ce rôle est un **principal technique** et ne
devient pas une autorité métier :

- le job garde `actor_id` et `actor_membership_id` de l'utilisateur demandeur ;
- le worker revérifie que cet utilisateur, son membership et l'organisation sont encore actifs ;
- il revérifie le rôle courant, dont la matrice de capacités versionnée accorde actuellement
  `automation:prepare:self` et `tasks:create` aux rôles admissibles (`sales`, `manager`, `admin`) ;
- l'audit distingue l'initiateur humain du processus technique ;
- un job sans acteur humain valide est refusé dans IMP-A4. Le principal `automation-system`, prévu pour de futurs
  déclencheurs automatiques, reste hors périmètre.

### 5.2 Job v1 fermé

```text
type             = automation_new_prospect_prepare
schema_version   = 1
subject_type     = prospect
subject_id       = prospect_id
organization_id  = tenant du prospect
actor_id         = utilisateur ayant demandé l'admission
actor_membership = membership ayant demandé l'admission
idempotency      = digest de l'identité fonctionnelle
```

Le handler retrouve l'admission par son `job_id` unique. Il ne reçoit ni titre libre, ni nom du prospect, ni permission,
ni liste de capabilities dans une charge à faire confiance.

### 5.3 Seconde garde

Dans une transaction fraîche, immédiatement avant l'effet, le handler relit et vérifie :

1. tenant, organisation, utilisateur demandeur et membership actifs ;
2. capabilities actuelles `automation:prepare:self` et `tasks:create` ;
3. flags global, organisation et Playbook ;
4. Playbook/version actifs, non suspendus et identiques à l'admission ;
5. Prévol non expiré, décision préparatoire et empreinte CRM toujours actuelle ;
6. prospect existant, non archivé et dans le même tenant ;
7. responsable choisi actif et dans le même tenant ;
8. admission encore `ready_to_prepare`, job correspondant et absence de tâche terminale concurrente.

La seconde garde recalcule depuis les tables canoniques. Elle ne considère jamais le Prévol comme un droit acquis.

## 6. Écriture CRM et reprise sans doublon

La création de tâche, son événement `created`, son audit et la transition de l'admission vers `prepared` doivent être
commités dans **une seule transaction métier**. La clé d'effet reste déterministe :

```text
automation-admission:<idempotency_key_digest>
```

Le job est marqué `completed` après ce commit. Si le worker tombe entre les deux :

1. le job peut être repris après expiration du bail ;
2. le handler recherche d'abord la tâche par clé d'effet ;
3. si elle existe avec la bonne empreinte, il rattache/réaffirme `prepared` puis termine le job ;
4. si la clé existe avec une autre empreinte, il bloque sur conflit ;
5. si l'issue du commit ne peut pas être prouvée, il place l'admission en `to_verify` et n'appelle pas une seconde fois la
   commande de création.

Les erreurs survenues avant toute tentative d'effet et classées transitoires peuvent suivre le retry borné de la file.
Une suspension, une capacité retirée, un responsable inactif, un Prévol obsolète ou une annulation sont des résultats
métier sans retry automatique.

## 7. Persistance, RLS et privilèges

La migration réalisée est `20261003_0034` et est réversible. Elle prépare :

- `assigned_membership_id` et sa FK tenantisée : nullable uniquement pour laisser les admissions historiques IMP-A3
  consultables, obligatoire pour toute admission créée par la commande IMP-A4 ;
- index unique partiel sur le `job_id` ;
- politique RLS `SELECT/UPDATE` dédiée à `prospect_worker` sur `automation_admissions` ;
- lectures worker strictement nécessaires sur flags, Playbooks, Prévols, décisions, prospect et responsable ;
- une surface d'écriture CRM étroite pour la création atomique de la tâche et de ses événements ;
- retrait symétrique des politiques, grants, index et colonne au rollback.

Le principe recommandé est de ne pas accorder `INSERT/UPDATE` général sur toutes les tables CRM. Une commande SQL
bornée dans `app_private`, ou une unité de travail équivalente avec des grants colonne/table minimaux, doit :

- imposer le tenant issu de la session ;
- accepter uniquement les identifiants et valeurs normalisés nécessaires ;
- vérifier les préconditions dans la même transaction ;
- créer ou retrouver l'effet idempotent ;
- lier la tâche à l'admission ;
- refuser tout usage par `prospect_app` et `PUBLIC`.

## 8. Transitions attendues

| Situation observée par le worker | Admission | Job | Effet CRM |
|---|---|---|---|
| garde valide, tâche créée ou retrouvée | `prepared` | `completed` | une tâche exactement |
| flag/suspension/capability révoqué | `blocked` | `failed` non rejouable | aucun |
| responsable absent ou inactif | `blocked` + `owner_unavailable` | `failed` non rejouable | aucun |
| annulation avant effet | `cancelled` | `cancelled` | aucun |
| erreur transitoire avant effet | inchangée/`ready_to_prepare` | `queued` selon backoff | aucun |
| effet potentiellement commité, preuve impossible | `to_verify` + `effect_uncertain` | `failed` non rejouable | jamais de retry aveugle |
| replay après tâche déjà prouvée | `prepared` | `completed` | aucune seconde tâche |

Une annulation reçue après le commit métier ne supprime pas la tâche et ne transforme pas `prepared` en `cancelled`.

## 9. Découpage de réalisation proposé

| Lot | Travail | Sortie vérifiable |
|---|---|---|
| A4.1 | migration 0034, modèle et rollback | responsable persistant, job unique, RLS worker fermée |
| A4.2 | dépôt/cas d'usage d'admission transactionnelle | prospect + Prévol + décision + admission + job atomiques |
| A4.3 | schéma API, route manuelle et mapping d'erreurs | droits croisés, replay stable, aucun tenant fourni par le client |
| A4.4 | dépôt d'exécution, seconde garde et commande CRM atomique | tâche unique ou blocage explicite |
| A4.5 | handler worker, retry, annulation et réconciliation | bail perdu/crash sans doublon |
| A4.6 | audit, métriques et preuves D2/D3 | corrélation inspectable sans PII |
| A4.7 | verrou qualité, migration/rollback Docker WSL | clôture reproductible sur PostgreSQL réel |

## 10. Matrice de tests de clôture

### API et transaction

- requête sans session, sans CSRF ou sans l'une des trois capabilities : refus et zéro écriture ;
- tenant injecté dans la charge ou champ inconnu : refus ;
- bloc Automation absent : création manuelle actuelle inchangée ;
- même clé/même charge : même prospect, admission et job ;
- même clé/charge différente : `409`, aucun nouvel objet ;
- panne avant commit : ni prospect, ni Prévol, ni admission, ni job ;
- flags désactivés : refus fermé et aucun job réclamable.

### Worker, garde et sécurité

- membership demandeur désactivé après admission : aucune tâche ;
- capability Automation ou CRM retirée après admission : aucune tâche ;
- suspension globale, organisation ou Playbook après admission : aucune tâche ;
- Prévol expiré ou prospect modifié : aucune tâche avec l'ancien snapshot ;
- responsable désactivé ou d'un autre tenant : `owner_unavailable`, aucune attribution de repli ;
- `prospect_app` ne peut pas écrire les tables Automation ;
- `prospect_worker` ne peut ni lire un autre tenant ni modifier arbitrairement une tâche existante ;
- job falsifié ou sans acteur humain : refus avant effet.

### Idempotence et résilience

- deux workers réclament/reprennent le même travail : une tâche ;
- crash avant effet : retry borné autorisé, une tâche finale ;
- crash après commit tâche mais avant `job.completed` : tâche retrouvée, aucun doublon ;
- perte de bail pendant le traitement : l'ancien worker ne peut plus finaliser ;
- timeout ambigu : `to_verify`, aucune seconde création ;
- annulation avant effet : `cancelled`, aucune tâche ;
- arrêt Docker puis redémarrage : reprise contrôlée depuis PostgreSQL.

### Migration et verrou

- `upgrade 0033 → 0034`, `current=head`, contrôle d'autogénération vide ;
- `downgrade 0034 → 0033`, puis nouvel `upgrade` ;
- tests unitaires domaine/use cases ;
- tests d'intégration PostgreSQL/RLS avec les rôles `prospect_app` et `prospect_worker` ;
- test réel du worker Docker ;
- Ruff, Pyright, Pytest réel, Vitest/axe et verrou qualité local complet.

## 11. Décisions confirmées le 3 octobre 2026

### Confirmation 1 — Premier point d'entrée API

**Décision confirmée :** commencer uniquement par `POST /api/prospects` (source manuelle), avec un bloc
`automation` explicite et optionnel. Sans ce bloc, le comportement actuel reste strictement identique. Google, CSV et
Meta réutiliseront plus tard le même cas d'usage, après validation de ce premier parcours.

**Ce que cette décision implique :** le premier test bout en bout reste petit et contrôlable ; aucune source existante ne
se met à produire des jobs silencieusement. L'alternative serait de raccorder toutes les sources dès IMP-A4, ce qui
multiplierait les transactions et scénarios de rollback avant d'avoir prouvé le worker.

**Statut : confirmée.** IMP-A4 raccorde d'abord la création manuelle explicite seulement.

### Confirmation 2 — Identité utilisée par le worker

**Décision confirmée :** `prospect_worker` reste l'identité technique de base de données, mais l'autorité métier
reste celle de l'utilisateur humain stocké dans le job. Le worker revérifie son membership et ses capabilities au moment
de l'effet. Aucun compte utilisateur fictif `automation-system` n'est créé dans IMP-A4 et aucun job sans acteur humain
n'est accepté.

**Ce que cette décision implique :** une révocation humaine après l'admission bloque réellement la tâche et l'audit peut
distinguer « demandé par » de « exécuté par ». L'alternative, le principal `automation-system`, doit être réservé aux
futurs déclencheurs automatiques et nécessite sa propre politique d'origine, de portée et de révocation.

**Statut : confirmée.** L'exécuteur technique est `prospect_worker` et l'autorité métier humaine est revérifiée.

### Confirmation 3 — Niveau de privilèges PostgreSQL

**Décision confirmée :** accorder au worker les lectures RLS nécessaires, mais enfermer l'effet dans une commande
serveur/SQL étroite et testée. Ne pas lui donner un droit général lui permettant de créer ou modifier n'importe quelle
tâche CRM.

**Ce que cette décision implique :** davantage de travail de migration et de tests, mais une compromission ou un bug du
worker reste borné au contrat `Nouveau prospect → tâche interne`. L'alternative, des grants larges sur
`prospect_tasks`, `prospect_task_events` et l'audit, est plus simple mais élargit fortement la surface d'écriture.

**Statut : confirmée.** Les privilèges restent minimaux et l'effet passe par une commande bornée.

### Confirmation 4 — Politique de reprise après crash

**Décision confirmée :** transaction atomique pour tâche + événement + audit + admission, puis finalisation du job.
À la reprise, le worker recherche toujours l'effet par clé avant toute création. Une tâche prouvée est rattachée ; une
issue qui ne peut pas être prouvée devient `to_verify` et n'est jamais rejouée automatiquement.

**Ce que cette décision implique :** le système peut demander une vérification humaine plutôt que risquer une seconde
tâche. L'alternative, retenter après chaque timeout, est incompatible avec `AUT-4203` et l'oracle zéro doublon.

**Statut : confirmée.** Toute reprise recherche d'abord l'effet ; une issue incertaine devient `to_verify` sans rejeu
automatique.

## 12. Definition of Ready / Definition of Done

### Ready

- les quatre confirmations de la section 11 sont données ;
- le commit IMP-A3 est présent sur la branche `codex/pre-phase-5-implementation` ;
- PostgreSQL/Redis/worker Docker WSL sont disponibles ;
- les flags restent désactivés par défaut ;
- seules des données synthétiques sont utilisées.

**État :** Definition of Ready satisfaite. Le développement reste conditionné à un GO explicite.

### Done

- la migration 0034 et son rollback sont démontrés sur PostgreSQL réel ;
- l'API ne fait confiance ni au tenant, ni aux capacités, ni aux timestamps du client ;
- le worker n'exécute aucune tâche après révocation, suspension, annulation ou obsolescence ;
- concurrence, crash avant/après effet et perte de bail produisent au plus une tâche ;
- `to_verify` interdit tout retry aveugle ;
- RLS et privilèges du worker sont testés sur deux tenants ;
- l'arrêt/redémarrage Docker reprend les jobs contrôlables ;
- le verrou qualité local complet est vert ;
- les flags restent désactivés et aucun effet externe n'est introduit.

## 14. Réalisation IMP-A4 — état au 3 octobre 2026

- migration `20261003_0034` : relation admission ↔ responsable, unicité admission ↔ job, politique RLS ciblée et
  deux commandes `SECURITY DEFINER` non publiques ;
- API : `POST /api/prospects` conserve son chemin CRM normal sans bloc `automation` ; avec ce bloc explicite, la
  commande atomique crée prospect, Prévol, décision, admission et job après les gardes serveur ;
- worker : seul le contrat fermé `automation_new_prospect_prepare:1` appelle la commande de préparation. Les états
  `blocked` et `to_verify` terminent le job sans retry automatique ;
- preuve PostgreSQL réelle : le replay retourne le même prospect/admission/job, le worker crée une seule tâche
  (responsable choisi, priorité `normal`, échéance `+24 h`) et les rôles API/worker ne peuvent pas appeler la
  commande de l'autre ;
- restent à exécuter avant clôture : rollback reproductible et verrou qualité local complet.

## 15. Références

- [IMP-A3 — Dossier de préparation](./IMP_A3_PREPARATION.md) ;
- [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ;
- [Contrats T2 — données, règles et orchestration](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) ;
- [Sécurité, garde et résilience T3](./VAGUE_T3_SECURITE_IA_RESILIENCE.md) ;
- [Backlog détaillé Étape 4](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [Pré-Phase 5 — préparation de l'implémentation](./PRE_PHASE_5_IMPLEMENTATION_AUTOMATISATION.md).
