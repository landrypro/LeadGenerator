# Préproduction P5.1 — procédure opératoire

Ce répertoire contient uniquement les artefacts de préparation. Il ne crée aucune ressource AWS/Azure à lui seul.

## Prérequis de mise en service

Avant toute exécution sur l'hôte préproduction isolé, un responsable habilité doit :

1. créer le registre ECR privé, le bucket de sauvegarde chiffré KMS et les paramètres `SecureString` sous `/marketteo/preproduction` ;
2. accorder à l'identité de déploiement le droit minimal de lire ces paramètres, de tirer l'image ECR et d'écrire seulement dans le préfixe S3 de sauvegarde ;
3. protéger l'environnement Azure `marketteo-preproduction` par une approbation nominative ;
4. renseigner les variables non secrètes du modèle `.env.preprod.example`, notamment domaine, compte AWS, URI S3 et identifiant KMS ;
5. vérifier que les flags Automation restent à `false`, le fournisseur Assistant à `fake`, et les invitations à `disabled`.

## Déploiement contrôlé

Le pipeline manuel `azure-pipelines.preprod.yml` reçoit la SHA Git exacte. Il exécute le verrou, construit l'image, relève le digest ECR et publie un manifeste. Le stage de déploiement ne s'exécute que si `deployPreproduction=true` et après l'autorisation de l'environnement Azure.

Sur l'hôte, il génère `.env.preprod` avec `scripts/preprod-render-env.sh`, vérifie le manifeste, effectue une sauvegarde chiffrée KMS, puis applique le déploiement. Les scripts `preprod-verify-release.sh` et `preprod-restore-verify.sh` constituent respectivement la preuve de cohérence SHA/digest et la preuve de restauration jetable.

Ne jamais lancer une restauration sur la base active, supprimer un volume, ni utiliser des données client. Toute activation ou changement de flag suit le registre des réserves Porte 4.
