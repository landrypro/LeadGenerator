# IMP-A3 — Dossier de préparation

> **Statut :** préparation prête pour le GO de développement ; décisions de section 7 confirmées le 2 octobre 2026.  
> **Portée :** admission `Nouveau prospect` idempotente et préparation d'une tâche CRM interne unique.  
> **Limites maintenues :** flags désactivés, aucune route HTTP, aucun worker branché, aucun appel IA, aucun envoi ou
> connecteur externe, aucune activation pour une organisation.

## 1. Objectif et backlog couvert

IMP-A3 transforme le résultat du Prévol en une admission durable, explicable et sans doublon. La tâche est créée dans
le CRM canonique ; l'Automatisation ne crée ni un second registre de tâches ni une copie du prospect.

| Item | Résultat préparé | Oracle de sortie |
|---|---|---|
| `AUT-4201` | Admission tenantisée et idempotente | même clé + même empreinte = même résultat ; empreinte différente = conflit |
| `AUT-4202` | Garde fraîche avant écriture CRM | révocation, suspension ou contexte changé = aucun effet |
| `AUT-4203` | État `to_verify` après résultat incertain | aucune seconde tâche automatique |
| `AUT-4204` | Tâche CRM interne unique | responsable actif et prochaine action explicite |
| `AUT-4205` | Passeport en lecture de références CRM | aucune copie métier parallèle |
| `AUT-4206` | Doublon exact et ambiguïté traités | rattachement sûr ou quarantaine, jamais fusion silencieuse |

Les preuves cibles sont `PV-IDEM-01`, `PV-IDEM-02`, `PV-SEC-03`, `PV-FUN-01`, `PV-FUN-02`, `PV-FUN-03`,
`PV-EXC-01` et `PV-OBS-01`.

## 2. Point de départ vérifié

| Élément disponible | Réutilisation prévue | Écart à couvrir dans IMP-A3 |
|---|---|---|
| Tables Automation isolées, RLS et flags (`IMP-A1/A2`) | Playbook, version, Prévol, décision et exception | admission durable et lien vers la tâche CRM |
| `prospect_tasks` CRM | tâche interne existante, idempotence par organisation/prospect/clé, événement et audit | aucune provenance Automation ni corrélation Automation stockée dans la tâche |
| `CreateTaskUseCase` | validation du prospect, du responsable actif et de la clé réutilisée | garde Automation fraîche avant l'appel CRM |
| `jobs` PostgreSQL | transport durable déjà idempotent, avec bail et annulation | aucune intégration Automation ni worker à ce stade |
| `automation_exceptions` | `owner_unavailable`, `ambiguous_match`, `effect_uncertain` | création/lecture contrôlée par le futur dépôt Automation |

Le modèle CRM actuel sait déjà refuser un responsable inactif et retourner la même tâche pour une même clé et une même
empreinte. IMP-A3 doit réutiliser ces garanties, jamais les contourner.

## 3. Modèle de données proposé

### 3.1 Entité dédiée `automation_admissions`

**Proposition recommandée :** ajouter une table Automation isolée et protégée par RLS. Elle représente l'intention et
son résultat métier, tandis que `prospect_tasks` reste la source canonique de la tâche.

```text
automation_admissions
  id
  organization_id
  prospect_id                         -> prospects (FK tenantisée)
  playbook_version_id                 -> automation_playbook_versions (FK tenantisée)
  requested_by_membership_id          -> memberships (FK tenantisée)
  preflight_id                        -> automation_preflights (FK tenantisée)
  decision_id                         -> automation_decisions (FK tenantisée)
  task_id?                            -> prospect_tasks (FK tenantisée)
  functional_identity_fingerprint     // SHA-256, jamais l'identité brute
  idempotency_key_digest              // HMAC/digest, jamais la clé brute
  request_fingerprint                 // SHA-256 de la charge canonique
  correlation_id
  state
  result_code
  created_at, updated_at, completed_at?
```

Contraintes préparées :

- unicité `(organization_id, idempotency_key_digest)` : le replay retrouve la même admission ;
- unicité métier `(organization_id, prospect_id, playbook_version_id, functional_identity_fingerprint)` : deux
  admissions concurrentes ne peuvent produire deux tâches ;
- lien tenantisé vers le prospect, le Prévol, la décision et, une fois créée, la tâche CRM ;
- états fermés : `accepted`, `preflight_required`, `ready_to_prepare`, `prepared`, `blocked`, `quarantined`,
  `to_verify`, `rejected`, `cancelled` ;
- RLS forcée, aucune permission `PUBLIC`, lecture seulement pour `prospect_app` jusqu'à l'intégration contrôlée de A4.

La relation est volontairement **Automation admission → tâche CRM**, et non l'inverse : aucune colonne Automation ne
sera ajoutée à `prospect_tasks` si le lien tenantisé ci-dessus suffit. Le Passeport lira les identifiants et états des
objets canoniques, sans recopier leur contenu.

### 3.2 États et absence d'effet

```text
accepted → preflight_required → ready_to_prepare → prepared
                    │                   │
                    ├─ blocked          ├─ blocked / quarantined
                    └─ cancelled        └─ to_verify
```

- `prepared` signifie qu'une unique tâche CRM a été retrouvée ou créée avec la clé d'effet.
- `to_verify` signifie que l'effet a pu avoir lieu, mais que son résultat n'est pas prouvé ; la seule action ultérieure
  est une recherche par clé/corrélation ou une résolution humaine.
- `blocked`, `quarantined` et `rejected` ne créent aucune tâche.

## 4. Contrats préparés

### Admission

```text
AdmitNewProspectCommand {
  organization_id       // issu du contexte serveur, jamais d'une valeur client fiable
  actor_id
  requested_membership_id
  prospect_id
  playbook_version_id
  preflight_id
  decision_id
  admission_identity
  idempotency_key
  request_fingerprint
  correlation_id
}
```

Préconditions : organisation et prospect actifs, même tenant, Playbook `new_prospect` non suspendu, flags fermés par
défaut mais évaluables, Prévol et décision actuels, capacité Automation du demandeur, et absence de doublon ambigu.

### Préparation de tâche

```text
PrepareInternalTaskCommand {
  admission_id
  expected_admission_version
  assigned_membership_id
  due_at
  task_title_code
  task_description_code
  effect_idempotency_key
  effect_fingerprint
  correlation_id
}
```

La commande effectue dans une transaction : relecture de l'admission, du prospect, du Prévol, du Playbook, de la
suspension, de la capacité `automation:prepare` et du droit CRM de créer une tâche, puis relecture de l'activité du
responsable. Elle appelle seulement ensuite la commande CRM canonique de tâche.

La permission de contact, y compris `unknown` ou `opted_out`, n'autorise ni ne bloque cette tâche interne. Elle reste
un signal distinct du Feu pour une future communication externe, hors IMP-A3.

## 5. Découpage de réalisation proposé

| Lot | Items | Travail | Sortie vérifiable |
|---|---|---|---|
| A3.1 | `AUT-4201`, `AUT-4206` | Valeurs de domaine, identité fonctionnelle, empreintes, réponses de replay/conflit/doublon/quarantaine | même commande rejouée stable ; charge différente refusée |
| A3.2 | `AUT-4201`, `AUT-4205` | migration `automation_admissions`, modèles SQLAlchemy, RLS, dépôt de lecture/écriture contrôlé | admission liée aux objets canoniques sans copie CRM |
| A3.3 | `AUT-4202`, `AUT-4204` | cas d'usage de préparation avec double garde ; adaptation minimale au `CreateTaskUseCase` existant | une seule tâche avec responsable actif et prochaine action |
| A3.4 | `AUT-4203` | transition `to_verify`, recherche de tâche par clé, exception `effect_uncertain` | aucun retry aveugle après réponse perdue |
| A3.5 | `AUT-4206`, `AUT-4704` | tests multi-tenant, concurrence, doublon exact, ambiguïté et responsable indisponible | rattachement sûr, quarantaine ou exception explicable |
| A3.6 | `AUT-4703`, `AUT-4707` | jeux synthétiques D2/D3 et inspection d'audit minimal | preuves sans PII, phrase libre ni secret |

IMP-A3 ne branche ni endpoint ni worker. IMP-A4 réalisera l'adaptateur HTTP, le déclenchement après création canonique,
le transport durable et la reprise contrôlée.

## 6. Matrice de tests de clôture

| Scénario | Attendu |
|---|---|
| même admission, même empreinte, deux appels concurrents | une admission terminale et une seule tâche CRM |
| même clé, empreinte différente | `idempotency_conflict`, aucune tâche supplémentaire |
| même référence externe dans deux organisations | aucune lecture ni écriture inter-tenant |
| doublon exact | admission rattachée ; pas de nouveau prospect ni tâche |
| correspondance ambiguë | `quarantined` + `ambiguous_match`, aucune tâche |
| responsable désactivé entre Prévol et garde | `blocked` + `owner_unavailable`, aucune réattribution |
| Playbook suspendu ou flag désactivé avant garde | refus fermé, aucune tâche |
| Prévol expiré ou empreinte CRM modifiée | admission invalide, nouveau Prévol requis |
| réponse CRM perdue après effet possible | `to_verify`, recherche par clé, jamais une seconde création |
| Passeport | références au prospect, à la tâche, au Prévol et à l'exception ; aucune copie de contenu CRM |

Tous les scénarios utilisent deux organisations et des données synthétiques. Les traces n'exposent que des codes, des
versions, des empreintes/digests et la corrélation ; elles excluent les contenus de tâche, coordonnées, phrases libres
et clés d'idempotence brutes.

## 7. Décisions confirmées avant le GO de développement

1. **Transport transactionnel.** L’admission et le job PostgreSQL idempotent sont écrits dans la même transaction que
   le prospect canonique ; aucun outbox générique n’est créé. Aucun job ni worker Automation n’est branché avant IMP-A4.
2. **Responsable de la première tâche.** Désignation humaine stricte : un utilisateur autorisé fournit explicitement le
   responsable. S’il est absent, inactif ou hors tenant, l’admission devient `owner_unavailable`. Aucun défaut
   automatique, round-robin ou aléatoire n’est admis.
3. **Échéance et contenu.** Échéance à `admitted_at + 24 h` dans le fuseau de l’organisation, priorité `normal`, titre
   `Prendre en charge le prospect {nom}` et description `Vérifier le contexte disponible et définir la prochaine action.`
   Le nom reste dans la tâche CRM, jamais dans les traces Automation.
4. **Principal d’écriture.** Seul un exécuteur serveur contrôlé peut appeler la commande CRM après double garde.
   `prospect_app` reste en lecture seule sur les tables Automation ; les privilèges de l’exécuteur seront ajoutés avec
   IMP-A4.

## 8. Definition of Ready / Definition of Done

### Ready

- décisions 1 à 4 ci-dessus confirmées ;
- flags désactivés et environnement local isolé conservés ;
- fixtures synthétiques à deux tenants disponibles ;
- aucun connecteur, appel IA réel ou donnée client dans les tests ;
- contrat de tâche CRM et capacités nécessaires relus lors de la conception détaillée.

### Done

- `AUT-4201` à `AUT-4206` ont un cas d'usage, une garde et les tests négatifs associés ;
- la migration et son rollback sont validés localement ;
- RLS interdit les accès inter-tenant et les écritures non autorisées ;
- les replays, conflits, concurrence et `to_verify` ne créent jamais une seconde tâche ;
- le Passeport ne contient que des références aux objets CRM canoniques ;
- preuves D2/D3 reliées à `AUT-4703`, `AUT-4704` et `AUT-4707` ;
- verrou qualité local vert ;
- aucun endpoint, worker, activation ou effet externe n'est introduit par IMP-A3.

## 9. Références

- [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ;
- [Contrats T2 — données, règles et orchestration](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) ;
- [Backlog détaillé Étape 4](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [Pré-Phase 5 — préparation de l'implémentation](./PRE_PHASE_5_IMPLEMENTATION_AUTOMATISATION.md).
