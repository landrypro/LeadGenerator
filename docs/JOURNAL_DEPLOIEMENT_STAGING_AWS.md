# Journal de déploiement de la staging Marketteo sur AWS

Dernière mise à jour : 17 septembre 2026  
Environnement : staging / QA  
Application : Marketteo CRM  
URL publique : <https://marketteo.gaiusconsulting.online>

## 1. Objet et règles de sécurité

Ce document décrit l'état réellement installé sur AWS et la procédure permettant de reconstruire le même environnement. Le déploiement a été préparé sans modifier le code applicatif. Le serveur utilise uniquement un état Git commité et propre.

Ce journal ne contient volontairement aucun mot de passe, aucune clé HMAC, aucune clé privée SSH et aucune clé Google. Les valeurs secrètes doivent être créées à nouveau lors de chaque installation et ne doivent jamais être copiées dans un ticket, un dépôt Git ou une conversation.

Points importants :

- `.env.qa` est le fichier de secrets actuellement utilisé sur EC2. Aucun second fichier `SECRETS` n'a été créé.
- `.env.qa` est ignoré par Git et ses permissions sont `600`, propriétaire `ubuntu:ubuntu`.
- Les mots de passe PostgreSQL et la clé HMAC ont été générés directement sur le serveur.
- La clé Google fournie pendant la préparation a été communiquée dans une conversation. Elle doit être considérée comme exposée, remplacée et restreinte dans Google Cloud avant tout usage durable.
- Les mots de passe de comptes applicatifs ne sont pas consignés dans ce document.

## 2. Résultat obtenu

Au moment du dernier contrôle :

- l'application publique répond en HTTPS ;
- `GET /api/health/live` répond `200` ;
- la readiness répond `ready` avec PostgreSQL et Redis à `ok` ;
- tous les conteneurs attendus sont démarrés ;
- Caddy force HTTP vers HTTPS et gère automatiquement le certificat Let's Encrypt ;
- PostgreSQL, Redis et Mailpit disposent de volumes persistants ;
- Mailpit est inaccessible depuis Internet et s'ouvre uniquement à travers un tunnel SSH ;
- le premier administrateur de plateforme est créé et sa connexion a été vérifiée ;
- deux organisations de validation ont été créées et leurs invitations apparaissent dans Mailpit.

Architecture :

```text
Internet
   |
DNS A : marketteo.gaiusconsulting.online -> 99.79.105.232
   |
Elastic IP AWS + Security Group (80/443 publics, 22 restreint)
   |
Caddy :80/:443 -- TLS Let's Encrypt
   |
Application FastAPI :8000 (réseau Docker seulement)
   |--------------------|--------------------|
PostgreSQL :5432     Redis :6379        Mailpit SMTP :1025
(interne Docker)     (interne Docker)    (interne Docker)
                                            |
                                 UI :8025 sur loopback EC2
                                            |
                               tunnel SSH local :8026
```

## 3. Inventaire « as built »

| Élément | Valeur installée |
|---|---|
| Fournisseur | Amazon Web Services |
| Région | `ca-central-1` — Canada Central |
| Zone de disponibilité | `ca-central-1a` |
| Nom de l'instance | `marketteo-staging-01` |
| ID de l'instance | `i-075e883876b04c71b` |
| Type d'instance | `m7i-flex.large` |
| AMI | `ami-02f1c1b3f3eedbd0d` |
| Système | Ubuntu 24.04 LTS |
| Noyau observé | `6.17.0-1017-aws` |
| Mémoire observée | `7.6 GiB` |
| Disque racine observé | `48 GiB`, environ `4.7 GiB` utilisés lors du contrôle |
| IP privée | `172.31.24.65` |
| Elastic IP | `99.79.105.232` |
| Security Group | `marketteo-staging-web` / `sg-0a998922306d2107c` |
| Domaine | `marketteo.gaiusconsulting.online` |
| Dossier applicatif | `/home/ubuntu/LeadGenerator` |
| Branche Git déployée | `codex/phase-2.4.3-audit` |
| Commit déployé | `1f4b4f6d0a91f6c43d41fc6e81490158f74051cd` |
| État Git sur EC2 | propre, zéro modification locale |
| Docker | `29.1.3` |
| Docker Compose | `2.40.3` |
| Pare-feu Ubuntu UFW | inactif ; le filtrage public repose sur le Security Group AWS |
| Redémarrage système | requis après les mises à jour Ubuntu ; pas encore effectué au dernier contrôle |

### Avertissement coût

`m7i-flex.large` n'est pas une micro-instance. Elle peut consommer rapidement les crédits d'un nouveau compte. Le programme AWS Free Tier actuel accorde aux nouveaux comptes jusqu'à 200 USD de crédits et le plan gratuit se termine au plus tard après six mois ou lorsque les crédits sont épuisés. Il faut contrôler immédiatement Billing, Free Tier et Cost Explorer, puis créer un budget avec alertes.

Références AWS :

- [FAQ AWS Free Tier](https://aws.amazon.com/free/free-tier-faqs/)
- [Documentation AWS Free Tier](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html)
- [Tarification des adresses IPv4 publiques](https://aws.amazon.com/vpc/pricing/)

L'Elastic IP/public IPv4 peut également générer un coût selon le plan et les allocations applicables au compte.

## 4. Création des ressources AWS

### 4.1 Choisir la région

Dans la console AWS, sélectionner `Canada (Central) — ca-central-1` avant de créer les ressources. Toutes les ressources de ce journal sont dans cette région.

### 4.2 Créer l'instance EC2

Paramètres réellement observés :

- nom : `marketteo-staging-01` ;
- Ubuntu Server 24.04 LTS ;
- type : `m7i-flex.large` ;
- disque racine : 48 GiB observés ;
- instance dans la zone `ca-central-1a` ;
- Security Group `marketteo-staging-web`.

La première installation a été faite sans fichier `.pem` disponible localement. L'accès initial a donc utilisé EC2 Instance Connect dans le navigateur. Pour une nouvelle installation, il est préférable de créer ou d'importer une paire de clés au lancement, puis de conserver sa clé privée dans un gestionnaire sécurisé.

### 4.3 Configurer le Security Group

Règles entrantes finales :

| Type | Protocole/port | Source | Rôle |
|---|---|---|---|
| SSH | TCP 22 | IP publique de l'administrateur, observée `70.24.224.140/32` | SSH direct depuis le poste autorisé |
| SSH | TCP 22 | préfixe réseau AWS géré pour EC2 Instance Connect | terminal EC2 Instance Connect |
| HTTP | TCP 80 | `0.0.0.0/0` | validation ACME et redirection vers HTTPS |
| HTTPS | TCP 443 | `0.0.0.0/0` | application publique |

Ne pas ajouter de règle publique pour PostgreSQL 5432, Redis 6379, l'application 8000 ou Mailpit 8025.

Aucune restriction sortante personnalisée n'a été ajoutée pendant cette préparation. Lors d'une reconstruction, vérifier que l'instance dispose au minimum des sorties nécessaires pour DNS, HTTPS, les dépôts Ubuntu, les registres Docker, Let's Encrypt et les API externes utilisées par l'application. Si la règle sortante AWS par défaut est conservée, consigner explicitement ce choix dans la revue de sécurité.

Si l'adresse IP publique de l'administrateur change, mettre à jour la règle SSH `/32`. Une connexion TCP qui expire sur le port 22 indique généralement que cette règle manque ou ne correspond plus à l'IP actuelle.

Contrôle Windows :

```powershell
Test-NetConnection 99.79.105.232 -Port 22
```

### 4.4 Allouer et associer l'Elastic IP

Dans EC2 > Elastic IP addresses :

1. allouer une adresse dans `ca-central-1` ;
2. l'associer à l'instance `i-075e883876b04c71b` ;
3. vérifier que l'adresse obtenue est celle utilisée par le DNS.

Adresse finale : `99.79.105.232`.

### 4.5 Configurer le DNS

Créer l'enregistrement suivant auprès du fournisseur DNS de `gaiusconsulting.online` :

```text
Type : A
Nom/hôte : marketteo
Valeur : 99.79.105.232
```

Le nom complet est `marketteo.gaiusconsulting.online`. Le domaine QA est le sous-domaine complet, et non le domaine racine `gaiusconsulting.online`.

Contrôles :

```bash
getent ahostsv4 marketteo.gaiusconsulting.online
curl -I http://marketteo.gaiusconsulting.online
```

Le premier doit retourner `99.79.105.232`. Le second doit retourner une redirection permanente `308` vers HTTPS.

## 5. Accès SSH

### 5.1 Accès initial avec EC2 Instance Connect

Dans la console EC2 :

1. ouvrir l'instance ;
2. cliquer sur **Connect** ;
3. choisir **EC2 Instance Connect** ;
4. utilisateur système : `ubuntu` ;
5. ouvrir le terminal.

Le prompt attendu ressemble à :

```text
ubuntu@ip-172-31-24-65:~$
```

### 5.2 Créer une clé SSH dédiée au poste administrateur

Sur Windows PowerShell :

```powershell
$stagingKey = Join-Path $env:USERPROFILE '.ssh\marketteo-staging-tunnel'
ssh-keygen -t ed25519 -f $stagingKey -C 'marketteo-mailpit-tunnel'
Get-Content ($stagingKey + '.pub')
```

Utiliser une phrase secrète et `ssh-agent` lorsque cela est possible. La clé actuelle a été dédiée uniquement à cet environnement.

Dans le terminal EC2 Instance Connect, ajouter uniquement la partie publique :

```bash
install -d -m 700 ~/.ssh
printf '%s\n' '<CLE_PUBLIQUE_ED25519>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Ne jamais copier la clé privée sur EC2.

Tester depuis Windows :

```powershell
$stagingKey = Join-Path $env:USERPROFILE '.ssh\marketteo-staging-tunnel'
ssh -o BatchMode=yes -o ConnectTimeout=15 -i $stagingKey ubuntu@99.79.105.232 'echo SSH_OK'
```

Le nom utilisateur doit être écrit `ubuntu@99.79.105.232`, sans antislash avant `@`.

## 6. Préparation d'Ubuntu

Depuis le terminal EC2 :

```bash
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
```

Lors de l'installation initiale, 30 paquets ont été mis à jour et certains paquets soumis au déploiement progressif Ubuntu ont été différés. Un redémarrage est maintenant requis.

Installer Docker et Compose depuis les paquets Ubuntu :

```bash
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
```

Se déconnecter puis se reconnecter afin que le groupe `docker` soit pris en compte, puis vérifier :

```bash
docker --version
docker compose version
systemctl is-active docker
```

Versions observées :

```text
Docker version 29.1.3
Docker Compose version 2.40.3
```

### Redémarrage encore à faire

Planifier une courte fenêtre, puis :

```bash
sudo reboot
```

Après reconnexion :

```bash
cd /home/ubuntu/LeadGenerator
docker compose --env-file .env.qa -f compose.qa.yaml ps
sh scripts/qa-status.sh
```

Les services utilisent `restart: unless-stopped` et doivent repartir automatiquement. Ne considérer le redémarrage terminé qu'après un nouveau contrôle HTTPS et readiness.

## 7. Transfert de l'état Git commité

Objectif appliqué : transférer l'état du projet sans aucune modification locale non commitée.

Sur EC2 :

```bash
cd /home/ubuntu
git clone <URL_DU_DEPOT_AUTORISE> LeadGenerator
cd /home/ubuntu/LeadGenerator
git switch codex/phase-2.4.3-audit
git checkout 1f4b4f6d0a91f6c43d41fc6e81490158f74051cd
git status --porcelain
```

La dernière commande doit ne produire aucune ligne.

Si l'on veut conserver la branche active plutôt qu'un HEAD détaché :

```bash
git switch codex/phase-2.4.3-audit
test "$(git rev-parse HEAD)" = "1f4b4f6d0a91f6c43d41fc6e81490158f74051cd"
```

État effectivement déployé :

```text
Branche : codex/phase-2.4.3-audit
Commit  : 1f4b4f6d0a91f6c43d41fc6e81490158f74051cd
Travail local sur EC2 : propre
```

Ne pas copier le dossier local Windows en bloc : il contient actuellement des changements de développement non commités qui ne font pas partie de cette staging.

## 8. Création de `.env.qa`

### 8.1 Créer le fichier privé

```bash
cd /home/ubuntu/LeadGenerator
umask 077
cp .env.qa.example .env.qa
chmod 600 .env.qa
```

Le dépôt contient :

```text
.env.qa.example     suivi par Git, sans secret
.env.qa             ignoré par Git, contient les secrets du serveur
```

Vérifier :

```bash
stat -c '%a %U:%G %n' .env.qa
git check-ignore -v .env.qa
```

Résultat attendu pour les permissions : `600 ubuntu:ubuntu .env.qa`.

### 8.2 Générer les secrets

Générer de nouvelles valeurs sur le serveur :

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 48
```

Utilisation :

1. premier résultat : `POSTGRES_PASSWORD` ;
2. deuxième résultat : `POSTGRES_APP_PASSWORD` ;
3. troisième résultat : `RATE_LIMIT_HMAC_KEY`.

Les valeurs hexadécimales sont compatibles avec les URL PostgreSQL sans échappement supplémentaire. Insérer les mêmes mots de passe dans leurs URL respectives :

```dotenv
DATABASE_URL=postgresql+asyncpg://prospect_app:<POSTGRES_APP_PASSWORD>@postgresql:5432/prospect
MIGRATION_DATABASE_URL=postgresql+asyncpg://prospect:<POSTGRES_PASSWORD>@postgresql:5432/prospect
```

Ne jamais afficher ensuite le fichier entier dans un journal de terminal partagé.

### 8.3 Modèle complet expurgé de `.env.qa`

Le fichier installé reprend toutes les variables ci-dessous. Les marqueurs `<...>` doivent être remplacés localement ; ils ne sont pas des valeurs valides.

```dotenv
QA_DOMAIN=marketteo.gaiusconsulting.online

APP_ENV=test
PUBLIC_APP_URL=https://marketteo.gaiusconsulting.online
CORS_ALLOWED_ORIGINS=https://marketteo.gaiusconsulting.online
SESSION_COOKIE_NAME=__Host-prospect_session
SESSION_COOKIE_SECURE=true

POSTGRES_DB=prospect
POSTGRES_USER=prospect
POSTGRES_PASSWORD=<64_CARACTERES_HEXADECIMAUX_GENERES>
POSTGRES_APP_PASSWORD=<64_CARACTERES_HEXADECIMAUX_GENERES>
DATABASE_URL=postgresql+asyncpg://prospect_app:<POSTGRES_APP_PASSWORD>@postgresql:5432/prospect
MIGRATION_DATABASE_URL=postgresql+asyncpg://prospect:<POSTGRES_PASSWORD>@postgresql:5432/prospect

REDIS_URL=redis://redis:6379/0
RATE_LIMIT_HMAC_KEY=<96_CARACTERES_HEXADECIMAUX_GENERES>

GOOGLE_MAPS_API_KEY=<NOUVELLE_CLE_RESTREINTE>
GOOGLE_MAPS_STATIC_API_KEY=<NOUVELLE_CLE_RESTREINTE>

INVITATION_DELIVERY_BACKEND=mailpit
INVITATION_FROM_EMAIL=no-reply@gaiusconsulting.online
INVITATION_SMTP_HOST=mailpit
INVITATION_SMTP_PORT=1025
INVITATION_SMTP_TIMEOUT_SECONDS=5
INVITATION_TTL_SECONDS=259200
INVITATION_ATTEMPT_WINDOW_SECONDS=900
INVITATION_ATTEMPT_ADDRESS_MAX=30
INVITATION_ATTEMPT_TOKEN_MAX=10
INVITATION_RESEND_COOLDOWN_SECONDS=60
INVITATION_RESEND_WINDOW_SECONDS=86400
INVITATION_RESEND_MAX_PER_WINDOW=5

LOGIN_RATE_LIMIT_WINDOW_SECONDS=900
LOGIN_RATE_LIMIT_PAIR_FAILURES=5
LOGIN_RATE_LIMIT_ADDRESS_FAILURES=20
SESSION_IDLE_SECONDS=1800
SESSION_ABSOLUTE_SECONDS=43200

DEPENDENCY_CONNECT_TIMEOUT_SECONDS=3
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT_SECONDS=10
DATABASE_STATEMENT_TIMEOUT_MS=15000
REDIS_MAX_CONNECTIONS=20
GOOGLE_PLACES_TIMEOUT_SECONDS=30
GOOGLE_STATIC_MAPS_TIMEOUT_SECONDS=20
MAP_SNAPSHOT_GRANT_TTL_SECONDS=300
MAP_SNAPSHOT_GRANT_MAX_ENTRIES=1000

MAILPIT_UI_PORT=8025
MAILPIT_MAX_MESSAGES=500
```

`CORS_ALLOWED_ORIGINS` correspond à l'origine autorisée pour les appels du navigateur : protocole + hôte, sans chemin. Pour cette staging, la valeur correcte est donc exactement `https://marketteo.gaiusconsulting.online`.

`APP_ENV=test` est intentionnel : l'application n'autorise le backend Mailpit que dans les environnements `development` ou `test`. Utiliser une autre valeur tout en conservant `INVITATION_DELIVERY_BACKEND=mailpit` empêche le démarrage de la configuration.

### 8.4 Clés Google

Les deux variables existent :

```dotenv
GOOGLE_MAPS_API_KEY=<NOUVELLE_CLE_RESTREINTE>
GOOGLE_MAPS_STATIC_API_KEY=<NOUVELLE_CLE_RESTREINTE>
```

Actions obligatoires recommandées :

1. révoquer/remplacer la clé communiquée pendant la préparation ;
2. restreindre les API autorisées au strict nécessaire ;
3. configurer des restrictions adaptées au mode d'utilisation de chaque clé ;
4. ne jamais commiter les nouvelles clés.

### 8.5 Valider la configuration Compose

```bash
docker compose --env-file .env.qa -f compose.qa.yaml config --quiet
```

Aucune sortie et un code retour zéro indiquent une configuration valide.

## 9. Stack Docker QA

### 9.1 Images et rôles

| Service | Image | Exposition |
|---|---|---|
| `app` | `prospect-crm-qa-app:latest`, construite depuis le `Dockerfile` | port 8000 uniquement dans le réseau Docker |
| `postgresql` | `postgres:17.10-alpine` | port 5432 uniquement dans le réseau Docker |
| `redis` | `redis:7.4.9-alpine` | port 6379 uniquement dans le réseau Docker |
| `mailpit` | `axllent/mailpit:v1.30.5` | SMTP 1025 interne ; UI liée à `127.0.0.1:8025` sur EC2 |
| `caddy` | `caddy:2-alpine` | ports publics 80 et 443 |
| `migrations` | image de l'application, profil `tools` | tâche ponctuelle |
| `database-role-provisioner` | `postgres:17.10-alpine`, profil `tools` | tâche ponctuelle |

### 9.2 Volumes persistants

Volumes réellement créés :

```text
prospect-crm-qa_prospect-qa-postgresql-data
prospect-crm-qa_prospect-qa-redis-data
prospect-crm-qa_prospect-qa-mailpit-data
prospect-crm-qa_prospect-qa-caddy-data
prospect-crm-qa_prospect-qa-caddy-config
```

Rôle :

- PostgreSQL : données métier ;
- Redis : fichier AOF ;
- Mailpit : base `/data/mailpit.db` ;
- Caddy data/config : certificats ACME et état Caddy.

Ne jamais utiliser `docker compose down -v` sur cet environnement sauf décision explicite de supprimer toutes les données persistantes.

## 10. Lancement initial

Le fichier `scripts/qa-deploy.sh` n'est pas exécutable dans le commit déployé. Cette commande échoue donc :

```bash
./scripts/qa-deploy.sh
# Permission denied
```

Utiliser explicitement `sh` :

```bash
cd /home/ubuntu/LeadGenerator
sh scripts/qa-deploy.sh
```

Le script réalise, dans cet ordre :

1. construction de l'image `app` ;
2. arrêt contrôlé de `app` et `caddy` ;
3. démarrage de PostgreSQL, Redis et Mailpit ;
4. création/mise à jour du rôle PostgreSQL applicatif `prospect_app` ;
5. exécution des migrations Alembic ;
6. démarrage de l'application et de Caddy ;
7. affichage de l'état final.

État final attendu :

```text
app          healthy
postgresql   healthy
redis        healthy
mailpit      healthy
caddy        running
```

Commandes de contrôle :

```bash
docker compose --env-file .env.qa -f compose.qa.yaml ps
sh scripts/qa-status.sh
```

Readiness attendue :

```json
{
  "status": "ready",
  "dependencies": {
    "postgresql": "ok",
    "redis": "ok"
  }
}
```

## 11. HTTPS et Caddy

Le fichier `deploy/qa/Caddyfile` :

- utilise `QA_DOMAIN` comme site ;
- compresse en zstd/gzip ;
- ajoute HSTS, `nosniff`, `DENY` pour les frames et `no-referrer` ;
- masque l'en-tête `Server` côté réponse HTTPS ;
- transmet les requêtes à `app:8000`.

Caddy obtient automatiquement un certificat Let's Encrypt lorsque :

- le DNS pointe vers l'Elastic IP ;
- le port 80 est accessible pour le challenge ACME ;
- le port 443 est accessible ;
- le domaine est exact dans `QA_DOMAIN`.

Certificat observé le 17 septembre 2026 :

```text
Sujet       : CN=marketteo.gaiusconsulting.online
Émetteur    : Let's Encrypt YE1
Valide dès  : 2026-09-17 13:37:39 UTC
Valide jusqu: 2026-12-16 13:37:38 UTC
```

Caddy doit le renouveler automatiquement. Les dates ci-dessus sont un constat historique, pas une valeur à configurer.

Contrôles :

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://marketteo.gaiusconsulting.online/api/health/live

printf '' | openssl s_client \
  -servername marketteo.gaiusconsulting.online \
  -connect marketteo.gaiusconsulting.online:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

Code de santé attendu : `200`.

## 12. Création du premier super-administrateur

Compte créé :

```text
Adresse courriel : guykongne@gmail.com
Nom affiché      : Guy SuperAdmin
Rôle             : Administrateur de plateforme
ID historique    : 094afbe2-7920-4d50-9da1-098418692d7b
```

Commande utilisée :

```bash
cd /home/ubuntu/LeadGenerator

BOOTSTRAP_PLATFORM_ADMIN_CONFIRM=CREATE_FIRST_PLATFORM_ADMIN \
BOOTSTRAP_PLATFORM_ADMIN_EMAIL='guykongne@gmail.com' \
BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME='Guy SuperAdmin' \
sh scripts/qa-bootstrap-platform-admin.sh
```

Le script demande le mot de passe et sa confirmation de façon interactive. Le mot de passe doit contenir entre 12 et 128 caractères. Il n'est jamais placé dans la ligne de commande ni dans ce document.

Le mécanisme est prévu pour le premier administrateur de plateforme. Une nouvelle installation générera un nouvel ID interne.

Connexion validée :

```text
https://marketteo.gaiusconsulting.online/login
```

## 13. Gestion des courriels de staging avec Mailpit

### 13.1 Comportement

La staging utilise :

```dotenv
APP_ENV=test
INVITATION_DELIVERY_BACKEND=mailpit
INVITATION_SMTP_HOST=mailpit
INVITATION_SMTP_PORT=1025
```

Les invitations sont envoyées par SMTP au conteneur Mailpit. Aucun message ne quitte le réseau Docker et aucun destinataire réel ne reçoit le courriel.

Mailpit conserve ses messages dans le volume persistant, base `/data/mailpit.db`, avec une limite configurée de 500 messages.

Cette configuration convient à la recette, mais pas à la production. Le code actuellement déployé prend en charge `mailpit` ou `disabled`; l'ajout d'un fournisseur réel comme AWS SES nécessitera une évolution applicative/configuration distincte.

### 13.2 Pourquoi le port 8025 n'est pas public

Dans Compose :

```text
127.0.0.1:8025 -> mailpit:8025
```

Le Security Group n'ouvre pas 8025. Ce choix protège les messages de test et surtout les jetons d'invitation.

### 13.3 Tunnel SSH final

Le poste Windows avait déjà une ancienne instance Mailpit via WSL sur `127.0.0.1:8025`. Le premier tunnel affichait donc la mauvaise boîte. Le port local final est `8026`, tandis que la destination EC2 reste `127.0.0.1:8025`.

Depuis Windows PowerShell :

```powershell
$stagingKey = Join-Path $env:USERPROFILE '.ssh\marketteo-staging-tunnel'
ssh -N `
  -L 127.0.0.1:8026:127.0.0.1:8025 `
  -o ExitOnForwardFailure=yes `
  -o ServerAliveInterval=30 `
  -o ServerAliveCountMax=3 `
  -i $stagingKey `
  ubuntu@99.79.105.232
```

Garder cette fenêtre ouverte. Ouvrir ensuite :

<http://127.0.0.1:8026>

Le tunnel en cours a été lancé en arrière-plan sur le poste administrateur. Il disparaîtra au redémarrage du poste ou à l'arrêt du processus SSH ; relancer alors la commande ci-dessus.

Avant de choisir un port local :

```powershell
Get-NetTCPConnection -LocalPort 8026 -State Listen -ErrorAction SilentlyContinue
```

### 13.4 Contrôles Mailpit

Depuis EC2 :

```bash
curl -fsS http://127.0.0.1:8025/api/v1/info
```

Vérifier dans la réponse :

- `Database` vaut `/data/mailpit.db` ;
- `Messages` augmente après une invitation ;
- la version attendue est `v1.30.5`.

La boîte contenait quatre messages lors du contrôle final : deux invitations et deux messages de diagnostic. Les deux diagnostics peuvent être supprimés sans effet sur l'application.

## 14. Exploitation courante

### État de la stack

```bash
cd /home/ubuntu/LeadGenerator
docker compose --env-file .env.qa -f compose.qa.yaml ps
sh scripts/qa-status.sh
```

### Journaux

```bash
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 app
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 caddy
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 mailpit
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 postgresql
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 redis
```

Pour suivre en continu, ajouter `-f`, puis quitter avec `Ctrl+C`.

### Redémarrer un seul service

```bash
docker compose --env-file .env.qa -f compose.qa.yaml restart mailpit
```

Remplacer `mailpit` par le service voulu. Vérifier ensuite son état et la readiness.

### Mettre à jour l'application après une évolution du code source

Principe : la staging reçoit uniquement un commit validé et poussé dans le dépôt distant. Ne jamais copier directement le dossier de développement Windows vers EC2 et ne jamais déployer des modifications non commitées.

#### Étape 1 — préparer et pousser le commit depuis le poste de développement

Après les tests et la revue des changements :

```powershell
git status
git add <FICHIERS_VALIDES>
git commit -m "Description de la mise à jour"
git push origin <BRANCHE_APPROUVEE>
git rev-parse HEAD
```

Noter le hash complet retourné par `git rev-parse HEAD`. Ce hash devient l'identifiant immuable de la version à déployer.

Ne pas inclure dans ce commit :

- `.env.qa` ou tout secret ;
- un dump de base de données ;
- des fichiers de travail non validés ;
- des artefacts locaux inutiles.

#### Étape 2 — effectuer les contrôles préalables sur EC2

Se connecter à l'instance, puis :

```bash
cd /home/ubuntu/LeadGenerator

git status --porcelain
git branch --show-current
git rev-parse HEAD
docker compose --env-file .env.qa -f compose.qa.yaml ps
sh scripts/qa-status.sh
```

Conditions nécessaires avant de continuer :

- `git status --porcelain` ne retourne aucune ligne ;
- le commit actuellement déployé est noté comme commit de retour arrière ;
- la stack est saine avant la mise à jour ;
- aucun incident en cours ne risque d'être confondu avec le déploiement.

Si l'arbre Git EC2 n'est pas propre, arrêter la procédure et comprendre l'origine des modifications. Ne pas utiliser `git reset --hard` pour les effacer sans décision explicite.

#### Étape 3 — sauvegarder PostgreSQL

```bash
cd /home/ubuntu/LeadGenerator
sh scripts/qa-backup.sh
```

Noter le chemin du dump affiché par le script et, pour une mise à jour importante ou comportant des migrations, copier le dump vers un stockage distinct avant de poursuivre.

#### Étape 4 — récupérer et examiner le commit approuvé

```bash
git fetch --all --prune
git show --stat --oneline <HASH_DU_COMMIT_APPROUVE>
```

Comparer les fichiers de déploiement et le modèle d'environnement entre l'ancienne et la nouvelle version :

```bash
git diff <ANCIEN_COMMIT>..<NOUVEAU_COMMIT> -- \
  .env.qa.example \
  compose.qa.yaml \
  deploy/qa/Caddyfile \
  scripts/qa-deploy.sh
```

Si `.env.qa.example` contient de nouvelles variables, les ajouter manuellement à `.env.qa`. Ne jamais remplacer `.env.qa` par le fichier exemple, car cela supprimerait les secrets actuels.

Valider ensuite la configuration :

```bash
docker compose --env-file .env.qa -f compose.qa.yaml config --quiet
```

#### Étape 5 — positionner exactement la version à déployer

Méthode recommandée pour garantir le commit exact :

```bash
git switch --detach <HASH_DU_COMMIT_APPROUVE>
test "$(git rev-parse HEAD)" = "<HASH_DU_COMMIT_APPROUVE>"
git status --porcelain
```

La dernière commande doit rester vide.

Si la politique de l'équipe impose de garder une branche active, utiliser plutôt :

```bash
git switch <BRANCHE_APPROUVEE>
git pull --ff-only
test "$(git rev-parse HEAD)" = "<HASH_DU_COMMIT_APPROUVE>"
git status --porcelain
```

Ne pas poursuivre si la branche distante ne pointe pas sur le hash approuvé.

#### Étape 6 — lancer le déploiement

```bash
sh scripts/qa-deploy.sh
```

Le script reconstruit l'image applicative, démarre les dépendances, provisionne le rôle PostgreSQL, applique les migrations Alembic, puis redémarre l'application et Caddy. Les volumes persistants sont conservés. Une courte indisponibilité est possible pendant le remplacement des conteneurs.

#### Étape 7 — valider immédiatement le déploiement

```bash
sh scripts/qa-status.sh

curl -sS -o /dev/null -w '%{http_code}\n' \
  https://marketteo.gaiusconsulting.online/api/health/live
```

Résultats requis :

- conteneurs essentiels `healthy` ;
- readiness `ready` ;
- PostgreSQL et Redis à `ok` ;
- santé publique `200`.

Effectuer ensuite une recette fonctionnelle minimale :

1. ouvrir la page de connexion ;
2. se connecter avec un compte autorisé ;
3. ouvrir les écrans principaux concernés par la mise à jour ;
4. créer une invitation de test si le flux d'identité a changé ;
5. vérifier sa réception dans Mailpit via <http://127.0.0.1:8026> ;
6. consulter les journaux de `app` et `caddy` pour détecter les erreurs nouvelles.

Journaux utiles :

```bash
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 app
docker compose --env-file .env.qa -f compose.qa.yaml logs --tail=200 caddy
```

Consigner après succès :

- date et heure UTC ;
- personne ayant effectué le déploiement ;
- ancien commit ;
- nouveau commit ;
- chemin de la sauvegarde ;
- résultat des contrôles techniques et fonctionnels.

#### Étape 8 — retour arrière applicatif

Si la nouvelle version échoue et qu'aucune migration incompatible n'a été appliquée :

```bash
cd /home/ubuntu/LeadGenerator
git switch --detach <ANCIEN_COMMIT>
git status --porcelain
sh scripts/qa-deploy.sh
sh scripts/qa-status.sh

curl -sS -o /dev/null -w '%{http_code}\n' \
  https://marketteo.gaiusconsulting.online/api/health/live
```

Le retour au code précédent n'annule pas automatiquement les migrations de base de données. Si le nouveau déploiement a appliqué une migration non rétrocompatible :

1. arrêter les écritures applicatives si nécessaire ;
2. consulter la stratégie de downgrade de la migration ;
3. choisir explicitement entre downgrade contrôlé et restauration du dump ;
4. ne pas improviser une restauration sur la staging active ;
5. valider la procédure sur un environnement jetable lorsque c'est possible.

La restauration PostgreSQL complète n'a pas encore été testée sur cette instance. Une mise à jour comportant une migration destructive ne doit donc pas être lancée avant d'avoir établi et validé son plan de retour arrière.

## 15. Sauvegarde PostgreSQL

Le dépôt fournit `scripts/qa-backup.sh`.

```bash
cd /home/ubuntu/LeadGenerator
sh scripts/qa-backup.sh
```

Le script crée un dump PostgreSQL au format custom dans :

```text
backups/qa/prospect-qa-YYYYMMDDTHHMMSSZ.dump
```

Le dossier `backups/` est ignoré par Git. Une sauvegarde laissée uniquement sur la même instance n'est pas suffisante : la copier vers un stockage distinct, chiffré et contrôlé, puis tester une restauration dans un environnement jetable.

Aucune restauration complète n'a encore été testée ni documentée comme validée sur cette instance.

## 16. Dépannage rencontré

### `Identity file ... not accessible`

Cause : aucun fichier `.pem` n'existait au chemin utilisé. Une clé créée après le lancement dans la console AWS n'est pas automatiquement ajoutée à une instance déjà existante.

Solution appliquée : connexion initiale avec EC2 Instance Connect, création d'une clé SSH dédiée sur Windows et ajout de sa clé publique à `~/.ssh/authorized_keys`.

### `connect to host ... port 22: Connection timed out`

Cause : port 22 non accessible depuis l'adresse du poste ou règle Security Group absente.

Solution appliquée : règle SSH `/32` pour l'adresse administrateur et règle pour le préfixe EC2 Instance Connect.

### `Permission denied` sur `./scripts/qa-deploy.sh`

Cause : le bit exécutable n'est pas présent dans le commit.

Solution :

```bash
sh scripts/qa-deploy.sh
```

### Certificat HTTPS non obtenu

Vérifier :

1. l'enregistrement A ;
2. l'association de l'Elastic IP ;
3. les règles 80 et 443 ;
4. `QA_DOMAIN` ;
5. `docker compose ... logs caddy`.

### Mailpit affiche d'anciens messages localhost

Cause observée : WSL occupait déjà `127.0.0.1:8025` sur Windows. Le navigateur affichait une ancienne instance Mailpit locale au lieu de celle d'EC2.

Diagnostic utile :

```powershell
Get-NetTCPConnection -LocalPort 8025 -State Listen
Get-Process -Id <OwningProcess>
```

Solution : utiliser le port local `8026` dans le tunnel.

Pour confirmer que l'on voit la bonne instance :

```powershell
Invoke-RestMethod http://127.0.0.1:8026/api/v1/info
```

La propriété `Database` doit être `/data/mailpit.db`.

### Invitation marquée envoyée mais invisible

La base PostgreSQL indiquait bien `delivery_status=sent`. L'application et le vrai Mailpit EC2 fonctionnaient ; seule l'interface consultée était la mauvaise instance locale à cause du conflit de port. Le tunnel sur 8026 a corrigé le problème.

## 17. Checklist de reconstruction

- [ ] Sélectionner `ca-central-1`.
- [ ] Créer l'instance Ubuntu et noter son type/coût.
- [ ] Créer le Security Group avec seulement 22 restreint, 80 et 443 publics.
- [ ] Allouer et associer une Elastic IP.
- [ ] Créer le DNS A du sous-domaine.
- [ ] Se connecter avec EC2 Instance Connect.
- [ ] Mettre Ubuntu à jour.
- [ ] Installer Docker Engine et Compose.
- [ ] Ajouter `ubuntu` au groupe Docker et se reconnecter.
- [ ] Récupérer uniquement le commit approuvé.
- [ ] Vérifier que l'arbre Git est propre.
- [ ] Créer `.env.qa` avec permissions 600.
- [ ] Générer tous les secrets sur le serveur.
- [ ] Installer des clés Google nouvelles et restreintes.
- [ ] Valider Compose avec `config --quiet`.
- [ ] Lancer `sh scripts/qa-deploy.sh`.
- [ ] Vérifier les cinq conteneurs persistants.
- [ ] Vérifier DNS, HTTP 308, certificat et health 200.
- [ ] Créer le premier administrateur de plateforme.
- [ ] Créer une invitation et la contrôler dans Mailpit.
- [ ] Mettre en place le tunnel Mailpit sur un port local libre.
- [ ] Effectuer une sauvegarde et l'externaliser.
- [ ] Configurer AWS Budget et les alertes de coût.
- [ ] Effectuer le redémarrage Ubuntu requis et revalider la stack.

## 18. Actions restantes et limites connues

Priorité haute :

1. remplacer et restreindre les clés Google exposées pendant la préparation ;
2. vérifier le plan AWS, les crédits restants et le coût de `m7i-flex.large` ;
3. créer un AWS Budget et des alertes de facturation ;
4. effectuer le redémarrage Ubuntu requis, puis refaire tous les contrôles ;
5. produire une première sauvegarde hors instance et tester sa restauration.

Améliorations recommandées :

- utiliser AWS Systems Manager Session Manager afin de réduire la dépendance à SSH public ;
- stocker les secrets dans AWS Systems Manager Parameter Store ou Secrets Manager ;
- ajouter une supervision et des alertes de disponibilité ;
- définir une politique de rotation et de rétention des sauvegardes ;
- tester une mise à jour de Mailpit depuis la version épinglée `v1.30.5` dans un environnement contrôlé ;
- intégrer un fournisseur de courriels réel uniquement pour la production ;
- documenter et tester un rollback applicatif et une restauration PostgreSQL.

Éléments non configurés à ce jour :

- aucun envoi SMTP réel vers Internet ;
- aucun port public pour Mailpit, PostgreSQL ou Redis ;
- aucun gestionnaire AWS de secrets ;
- aucune sauvegarde externalisée confirmée ;
- aucune restauration validée ;
- aucune supervision CloudWatch applicative détaillée ;
- aucun pipeline de déploiement automatique vers cette instance.

## 19. Contrôle final minimal après toute intervention

```bash
cd /home/ubuntu/LeadGenerator

git status --porcelain
docker compose --env-file .env.qa -f compose.qa.yaml ps
sh scripts/qa-status.sh
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://marketteo.gaiusconsulting.online/api/health/live
```

Critères de succès :

- aucune modification Git sur EC2 ;
- application, PostgreSQL, Redis et Mailpit `healthy` ;
- Caddy démarré ;
- readiness `ready` ;
- santé publique `200` ;
- connexion utilisateur fonctionnelle ;
- nouvelle invitation visible dans le Mailpit EC2 via <http://127.0.0.1:8026>.
