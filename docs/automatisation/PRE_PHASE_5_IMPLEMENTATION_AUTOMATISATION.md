# Pré-Phase 5 — Préparation de l'implémentation Automatisation

> **Statut : préparation d'implémentation autorisée par Porte 4 `GO avec réserves`.**  
> **Portée autorisée :** `P4-Lite`, sous feature flags désactivés par défaut.  
> **Interdictions maintenues :** envoi externe, appel OpenAI réel, connecteurs sociaux, changement silencieux du pipeline,
> réattribution automatique et production générale.

## 1. Objet

Ce dossier prépare l'implémentation de l'Automatisation sans élargir la promesse validée : Marketteo prépare, explique
et demande une approbation. Il ne remplace pas le CRM canonique et n'agit jamais silencieusement.

Les zones encore imprécises seront traitées progressivement dans le registre des réserves. Cette règle ne s'applique
pas aux invariants de sécurité : isolation tenant, capacités, garde fraîche, idempotence, audit et absence d'envoi
restent obligatoires avant toute mise sous flag utilisable.

## 2. Tranche d'implémentation autorisée — `P4-Lite`

| Inclus | Limite impérative |
|---|---|
| Noyau Feu relationnel et Prévol versionné | Même version de règle au Prévol et à la garde fraîche |
| Admission `Nouveau prospect` | Source manuelle en premier ; Google et CSV réutiliseront ensuite le même contrat ; objets CRM canoniques uniquement |
| Tâche CRM interne préparée | Une seule tâche idempotente ; pas de communication externe |
| Point d'entrée IA unique | Schéma fermé, faux fournisseur par défaut, aucun outil ni écriture IA |
| Passeport, audit et exceptions | Données minimisées, corrélation et résolution humaine des ambiguïtés |
| Feature flags et suspension | Valeur sûre désactivée, arrêt immédiat et rollback documenté |

Sont explicitement exclus : OpenAI réel, brouillons externes, Playbooks `Proposition en attente` et `Occasion oubliée`,
connecteurs LinkedIn/Facebook, envoi de courriel/SMS, fermeture ou déplacement d'opportunité, attribution automatique
et activation de production.

## 3. Découpage recommandé

| Tranche | Résultat | Réserves à surveiller | Sortie attendue |
|---|---|---|---|
| `IMP-A1` | Tables Automation isolées, RLS, migrations réversibles et flags | environnement et rollback | schéma et flags vérifiés hors production |
| `IMP-A2` | Moteur Feu, versions, Prévol et Passeport | fidélité Prévol/garde | preuves déterministes D2/D3 |
| `IMP-A3` | Admission idempotente et tâche interne préparée | concurrence, doublons, responsabilités | tâche unique ou exception explicable |
| `IMP-A4` | API manuelle et worker contrôlé | garde avant effet, suspension, reprises | aucun effet après arrêt ou permission retirée |
| `IMP-A5` | Assistant IA encadré avec faux fournisseur | schéma, repli, données et budget | intention valide ou repli, zéro outil |
| `IMP-A6` | Observabilité, tests d'exception et rollback | logs, PII, `to_verify` et charge | dossier de preuves `P4-Lite` |

Chaque tranche doit pouvoir être désactivée indépendamment. Une réserve nouvelle est consignée, qualifiée et traitée
dans la tranche concernée ; elle ne bloque les autres tranches que si elle remet en cause un invariant de sécurité ou
un contrat de données.

## 4. Règles de développement

1. Toute nouvelle table Automation est isolée par organisation et protégée par RLS.
2. Toute commande porte un tenant, un acteur, une version, une clé d'idempotence et une corrélation.
3. Toute écriture CRM revalide capacité, Feu, version, suspension et état juste avant effet.
4. Tout résultat incertain devient `to_verify` ; aucun retry aveugle ne peut créer une seconde tâche.
5. OpenAI est représenté par un port ; seul le faux fournisseur est admis dans cette étape.
6. Les flags sont désactivés par défaut, avec arrêt global et par organisation.
7. Les journaux conservent des codes, versions et corrélations, jamais les phrases libres, secrets ou PII inutile.

### 4.1 Décisions d'application `IMP-A4` confirmées le 3 octobre 2026

Ces décisions bornent le premier raccordement runtime sans modifier le contrat fonctionnel commun des sources :

1. seul `POST /api/prospects`, sur demande Automation explicite, est raccordé dans IMP-A4 ; Google, CSV et Meta restent
   hors branchement jusqu'à la preuve du premier parcours ;
2. `prospect_worker` est l'exécuteur technique, mais le job conserve l'utilisateur humain demandeur et le worker
   revérifie son membership ainsi que `automation:prepare:self` et `tasks:create` avant l'effet ;
3. aucun principal métier `automation-system` n'est créé dans IMP-A4 et aucun job sans acteur humain valide n'est admis ;
4. les droits PostgreSQL du worker sont minimaux : l'effet passe par une commande bornée, tenantisée et idempotente,
   jamais par des droits généraux d'écriture sur les tâches CRM ;
5. toute reprise recherche d'abord l'effet par sa clé ; une issue non prouvable devient `to_verify` et interdit toute
   seconde création automatique.

### 4.2 Trace de réalisation IMP-A4 — 3 octobre 2026

La décision est matérialisée par la migration `20261003_0034`, une admission SQL transactionnelle et une commande
d'effet SQL séparée, accessibles respectivement au rôle API et au rôle worker. Le raccordement est limité au bloc
Automation explicite de `POST /api/prospects`. La tâche produite reste interne, de priorité `normal`, échue à `+24 h`;
elle conserve le responsable humain choisi. Les admissions antérieures à IMP-A4 restent lisibles sans responsable
historique, mais ne sont pas exécutables. Cette compatibilité ne désactive aucune garde pour les nouvelles admissions.

### 4.3 Décisions d'application `IMP-A5` confirmées le 3 octobre 2026

Le [dossier de préparation IMP-A5](./IMP_A5_PREPARATION.md) traduit S4-3 en une tranche verticale sans fournisseur réel :
surface `Aujourd'hui`, API d'intention, schéma fermé, faux fournisseur déterministe, plan temporaire et repli guidé.
Les décisions suivantes sont confirmées :

1. créer `/app/automation/today`, avec `Automatisation` après `Tableau de bord`, et rediriger `/app/automation` ;
2. utiliser un corpus fake déterministe FR/EN ; activer six intentions sûres et refuser proprement les deux Playbooks
   hors `P4-Lite` ;
3. conserver le plan strictement temporaire, sans table, Prévol, job ni effet CRM ;
4. appliquer les seuils locaux configurables documentés dans IMP-A5, avec échec fermé vers le repli guidé.

Ces confirmations alignent la préparation mais ne constituent pas le GO de développement. OpenAI réel, la production
et les effets externes restent interdits.

### 4.4 Décisions d'application `IMP-A6` confirmées le 4 octobre 2026

Le [dossier de préparation IMP-A6](./IMP_A6_PREPARATION.md) fixe l'exécution des preuves de résilience, audit et
rollback de `P4-Lite`. Les décisions confirmées sont :

1. produire exclusivement des preuves D3 locales, reproductibles et synthétiques sur Docker/WSL ; ni staging, ni D4,
   ni activation durable ne sont autorisés ;
2. injecter les pannes uniquement dans les doubles, fixtures et hooks internes de test, jamais depuis le runtime,
   une API, un flag exploitable ou une instruction Assistant ;
3. appliquer le rollback dans l'ordre flags → arrêt worker → annulation des travaux non exécutés → réconciliation des
   `to_verify` → downgrade Alembic sur base jetable → `upgrade head` et preuve de non-duplication ;
4. minimiser les rapports sous `test-results/automation-imp-a6/`, versionner tests, manifestes et procédures, et
   exiger verrou vert plus revue Produit/QA/Sécurité avant clôture, sans autoriser l'activation.

Le GO de développement IMP-A6 a été reçu le 4 octobre 2026. La migration `20261004_0035`, les scénarios synthétiques,
la procédure de rollback et le générateur de preuve minimisée sont implémentés. Le verrou qualité complet est vert et
le rapport D3 minimisé est produit ; la décision de Porte 4 est un `GO avec réserves`. Les interdictions `P4-Lite`
demeurent.

## 5. Gestion progressive des points d'ombre

| Catégorie | Traitement au fil de l'eau | Effet sur l'implémentation |
|---|---|---|
| UX mineure ou libellé | Décision produit et test ciblé | Non bloquant si le contrat reste identique |
| Estimation ou capacité | Ajuster la tranche et le calendrier | Peut réduire le périmètre, pas les garde-fous |
| Quota ou coût OpenAI | Paramètre de configuration et repli local | Bloque seulement l'activation OpenAI réelle |
| Rétention ou contrat IA | Validation Données/Sécurité | Bloque tout appel IA réel |
| Sécurité, tenant, permission, idempotence, rollback | Décision immédiate et preuve obligatoire | Bloque la tranche concernée |
| Nouvel effet externe | Nouvelle décision de porte | Hors `P4-Lite` |
| Décision d'implémentation validée | Reporter la décision dans le dossier d'implémentation et les spécifications de référence concernées | Aucun développement ne démarre sur un contrat documentaire contradictoire |

## 6. Definition of Ready

- verdict Porte 4 `GO avec réserves` enregistré ;
- référence `RF-AUT-2.1` et périmètre `P4-Lite` figés ;
- branche, environnement isolé et données synthétiques disponibles ;
- propriétaires Produit, Engineering, QA et Sécurité identifiés par tranche ;
- faux fournisseur IA et flags désactivés par défaut définis ;
- aucune donnée client ou secret OpenAI requis pour démarrer.

## 7. Definition of Done de la préparation

- tranches `IMP-A1` à `IMP-A6` reliées aux items `AUT-4101..4708` ;
- critères d'acceptation, preuves et réserves identifiés pour chaque tranche ;
- limites d'effet explicites et vérifiables ;
- parcours de rollback et d'arrêt écrits avant l'intégration worker ;
- aucune activation réelle ou production créée par cette préparation.

## 8. Conditions avant activation

Une implémentation peut être intégrée derrière flags désactivés. Son activation, même pour une organisation pilote,
nécessitera au minimum : preuves D2/D3 de la tranche, revue QA/Sécurité, rollback répété, audit inspectable et décision
produit explicite. L'appel OpenAI réel nécessitera en plus quotas, contrat, rétention et protection des données validés.

## 9. Documents associés

- [Porte 4 — décision `GO avec réserves`](./PORTE_4_PRET_A_CONSTRUIRE.md) ;
- [S4-7 — registre des réserves](./S4_7_LEVEE_RESERVES_PORTE_4.md) ;
- [Backlog Étape 4](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [Protocole de preuves](./PREUVES_VALIDATION_ETAPE_4.md) ;
- [IMP-A5 — dossier de préparation](./IMP_A5_PREPARATION.md) ;
- [IMP-A6 — dossier de préparation](./IMP_A6_PREPARATION.md) ;
- [Phase 4.7 — réserve du socle](../PHASE_4_7_RESERVE.md).
