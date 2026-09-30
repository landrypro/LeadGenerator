# Phase 4.2 — Worker et traitements fiables

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 4.2 — Worker et traitements fiables |
| Version | 0.4 — réalisation technique et verrou qualité local VERT |
| Statut | Décisions `P4.2-01` à `P4.2-08` validées ; socle 4.2 implémenté et verrou qualité local VERT le 24 septembre 2026 à 00:11 UTC ; recette fonctionnelle en 4.6 |
| Date | 23 septembre 2026 |
| Contrat parent | [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md) |
| Prérequis | PostgreSQL et RLS 2.3, audit 2.4, import CSV 3.1, Redis et observabilité existants ; verrou technique 4.1 VERT |

## 1. Résultat attendu et frontière du lot

4.2 fournit un mécanisme durable pour exécuter hors requête HTTP les travaux métier autorisés. Une requête peut
enregistrer un travail dans la même transaction que sa décision métier, puis répondre sans attendre son exécution.
Un redémarrage, une concurrence entre workers ou une perte de signal de réveil ne doit ni perdre le travail, ni
multiplier ses effets métier. L’état de chaque travail et de ses tentatives est consultable par les composants internes
et vérifiable par un opérateur autorisé.

Le lot livre le schéma, les ports applicatifs, le processus worker, les règles de reprise, la supervision, le
déploiement de test/QA et les tests de fiabilité. Il ne déclenche aucun export, import massif ou connecteur réel :
les gestionnaires métier et leurs routes utilisateur appartiennent respectivement à 4.3 et 4.5. Un gestionnaire
inoffensif réservé aux tests démontre le cycle de vie de bout en bout, sans route publique d’envoi de travaux.

Les rappels CRM existants et l’import synchrone de 3.1 continuent leur fonctionnement actuel. Leur bascule éventuelle
vers le worker exige un contrat de migration propre à leur lot. Aucun traitement Google, scraping, envoi de message,
purge de données métier ou synchronisation fournisseur n’est activé par la seule livraison de 4.2.

## 2. Architecture validée

1. **PostgreSQL est la source de vérité et la file durable.** Le travail et sa demande sont écrits atomiquement avec
   l’opération métier qui le justifie. Un `COMMIT` rend le travail éligible ; un `ROLLBACK` ne laisse aucun travail.
   Une file Redis seule ou une tâche en mémoire du processus HTTP ne satisfait pas ce contrat.
2. **Le worker est un processus distinct de l’API**, construit depuis la même version applicative, sans port HTTP
   public. Il interroge PostgreSQL toutes les 2 secondes lorsqu’il est inactif. Un signal Redis peut accélérer le
   réveil à l’avenir, mais sa perte ne change pas l’exactitude ni le délai maximal de scrutation.
3. **La réservation est atomique**, au moyen d’une transaction courte et de `FOR UPDATE SKIP LOCKED`. Le worker
   réserve seulement un travail éligible, enregistre une tentative et un jeton de possession, puis ferme cette
   transaction avant l’exécution. Aucun verrou SQL n’est gardé pendant un appel métier ou réseau.
   Le choix du prochain travail alterne entre organisations éligibles selon leur dernier passage, puis prend leur
   plus ancien travail disponible. Une organisation chargée ne doit pas affamer les autres.
4. **Les effets métier s’exécutent dans une transaction locataire distincte.** Le worker fixe explicitement
   `app.organization_id`, `app.actor_id` et `app.request_id` pour chaque travail selon le socle RLS existant. Il
   remet le contexte à zéro entre deux travaux et ne réutilise jamais le contexte locataire précédent.
5. **Le balayage inter-organisation de la file est isolé.** Une fonction PostgreSQL `SECURITY DEFINER` dédiée à la
   seule réservation des métadonnées de travaux est possédée par un rôle non connectable, avec `search_path` figé,
   droits `EXECUTE` accordés uniquement à un nouveau rôle de connexion worker et aucun accès aux tables CRM par le
   propriétaire de la fonction. Le rôle worker reçoit séparément les seuls privilèges locataires nécessaires aux
   gestionnaires autorisés, sans `BYPASSRLS`. Les tables de travaux conservent `FORCE ROW LEVEL SECURITY` ; ce
   propriétaire dispose seulement d’une politique de file adaptée. Les lectures métier et les transitions
   ordinaires restent soumises à la RLS locataire. Les migrations et tests prouvent qu’un rôle Web ne peut pas
   parcourir les travaux
   d’une autre organisation ni appeler la fonction privilégiée.

Le processus s’arrête proprement sur `SIGTERM` : il cesse de réserver, termine le travail en cours dans un délai de
30 secondes si possible, puis libère le processus. Un travail interrompu est repris après expiration de son bail.
Le déploiement lance les migrations avant la nouvelle version du worker et bloque toute réservation d’un type ou
d’une version de contrat inconnus du binaire courant.

## 3. Modèle persistant et contrat des travaux

### 3.1 `jobs`

Chaque ligne porte au minimum : `id` UUID, `organization_id`, `type` dans un registre fermé, `schema_version`,
`subject_type` et `subject_id` contrôlés, `actor_membership_id` ou `system_origin`, `idempotency_key_digest`,
`request_fingerprint`, `status`, `created_at`, `available_at`, `started_at`, `finished_at`, `attempt_count`,
`max_attempts`, `lease_until`, `owner_token`, `heartbeat_at`, `cancel_requested_at`, `last_error_code`,
`result_code`, `expires_at` et `version`. Les dates sont en UTC. `subject_id` est une référence interne, pas un
nom libre. Le travail ne contient ni fichier, ni corps d’API, ni données personnelles, ni secret, ni URL signée.

Le condensat de clé est un HMAC-SHA-256 avec secret applicatif versionné, sans conserver la clé brute ; les anciennes
versions restent vérifiables pendant la conservation des travaux lors d’une rotation de secret. L’unicité de
`(organization_id, type, idempotency_key_digest)` couvre la durée de conservation du travail. Pendant une rotation,
les digests des versions encore actives sont recherchés avant insertion. La même clé et la même empreinte rendent
le même identifiant ; une empreinte différente donne un conflit explicite. Après
purge, le producteur métier doit encore posséder son propre marqueur durable d’idempotence si un rejeu tardif peut
produire un effet. Une clé de travail n’est donc jamais la seule garantie d’unicité d’un prospect, export ou événement.

### 3.2 `job_attempts` et événements

Une tentative enregistre son numéro, son début, sa fin, le jeton de possession, un résultat codifié et une durée.
Un événement de transition enregistre travail, organisation, ancien/nouvel état, instant, origine ou acteur et code
de raison. L’insertion d’un événement et la transition correspondante sont atomiques. L’audit métier existant
enregistre séparément toute décision visible pour le client ; les traces techniques ne remplacent pas cet audit.
Les journaux, métriques et événements de file excluent noms, adresses, cellules CSV, charges utiles, jetons et
réponses de fournisseurs.
Un état de planification par organisation garde le dernier passage et le nombre de travaux actifs ; son verrouillage
transactionnel rend atomiques la limite d’admission, l’équité et la limite d’un travail actif par organisation.
La clôture d’un travail libère le créneau dans la même transaction. La récupération d’un bail expiré remplace son
propriétaire sans compter un second travail actif ; elle répare également un compteur incohérent après panne.

### 3.3 États et transitions

| État initial | Événement | État final | Règle |
| --- | --- | --- | --- |
| absent | admission validée et transaction commise | `queued` | Retourne un ID et une date de disponibilité. |
| `queued` | réservation exclusive | `running` | Incrémente `attempt_count`, fixe bail et jeton de possession. |
| `running` | effet confirmé avec jeton courant | `succeeded` | Écrit le résultat minimal et clôt la tentative. |
| `running` | erreur transitoire, tentatives restantes | `queued` | Fixe `available_at` futur et un code d’erreur fermé. |
| `running` | erreur permanente ou tentatives épuisées | `failed` | Conserve le diagnostic codifié pour l’opérateur. |
| `queued` | annulation autorisée | `cancelled` | Aucun gestionnaire métier ne s’exécute. |
| `running` | demande d’annulation | `running` | `cancel_requested_at` est fixé ; le gestionnaire s’arrête à un point sûr. |
| `running` | arrêt sûr confirmé | `cancelled` | Impossible si l’effet irréversible a déjà été validé. |

`succeeded`, `failed` et `cancelled` sont terminaux. Un travail terminal n’est jamais remis directement dans la
file. Une relance administrative crée un nouveau travail, lié à l’ancien par une référence interne, après nouvelle
vérification des droits et de l’idempotence métier. Une demande d’annulation tardive retourne l’état terminal réel.

## 4. Admission, autorisation et exécution

L’admission passe par un port applicatif typé `enqueue(context, job_type, subject_id, idempotency_key,
fingerprint)`. Le registre associe à chaque type sa version, son schéma d’entrée fermé, sa capacité d’admission,
ses préconditions d’exécution, son budget de temps, sa politique de reprise et ses effets idempotents. Aucun nom de
classe, SQL, URL arbitraire, commande shell ou chemin de fichier fourni par le client n’est exécutable.
La limite initiale est de 100 travaux `queued` par organisation, vérifiée atomiquement à l’admission. Un refus de
capacité est explicite et n’efface pas la demande métier ; le producteur décide si l’opération entière est annulée.

L’acteur est vérifié à l’admission. Au démarrage de **chaque** tentative, avant l’effet et à chaque reprise après
attente, le gestionnaire recharge l’organisation, la ressource et les autorisations pertinentes. Une adhésion
désactivée, une organisation suspendue, une acquisition révoquée ou une licence/permission expirée bloque les
nouveaux effets. Le type décide si cela donne `failed` avec code permanent ou `cancelled`, sans réactiver un droit
historique. Un travail système utilise une origine système enregistrée, un acteur technique auditable propre à
l’organisation et une politique explicite par type ; il n’emprunte pas silencieusement les droits d’un ancien
utilisateur. Sans acteur technique valide, le travail système n’est pas admis.

La lecture d’état par l’application exige l’organisation active et une capacité propre au futur type métier. 4.2
n’ouvre aucune route générique de création, relance ou consultation de travaux à l’utilisateur final. Les routes de
4.3/4.5 présenteront uniquement un résultat minimal (`id`, `type`, `status`, `created_at`, `finished_at`,
`result_code`) selon leurs droits et avec `Cache-Control: no-store`. Un identifiant de travail d’une autre
organisation doit répondre sans révéler son existence.

## 5. Bail, reprise et concurrence

| Paramètre validé | Valeur 4.2 | Règle |
| --- | --- | --- |
| Scrutation au repos | 2 s | La perte d’un signal facultatif ne perd aucun travail. |
| Concurrence initiale | 2 processus, 1 travail actif chacun ; 1 travail actif par organisation | Limite imposée atomiquement par la base, pas par un simple compteur lu avant réservation. |
| Admission | 100 travaux en attente par organisation | Limite atomique, sans perte silencieuse. |
| Bail | 90 s | Renouvellement toutes les 20 s ; récupération après expiration. |
| Arrêt gracieux | 30 s | Ensuite la récupération par bail est obligatoire. |
| Tentatives | 3 au total, sauf type plus strict | Après la première erreur transitoire : 30 s ; après la deuxième : 2 min, avec gigue bornée de 20 %. |
| Exécution maximale | 30 min par tentative, sauf contrat de type plus strict | Dépassement traité comme erreur transitoire si l’effet est rejouable. |

La récupération d’un bail expiré réserve une nouvelle tentative avec un nouveau `owner_token`. Toute écriture
d’état ou de résultat par l’ancien propriétaire est refusée par comparaison du jeton et du numéro de tentative.
Le gestionnaire doit aussi vérifier cette possession avant de valider un effet local ; une contrainte d’unicité métier
ou une clé d’idempotence externe protège les effets lors d’une panne entre leur validation et la confirmation du
travail. Le modèle fournit une exécution **au moins une fois** ; il ne promet pas une exécution physique exactement
une fois. Un futur connecteur sans idempotence fournisseur ni mécanisme de réconciliation ne peut pas être enregistré
comme type rejouable.

Les erreurs sont classées par codes fermés : `dependency_unavailable`, `timeout`, `lease_lost` (transitoires),
`authorization_revoked`, `subject_missing`, `invalid_contract`, `provider_rejected` (permanentes), et
`attempts_exhausted` à la clôture. Une erreur inconnue est journalisée de manière expurgée, puis traitée selon le
plafond de tentatives ; son texte brut ne devient jamais un résultat utilisateur. La « file d’échec » est la vue
opérateur des travaux `failed`, persistée en PostgreSQL, pas une liste Redis sans historique.

## 6. Déploiement, stockage et conservation

En local et en QA sur l’hôte Compose existant, un service `worker` séparé utilise la même image que l’API, avec une
commande dédiée, `restart: unless-stopped`, sans port publié et avec ses propres secrets limités aux dépendances
requises, notamment le rôle PostgreSQL worker distinct du rôle Web. Il dépend de PostgreSQL sain et ne se déclare
prêt qu’après vérification des migrations et des gestionnaires enregistrés.
Redis reste disponible pour les services existants ; une panne Redis ne doit pas bloquer la réservation PostgreSQL
si le type exécuté n’en dépend pas. L’API ne lance aucun worker dans son cycle de vie. La supervision distingue
processus vivant, accès à PostgreSQL et progression réelle de la file ; une simple boucle bloquée ne vaut pas santé.

Le stockage privé actuel des CSV de 3.1 est local (`IMPORT_TEMP_DIRECTORY`, limite de 10 Mio, durée maximale de
24 h). Il reste synchrone en 4.2. Si un futur gestionnaire worker lit un fichier, l’API et le worker doivent partager
un volume privé durable sur le même hôte, ou employer un stockage objet privé validé ; aucune référence à un chemin
local de l’API ne suffit à garantir l’accès du worker. Le choix initial QA est un volume Compose privé partagé,
monté uniquement aux services qui en ont besoin. Un déploiement multi-hôte est bloqué tant que le stockage partagé,
son chiffrement, ses sauvegardes et sa suppression vérifiable ne sont pas contractualisés. 4.2 ne produit aucun
fichier téléchargeable ; 4.3 fixera le contrat des artefacts d’export avant leur activation.

En 4.2, un balayeur appelle le nettoyage déjà prévu des CSV 3.1 expirés depuis ce volume partagé ; il n’ouvre pas
leur contenu et ne modifie pas les rapports d’import. Les échecs de suppression sont comptés et repris.

Les lignes `succeeded` et `cancelled` sont conservées 30 jours après fin ; les lignes `failed` et leurs tentatives,
90 jours. Les tentatives et événements suivent la durée de leur travail parent. Un balayeur indépendant, idempotent
et borné en taille efface ensuite les seules métadonnées de file expirées ; il ne supprime ni audit métier, ni
prospect, ni preuve de conservation. Les fichiers temporaires de 3.1 gardent leur limite de 24 h et leur suppression
sur finalisation. Une future sortie de 4.3 aura son propre délai, son registre d’artefacts et un test de suppression.
Ces durées techniques validées ne remplacent aucune politique légale de conservation.

## 7. Supervision et exploitation

Métriques agrégées sans identifiant personnel : profondeur `queued`, plus ancien travail disponible, nombre de
`running` et de `failed`, tentatives par code, latence admission-début, durée d’exécution, baux expirés et âge du
dernier balayage. Les dimensions autorisées sont environnement et type contrôlé ; l’organisation et l’acteur ne
sont pas des étiquettes de métrique. Les logs structurés contiennent `job_id`, `request_id`, type, tentative, état,
durée et code d’erreur, jamais le contenu métier.

Un opérateur autorisé peut consulter, via un outil interne protégé, l’état codifié, les tentatives et les travaux en
échec. La relance exige un motif, une nouvelle vérification de droits et un nouvel ID ; elle est auditée. Aucune
action directe sur Redis ou modification manuelle du statut SQL ne constitue une procédure de reprise normale.
Le guide d’exploitation explique : arrêt/redémarrage, inspection des baux, saturation, panne PostgreSQL, panne du
stockage privé, travaux échoués, purge et retour arrière. Le retour arrière du binaire ne doit pas faire consommer
par l’ancien worker un `schema_version` inconnu.

Une alerte se déclenche si aucun worker n’a renouvelé sa présence depuis 60 secondes alors que des travaux sont
éligibles, si le plus ancien travail éligible attend plus de 5 minutes, si un travail passe en `failed`, ou si le
balayeur n’a pas terminé depuis 30 minutes. Les seuils sont configurables par environnement ; l’alerte contient
un code et un nombre, sans charge métier.

La mise en service suit l’ordre : migration additive et droits SQL, déploiement du binaire API/worker avec registres
compatibles, vérification de santé et tests de réservation, puis activation explicite des types métier dans leurs
lots. En cas de retour arrière, l’admission des nouveaux types est arrêtée, les workers sont drainés et les lignes
de travaux sont conservées. Une migration de suppression de la file n’est pas une opération de retour arrière.

## 8. Critères de validation et scénarios chiffrés

| ID | Scénario | Résultat attendu |
| --- | --- | --- |
| `JOB-01` | Admission dans une transaction métier ensuite annulée | Aucun travail réservé ou visible après `ROLLBACK`. |
| `JOB-02` | Deux admissions même organisation/type/clé/empreinte, puis même clé avec empreinte différente | Un seul ID pour les deux premières ; conflit pour la troisième. |
| `JOB-03` | Deux workers réservent simultanément 20 travaux de deux organisations | Chaque tentative a un propriétaire unique ; au plus un travail actif par organisation ; aucun travail perdu. |
| `JOB-04` | Worker interrompu après effet métier local validé mais avant `succeeded` | Nouveau bail et nouvelle tentative ; effet métier présent une fois grâce au marqueur durable, travail finalement `succeeded`. |
| `JOB-05` | Ancien worker termine après perte de bail et réservation par un autre | Son jeton est refusé ; il ne peut écraser ni état, ni résultat de la nouvelle tentative. |
| `JOB-06` | Deux erreurs transitoires, puis succès | Trois tentatives ; disponibilités retardées de 30 s puis 2 min avec gigue bornée ; état final `succeeded`. |
| `JOB-07` | Erreur permanente à la première tentative et erreur transitoire répétée sur un autre travail | Premier travail `failed` immédiatement ; second `failed` après trois tentatives ; tous deux visibles dans la vue d’échec. |
| `JOB-08` | Annulation en attente, puis annulation pendant un effet irréversible déjà validé | Premier travail `cancelled` sans effet ; second conserve son état réel et n’efface pas l’effet. |
| `JOB-09` | Organisation B demande l’état d’un travail A ; un travail A est suivi d’un travail B sur le même processus | Aucun détail de A n’est révélé ; les effets de B restent dans B et le contexte RLS de A ne persiste pas. |
| `JOB-10` | Adhésion ou licence révoquée entre admission et exécution | Aucun nouvel effet ; code permanent et événement d’audit selon le type. |
| `JOB-11` | Worker arrêté, Redis indisponible, puis worker redémarré | Les travaux commis demeurent en base et sont exécutés lorsque PostgreSQL et le worker sont disponibles. |
| `JOB-12` | Balayage après 30 et 90 jours, avec fichier CSV 3.1 expiré et audit métier présent | Seules les métadonnées et le fichier effectivement expirés sont supprimés ; audit et données métier restent intacts. |
| `JOB-13` | Ancien worker rencontre un type ou `schema_version` plus récent | Travail non consommé et alerte opérateur ; aucune boucle d’échec ni mutation métier. |

Les tests utilisent PostgreSQL réel pour RLS, contraintes, concurrence, bail, migration et reprise ; une horloge
contrôlée pour les délais ; et des doubles d’effet pour simuler l’arrêt au point critique. Le verrou qualité de
l’incrément exécute migrations, analyses statiques, tests backend/frontend sans skip, build et inspection d’artefact.
La recette fonctionnelle regroupée reste au lot 4.6, selon le contrat parent.

## 9. Décisions validées par le responsable produit

Les huit décisions `P4.2-01` à `P4.2-08` ont été approuvées le 23 septembre 2026.

| ID | Décision validée | Motif ou conséquence |
| --- | --- | --- |
| `P4.2-01` | PostgreSQL fait foi pour la file et les états ; Redis ne sert pas de source durable de travaux. | Admission atomique et reprise après perte de signal. |
| `P4.2-02` | Worker séparé de l’API, initialement sur le même hôte Compose en local/QA. | Cycle de vie, ressources et arrêt indépendants. |
| `P4.2-03` | Exécution au moins une fois, bail de 90 s, renouvellement de 20 s, trois tentatives et délais de 30 s puis 2 min. | Garantie honnête et bornée ; chaque effet doit être idempotent. |
| `P4.2-04` | Deux workers au départ, un travail actif par organisation ; aucun gestionnaire métier public en 4.2. | Capacité de test sans déclencher prématurément 4.3/4.5. |
| `P4.2-05` | Métadonnées terminales conservées 30 jours, échecs 90 jours ; CSV 3.1 reste à 24 h. | Diagnostic borné et respect du contrat d’import existant. |
| `P4.2-06` | Volume privé partagé pour QA mono-hôte ; stockage objet ou équivalent requis avant un déploiement multi-hôte de travaux à fichiers. | Évite les références locales inaccessibles au worker. |
| `P4.2-07` | Consultation et annulation utilisateur définies par chaque futur type métier ; pas d’API générique de file en 4.2. | Surface d’accès minimale et droits contextualisés. |
| `P4.2-08` | Limite de 100 travaux en attente par organisation et réservation équitable entre organisations. | Protège la file et évite la famine d’un locataire. |

Le responsable produit a donné le GO d’implémentation 4.2 le 23 septembre 2026, après avoir validé ces huit
décisions. Les valeurs de concurrence, de reprise et de conservation ainsi que le modèle de déploiement ci-dessus
font partie du contrat approuvé. L’état de réalisation et les preuves de qualité sont suivis dans le
[`PHASE_4_2_RAPPORT_IMPLEMENTATION.md`](PHASE_4_2_RAPPORT_IMPLEMENTATION.md).
