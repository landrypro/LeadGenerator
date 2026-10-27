# P53-10 — Recette synthétique locale

| Champ | Valeur |
| --- | --- |
| Périmètre | Adaptateurs `disabled` et `simulated`, sans fournisseur externe |
| Devises | CAD, USD, EUR et XAF, sans conversion |
| Décisions | `P53-10-D01` à `P53-10-D04`, approuvées le 24 octobre 2026 |
| État de la recette | Preuve automatisée locale verte le 27 octobre 2026 ; validation Produit/QA et Sécurité à recueillir |
| Hors périmètre | `P53-SBX-01` et parcours Stripe sandbox P53-09, paiement réel, activation client |

## Exécution reproductible

Depuis la racine du dépôt, sur Windows avec Docker dans WSL et une base de qualité libre :

```powershell
.\scripts\Test-QualityGateLocal.ps1 `
  -DockerMode wsl `
  -WslDistribution "Ubuntu-24.04" `
  -TestPostgresPort 55434 `
  -QualityTempRoot "D:\CodexQuality"
```

Le port `55434` évite les bases locales présentes sur `55432` et `55433` au moment de cette recette. Le verrou détruit et recrée uniquement la composition `prospect-crm-quality` ; choisir un autre port libre si nécessaire. Les tests utilisent des rôles PostgreSQL distincts et des données fictives.

## Preuves attendues

Le [manifeste versionné](./recettes/p53-10/manifest.json) fixe 20 scénarios locaux et leurs oracles. Le verrou doit produire :

- `test-results/p53-10/runs/<run_id>/evidence.json` : verdict calculé scénario → oracle → cas JUnit exact ; compteurs, SHA Git, empreinte de l'arbre source incluant les fichiers non commités, révision Alembic, empreintes SHA-256 des rapports et liste des artefacts inspectés ;
- `test-results/p53-10/runs/<run_id>/case-results.json`, `junit-extract.xml`, `packet.zip` et `packet.sha256` : relevé et extrait JUnit expurgés des cas réussis, empaquetés avec le manifeste et le verdict ; le JUnit brut reste hors du paquet ;
- `test-results/p53-10/runs/<run_id>/pytest-quality.xml` : copie du JUnit brut de cette exécution, à conserver sous contrôle d'accès pour vérifier l'empreinte et les cas du paquet ;
- `test-results/pytest-quality.xml`, `pytest-p53-01.xml`, `pytest-p53-03.xml` à `pytest-p53-08.xml`, `vitest.xml` : cas exécutés sans fail, error ou skip ;
- `test-results/alembic-current.txt`, `alembic-upgrade.log`, `alembic-downgrade.log`, `alembic-reupgrade.log` et leurs copies dans `p53-10/runs/<run_id>/`, plus `alembic-reconstruction.json` : trois étapes et schéma sur base jetable ;
- `test-results/phase-4-6/browser-axe.json` : 44 parcours, axe PASS ;
- `test-results/quality-summary.md` : verdict de **l'exécution courante**, marqué `EN COURS` au départ, `ROUGE` en cas d'échec et `VERT` uniquement après la vérification du paquet.

Le générateur refuse les rapports absents, antérieurs à l'exécution, en échec ou ignorés, les oracles ou correspondances oracle → cas modifiés, les cas JUnit non retrouvés, la mauvaise révision Alembic, les résultats navigateur non conformes et les marqueurs sensibles dans les rapports inspectés, dont `vitest-console.log`. Le test `P53-WEB-02` envoie cent webhooks signés à l'API réelle de test, recrée les objets serveur à mi-parcours et vérifie en PostgreSQL une seule admission, transition et écriture d'audit. L'instrumentation du parcours simulé autorise seulement la connexion à la base locale et bloque les autres résolutions DNS, connexions TCP, `sock_connect` asynchrones et appels SMTP ; une tentative témoin confirme le blocage. Un test direct du simulateur complète cette preuve. L'inspection humaine des autres sorties reste distincte.

Le paquet peut être vérifié sans base ni application en cours :

```powershell
$match = Get-Content .\test-results\quality-summary.md | Select-String 'Exécution P53-10 : ([0-9a-f]{32})'
$runId = $match.Matches[0].Groups[1].Value
$packet = Join-Path (Join-Path .\test-results\p53-10\runs $runId) 'packet.zip'
$hash = Join-Path (Join-Path .\test-results\p53-10\runs $runId) 'packet.sha256'
$junit = Join-Path (Join-Path .\test-results\p53-10\runs $runId) 'pytest-quality.xml'
.\.venv\Scripts\python.exe .\scripts\p53_10_evidence.py verify `
  $packet $hash $junit
```

Le vérificateur contrôle l'empreinte, les 20 scénarios, les oracles obligatoires, le relevé et l'extrait des cas, puis compare le JUnit brut au paquet lorsqu'il est fourni. Le JUnit brut reste local et sous contrôle d'accès ; il n'est jamais dans `packet.zip`. Pour comparer l'état source actuel à celui du dossier : `.\.venv\Scripts\python.exe .\scripts\p53_10_evidence.py fingerprint .`. Une modification, même d'un fichier non suivi par Git, change cette empreinte et rend le dossier antérieur non reproductible. Chaque nouvelle exécution garde son dossier propre et ne détruit pas un paquet antérieur.

## Journal de validation

Une première exécution complète du 26 octobre 2026 a été verte : 598 tests backend, 253 tests Vitest, 44 parcours navigateur avec axe PASS et 20 scénarios P53-10. Après le durcissement du générateur, 599 tests backend ont passé dans une relance ; celle-ci a été interrompue pendant Vitest. Les relances suivantes ont échoué pendant Alembic parce que le service Docker/WSL a redémarré et coupé la connexion PostgreSQL. La reproduction sur une composition isolée a également perdu PostgreSQL au milieu d'une requête, puis les conteneurs se sont retrouvés arrêtés. Le rapport vert de cette ancienne version reste **historique** ; la version présente du code exige une nouvelle exécution.

Le 27 octobre, trois exécutions ont d'abord échoué pendant le downgrade Alembic après une interruption de PostgreSQL sur WSL. Après rétablissement du service, le verrou complet a réussi : exécution `6f03eabb42944876a56b9762c63e731f`, 610 tests backend, 253 tests Vitest, 44 parcours navigateur avec axe PASS et 20 scénarios P53-10 `passed`. Le test des cent webhooks signés a été exécuté dans la suite backend réelle. Le paquet expurgé et sa copie JUnit brute ont été vérifiés ; l'empreinte source de cette exécution est `50dea3b4927a9f1c8ccbd58d864e230b7986bc8facf39c3017fe5fae65f04127`. Cette preuve reflète un arbre Git non commité ; toute modification ultérieure exige une nouvelle exécution pour couvrir le nouvel état.

La preuve automatisée locale est obtenue pour l'exécution ci-dessus. Il reste à conserver le paquet et son empreinte dans l'emplacement de preuves retenu, à vérifier l'état source final après commit et à recueillir les validations Produit/QA et Sécurité. L'incident Docker/WSL antérieur est conservé dans le journal comme historique d'exécution.

## Matrice de lecture

| Famille | IDs | Preuve centrale |
| --- | --- | --- |
| Prix et sessions | `P53-CAT-01`, `P53-CHK-01/02`, `P53-SIM-01` | Prix serveur, concurrence, rejeu et timeout sans seconde session. |
| Webhooks | `P53-WEB-01/02/03/04` | Signature, cent livraisons, ordre et collision. |
| Cycle | `P53-SUB-01/02`, `P53-CAN-01/02`, `P53-REF-01` | Paiement, grâce, annulation et remboursement borné. |
| Réconciliation | `P53-REC-01/02/03/04` | Correction prouvée, divergences bloquées, reprise et commande manuelle auditée. |
| Protection | `P53-RLS-01`, `P53-SEC-01`, `P53-NOEXT-01` | RLS, artefacts minimisés et instrumentation réseau/SMTP. |

`P53-REC-01` couvre deux oracles distincts : divergence de projection et timeout après effet. Le générateur exige les deux. Les variantes de devise explicitement marquées dans le manifeste sont recherchées chacune par identifiant JUnit exact.

## Critères et réserves

La **preuve automatisée locale** est conforme uniquement si les 20 scénarios et tous leurs oracles sont `passed`, que le verrou complet est vert et que le paquet expurgé est vérifiable. Une erreur ou un skip ferme le verdict.

La **validation fonctionnelle et sécurité** sera consignée ici après examen par Produit/QA et Sécurité : couverture des oracles, absence de données sensibles dans les artefacts, instrumentation réseau, et acceptation de la limite locale. Cette signature ne ferme pas `P53-SBX-01`, P53-09, les réserves Porte 4/P5.1 ni les portes de mise en service.

| Visa | Responsable | État | Point à examiner |
| --- | --- | --- | --- |
| Recette fonctionnelle locale | Produit/QA | En attente | Les 20 scénarios et leurs oracles, dont les deux oracles `P53-REC-01`, avec les quatre devises. |
| Inspection sécurité locale | Sécurité | En attente | Paquet expurgé, rapports locaux, absence d'effet externe instrumentée et limites du scan automatique. |

Après ces visas, consigner la date, la révision Git effectivement revue et l'empreinte du paquet accepté. Toute modification ultérieure de la branche exige une nouvelle preuve sur le nouvel état.
