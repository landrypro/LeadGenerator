# Mini-recette fonctionnelle — Pré-Phase 5.1

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Périmètre | Phase 5.1 — Préproduction et mesure de référence |
| Type | Recette fonctionnelle courte, à exécuter après livraison du lot 5.1 |
| Statut | Préparée le 4 octobre 2026 — aucune activation autorisée |
| Référence | Cadrage « Phase 5.1 — Préproduction et mesure de référence » |

## 1. But et limites

Cette recette vérifie que la version approuvée de Marketteo peut être déployée, contrôlée, restaurée et mesurée dans une préproduction isolée. Elle apporte une preuve fonctionnelle rapide ; elle ne remplace ni le verrou qualité, ni les revues de sécurité, ni les essais de charge détaillés.

Elle n'autorise pas le paiement, l'abonnement, une organisation cliente, des données client, un envoi réel, un fournisseur réel ou une activation d'Automation.

## 2. Préconditions de lancement

- GO explicite de développement du lot 5.1 ;
- SHA Git approuvé et verrou qualité vert ;
- préproduction isolée disponible, avec données exclusivement synthétiques ;
- image OCI privée, manifeste de version et accès de recette disponibles ;
- Mailpit de test et fournisseurs fake configurés ;
- aucune clé, donnée ou organisation cliente utilisée.

## 3. Parcours à exécuter

| ID | Parcours | Action de recette | Résultat attendu | Preuve minimale |
| --- | --- | --- | --- | --- |
| P51-MR-01 | Version promue | Ouvrir le rapport de déploiement puis l'application de préproduction. | Le SHA, le digest, la révision de migration et les versions API/worker concordent ; l'application est `live` et `ready`. | Rapport de déploiement daté, sans secret. |
| P51-MR-02 | Connexion fonctionnelle | Se connecter avec un compte et des données de recette synthétiques, puis parcourir un écran CRM autorisé. | Accès normal ; aucune donnée cliente n'est présente. | Capture ou résultat de recette synthétique. |
| P51-MR-03 | Action métier bornée | Créer, consulter puis modifier une donnée CRM de test ; vérifier l'exécution du worker associé si applicable. | L'action est persistée, lisible après rechargement et le worker est sain. | Identifiant synthétique et résultat du worker. |
| P51-MR-04 | Frontières externes | Exécuter un parcours qui solliciterait Google, OpenAI, e-mail ou Automation. | Seuls les simulateurs/Mailpit sont utilisés ; aucun appel réel, envoi réel ou flag Automation activé. | Trace fake ou Mailpit, sans PII. |
| P51-MR-05 | Migration reproductible | Déployer la révision sur une base vide puis sur un jeu synthétique de révision précédente. | Migration attendue ; API et worker redeviennent `ready` ; contrôles de cohérence positifs. | Révision Alembic et journal de résultat. |
| P51-MR-06 | Sauvegarde et restauration | Produire une sauvegarde, la vérifier puis restaurer uniquement dans l'environnement jetable. | Somme de contrôle valide, application `ready`, cohérence vérifiée ; aucune écriture dans la préproduction active. | Rapport de restauration : durée, résultat, cible jetable. |
| P51-MR-07 | Retour arrière applicatif | Simuler un échec compatible après déploiement et revenir au dernier digest approuvé. | Retour au digest précédent sans suppression de volume ni restauration sur la cible active. | SHA/digest avant et après, résultat des sondes. |
| P51-MR-08 | Alertes et ligne de base | Déclencher de façon contrôlée un échec de sonde ou de sauvegarde, puis rejouer le profil synthétique de référence. | Alerte, propriétaire et runbook identifiables ; rapport coût/latence versionné, sans PII, SLO ni prix publiés. | Alerte anonymisée et rapport de référence. |

## 4. Critères de passage

La mini-recette est **PASS** si les huit parcours sont validés, que toutes les preuves sont datées et que les frontières suivantes ont été respectées : préproduction isolée, données synthétiques, absence de secrets/PII dans les preuves, fournisseurs réels désactivés et Automation non activée.

Un échec sur l'immuabilité de version, les secrets, l'isolation des données, la restauration active ou un appel réel impose un **STOP** : aucun passage vers 5.2 n'est recommandé avant correction et rejeu du scénario concerné.

## 5. Compte rendu

| Décision | Date | Responsable | Preuves / lien | Réserves |
| --- | --- | --- | --- | --- |
| PASS / FAIL / BLOQUÉ |  |  |  |  |

## 6. Sortie

Un PASS prépare la Phase 5.2 (décisions commerciales) sans l'autoriser automatiquement. Le paiement, les prix, les abonnements, le checkout et toute activation cliente restent hors périmètre de cette recette.
