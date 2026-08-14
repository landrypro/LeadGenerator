# Guide de déploiement QA — Oracle Always Free

## 1. Préparer la VM

Créez une VM Oracle Always Free Ubuntu, ouvrez uniquement les ports `22`, `80` et `443`, puis installez Docker et le
plugin Compose. Associez un domaine ou sous-domaine public, par exemple `qa.example.com`, vers l’adresse publique de
la VM.

## 2. Installer le projet

```bash
git clone <URL_DU_DEPOT> LeadGenerator
cd LeadGenerator
cp .env.qa.example .env.qa
nano .env.qa
```

Renseignez au minimum `QA_DOMAIN`, `PUBLIC_APP_URL`, `CORS_ALLOWED_ORIGINS`, les mots de passe PostgreSQL, la clé
`RATE_LIMIT_HMAC_KEY` et les clés Google de recette. Les mots de passe présents dans l’exemple doivent tous être
remplacés.

## 3. Déployer

```bash
bash scripts/qa-deploy.sh
bash scripts/qa-status.sh
```

La commande applique les rôles PostgreSQL, les migrations Alembic et démarre l’application derrière Caddy. La readiness
doit retourner PostgreSQL et Redis à `ok`.

## 4. Créer le premier administrateur plateforme

```bash
export BOOTSTRAP_PLATFORM_ADMIN_CONFIRM=CREATE_FIRST_PLATFORM_ADMIN
export BOOTSTRAP_PLATFORM_ADMIN_EMAIL=admin@example.ca
export BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME="Administrateur QA"
bash scripts/qa-bootstrap-platform-admin.sh
```

Le script demande le mot de passe de manière interactive. Utilisez un mot de passe de recette unique.

## 5. Lire les courriels Mailpit

Mailpit n’est pas exposé publiquement. Depuis votre poste :

```bash
ssh -L 8025:127.0.0.1:8025 ubuntu@qa.example.com
```

Ouvrez ensuite `http://127.0.0.1:8025` localement. Les liens d’invitation doivent pointer vers
`https://qa.example.com`.

## 6. Sauvegarder la recette

```bash
bash scripts/qa-backup.sh
```

Le fichier généré est placé dans `backups/qa/`. Ce dossier n’est pas destiné à être commité.

## 7. Mettre à jour

```bash
git pull
bash scripts/qa-backup.sh
bash scripts/qa-deploy.sh
```

En cas d’échec après mise à jour, conservez la sauvegarde et revenez au commit précédent avec Git avant de relancer le
déploiement.

## 8. Règles QA

- Utiliser uniquement des données fictives.
- Ne jamais envoyer d’invitations à des clients réels.
- Limiter les quotas Google de la clé QA.
- Ne pas exposer Mailpit, PostgreSQL ou Redis dans le pare-feu Oracle.
- Supprimer l’instance ou les données QA lorsque la recette est terminée.
