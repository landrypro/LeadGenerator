# P53-10 — Consolidation des preuves et recette synthétique

| Métadonnée | Valeur |
| --- | --- |
| Statut | Décisions `P53-10-D01` à `P53-10-D04` approuvées ; preuve automatisée locale verte le 27 octobre 2026 ; validations Produit/QA et Sécurité à recueillir |
| Périmètre | P5.3 local : simulateur de paiement, webhooks, cycle d'abonnement et réconciliation |
| Données | Fixtures fictives uniquement ; CAD, USD, EUR et XAF, sans conversion |
| Référence | [Spécifications P5.3](./PHASE_5_3_SPECIFICATIONS_DETAILLEES.md), [contrat simulateur](./PHASE_5_3_SIMULATEUR_PAIEMENT_WEBHOOKS.md), [décisions P5.3](./PHASE_5_3_DECISIONS.md) |

## 1. Résultat attendu et frontière

P53-10 doit produire une **recette vérifiable**, reliant chaque scénario local P5.3 à un ou plusieurs tests exécutés, à leur résultat JUnit et aux contrôles de sécurité. Un lecteur doit pouvoir retrouver la révision Git, la révision Alembic, la commande exécutée, l'horodatage, les rapports et les éventuels écarts sans déduire la couverture d'un simple total de tests.

La recette porte sur `disabled` et `simulated`, sur PostgreSQL/Redis de test et sur des données synthétiques. `P53-09` et `P53-SBX-01` (Stripe sandbox) sont traités dans une autre conversation : leur preuve sera annexée plus tard avec une décision explicite. P53-10 local peut être accepté avant cette annexe, mais **la clôture technique globale P5.3 et toute activation restent distinctes**. Aucun paiement réel, email, donnée client ou appel au fournisseur n'est autorisé par ce lot.

## 2. Point de départ constaté

Le verrou local du 24 octobre 2026 a produit `test-results/quality-summary.md` avec le verdict `VERT`, la révision Alembic attendue `20261023_0058`, `pytest-quality.xml` (563 tests), `pytest-p53-08.xml` (92 tests), `vitest.xml` (245 tests) et `phase-4-6/browser-axe.json` (44 parcours, axe PASS). Le commit courant au moment du cadrage est `008c515` (`P53-08`). Ces fichiers sont des **preuves d'exécution locales**, pas encore un dossier P53-10 complet : le résumé ne cite pas P53-08 dans sa liste de rapports et ne fournit pas de correspondance scénario → test → résultat. Le dossier à créer devra indiquer la révision effectivement testée et signaler tout état de travail non commité ; il ne devra pas attribuer rétroactivement le verrou du 24 octobre à un nouveau commit.

Le précédent [P52-08](./RECETTE_P52_08_SYNTHETIQUE.md) fournit un modèle utile : manifeste versionné, fichier `evidence.json` généré et vérification JUnit sans skip. P53-10 l'étend aux scénarios P5.3, aux quatre devises et aux contrôles d'absence d'effet externe. La [recette synthétique](./RECETTE_P53_10_SYNTHETIQUE.md) décrit la commande et les artefacts.

## 3. Registre de couverture réalisé

Le [manifeste versionné](./recettes/p53-10/manifest.json) contient les 20 scénarios locaux, leurs oracles et les identifiants **exacts** des cas JUnit. Une empreinte du contrat oracle → cas est fixée indépendamment dans le générateur ; changer la correspondance exige donc une modification explicite du contrat. Le générateur vérifie les cas dans le rapport du verrou complet et calcule un résultat pour chaque oracle. Les variantes paramétrées CAD, USD, EUR et XAF sont vérifiées individuellement lorsque la devise fait partie de l'oracle. Le tableau ci-dessous facilite la lecture ; le manifeste constitue la correspondance exhaustive.

| Scénarios | Tests reliés dans le manifeste | Oracle contrôlé |
| --- | --- | --- |
| `P53-CAT-01`, `P53-CHK-01/02`, `P53-SIM-01` | `tests/test_billing_api.py`, `tests/test_billing_sessions.py`, `tests/integration/test_billing_checkout_portal.py`, `tests/test_billing_simulator.py` | Prix choisi côté serveur ; concurrence/idempotence ; timeout sans deuxième session. |
| `P53-WEB-01/02/03/04` | `tests/test_billing_webhook_admission.py`, `tests/integration/test_p53_10_billing_proofs.py`, `tests/integration/test_billing_projection.py`, `tests/test_billing_simulator.py` | Signature, fraîcheur, cent livraisons par l'API sur deux instances serveur, une seule admission et projection durable, ordre et collision. |
| `P53-SUB-01/02`, `P53-CAN-01/02`, `P53-REF-01` | `tests/test_billing_domain.py`, `tests/test_billing_lifecycle.py`, `tests/integration/test_billing_projection.py` | États, période, grâce, annulation, remboursement et audit. |
| `P53-REC-01/02/03/04` | `tests/test_billing_reconciliation.py`, `tests/integration/test_billing_reconciliation_observations.py` | Correction uniquement avec preuve locale certaine ; divergence bloquée ; reprise ; commande manuelle autorisée et auditée. |
| `P53-RLS-01` | `tests/integration/test_billing_schema.py`, `tests/integration/test_billing_reconciliation_observations.py` | Lecture/écriture inter-tenant et accès non autorisé refusés sans révélation. |
| `P53-SEC-01` | Tests d'audit/API existants **plus inspection des artefacts produits** | Aucun secret, donnée bancaire, URL sensible ni payload brut dans rapports, logs et audits. |
| `P53-NOEXT-01` | `tests/test_p53_10_local_proofs.py`, `tests/integration/test_p53_10_billing_proofs.py` et adaptateur `disabled` | DNS, TCP et SMTP instrumentés pendant l'admission API et la projection worker ; seul PostgreSQL de test est autorisé. |

Le verrou ajoute les contrôles de migration, RLS, reconstruction après rollback, adaptateur `disabled`, résolution des webhooks et variantes des quatre devises. Une preuve manquante rend le dossier local non conforme.

Les deux documents P5.3 emploient `P53-REC-01` avec des formulations différentes : divergence de projection dans la spécification générale, timeout après effet dans le contrat du simulateur. Le manifeste conserve **les deux oracles sous le même ID**, avec des cas JUnit distincts, et le générateur exige les deux. `P53-WEB-04` et `P53-REC-02/03/04` proviennent du contrat du simulateur et font également partie de la recette locale.

## 4. Dossier de preuves produit par le verrou

| Artefact | Contenu minimal |
| --- | --- |
| `docs/recettes/p53-10/manifest.json` | Version du contrat, périmètre `synthetic`, 20 scénarios fermés, cas JUnit attendus, références aux contrôles complémentaires ; aucun résultat inventé. |
| `test-results/p53-10/runs/<run_id>/evidence.json` | Résultats calculés à partir des rapports de la **même exécution**, Git SHA, empreinte de tous les fichiers Git visibles, état propre/sale, Alembic, UTC, compteurs, empreintes SHA-256 des rapports, verdict par scénario et réserves. |
| `test-results/p53-10/runs/<run_id>/case-results.json` et `junit-extract.xml` | Relevé et extrait JUnit expurgés des cas effectivement réussis, liés par empreinte au rapport complet et au verdict. |
| `test-results/p53-10/runs/<run_id>/pytest-quality.xml` et journaux Alembic | Copie JUnit brute sous contrôle d'accès, et journaux distincts pour upgrade, downgrade, nouvel upgrade ; leur empreinte figure dans `evidence.json`. |
| `docs/RECETTE_P53_10_SYNTHETIQUE.md` | Commande reproductible, matrice lisible, résultats constatés, limites et procès-verbal de recette locale. |
| Rapports existants | JUnit backend ciblés et complet, JUnit Vitest, rapport navigateur/axe, migration, audit npm et résumé du verrou. |

Le manifeste et la recette documentaire sont destinés à être versionnés avec le commit P53-10. `evidence.json` et les rapports volumineux sont générés sous `test-results/`. Chaque exécution conserve son propre dossier `test-results/p53-10/runs/<run_id>/`. Le paquet expurgé `packet.zip` contient le manifeste, le verdict, `case-results.json` et `junit-extract.xml` ; son empreinte est dans `packet.sha256`. Le vérificateur autonome contrôle leur cohérence sans base ni serveur, puis peut comparer le JUnit brut archivé sous contrôle d'accès. Leur archivage dans un emplacement de preuves partagé reste à effectuer lors de la revue. On ne copie ni `.env`, ni secret, ni corps de webhook, ni base de données dans ce paquet.

Le générateur refuse : rapport manquant, test absent/échoué/ignoré, révision Alembic inattendue, scénario sans oracle, exécution de rapports de dates différentes ou sortie non synthétique. Il lie les rapports à un identifiant d'exécution, vérifie leurs horodatages et calcule leurs empreintes. Il distingue les preuves **automatiques** des attestations **manuelles** ; une valeur déclarative `no_external_effects: true` ne suffit pas à établir l'absence d'effet externe.

## 5. Exécution et contrôles de sûreté

1. Lancer le verrou complet sur une base de qualité Docker neuve en mode WSL, avec le mode fournisseur `simulated` ou `disabled`, les flags d'activation réelle désactivés et les fixtures fictives. La commande habituelle est `./scripts/Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04" -QualityTempRoot "D:\CodexQuality"` depuis PowerShell ; les ports de qualité doivent être disponibles avant le départ.
2. Faire échouer le verrou si un JUnit ciblé ou complet contient un échec, une erreur ou un skip, ou si un scénario du manifeste n'a aucun cas réussi correspondant. Inclure `pytest-p53-08.xml` dans le résumé produit par le verrou.
3. Vérifier la migration `upgrade head`, `alembic current`, `alembic check` et le rollback sur base jetable ; l'isolation RLS et les droits de la commande manuelle sont contrôlés avec des rôles de test distincts.
4. Inspecter les rapports JUnit, `vitest-console.log`, la preuve P52-08, le rapport navigateur, les sorties Alembic et le contexte d'exécution avec des règles explicites de détection de secrets, données bancaires et URL de session ; revoir les faux positifs, sans publier les chaînes trouvées dans `evidence.json`. Le registre `scanned_artifacts` donne la portée exacte du contrôle automatique ; l'inspection humaine couvre les autres sorties avant visa Sécurité.
5. Établir l'absence d'effet externe pour le parcours simulé couvert par la recette : `test_p53_10_simulator_has_no_network_or_smtp_effect` instrumente directement le simulateur ; `test_hundred_signed_webhooks_across_restart_have_one_durable_effect_and_no_external_calls` instrumente DNS, TCP, `sock_connect` asynchrone et SMTP autour de cent admissions signées via l'API et du worker PostgreSQL, avec seule la base locale autorisée. Une tentative témoin confirme que le blocage `sock_connect` agit réellement.
6. Vérifier `packet.zip` avec `packet.sha256`, l'extrait expurgé et la copie JUnit brute, puis comparer l'empreinte de l'arbre source à celle du verdict. L'empreinte inclut les fichiers Git non commités et est comparée avant/après le verrou ; toute modification exige une nouvelle preuve. Faire ensuite signer la recette locale par Produit/QA et Sécurité selon les responsabilités déjà définies.

Un lancement du verrou s'arrête/recrée la composition `prospect-crm-quality` ; il doit être planifié quand cette base de test est libre. Le résumé de l'exécution courante passe à `EN COURS` dès le début, à `ROUGE` en cas d'échec et à `VERT` après vérification du paquet ; un ancien dossier vert reste consultable sans masquer l'échec courant. L'exécution `6f03eabb42944876a56b9762c63e731f` du 27 octobre 2026 a produit une preuve automatisée verte pour les 20 scénarios locaux, avec 610 tests backend et 253 tests Vitest sans échec ni skip. Elle précède le présent alignement documentaire : une nouvelle preuve doit couvrir l'état source final. La [recette locale](./RECETTE_P53_10_SYNTHETIQUE.md) donne le détail des résultats ; la revue humaine reste distincte.

## 6. Critères de sortie

**P53-10 local conforme** si : tous les scénarios locaux des sections 3 et 5 sont `passed` avec cas JUnit exacts, zéro fail/error/skip ; les quatre devises sont couvertes ; migration/RLS/rollback sont démontrés ; inspection des artefacts et contrôle d'effet externe sont concluants ; le paquet de preuves est traçable et reproductible ; la recette locale est signée.

**Reste réservé** : `P53-SBX-01`, la parité Stripe sandbox et les décisions P53-09 ; les portes Finance, Juridique, Sécurité et Exploitation ; les réserves P5.1/Porte 4 ; tout paiement réel ou activation client. Le résultat P53-10 local est une preuve pour ces décisions ultérieures, pas leur validation.

## 7. Décisions approuvées par le commanditaire

| ID | Décision approuvée le 24 octobre 2026 | Conséquence |
| --- | --- | --- |
| `P53-10-D01` | La **recette locale du simulateur est séparée** de l'annexe Stripe sandbox P53-09. | P53-10 peut être clos localement si ses preuves sont complètes ; `P53-SBX-01` reste explicitement ouvert. |
| `P53-10-D02` | Le manifeste et la recette lisible sont versionnés ; les JUnit et `evidence.json` sont générés ; un paquet expurgé est archivé avec SHA-256. | Une revue peut relier scénarios, tests et révision sans verser des logs sensibles dans Git. |
| `P53-10-D03` | L'absence d'effet externe est vérifiée par réseau bloqué/instrumenté et inspection des artefacts. | Les affirmations « sans réseau » et « sans secret » reposent sur une observation, pas sur un champ déclaratif. |
| `P53-10-D04` | Produit/QA et Sécurité valident la recette locale ; les autorisations Stripe/réel suivent des portes séparées. | La clôture locale possède des responsables identifiés sans élargir le GO de mise en service. |

Après GO explicite de développement, l'ordre d'exécution proposé est : (1) figer le manifeste et vérifier chaque oracle ; (2) combler les lacunes par des tests ciblés ; (3) coder le générateur et son échec fermé dans le verrou ; (4) produire la recette et l'archive expurgée ; (5) exécuter le verrou complet et recueillir les validations.
