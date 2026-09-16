# LeadGenerator — Contre-audit technique et recommandations consolidées

**Date :** 5 septembre 2026 (America/New_York).  
**Document examiné :** `C:/Users/Admin/Downloads/Audit_LeadGenerator (1).md`, daté du 14 août 2026.  
**Référence Git :** `e535848d42b3ca527fc3a640adc1576664640819`, complétée par les modifications locales présentes lors de la revue.  
**Livrable :** recommandations uniquement. Aucun changement de code, de dépendances, de configuration ou de déploiement.

## 1. Avis de décision

L’audit initial identifie de vrais points forts et une dette de dépendances réelle, mais sa conclusion « rien de structurel » est trop affirmative. Ses notes en étoiles et appréciations « senior/staff » ne reposent sur aucune grille mesurable. Elles ne constituent pas une garantie de sécurité ni de maturité opérationnelle.

La priorité est de rendre cohérents **le code examiné, les dépendances déclarées, l’environnement de test et l’image livrée**. L’environnement Python local contient déjà FastAPI **0.139.2** et Starlette **1.3.1**, tandis que `backend/requirements.txt` impose encore FastAPI **0.116.1**. Les résultats obtenus localement ne prouvent donc pas le comportement du prochain build Docker.

Autre correction majeure : le code utilise déjà `request.url.path` pour décider si les erreurs de validation doivent être assainies. L’audit présente cet usage comme une éventualité future. Avec une version vulnérable, ce point fournit un scénario concret de dégradation du contrat de confidentialité des erreurs, sous réserve qu’un en-tête Host malformé atteigne l’application. Il ne démontre pas un contournement de connexion ou une fuite inter-organisations.

**Décision proposée :** conserver l’architecture, corriger et vérifier la chaîne de livraison et les décisions de sécurité liées au chemin HTTP, renforcer le contrôle d’architecture et les preuves RLS. Reporter le durcissement CORS et le rangement cosmétique après ces travaux.

## 2. Méthode et limites

La double critique s’applique à chaque proposition :

1. Vérifier sa prémisse contre le dépôt et, lorsque nécessaire, les sources officielles.
2. Critiquer le remède lui-même : compatibilité, coût, effets indésirables et preuve de réussite attendue.

Le document reçu est une source à examiner, pas une autorisation d’exécuter ses suppressions ou mises à jour. La revue a porté sur les dépendances, Docker/Compose/Caddy, Azure Pipelines, le bootstrap HTTP, les protections d’authentification, la configuration, les unités de travail et migrations PostgreSQL, les tests d’architecture et certains tests RLS, ainsi que les fichiers suivis par Git.

Deux sondes ont été exécutées **en mémoire**, sans installation : lecture des métadonnées des paquets locaux et construction d’une requête Starlette avec Host malformé ; reproduction de la logique AST du test d’architecture sur trois imports interdits plausibles. Aucun serveur distant n’a été sondé et aucune base n’a été modifiée.

Ce contre-audit n’est ni un pentest, ni une exécution complète de la CI, ni une certification d’absence de secrets. Aucun nouveau `pip-audit` n’a été lancé ; le nombre « 8 avis » du document initial n’est pas reproduit. Les versions de l’image réellement déployée et les protections effectives du proxy restent inconnues. Les fichiers `.env` et le contenu des imports utilisateurs n’ont pas été lus.

L’arbre de travail contenait déjà de nombreuses modifications et des migrations non suivies par Git. Les écarts contemporains ne doivent pas être attribués rétroactivement à l’état du 14 août.

## 3. Analyse des propositions de sécurité

### 3.1 Starlette : correction nécessaire, diagnostic à préciser

**Première critique.** CVE-2026-48710 / GHSA-86qp-5c8j-p5mr est bien documentée. L’avis consulté indique les versions affectées jusqu’à 1.0.0, un correctif en 1.0.1 et un score CVSS de **6,5, modéré**. Qualifier cette même note de « critique » mélange classification et priorité métier. La faille permet une divergence entre chemin routé et chemin reconstruit à partir de Host ; l’impact dépend des décisions prises avec ce dernier. [Avis de sécurité](https://github.com/advisories/GHSA-86qp-5c8j-p5mr).

FastAPI 0.116.1 impose bien `starlette>=0.40.0,<0.48.0`. Cela prouve une plage déclarée incompatible avec le correctif ; cela ne prouve pas à soi seul une résolution exacte vers **0.47.3** à chaque installation. Le fichier du projet ne verrouille pas Starlette explicitement. [Métadonnées FastAPI 0.116.1](https://github.com/fastapi/fastapi/blob/0.116.1/pyproject.toml).

**Preuve locale.** `.venv/Scripts/python.exe` rapporte FastAPI 0.139.2, Starlette 1.3.1 et Uvicorn 0.35.0. Une requête ASGI construite avec le chemin `/api/auth/login` et `Host: example.com/public?x=` conserve le bon `request.url.path` dans cet environnement. Ce résultat limité est compatible avec la présence du correctif ; il ne valide ni tout le gestionnaire HTTP ni le déploiement.

Dans `backend/app/bootstrap.py:695`, `protected_payload` dépend de `request.url.path.startswith(...)`. À la ligne 714, un résultat faux bascule vers le gestionnaire standard FastAPI. D’autres décisions de format d’erreur utilisent ce même chemin jusqu’à la ligne 757. Sur une pile vulnérable acceptant le Host malformé, l’assainissement pourrait donc être évité et des détails de validation ou des entrées invalides renvoyés. La sensibilité des champs effectivement renvoyés doit être mesurée avec des données synthétiques. Réfléchir une donnée fournie par le demandeur n’est pas automatiquement divulguer les données d’un tiers.

Les invitations sont construites depuis une URL configurée : `application/use_cases/provisioning.py:471` et `organization.py:668`. L’audit ne démontre pas d’empoisonnement de ces liens par Host.

**Deuxième critique : le remède proposé.** On ne peut pas simplement retirer dans le projet la borne haute publiée par FastAPI. Ajouter Starlette 1.x tout en gardant FastAPI 0.116.1 produit un conflit de dépendances ; forcer l’installation masquerait ce conflit.

**Recommandation consolidée — P1, avant prochaine livraison :** sélectionner une combinaison FastAPI/Starlette compatible et corrigée, après examen de ses changements ; verrouiller ses dépendances transitives et reconstruire un environnement propre et l’image. Le seuil 1.0.1 est un correctif de cette CVE, pas une prescription de version finale ni une garantie contre les autres avis. Faire dépendre la confidentialité des erreurs du chemin ASGI/routage maîtrisé ou de métadonnées de routes, en tenant compte du montage sous préfixe ; envisager aussi un assainissement uniforme des erreurs API pour éviter une liste de préfixes fragile.

**Contre-argument à cette recommandation :** uniformiser trop largement peut masquer des erreurs utiles au client ; changer les chemins peut casser les applications montées. Préserver le contrat public documenté et tester les préfixes réels.

**Acceptation :** versions effectives archivées pour tests et image, `pip check` réussi, scan sans avis non traité, et cas HTTP synthétiques normal/malformé démontrant un assainissement stable pour authentification, invitations et prospects, directement puis via le proxy de QA. Vérifier aussi cookies, CSRF, redirections et fichiers statiques après mise à jour.

### 3.2 Proxy : risque valable, mécanisme décrit incorrectement

**Première critique.** La commande finale du `Dockerfile` configure bien `--forwarded-allow-ips "*"`. Cependant, le middleware d’Uvicorn **0.35.0** traite `X-Forwarded-For` et `X-Forwarded-Proto`, pas `X-Forwarded-Host`. Le lien direct fait par l’audit avec ce dernier est erroné. [Code Uvicorn 0.35.0](https://github.com/Kludex/uvicorn/blob/0.35.0/uvicorn/middleware/proxy_headers.py).

Un risque plus directement relié au code est l’usurpation d’IP : `presentation/api/routers/auth.py:36` utilise `request.client.host` pour le limiteur. Si une source non fiable atteint Uvicorn directement et peut fixer l’IP transmise, la dimension IP du contrôle peut perdre sa valeur.

`compose.qa.yaml` ne publie pas le port de l’application sur l’hôte : il utilise `expose: 8000`. Caddy publie 80/443 et relaie vers l’application. Cela réduit l’exposition externe directe, sans prouver l’isolement vis-à-vis des autres conteneurs ou la configuration du serveur réel.

**Deuxième critique.** Une IP Docker codée en dur peut changer après recréation. Faire confiance à tout un réseau partagé élargit à nouveau la confiance. Remplacer `*` sans tester peut faire voir l’IP du proxy pour tous les utilisateurs et déclencher des limitations collectives.

**Recommandation — P1 :** définir les sources de confiance d’après la topologie réelle, segmenter le réseau si nécessaire, garantir le traitement des en-têtes par le proxy et vérifier l’inaccessibilité du backend depuis les sources non autorisées. La politique Host et la confiance dans les en-têtes de proxy sont deux contrôles distincts.

**Acceptation :** derrière Caddy, l’IP et le schéma correspondent à la connexion réelle ; un client ne choisit pas son IP logique par un en-tête ; deux clients indépendants conservent des compteurs IP distincts. Un backend inaccessible directement ne dispense pas de documenter les pairs internes autorisés.

### 3.3 Scan Python : bonne proposition, portée trop limitée

**Première critique.** Le YAML contient `npm audit --audit-level=high`, mais pas de scan Python. Ajouter cette étape est pertinent. Le nombre d’avis n’est toutefois pas une mesure du nombre de chemins exploitables ; il faut conserver les identifiants, versions, conditions d’impact et décisions.

**Deuxième critique.** Scanner uniquement la `.venv` actuelle manquerait la divergence avec le build. Un scan des dépendances Python ne couvre ni les paquets système du conteneur ni toutes les attaques de chaîne logicielle. Un scanner détecte des vulnérabilités connues ; il ne certifie pas que le code des dépendances est sûr. [Projet pip-audit](https://github.com/pypa/pip-audit).

**Recommandation — P1 :** auditer la résolution verrouillée effectivement installée dans la CI et l’image, publier un rapport machine lisible et appliquer une politique d’exceptions limitée dans le temps, avec responsable, justification et échéance. Prévoir une réévaluation régulière des mêmes artefacts, car de nouveaux avis peuvent apparaître sans changement de code. C’est une proposition, aucune automatisation n’a été créée.

**Acceptation :** un avis non accepté bloque la livraison ; une indisponibilité du service d’audit n’apparaît pas comme un résultat « sain » ; la résolution et le rapport sont rattachés au commit et à l’image. Garder un seul scanner Python au départ pour limiter la maintenance.

### 3.4 CORS : optimisation secondaire

**Première critique.** `bootstrap.py:684` autorise tous les noms d’en-têtes CORS, avec origines configurées. Ce n’est pas équivalent à autoriser toutes les origines, et CORS n’est pas une barrière contre les clients non navigateurs. L’audit a raison de classer ce point bas.

**Deuxième critique.** Limiter arbitrairement la liste à `Content-Type` et `X-CSRF-Token` peut casser un en-tête de corrélation ou une évolution des appels. Le bénéfice de sécurité est modeste quand l’origine autorisée et le contrôle CSRF sont déjà les barrières principales.

**Recommandation — P3 :** inventorier les en-têtes réellement nécessaires, puis resserrer si cela simplifie le contrat API. Tester les prérequêtes autorisées et le rejet d’une origine étrangère, y compris sur les réponses d’erreur. Ne pas retarder la correction des dépendances pour cela.

### 3.5 HEALTHCHECK : une lacune déjà compensée

Le Dockerfile n’a pas de `HEALTHCHECK`, mais `compose.qa.yaml`, service `app`, configure une sonde sur `/api/health/live`. Le dépôt contient aussi `tests/test_readiness.py` ; la présence de ces tests ne suffit pas à prouver le branchement opérationnel de la disponibilité.

**Recommandation — P3 :** conserver la sonde existante, vérifier que le mécanisme de déploiement utilise aussi la disponibilité appropriée avant d’envoyer du trafic. Une sonde de vie ne doit pas provoquer une boucle de redémarrages lorsqu’une dépendance externe tombe. Ajouter une deuxième définition dans Docker n’est utile que pour les modes de livraison qui ne passent pas par Compose.

## 4. Réévaluation des appréciations positives

| Affirmation initiale | Conclusion après examen | Recommandation et contre-critique |
|---|---|---|
| Architecture propre et frontières strictement testées | Les quatre couches et le bootstrap sont présents. La garantie AST est incomplète. | Renforcer le contrôle ciblé, sans réécrire l’architecture. Voir §5. |
| RLS empêche toute fuite si un filtre est oublié | Vrai sous conditions de rôle, table, politique et contexte ; pas une propriété absolue de tout le système. | Maintenir une matrice de tables et chemins privilégiés. Ne pas annoncer une faille RLS sans scénario. |
| Argon2id bien paramétré | Code confirmé : coût 3, mémoire 65 536 KiB, parallélisme 4. | Conserver ; mesurer latence et mémoire sous charge avant toute hausse des paramètres. Un coût plus élevé peut dégrader la disponibilité. |
| Hash factice égalisant le temps | `verify_dummy` est appelé lorsque le compte ou le hash manque. | Bonne réduction d’un signal, pas preuve d’égalité des durées : requêtes DB et autres branches diffèrent. N’ajouter une campagne statistique que si le modèle de menace la justifie. |
| Cookies sûrs et expirations distinctes | `responses.py:36` confirme HttpOnly, Secure configurable, SameSite lax, Path `/`, sans Domain. La configuration impose Secure et `__Host-` en production ; Redis gère idle/absolue. | Vérifier le comportement livré et les révocations/changements d’organisation. HttpOnly ne bloque pas les actions qu’un script XSS peut déclencher au nom du navigateur. |
| CSRF renforcé | Vérifications Origin/Referer, JSON et `hmac.compare_digest` confirmées dans `security.py`. | Préserver ; une fonction présente ne prouve pas sa couverture sur chaque mutation. Tester un parcours représentatif et inventorier les routes mutantes. La vérification Content-Type seule ne remplace pas CSRF. |
| Rate limiting solide | Contrôle avant vérification du mot de passe, dimensions IP/email et implémentation Redis présents. | Valider la confiance proxy et le comportement en panne Redis ; ne pas promettre une protection absolue contre une attaque distribuée. |
| Configuration « secure by default » | Des refus explicites existent pour `APP_ENV=production`. | Conserver ; vérifier que le déploiement sélectionne réellement ce mode. L’existence des validations ne certifie pas les variables du serveur. |
| Recherche exhaustive négative de secrets | Affirmation non reproductible : aucun périmètre historique ni rapport fourni. Un `.env` local existe, ce qui n’est pas anormal en soi. | Scan expurgé de l’historique et des artefacts, sans reproduire les valeurs. Rotation seulement si exposition établie ; ne pas confondre fichier local et secret publié. |
| Absence d’injection SQL | Paramétrage visible, mais ce contre-audit ne démontre pas l’absence sur tous les chemins. Les migrations emploient aussi du SQL construit à partir de noms internes. | Examiner la provenance des entrées dans les requêtes et fonctions privilégiées. La présence de `text()` ou d’une f-string n’est pas à elle seule une vulnérabilité. |
| Frontend sans sinks dangereux ni stockage de tokens | Recherche ciblée sans résultat dans `client/src` pour les quatre motifs cités. | Signal favorable, pas preuve d’absence de XSS, de fuite via URL, export ou bibliothèque. Éviter une refonte d’authentification sans besoin démontré. |
| Erreurs sensibles toujours assainies | Intention confirmée, mais décision fondée sur l’URL reconstruite. | Traiter le point du §3.1 et tester les routes nouvelles ; c’est plus utile que l’appréciation globale. |
| Typage strict et lint strict | `strict=True` confirmé ; `ignore_missing_imports=True` atténue certaines garanties. Ruff applique une sélection précise de règles. | Réduire les exceptions de typage là où elles masquent un risque réel ; ne pas activer toutes les règles sans bénéfice mesuré. |
| 37 fichiers de tests démontrent la qualité | Le dépôt actuel a évolué ; un compte de fichiers ne mesure ni les scénarios ni l’efficacité. | Rattacher les preuves aux risques : isolation, permissions, concurrence, rollback, expiration. Les tests avec fake et les tests PostgreSQL/Redis ont des rôles complémentaires. |
| Pas de `except Exception` | Faux pour l’état examiné : exemples dans `routers/retention.py:95` et `tenant_unit_of_work.py`. | Examiner chaque usage : nettoyage transactionnel et remise en exception peuvent être corrects. Ne pas supprimer mécaniquement ces blocs. |
| Capacités centralisées | Organisation des capacités et exceptions métier favorable à l’auditabilité. | Vérifier leur application sur chaque commande et les chemins SQL privilégiés ; un registre central n’impose pas seul les permissions. |

## 5. Deux garanties à consolider sans refonte

### 5.1 Le test d’architecture accepte certains imports interdits

`tests/test_architecture_boundaries.py:7` ne conserve que la première composante de `node.module` ou du nom importé ; les imports relatifs sans module sont ignorés. La liste de frameworks interdits est limitée.

La reproduction en mémoire de cette logique accepte les trois formes suivantes :

| Import fictif depuis une couche intérieure | Racine vue par le contrôle | Problème |
|---|---|---|
| `from backend.app.infrastructure import postgres` | `backend` | La couche visée disparaît. |
| `from .. import infrastructure` | Aucune | `node.module` vaut `None`. |
| `import sqlalchemy` | `sqlalchemy` | Dépendance externe absente de la liste interdite. |

Il s’agit d’une **faille du contrôle**, pas d’une preuve que ces imports existent dans le domaine actuel.

**Recommandation — P2 :** résoudre les imports absolus et relatifs par rapport au fichier source, puis appliquer les frontières ; expliciter les dépendances externes admises pour le domaine. Ajouter quelques cas négatifs au contrôle lui-même pour prouver qu’il rejette une transgression.

**Contre-critique :** développer un analyseur complet serait disproportionné. Un outil de contrats d’import peut être évalué si les règles se multiplient ; une correction AST ciblée suffit si elle couvre les formes utilisées. Ne pas exiger une réorganisation des couches uniquement pour satisfaire le test.

**Acceptation :** les trois formes interdites sont rejetées et les imports légitimes restent acceptés.

### 5.2 RLS : protection substantielle, avec une base de confiance explicite

`infrastructure/postgres/tenant_unit_of_work.py` configure transactionnellement `app.actor_id`, `app.organization_id` et `app.request_id`. `app.audit_scope`, cité comme mécanisme général dans l’audit, intervient notamment dans les accès aux événements d’audit : ce n’est pas l’unique clé du cloisonnement.

Les migrations utilisent `ENABLE` et `FORCE ROW LEVEL SECURITY`. Le script de rôles crée `prospect_app` avec `NOBYPASSRLS` et un rôle `prospect_rls_definer` avec `BYPASSRLS` et `NOLOGIN`. Des fonctions `SECURITY DEFINER` existent : elles font partie des chemins privilégiés à vérifier, sans constituer par leur seule présence un défaut.

PostgreSQL précise que les superutilisateurs et les rôles BYPASSRLS contournent les politiques ; les propriétaires ont un comportement spécifique, modifiable par FORCE RLS. La protection doit donc être évaluée avec les droits effectifs du runtime. [Documentation PostgreSQL](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

Le dépôt possède déjà des tests utiles : `tests/integration/test_tenant_rls.py:182` vérifie rôles/métadonnées, `:403` le refus par défaut et le cloisonnement, `:473` la remise à zéro du contexte après commit, rollback et réutilisation du pool. Il ne faut pas recommander ces tests comme s’ils n’existaient pas.

**Recommandation — P1 pour toute nouvelle table métier :** étendre la couverture existante aux tables nouvelles, aux opérations de lecture/écriture et aux fonctions privilégiées ; vérifier aussi caches, fichiers et exports, qui ne sont pas protégés automatiquement par PostgreSQL. Vérifier les droits de création dans les schémas du `search_path`, les droits EXECUTE et la validation acteur/organisation dans chaque fonction privilégiée.

**Contre-critique :** multiplier des tests SQL identiques par table peut coûter cher. Préférer un inventaire automatisé et quelques scénarios adverses représentatifs, complétés par les exceptions propres aux fonctions privilégiées. Aucun besoin de supprimer le modèle RLS ou de passer à une base par client n’est établi ici.

## 6. CI, reproductibilité et exploitation : omissions de l’audit

### 6.1 Révision Alembic attendue décalée dans l’arbre actuel

`azure-pipelines.yml` attend `20260904_0015`. Deux migrations locales non suivies ajoutent `20260905_0016`, puis `20260905_0017`. **Si ces fichiers sont livrés ensemble sans ajustement de la valeur attendue**, `upgrade head` et le contrôle de révision attendront des états différents. C’est une incohérence statique conditionnelle, pas un échec CI effectivement observé.

**Recommandation — P1 avant intégration :** aligner la révision attendue sur le lot réellement livré et vérifier l’unicité de la tête. Conserver une révision attendue liée à la livraison ; dériver aveuglément la valeur du même dossier pourrait masquer une migration oubliée. Acceptation : la révision de release, la tête unique et la base migrée coïncident.

### 6.2 Migrations dans les deux sens : portée à ne pas exagérer

La CI réalise un downgrade jusqu’à `20260723_0002`, puis remonte. Ce n’est pas un retour jusqu’à une base vide. L’opération est utile, mais ne prouve pas la conservation des données métier ni la viabilité d’un retour arrière en production. `alembic check` ne certifie pas toutes les politiques RLS et fonctions SQL personnalisées.

**Recommandation — P2 :** pour les migrations à risque, tester depuis la version précédemment livrée avec un jeu de données représentatif, vérifier les invariants et prévoir une stratégie de récupération. **Contre-critique :** ne pas imposer un downgrade destructeur en production ; une correction en avant avec sauvegarde validée peut être préférable.

### 6.3 Qualité définie dans le YAML, application effective non vérifiée

Lint, mypy, tests, refus de skips et contrôles d’artefacts sont présents. Les déclencheurs visibles portent sur main/master. Les politiques de branche, permissions de contournement, exécutions PR et résultats Azure ne sont pas démontrés par ce seul fichier.

**Recommandation — P2 :** vérifier qu’un échec empêche réellement intégration et livraison, avec une preuve d’exécution rattachée au commit. Préserver le refus des skips tant qu’il reste praticable ; toute exception future doit être explicite et temporaire. Ne pas déduire l’absence de contrôle PR de l’absence d’un bloc YAML particulier.

### 6.4 Artefact testé et artefact livré

Docker utilise des tags mobiles (`node:22-alpine`, `python:3.12-slim`) et met à jour pip avant installation. Le pipeline installe les dépendances pour tester ; un build ultérieur peut résoudre une autre arborescence transitive. La dérive locale observée rend ce sujet concret.

**Recommandation — P1/P2 :** produire un verrouillage transitif et un inventaire des composants, identifier l’image par digest et vérifier l’artefact destiné à être promu. Ajouter ensuite un scan des composants système de l’image. **Contre-critique :** figer un digest sans mécanisme de mise à jour fige aussi des défauts ; associer immutabilité de release et entretien planifié, sans multiplier les outils d’emblée.

### 6.5 Sauvegarde et restauration

`scripts/qa-backup.sh` crée un `pg_dump -Fc`. C’est un point de départ existant ; il ne fournit pas à lui seul la preuve d’une restauration, d’une conservation hors machine ou d’un délai de reprise. La revue n’établit pas que ces mécanismes sont absents ailleurs.

**Recommandation — P2, avant données importantes :** réaliser une restauration isolée et documenter les objectifs de perte maximale et de délai de reprise, ainsi que les fichiers externes nécessaires aux imports. **Contre-critique :** ne pas sauvegarder systématiquement les sessions Redis pour les restaurer ; forcer une reconnexion peut être préférable. Dimensionner la conservation selon la valeur des données et les engagements réels.

## 7. Hygiène du dépôt : nettoyage sélectif

La présence Git des documents Word de racine, du verrou Office, des trois `.bat` et des noms atypiques est confirmée. Les noms Unicode ne rendent pas nécessairement un fichier illisible ou inutilisable ; son utilité doit être vérifiée avant suppression. Un `.bat` mal nommé peut contenir une procédure utile à convertir en `.ps1` documenté.

**L’exclusion globale `*.docx` est déconseillée :** des manuels utilisateurs `.docx` utiles sont suivis sous `docs/manuel-utilisateur`. `*.bat` peut également masquer un script légitime. Ajouter une règle ignore ne retire pas un fichier déjà suivi et n’efface pas son historique.

Un point plus significatif est omis : Git suit un CSV sous `.runtime/imports/`, actuellement marqué supprimé dans l’arbre local. Son contenu n’a pas été consulté et sa sensibilité n’est pas connue. C’est toutefois un emplacement de données d’exécution à distinguer des fixtures de test.

**Recommandation — P2 si données réelles, sinon P3 :** inventorier et classer avant nettoyage ; exclure les fichiers temporaires Office et les chemins d’exécution, garder les livrables métier, déplacer les scripts utiles. Vérifier confidentiellement si l’import suivi est synthétique. Une exposition réelle pourrait justifier un traitement de l’historique ; ce traitement doit être préparé séparément, car il peut perturber les clones et n’annule pas les copies déjà diffusées.

**Acceptation :** aucun fichier d’exécution ou verrou Office suivi, manuels toujours versionnables, scripts utiles conservés sous des noms explicites. Aucun fichier n’a été supprimé dans le cadre de ce contre-audit.

## 8. Plan de recommandations priorisé

Les priorités expriment l’ordre de traitement, pas un score CVSS. Les efforts sont relatifs : faible = intervention locale ; moyen = plusieurs composants et validation ; variable = dépend du déploiement.

| Ordre | Action proposée | Priorité / effort | Preuve de clôture |
|---|---|---|---|
| 1 | Réconcilier dépendances déclarées/locales/image, choisir une pile corrigée compatible | P1 / moyen | Installation propre, inventaire, `pip check`, scan et tests sur la pile livrée |
| 2 | Retirer la dépendance à l’URL reconstruite pour la confidentialité des erreurs | P1 / moyen | Erreurs synthétiques assainies avec Host normal/malformé, chemin direct et proxy |
| 3 | Vérifier puis limiter la confiance proxy selon le réseau réel | P1 / variable | IP non falsifiable, schéma correct, backend non exposé aux sources non fiables |
| 4 | Ajouter un scan Python de la résolution livrée et une politique de traitement | P1 / faible à moyen | Rapport archivé et gate vérifié |
| 5 | Aligner le lot de migrations et la révision attendue avant intégration | P1 / faible | Tête unique et révision de release cohérentes |
| 6 | Étendre les preuves RLS aux nouvelles tables/commandes et chemins privilégiés | P1 pour le nouveau périmètre / moyen | Tests existants étendus, refus inter-organisations sur les opérations concernées |
| 7 | Réparer les angles morts du contrôle d’architecture | P2 / faible à moyen | Imports interdits fictifs rejetés, imports permis acceptés |
| 8 | Vérifier la politique de branches et le lien entre tests et artefact promu | P2 / variable | Échec réellement bloquant et traçabilité commit/image |
| 9 | Qualifier le CSV suivi et vérifier la récupération des données | P2 / variable | Classification sans exposition et restauration isolée prouvée |
| 10 | Nettoyer sélectivement, puis resserrer CORS si utile | P3 / faible | Documents utiles conservés, prérequêtes métier fonctionnelles |

**À ne pas faire sur la seule foi de l’audit :** forcer Starlette en ignorant FastAPI ; supprimer globalement Word ou les scripts ; remplacer l’architecture ; ajouter un second HEALTHCHECK sans besoin ; présenter « aucune fuite possible » ou « aucun secret » comme un résultat prouvé ; considérer une CI locale verte comme équivalente à la validation de l’image.

## 9. Registre des preuves et incertitudes

| Élément | État de preuve |
|---|---|
| FastAPI 0.116.1 déclaré et installation Docker depuis requirements | Confirmé par lecture du dépôt |
| FastAPI 0.139.2 / Starlette 1.3.1 dans `.venv` | Confirmé par métadonnées locales |
| Version Starlette de l’image déployée | Non vérifiée |
| CVE, plage affectée et correctif | Vérifiés auprès de l’avis publié |
| Contournement d’assainissement dans une pile vulnérable | Scénario déduit du code et de l’avis ; non reproduit sur cette pile |
| Authentification contournée / fuite de données d’un autre tenant | Non démontré |
| Trois angles morts AST | Reproduits en mémoire, sans changement de fichier source |
| Tests RLS et sonde Compose | Présence et intentions vérifiées ; suite non exécutée ici |
| Huit avis pip-audit | Non reproduits, inventaire initial non fourni |
| Alignement CI avec les migrations locales | Incohérence conditionnelle constatée avant leur intégration |
| CSV d’exécution suivi | Métadonnée Git confirmée ; contenu et sensibilité non examinés |
| Qualité et sécurité globales de production | Non certifiées par cette revue |

Les sources externes ci-dessus ont été consultées pour ce contre-audit. Les chemins de code se rapportent à l’arbre local décrit en tête ; les numéros de ligne peuvent changer avec les travaux déjà en cours. La recommandation centrale est d’améliorer les preuves et la cohérence de livraison, tout en préservant les contrôles applicatifs déjà utiles.
