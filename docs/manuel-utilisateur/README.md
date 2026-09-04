# Projet de manuel utilisateur - Marketteo CRM

## Objectif

Ce dossier est la source de référence du manuel utilisateur de Marketteo CRM. Il doit rester synchronisé avec les écrans livrés, les capacités par rôle et les règles de conformité réellement appliquées par l'application.

La première édition couvre l'état fonctionnel observé dans le dépôt au 25 août 2026. Elle s'adresse aux commerciaux, gestionnaires, administrateurs d'organisation et administrateurs de plateforme.

## Livrables

- `MANUEL_UTILISATEUR.md` : source éditoriale versionnée ;
- `MATRICE_COUVERTURE.md` : couverture des écrans, rôles et captures ;
- `Marketteo_CRM_Manuel_Utilisateur_v0.1.docx` : édition Word générée et vérifiée ;
- `scripts/build_user_manual.py` : générateur reproductible du document Word.

## Ligne éditoriale

- Employer **Marketteo CRM** comme nom du produit.
- Reprendre les libellés visibles de l'interface entre guillemets ou en gras.
- Écrire des procédures courtes qui commencent par un verbe d'action.
- Séparer clairement une donnée CRM persistante d'une donnée Google temporaire.
- Ne jamais présenter une fonctionnalité planifiée comme disponible.
- Signaler les actions sensibles, irréversibles ou journalisées avant l'étape concernée.
- Utiliser « courriel », « organisation », « prospect » et « canal de contact » de façon constante.

## Sources de vérité

En cas de divergence, appliquer cet ordre :

1. comportement observable et tests automatisés du client ;
2. capacités et règles métier du serveur ;
3. routes de l'application ;
4. spécifications fonctionnelles ;
5. texte du manuel existant.

Les principales sources actuelles sont `client/src/app/routes.js`, les composants sous `client/src/features`, `backend/app/domain/identity.py` et `docs/SPECIFICATION_CRM_V1.md`.

## Périmètre de l'édition 0.1

Sont documentés :

- invitation, création de compte, connexion et changement d'organisation ;
- recherche Google ponctuelle et ajout d'établissements au CRM ;
- création manuelle, recherche et consultation des prospects ;
- profil CRM, contacts, canaux et permissions de contact ;
- fournisseurs, acquisitions et provenance ;
- politiques de conservation, holds, déclarations et import CSV réel ;
- organisation, membres, invitations et journal d'activité ;
- administration des organisations et audit de plateforme ;
- limites actuelles et dépannage de premier niveau.

Ne sont pas décrits comme disponibles : export des contenus Google, pipeline commercial complet, tâches/rappels, opportunités, facturation et automatisations futures.

## Cycle de mise à jour

1. Repérer les routes, libellés, capacités ou règles métier modifiés.
2. Mettre à jour `MATRICE_COUVERTURE.md`.
3. Réviser la procédure correspondante dans `MANUEL_UTILISATEUR.md`.
4. Mettre à jour ou refaire les captures concernées.
5. Régénérer le DOCX.
6. Vérifier le rendu page par page et exécuter les audits structurels.
7. Incrémenter la version et résumer le changement dans l'historique du manuel.

## Définition de terminé

Une édition est publiable lorsque :

- chaque route visible est couverte ou explicitement exclue ;
- les actions sont cohérentes avec les capacités des rôles ;
- tous les boutons, onglets et messages cités existent dans l'interface ;
- les limites Google, provenance, permission de contact et conservation sont exactes ;
- aucune donnée réelle de client n'apparaît dans les exemples ou captures ;
- les captures sont lisibles et portent un texte alternatif ;
- le DOCX ne comporte ni chevauchement, ni texte rogné, ni tableau brisé ;
- la version, la date et l'état de validation sont visibles.

## Décisions encore requises avant une édition 1.0

- régénérer les captures et le DOCX après la migration des libellés visibles vers « Marketteo CRM » ;
- fournir l'URL de production et le canal officiel de soutien ;
- choisir un jeu de données de démonstration et produire les captures d'écran ;
- faire valider les consignes de conformité par la personne responsable ;
- confirmer si l'administration de plateforme doit rester dans le même manuel ou devenir un guide séparé.
