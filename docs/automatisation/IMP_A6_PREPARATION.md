# IMP-A6 — Dossier de préparation : résilience, audit et rollback

> **Statut :** implémentation réalisée et verrou qualité complet vert le 4 octobre 2026 ; preuve D3 locale
> minimisée produite. La décision de Porte 4 est un `GO avec réserves` ; aucune activation n'est autorisée.
>
> **Prérequis :** `IMP-A1` à `IMP-A5` intégrés sous flags désactivés ; environnement Docker/WSL local ; données
> strictement synthétiques.

## 1. Objectif

IMP-A6 clôt la construction `P4-Lite` par des preuves exécutables de sûreté : l'Automatisation doit soit produire une
unique tâche interne explicable, soit s'arrêter dans un état bloqué, `to_verify` ou nécessitant une intervention
humaine. Elle ne crée aucun nouveau Playbook, connecteur, appel IA réel, envoi externe ni activation client.

La tranche couvre les items `AUT-4601` à `AUT-4607` et alimente les preuves `AUT-4703` à `AUT-4708` :

| Volet | Résultat à démontrer | Preuve cible |
|---|---|---|
| Fixtures et oracles | deux tenants, rôles, doublons, ambiguïtés et données adversariales reproductibles | `PV-DATA-03`, `PV-QA-01` |
| Exceptions | aucun effet silencieux pour doublon, responsable invalide, règle obsolète ou résultat incertain | `PV-S47-RUN-02` |
| Résilience | arrêt, reprise, concurrence et réconciliation sans deuxième effet | `PV-S47-RES-01`, `PV-OPS-03` |
| Audit et métriques | corrélation reconstituable, labels bornés, aucune phrase libre ni PII | `PV-S47-OBS-01` |
| Rollback | retour contrôlé de flags, worker et migrations de test sans perte ni doublon | `PV-DATA-01`, `PV-OPS-03` |
| IA encadrée | faux fournisseur, schéma fermé, repli et limites locales toujours appliqués | `PV-S47-AI-01` |
| Porte 4 | réserves, résultats et interdictions assemblés sans surpromesse | `PV-S47-GATE-01` |

## 2. Frontière impérative

Sont autorisés uniquement les tests locaux sur PostgreSQL, Redis, worker et fournisseur fake. Les flags restent à
`false` hors scénario de test contrôlé. Les fixtures n'emploient ni données client, ni courriel, téléphone, secret,
phrase libre durable ou contenu de brouillon.

Sont hors périmètre : OpenAI réel, connecteurs, envoi de message, brouillon externe, changement de pipeline,
réattribution automatique, staging/production et preuve D4.

## 3. Inventaire des scénarios à automatiser

Chaque scénario doit contenir le tenant, l'acteur humain, la version de règle, la corrélation, l'oracle de non-effet
et le nettoyage de la fixture.

| ID | Injection contrôlée | Oracle attendu |
|---|---|---|
| `A6-RES-01` | retrait de capacité entre admission et exécution worker | job bloqué ; aucune tâche créée ; audit de refus minimal |
| `A6-RES-02` | suspension globale ou d'organisation avant effet | job annulé/bloqué ; aucune nouvelle prise d'effet |
| `A6-RES-03` | deux workers tentent la même admission | une seule tâche interne idempotente ; un seul effet CRM |
| `A6-RES-04` | timeout après résultat potentiellement écrit | état `to_verify` ou effet retrouvé par clé ; jamais de retry aveugle |
| `A6-RES-05` | redémarrage du worker sur job repris | garde fraîche réévaluée ; pas de second effet |
| `A6-RES-06` | version Feu/Prévol devenue obsolète | refus explicable ou nouveau Prévol ; pas d'effet avec une version périmée |
| `A6-RES-07` | panne Redis ou PostgreSQL lors d'une garde | arrêt fermé ; exception contrôlée ; aucune création partielle |
| `A6-EXC-01` | doublon exact | rattachement/effet unique ; corrélation retrouvable |
| `A6-EXC-02` | doublon ambigu ou responsable inactif | `to_verify`/exception humaine ; aucune fusion ni attribution silencieuse |
| `A6-AI-01` | sortie IA hors schéma, timeout ou quota/circuit ouvert | repli guidé ; aucun outil, Prévol, job ni écriture CRM |
| `A6-AI-02` | note CRM contenant une instruction d'injection | intention refusée/clarifiée ; aucune donnée CRM exécutée comme instruction |
| `A6-OBS-01` | succès, refus, exception et suspension | codes/version/corrélation présents ; ni texte libre, ni secret, ni PII dans audit et métriques |

## 4. Plan d'exécution proposé

1. **Fixtures et tests déterministes.** Versionner des fixtures synthétiques `ORG-ALPHA` et `ORG-BETA`, puis ajouter
   les tests d'isolation tenant, de garde fraîche, d'idempotence, d'exception et de non-effet.
2. **Injection de pannes test-only.** Utiliser des doubles ou points d'injection exclusivement disponibles dans les
   tests ; aucune route, variable d'environnement d'exploitation ou commande utilisateur ne doit pouvoir déclencher
   une panne volontaire.
3. **Observabilité.** Vérifier les événements d'audit et l'export de métriques avec des listes de labels fermées.
   La corrélation est vérifiable, mais les journaux de preuve ne recopient ni requête Assistant, ni données CRM.
4. **Arrêt et rollback.** Désactiver d'abord les flags et invalider les travaux non exécutés ; réconcilier ensuite les
   états incertains. Le downgrade Alembic est répété seulement sur une base de test jetable, à partir d'un état
   explicitement identifié, et est suivi d'un `upgrade head` et des tests de non-régression.
5. **Dossier de preuves.** Produire des rapports sanitaires et minimisés sous `test-results/automation-imp-a6/` ; le
   dépôt conserve les tests, procédures et manifestes, jamais des données réelles ou secrets.

## 5. Critères d'acceptation

IMP-A6 sera terminée uniquement si tous les critères suivants sont satisfaits :

- zéro lecture ou écriture inter-organisation dans les scénarios négatifs ;
- zéro tâche/prospect/brouillon dupliqué lors d'un rejeu, d'une concurrence ou d'une reprise ;
- 100 % des résultats incertains basculent vers `to_verify`, la réconciliation idempotente ou une exception humaine ;
- retrait de capacité, suspension ou flag désactivé empêchent l'effet avant écriture ;
- chaque décision vérifiable expose corrélation, version, état et code de motif sans PII inutile ;
- les métriques Assistant restent limitées à des codes fermés ;
- rollback de migration exécuté sur base jetable, puis remontée à `head`, sans perte d'objet CRM ni doublon ;
- verrou qualité complet vert après chaque série significative de preuves ;
- les rapports D3 datés indiquent clairement version Git, migrations, configuration synthétique et oracle.

Les objectifs de capacité `S95 ≤ 3 s` et `Smax ≤ 9 s` restent des hypothèses de mesure. Ils ne deviennent pas un SLO
avant protocole de charge explicitement approuvé et exécuté.

## 6. Rôles et limites de décision

Les rôles déjà confirmés pour `AUT-4701` sont conservés : Produit, QA et Sécurité sont tenus par le commanditaire ;
Backend et environnement sont préparés par l'équipe de développement. Les preuves D3 sont exécutées localement ;
elles ne constituent ni une approbation de production ni une autorisation d'activation.

Toute réserve critique (isolement tenant, capacité, garde fraîche, idempotence, rollback ou PII) arrête la tranche.
Une réserve non critique est documentée dans le dossier Porte 4 avec owner, impact et action de suivi.

## 7. Décisions d'application confirmées avant le GO de développement

### Confirmation 1 — Niveau de preuve et environnement

**Règle confirmée :** les preuves IMP-A6 sont exécutées uniquement en local Docker/WSL sur fixtures synthétiques. Elles
produisent des résultats D3 reproductibles, mais ne permettent ni flag activé durablement, ni staging, ni D4.

**Décision : confirmée.** Les preuves restent locales, synthétiques et D3 reproductibles ; elles ne permettent ni
staging, ni D4, ni activation durable.

### Confirmation 2 — Injection de pannes

**Règle confirmée :** les pannes sont injectées uniquement par doubles de test, fixtures ou hooks internes non exposés au
runtime normal. Aucun endpoint, flag exploitable ou instruction Assistant ne permet de déclencher une panne.

**Décision : confirmée.** Les injections de panne sont limitées aux doubles, fixtures et hooks internes de test non
exposés au runtime normal.

### Confirmation 3 — Ordre de rollback

**Règle confirmée :** appliquer l'ordre strict : désactivation globale/organisation/Playbook → arrêt de prise en charge
worker → annulation des travaux non exécutés → réconciliation des `to_verify` par clé idempotente → rollback Alembic
seulement sur base jetable → `upgrade head` et preuve de non-duplication.

**Décision : confirmée.** Le rollback suit l'ordre proposé et le downgrade Alembic reste limité à une base jetable,
suivi d'une remontée à `head` et d'une preuve de non-duplication.

### Confirmation 4 — Preuves, conservation et décision de porte

**Règle confirmée :** les rapports d'exécution sont minimisés et stockés sous `test-results/automation-imp-a6/`; les
tests, manifestes et procédures sont versionnés. Aucune phrase libre, PII, secret, copie de requête Assistant ou
donnée CRM brute n'est conservé. La clôture IMP-A6 exige le verrou qualité vert, puis une revue Produit/QA/Sécurité ;
elle ne change pas l'interdiction d'activation `P4-Lite` sans décision de porte séparée.

**Décision : confirmée.** Les rapports sont minimisés sous `test-results/automation-imp-a6/`; la clôture exige le
verrou vert et la revue Produit/QA/Sécurité, sans lever l'interdiction d'activation.

Le GO de développement a été donné le 4 octobre 2026. OpenAI réel, staging, production et tout effet externe restent
interdits ; le GO ne constitue ni une validation D3 finale, ni une autorisation d'activation.

## 8. Definition of Ready

- commit IMP-A5 présent sur `codex/pre-phase-5-implementation` ;
- PostgreSQL, Redis, Mailpit et worker Docker/WSL disponibles et réinitialisables ;
- espace disque disponible pour le verrou et les rapports temporaires ;
- les quatre confirmations ci-dessus sont données ;
- toutes les données de test restent synthétiques ;
- aucun flag Automation n'est activé durablement.

## 9. Sortie attendue

La sortie est un dossier `P4-Lite` de preuves : tests automatisés, manifeste de fixtures, procédure de rollback,
résultats minimisés et registre de réserves. Elle permet d'assembler `PV-S47-RUN-01`, `PV-S47-RUN-02`,
`PV-S47-RES-01`, `PV-S47-OBS-01`, `PV-S47-AI-01` et `PV-S47-GATE-01`, sans prétendre produire une preuve D4 ou une
autorisation d'activation.

## 10. Trace d'implémentation du 4 octobre 2026

- migration additive `20261004_0035` : fermeture terminale des admissions, refus des versions de règle périmées et
  audit minimal des états `blocked`/`to_verify` ;
- worker : retrait d'autorisation clôturé avant l'échec permanent du job ;
- fixtures : [`fixtures/imp-a6/manifest.json`](./fixtures/imp-a6/manifest.json), deux tenants synthétiques et injections
  de panne limitées aux tests ;
- procédure : [`IMP_A6_ROLLBACK.md`](./IMP_A6_ROLLBACK.md), avec reconstruction Alembic réservée à la base jetable ;
- preuves automatisées : retrait d'autorisation, responsable indisponible, suspension, règle périmée, concurrence,
  reprise, effet incertain, panne de dépendance et replis Assistant ;
- générateur du rapport minimisé `test-results/automation-imp-a6/evidence.json`, exécuté par le verrou complet.

État de validation au 4 octobre 2026 : verrou qualité complet vert sur Docker/WSL avec répertoire temporaire
`D:\CodexQuality` : 381 tests backend, 218 tests frontend et 44 parcours navigateur/axe passés, sans test ignoré.
Le rapport D3 minimisé `test-results/automation-imp-a6/evidence.json` atteste la migration `20261004_0035`, la
reconstruction de rollback et les scénarios IMP-A6. Cette preuve reste locale, synthétique et sans activation ; la
revue Produit/QA/Sécurité est enregistrée dans la décision de Porte 4 : `GO avec réserves`.
