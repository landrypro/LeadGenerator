# Prototype autonome — navigation hybride V2

Ouvrir `index.html` dans un navigateur. Aucun serveur, aucune installation, aucune clé et aucune connexion à l’application ne sont nécessaires. Les fichiers de ce dossier sont indépendants du client et du backend. Pour retirer le prototype, retirer uniquement ce dossier.

Pour une revue complète, suivre [RECETTE_PROTOTYPE_V2.md](RECETTE_PROTOTYPE_V2.md) et consigner les résultats dans [RECETTE_PROTOTYPE_V2_REGISTRE.csv](RECETTE_PROTOTYPE_V2_REGISTRE.csv).

**Statut de la recette : GO de conception accordé le 25 septembre 2026.** Quatorze scénarios ont été validés directement à `PASS`. L'anomalie historique `ROLE-V2-02` est corrigée et son rejeu `ROLE-V2-02-R1` est à `PASS`.

## Retouches V2

- Un changement de largeur conserve les résultats, les sélections et les champs saisis.
- Le compte reste accessible sans organisation ; aucun changement d’organisation n’est proposé aux profils Sans organisation et Plateforme.
- Le profil Plateforme expose séparément Plateforme et Audit plateforme, sur ordinateur comme dans le menu mobile.
- La catégorie de la destination active est mise en évidence.
- La fenêtre possède un titre accessible associé ; les libellés de navigation, fermeture et accès direct sont traduits.
- La sélection globale reflète la sélection partielle et exclut les résultats déjà ajoutés.
- Après une recherche, le sélecteur « Atelier V2 — état simulé » permet d’examiner résultats, chargement, absence de résultats, erreur réseau, quota atteint et interruption. Les actions de récupération sont fictives.
- Le Retour natif et le clavier virtuel restent à tester sur un appareil réel. La matrice des droits reste illustrative, pas contractuelle.

## Contenu

- Atelier de comparaison des largeurs 320 à 1440 px, français/anglais et profils simulés.
- Navigation hybride, tiroir, barre mobile et variante « Menu seul ».
- Changement d’organisation avec purge des résultats fictifs.
- Recherche locale simulée, paramètres brouillon/appliqués, annulation, sélection et ajout fictif avec nom CRM explicitement saisi.
- Maquettes de destination Usage et Exports ; les autres pages illustrent surtout le repérage dans la navigation.
- Automatisation invisible par défaut, activable uniquement dans les commandes de l’atelier comme projection future.
- Décision de recette : une fois activée, Automatisation se place immédiatement après Tableau de bord ; sur mobile, la barre inférieure conserve Accueil, Tâches, Prospects, Pipeline et Plus.

## Parcours de revue

1. À 1440 px, retrouver Tâches, Usage, Exports et Journal d’activité.
2. À 1024 px, ouvrir le tiroir puis le fermer avec Échap ; vérifier le retour au déclencheur.
3. À 390 puis 320 px, comparer la barre inférieure avec « Menu seul » et ouvrir Plus.
4. Ouvrir Acquisition → Recherche d’établissements, définir les paramètres et simuler une recherche.
5. Modifier la ville puis annuler : le résumé et les résultats restent ceux de la recherche appliquée.
6. Sélectionner deux établissements, saisir leurs noms internes dans Détails et simuler l’ajout.
7. Changer d’organisation : les résultats de l’espace précédent disparaissent.
8. Basculer en anglais puis en profil Commercial, Plateforme et Sans organisation.
9. Activer la projection Automatisation pour évaluer sa place future.

## Limites et décisions de maquette

Les permissions sont simplifiées pour la démonstration et ne remplacent pas la matrice réelle de capacités. Aucune action ne contacte une API, ne crée un export ou un enregistrement CRM. Aucun stockage navigateur n’est utilisé. Les noms d’entreprises sont inventés. La carte est un emplacement réservé, pas une carte géographique. L’autocomplétion des lieux n’est pas reproduite.

Le prototype ferme et abandonne le brouillon lors d’une annulation. Le bouton Retour natif du navigateur et les lecteurs d’écran demandent une validation spécifique avant implémentation. Le changement de langue/profil dans l’atelier réinitialise les résultats. Les tests utilisateurs, le taux de réussite et la conformité d’accessibilité restent à réaliser ; cet artefact ne vaut pas validation de ces critères.
