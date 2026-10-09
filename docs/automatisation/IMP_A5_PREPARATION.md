# IMP-A5 — Dossier de préparation

> **Statut :** préparation terminée ; quatre décisions d'application confirmées le 3 octobre 2026 ; développement en
> attente d'un GO explicite.
> **Branche cible :** `codex/pre-phase-5-implementation`.
> **Portée :** Assistant IA encadré, faux fournisseur déterministe, plan temporaire et repli guidé.
> **Limites maintenues :** flags désactivés par défaut, données synthétiques uniquement, aucun appel OpenAI réel,
> aucun outil IA, aucune écriture CRM, aucun Prévol créé, aucun job et aucun effet externe.

## 1. Objectif et backlog couvert

IMP-A5 doit fournir une première tranche verticale vérifiable de l'Assistant d'`Aujourd'hui` :

```text
utilisateur authentifié
  → intention libre ou suggestion guidée
  → quota et budget synthétique
  → faux fournisseur sans outil
  → validation du schéma fermé
  → résolution serveur en lecture seule
  → plan lisible OU clarification/refus/repli
  → arrêt sans Prévol, job ni effet CRM
```

| Item | Résultat runtime attendu | Oracle principal |
|---|---|---|
| `AUT-4301` | sortie `AssistantIntentSchemaV1` fermée et versionnée | tout champ inconnu invalide la sortie |
| `AUT-4302` | port d'interprétation sans outil ni autorité | le faux fournisseur ne connaît ni tenant, ni dépôt, ni CRM |
| `AUT-4303` | texte et réponse brute éphémères | aucune phrase libre dans la base, les logs, l'audit ou les métriques |
| `AUT-4304` | plan lisible construit par le serveur | périmètre, volume, contrôles et absence d'effet visibles |
| `AUT-4305` | clarification, refus et repli déterministes | panne, quota ou sortie invalide restent dans `Aujourd'hui` |
| `AUT-4306` | limites configurables et prouvables | blocage avant fournisseur quand une limite est atteinte |
| `AUT-4604` | corpus adversarial exécutable | `AI-ADV-01..10` sans effet |

## 2. Point de départ vérifié

| Élément disponible | Réutilisation IMP-A5 | Écart à réaliser |
|---|---|---|
| capacité `automation:plan:create` | autorisation serveur pour `admin`, `manager` et `sales` actifs | route API et tests de révocation |
| flags global, organisation et Playbook | arrêt fermé de l'Automatisation | flag Assistant indépendant, désactivé par défaut |
| moteur Feu et tables de Prévol | sources canoniques de règles et de limites | lectures seulement ; aucune création dans IMP-A5 |
| API FastAPI authentifiée | session, tenant serveur, CSRF, corrélation | route `/api/automation/intent-plans` |
| Redis local | compteurs distribués et scénarios d'indisponibilité | quota/budget Assistant avec clés pseudonymisées |
| application React bilingue | coque, capacités, navigation et accessibilité | surface `/app/automation/today` et composant Assistant |
| métriques Prometheus bornées | compteurs sans identifiant | labels Assistant fermés |

La route et la surface `Automatisation` n'existent pas encore. Le fournisseur réel n'est pas raccordé. Aucune migration
SQL n'est nécessaire si le plan reste temporaire et si les limites IMP-A5 restent dans Redis.

## 3. Périmètre proposé

### Inclus

- entrée `Automatisation` après `Tableau de bord` dans la navigation de bureau ;
- route canonique `/app/automation/today`, avec `/app/automation` redirigée vers elle ;
- un seul champ libre, uniquement dans `Aujourd'hui`, plus trois suggestions guidées ;
- route authentifiée `POST /api/automation/intent-plans` ;
- contrat domaine fermé, validateur strict et port `AssistantInterpreterPort` ;
- faux fournisseur déterministe français/anglais et fautes injectables pour les tests ;
- résolution serveur en lecture seule des volumes et contrôles disponibles ;
- plan temporaire, clarification, refus ou `FALLBACK_GUIDED` ;
- limites Redis, métriques sans identifiant et tests adversariaux synthétiques ;
- tests unitaires, API, PostgreSQL/RLS de lecture, Redis et navigateur/axe.

### Exclus

- SDK, secret, réseau ou modèle OpenAI réel ;
- accès du fournisseur à PostgreSQL, Redis, worker, fichiers, connecteurs ou session ;
- persistance du texte, de la réponse brute ou du plan ;
- création d'un `automation_preflight`, d'une `automation_decision`, d'une admission ou d'un job ;
- tâche, réattribution, mouvement du pipeline, brouillon, approbation ou envoi ;
- activation par défaut, organisation pilote ou production ;
- surfaces complètes `Playbooks` et `Entrées et exceptions` ;
- Playbooks `Proposition en attente` et `Occasion oubliée`, exclus de `P4-Lite`.

## 4. Architecture proposée

### 4.1 Frontière sans outil

```text
AssistantInterpreterPort.interpret(AssistantInterpretationRequest)
  -> AssistantInterpretationResult
```

Le port reçoit seulement : `request_id`, version, locale, texte éphémère, codes autorisés, limite maximale et
corrélation. Il ne reçoit jamais `TenantContext`, identifiant CRM, capacité, token, connexion SQL, client Redis, dépôt,
queue, worker, connecteur ou système de fichiers.

L'orchestrateur serveur possède l'autorité. Il :

1. dérive l'organisation, l'utilisateur et la locale de la session ;
2. exige `automation:plan:create` et les flags applicables ;
3. réserve le quota avant d'appeler le port ;
4. valide strictement la sortie ;
5. résout les volumes et contrôles via des ports de lecture sous RLS ;
6. construit les textes depuis des clés locales ;
7. retourne un plan temporaire ou un repli ;
8. efface toutes les références au texte et à la réponse brute en fin de requête.

### 4.2 Faux fournisseur déterministe

Le faux fournisseur est un adaptateur local explicitement nommé `fake`. Il n'imite pas un appel réseau et ne doit pas
être présenté comme une intelligence réelle. Son corpus versionné contient des phrases synthétiques françaises et
anglaises, leurs intentions attendues et des variantes contrôlées.

- une suggestion guidée produit directement une intention connue ;
- une phrase reconnue par le corpus produit toujours la même structure ;
- une phrase ambiguë produit `clarify_request` ;
- une demande interdite produit `unsupported_request` ;
- une phrase inconnue ne déclenche pas une heuristique hasardeuse : elle demande une clarification ;
- les tests peuvent injecter `timeout`, `provider_unavailable` ou une sortie invalide ;
- aucun mode de test n'est sélectionnable par le navigateur ou par un champ de la requête publique.

## 5. Catalogue actif proposé pour `P4-Lite`

Le schéma conserve les huit codes de S4-3, mais le serveur transmet au faux fournisseur seulement le sous-ensemble
autorisé par cette tranche.

| Code | État IMP-A5 | Réponse |
|---|---|---|
| `scope_open_prospects` | actif | plan de consultation borné |
| `rebalance_open_prospects` | actif en lecture seulement | plan de revue, jamais de réattribution |
| `prepare_new_prospect_followup` | actif | plan explicatif, sans créer de Prévol ou tâche |
| `explain_automation_status` | actif | explication codifiée des flags/contrôles visibles |
| `clarify_request` | actif | question et choix guidés |
| `unsupported_request` | actif | refus et alternatives autorisées |
| `review_pending_proposals` | désactivé en `P4-Lite` | refus codifié, Playbook futur |
| `review_forgotten_opportunities` | désactivé en `P4-Lite` | refus codifié, Playbook futur |

Les trois suggestions par défaut restent : `Prospects en cours`, `Répartir la charge` et `Repérer les relances`.

## 6. Contrat API proposé

### 6.1 Requête

```json
{
  "schema_version": 1,
  "input_mode": "free_text",
  "user_text": "Montre-moi les prospects en cours"
}
```

Ou, sans texte libre :

```json
{
  "schema_version": 1,
  "input_mode": "guided",
  "suggestion_code": "scope_open_prospects"
}
```

Règles :

- `input_mode` impose exactement un de `user_text` ou `suggestion_code` ;
- les propriétés additionnelles sont refusées ;
- le texte est une chaîne non vide après normalisation et possède une taille maximale configurable ;
- l'organisation, la locale, les codes autorisés, la limite de portée et la corrélation viennent du serveur ;
- authentification, organisation active, origine de confiance, JSON et CSRF sont obligatoires ;
- la capacité `automation:plan:create` est revérifiée à chaque demande ;
- la suggestion guidée emprunte le même validateur et le même constructeur de plan que la phrase libre.

### 6.2 Sortie

```json
{
  "data": {
    "result_code": "plan_ready",
    "intent": {
      "schema_version": 1,
      "intent_code": "scope_open_prospects",
      "playbook_code": null,
      "scope_kind": "assigned_open_prospects",
      "scope_limit": 50,
      "clarification_required": false,
      "clarification_key": null,
      "explanation_key": "plan_scope_open_prospects"
    },
    "plan": {
      "title_key": "plan_scope_open_prospects",
      "resolved_count": 12,
      "bounded_count": 5,
      "control_codes": ["read_only", "server_resolved_scope"],
      "not_performed_codes": ["no_crm_write", "no_preflight", "no_external_send"],
      "next_step_code": "review_plan"
    },
    "suggestion_codes": []
  },
  "correlation_id": "server-generated",
  "schema_version": 1
}
```

`result_code` appartient à `plan_ready`, `clarification_required`, `intent_not_supported` ou `fallback_guided`. Le client
n'affiche jamais de texte libre renvoyé par le fournisseur : toutes les phrases visibles proviennent de clés traduites
connues du serveur/client.

Les erreurs de protocole et d'autorisation restent des erreurs HTTP. Les indisponibilités du faux fournisseur, limites
atteintes et sorties invalides retournent un résultat métier `fallback_guided`, avec HTTP 200, afin de conserver les
suggestions au même endroit. Le résultat indique explicitement qu'aucune action n'a été exécutée.

## 7. Plan temporaire et absence d'effet

IMP-A5 ne crée pas de table et n'utilise pas `automation_preflights` comme stockage de plan. Le plan vit seulement dans
la réponse HTTP et dans l'état React de la page courante. Un rechargement l'efface.

Le serveur peut lire des agrégats canoniques sous RLS pour corriger un volume proposé. Il ne transmet au fournisseur ni
les lignes CRM, ni leurs identifiants. Si la lecture nécessaire n'est pas disponible ou autorisée, le plan affiche un
volume indisponible ou demande une clarification ; il n'invente jamais de nombre.

Dans cette tranche, `Préparer ce plan` devient une confirmation locale de garde-fou : elle rappelle qu'aucun objet n'a
été créé et renvoie vers la revue du plan. Elle ne lance ni moteur Feu, ni Prévol, ni admission. Le raccordement à un
Prévol durable exigera une tranche explicitement autorisée et une nouvelle revalidation serveur.

## 8. Données, traces et métriques

### Interdit partout

- phrase libre et prompt ;
- réponse brute ou message d'erreur brut du fournisseur ;
- noms, courriels, téléphones, notes ou extraits CRM ;
- identifiants CRM dans les métriques ;
- clés Redis contenant un courriel, une phrase ou un UUID en clair.

### Autorisé

- corrélation ;
- version du schéma et du corpus ;
- code d'intention validé ;
- code de résultat/repli ;
- compteurs et durée agrégés ;
- empreinte HMAC pseudonymisée pour les compteurs Redis.

Métriques proposées : nombre de demandes par `mode/result`, durée par `provider/result`, rejets de schéma, blocages par
`scope=user|organization|budget` et replis par motif fermé. L'audit métier détaillé et le registre durable d'usage sont
réservés à IMP-A6 ; IMP-A5 ne modifie pas le schéma SQL pour journaliser un texte ou un plan.

## 9. Limites proposées pour le local `P4-Lite`

Les valeurs suivantes sont des paramètres de sécurité de développement, pas des engagements commerciaux :

| Paramètre | Valeur proposée | Comportement à la limite |
|---|---:|---|
| taille du texte | 500 caractères Unicode | `422` avant fournisseur |
| requêtes utilisateur | 10 / 60 secondes | `fallback_guided`, sans fournisseur |
| requêtes organisation | 100 / heure | `fallback_guided`, sans fournisseur |
| budget synthétique organisation | 500 unités / jour UTC | `fallback_guided`, sans fournisseur |
| coût du faux appel | 1 unité | réservé atomiquement avant l'appel |
| délai du port | 2 secondes | `timeout` → repli, aucun retry |
| circuit ouvert | 5 échecs / 60 secondes, ouverture 60 secondes | repli sans appel |
| portée maximale | 50 objets | borne serveur ou clarification |

Redis applique les fenêtres et le budget de manière atomique. Une suggestion guidée qui ne passe pas par le port coûte
zéro unité. Si Redis est indisponible, le système échoue fermé vers `fallback_guided` ; il ne contourne pas les limites.
Les clés expirent avec leur fenêtre et ne contiennent qu'un digest HMAC du périmètre.

## 10. UX et accessibilité proposées

- la page est accessible uniquement si `automation:read:self` et `automation:plan:create` sont présentes ;
- le champ annonce clairement : « L'Assistant prépare un plan. Il ne modifie pas le CRM. » ;
- aucune saisie libre équivalente n'existe ailleurs ;
- un compteur de caractères est visible près de la limite ;
- le formulaire reste utilisable au clavier et son état de chargement est annoncé ;
- clarification, refus, quota et panne ont des titres et messages distincts ;
- le plan affiche demande reformulée, périmètre, volume, contrôles, éléments non réalisés et prochaine étape ;
- les textes sont disponibles en `fr-CA` et `en-CA` ;
- sur mobile, `Automatisation` est la première entrée de `Plus` et rejoint le même champ ;
- aucun écran vide ou erreur technique n'est montré lors d'un repli.

## 11. Découpage de réalisation proposé

| Lot | Travail | Sortie vérifiable |
|---|---|---|
| A5.1 | domaine : enums, requête/résultat, schéma fermé | validation positive/négative pure |
| A5.2 | port et faux fournisseur/corpus | résultats déterministes, zéro dépendance interdite |
| A5.3 | quota/budget Redis et circuit | blocage atomique avant fournisseur |
| A5.4 | orchestrateur, résolution serveur et métriques | plan canonique ou repli, aucune persistance |
| A5.5 | route API et mapping des erreurs | auth, CSRF, capacité et contrat strict |
| A5.6 | route React `Aujourd'hui`, suggestions et états | parcours bilingue clavier/mobile/axe |
| A5.7 | corpus `AI-ADV-01..10` et inspections de traces | `PV-AI-01..06`, `PV-UX-02` |
| A5.8 | Docker WSL et verrou complet | PostgreSQL/Redis réels, verrou vert |

## 12. Matrice de tests de clôture

### Domaine et fournisseur

- les huit champs de sortie sont requis/contrôlés selon leur variante ;
- une propriété supplémentaire, une URL, un identifiant CRM, une capacité ou une commande invalide la sortie ;
- chaque phrase synthétique FR/EN produit l'intention attendue ;
- phrase inconnue → clarification, jamais une intention inventée ;
- intentions désactivées en `P4-Lite` → refus codifié ;
- timeout, indisponibilité et sortie invalide → même `FALLBACK_GUIDED`, sans retry.

### API et sécurité

- session absente, organisation inactive, CSRF invalide ou capacité absente : refus avant fournisseur ;
- tenant, locale, limite ou code autorisé injecté par le client : propriété inconnue refusée ;
- texte vide, trop long ou type incorrect : `422` ;
- révocation de capacité entre deux requêtes : seconde requête refusée ;
- fournisseur inspecté : aucun dépôt, session, token, capacité ou client technique disponible ;
- corpus hostile `AI-ADV-01..10` : refus, clarification ou repli selon l'oracle, zéro effet.

### Données, quota et résilience

- phrase sensible absente de PostgreSQL, Redis, logs, audit, métriques et rapport d'erreur ;
- réponse brute invalide absente des mêmes sorties ;
- deux instances consomment un quota partagé sans dépasser la limite ;
- quota utilisateur, organisation et budget bloquent avant l'appel ;
- Redis indisponible, délai dépassé et circuit ouvert donnent un repli lisible ;
- aucun enregistrement dans Prévols, décisions, admissions, jobs, tâches ou opportunités.

### Frontend et navigateur

- navigation bureau/mobile conforme et unique ;
- suggestions et saisie utilisent le même endpoint ;
- plan, clarification, refus et repli accessibles au clavier et aux lecteurs d'écran ;
- aucun texte brut du fournisseur n'est injecté dans le DOM ;
- `Préparer ce plan` confirme l'absence d'effet et ne déclenche aucune mutation ;
- Vitest, axe et recette navigateur restent stables.

### Verrou local

- Ruff, format, Pyright et Pytest ;
- tests PostgreSQL/RLS réels pour les lectures tenantisées ;
- tests Redis réels pour quota, concurrence et expiration ;
- Vitest/axe et build Vite ;
- recette navigateur 4.6 ;
- diff Git et verrou qualité local complet.

## 13. Quatre confirmations données le 3 octobre 2026

### Confirmation 1 — Surface UX et route

**Proposition :** créer maintenant la vraie surface `/app/automation/today`, ajouter `Automatisation` après
`Tableau de bord`, et rediriger `/app/automation` vers `Aujourd'hui`. Ne pas intégrer le champ au Tableau de bord CRM,
car cela confondrait les deux espaces et contredirait la navigation fonctionnelle validée.

**À confirmer :** oui/non pour cette nouvelle route et cette position dans la navigation.

**Décision : confirmée.** La surface cible est `/app/automation/today`, accessible depuis `Automatisation` après
`Tableau de bord`; `/app/automation` la rejoint par redirection.

### Confirmation 2 — Faux fournisseur et intentions actives

**Proposition :** utiliser un faux fournisseur déterministe basé sur un corpus synthétique versionné FR/EN. Activer les
six intentions sûres de la section 5 ; conserver `review_pending_proposals` et `review_forgotten_opportunities` dans le
schéma mais les refuser en `P4-Lite`, car leurs Playbooks sont hors périmètre. Une phrase inconnue demande une
clarification au lieu d'être classée par heuristique.

**À confirmer :** oui/non pour ce comportement et ce sous-ensemble d'intentions.

**Décision : confirmée.** Le corpus déterministe FR/EN et le sous-ensemble de six intentions sont adoptés ; les deux
Playbooks hors `P4-Lite` restent refusés proprement.

### Confirmation 3 — Plan strictement temporaire

**Proposition :** ne créer aucune table, ne persister ni texte ni plan, et ne créer aucun Prévol/job/effet. Le bouton
`Préparer ce plan` reste une confirmation UX sans mutation pendant IMP-A5. Les volumes affichés sont recalculés en
lecture seule par le serveur ; une donnée indisponible n'est jamais inventée.

**À confirmer :** oui/non pour cette frontière. Un véritable passage du plan au Prévol devra alors faire l'objet d'une
tranche ultérieure explicitement autorisée.

**Décision : confirmée.** Le plan est strictement temporaire et `Préparer ce plan` ne produit aucune mutation dans
IMP-A5.

### Confirmation 4 — Limites locales et échec fermé

**Proposition :** adopter les valeurs de la section 9 : 500 caractères, 10 requêtes utilisateur/minute,
100 requêtes organisation/heure, 500 unités synthétiques/jour, coût fake 1, délai 2 s, circuit après 5 échecs et portée
maximale 50. Les valeurs restent configurables. Redis indisponible ou limite atteinte produit un repli guidé avant tout
appel, jamais un contournement.

**À confirmer :** oui/non pour ces valeurs initiales et cette politique d'échec fermé.

**Décision : confirmée.** Les huit limites locales proposées sont adoptées comme paramètres configurables de
développement `P4-Lite`, sans valeur commerciale ni autorisation OpenAI réelle.

## 14. Definition of Ready / Definition of Done

### Ready

- les quatre confirmations de la section 13 sont données ;
- le commit IMP-A4 est présent sur `codex/pre-phase-5-implementation` ;
- PostgreSQL et Redis Docker WSL sont disponibles ;
- seuls le faux fournisseur et des données synthétiques sont utilisés ;
- le flag Assistant reste désactivé par défaut ;
- un GO explicite est donné après alignement des spécifications concernées.

**État :** les décisions d'application et l'alignement documentaire sont satisfaits. Le développement reste en attente
d'un GO explicite distinct.

### Done

- un utilisateur autorisé obtient un plan fermé ou un repli guidé depuis `Aujourd'hui` ;
- le faux fournisseur n'a aucun outil ni autorité ;
- le texte et la réponse brute sont absents de toute persistance et trace ;
- quotas, budget, timeout, circuit et sortie invalide sont prouvés avant appel/effet ;
- `AI-ADV-01..10` passent avec zéro effet ;
- aucun Prévol, job ou objet CRM n'est créé par l'Assistant ;
- les parcours FR/EN, mobile, clavier et axe passent ;
- le verrou qualité local complet est vert.
