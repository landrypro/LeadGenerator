# Recette applicative — Relooking UX : navigation et recherche mobile

## 1. Objet et verdict attendu

Cette recette couvre les trois lots du relooking UX livrés ensemble :

| Lot | Périmètre | Référence |
| --- | --- | --- |
| NAV-L1 | Navigation globale, catégories, droits, Plateforme, organisation et compte | [Rapport L1](RAPPORT_NAVIGATION_LOT_1.md) |
| NAV-L2 | Seuils responsive, panneau modal, barre mobile, focus, Retour et zones sûres | [Rapport L2](RAPPORT_NAVIGATION_LOT_2.md) |
| NAV-L3 | Recherche Google mobile : brouillon/appliqué, résultats, carte, sélection et ajout CRM | [Rapport L3](RAPPORT_NAVIGATION_LOT_3.md) |

Le verdict est **PASS** lorsque tous les scénarios applicables sont PASS et qu’aucun défaut bloquant d’accès, de droits, de navigation ou de mutation CRM n’est observé. Les contrôles automatisés sont déjà verts ; cette campagne les complète sur l’application réelle et les appareils réels.

## 2. Prévol

1. Démarrer l’application dans l’environnement retenu et se connecter à une organisation de démonstration non sensible.
2. Confirmer que le build courant est chargé (forcer le rechargement sans cache si nécessaire).
3. Préparer les comptes ci-dessous ou leurs équivalents ; noter uniquement les rôles, jamais les mots de passe, cookies ou jetons.
4. Pour NAV-L3, utiliser le fournisseur Google de test/configuré et une requête métier simple, par exemple `plombier` autour de Québec. Ne pas créer de données réelles.
5. Préparer au moins un téléphone iOS et un téléphone Android, ou deux navigateurs mobiles réels ; prévoir aussi un navigateur desktop à 100 % et 200 % de zoom.

| Alias de recette | Profil requis | Usage |
| --- | --- | --- |
| `UX-ADMIN-FR` | Admin d’organisation fr-CA, multi-organisation si possible | Parcours complet, catégories, changement d’organisation, recherche/CRM |
| `UX-SALES` | Sales avec capacités restreintes | Filtrage réel des destinations et barre mobile réduite |
| `UX-PLATFORM` | Administrateur plateforme, sans organisation active | Plateforme, Audit plateforme et Compte |
| `UX-ADMIN-EN` | Admin en-CA | Libellés, longueurs et comportements EN |

## 3. Grille de preuve

Pour chaque scénario, consigner : identifiant, statut `PASS` / `FAIL` / `BLOCKED` / `NOT RUN` / `N/A`, appareil/navigateur, rôle, organisation, date UTC et une phrase de constat. Joindre une capture uniquement si elle apporte une preuve ; elle ne doit contenir ni donnée personnelle, ni secret, ni information Google sensible.

## 4. NAV-L1 — Navigation globale

| ID | Action | Résultat attendu |
| --- | --- | --- |
| NAV-L1-01 | Avec `UX-ADMIN-FR` sur desktop large, parcourir les accès directs et ouvrir Acquisition, Données et audit, Administration. | Ordre et catégories conformes ; aucun lien métier perdu ; repère actif sur la route courante. |
| NAV-L1-02 | Rejouer avec `UX-SALES`. | Seules les destinations autorisées sont visibles ; aucun groupe vide ; aucune destination interdite n’est atteignable via le menu. |
| NAV-L1-03 | Avec `UX-PLATFORM`, sans organisation active, ouvrir le menu principal. Rejouer avec uniquement une des deux capacités plateforme si disponible. | Plateforme et Audit plateforme sont indépendants ; Compte reste accessible sans organisation. |
| NAV-L1-04 | Ouvrir un groupe puis le fermer avec Échap, Tab hors du groupe et clic extérieur. Ouvrir un lien avec Ctrl/Cmd. | Fermeture attendue, focus cohérent ; Ctrl/Cmd conserve le comportement du navigateur. |
| NAV-L1-05 | Avec un compte multi-organisation, changer d’organisation depuis l’en-tête. | L’état d’attente est compréhensible ; l’arrivée est autorisée ; menus et droits sont recalculés sans fuite de l’organisation précédente. |
| NAV-L1-06 | Ouvrir le compte, vérifier le rôle, le Manuel et Déconnexion. | Identité/rôle corrects, Compte et Manuel accessibles, aucune régression de déconnexion. |
| NAV-L1-07 | Vérifier les pages Prospects, Pipeline, Opportunités et Recherche Google. | URL et contenu métier inchangés ; Automatisation n’apparaît pas encore dans la navigation. |

## 5. NAV-L2 — Responsive et accessibilité

Jouer au minimum les largeurs 1440, 1400, 1024, 640, 600, 390 et 320 px. À défaut de redimensionnement physique, utiliser le mode responsive du navigateur puis confirmer les contrôles tactiles sur appareil réel.

| ID | Action | Résultat attendu |
| --- | --- | --- |
| NAV-L2-01 | À 1440 px puis 1400 px, observer l’en-tête avec un nom d’organisation/utilisateur long. | Navigation complète à partir de 1400 px, sans chevauchement ni défilement horizontal. |
| NAV-L2-02 | Entre 601 et 1399 px, ouvrir `Menu`. | En-tête compact ; panneau lisible et défilable ; toutes les destinations autorisées restent disponibles. |
| NAV-L2-03 | À 600 px puis 390/320 px, vérifier la barre `Accueil | Tâches | Prospects | Pipeline | Plus` avec `UX-ADMIN-FR`, puis `UX-SALES`. | Ordre stable, entrées filtrées par droits, `Plus` toujours présent ; route hors raccourcis repérée par Plus. |
| NAV-L2-04 | Dans le panneau compact, vérifier focus initial, Tab/Shift+Tab, Échap, fermeture et clic arrière. | Focus contenu dans le panneau ; arrière-plan non interactif ; fermeture et retour du focus au déclencheur. |
| NAV-L2-05 | Ouvrir le panneau puis utiliser Retour navigateur ; le rouvrir, naviguer à un lien, puis utiliser Avance si disponible. | Retour ferme d’abord le panneau sans changer de page ; navigation ferme le panneau sans le rouvrir par Avance. |
| NAV-L2-06 | Sur téléphone, portrait puis paysage, ouvrir `Plus` et les paramètres Google ; afficher le clavier virtuel dans un champ. | `100dvh`, zones sûres et défilement conservent fermeture/actions accessibles ; aucune barre ne masque les commandes. |
| NAV-L2-07 | À 200 % de zoom desktop, rejouer le panneau et les liens en fr-CA puis en-CA. | Repli compact utilisable, focus visible, aucun débordement horizontal ni texte tronqué de manière bloquante. |
| NAV-L2-COR-01 | Sur téléphone, ouvrir `Plus` puis vérifier Acquisition, Données et audit et Administration. Replier/réouvrir une rubrique. | Les catégories sont déployées à l’ouverture et restent repliables ; leurs liens sont visibles et activables : Recherche/Sources, Quotas/Conservation/Historique/Exports/Journal, Organisation/Membres. |

## 6. NAV-L3 — Recherche Google mobile

Effectuer ces scénarios à 390 px au minimum. Avant une écriture CRM, utiliser un établissement de test et un nom interne explicite préfixé `UX-`.

| ID | Action | Résultat attendu |
| --- | --- | --- |
| NAV-L3-01 | État initial : ouvrir Recherche Google sans résultat. | Invitation à définir les paramètres ; aucun faux résultat ni carte centrale vide prioritaire ; estimation Google visible. |
| NAV-L3-02 | Ouvrir Paramètres, saisir type d’entreprise, sélectionner pays/région puis ville/quartier via autocomplétion, ajuster rayon/zone de service et lancer la recherche. | Coordonnées résolues automatiquement ; une recherche explicite seulement ; résultats temporaires affichés en priorité. |
| NAV-L3-03 | Après résultat, relever le résumé appliqué puis ouvrir Modifier, changer le type/rayon et fermer avec X ou Échap. | Le panneau est modal, le brouillon est conservé ; le résumé et les résultats restent ceux de la dernière recherche appliquée. |
| NAV-L3-04 | Rouvrir les paramètres après NAV-L3-03 puis choisir Annuler. | Le brouillon est abandonné et les paramètres reviennent exactement à la dernière recherche appliquée. |
| NAV-L3-05 | Depuis les résultats, choisir Voir la carte puis Masquer la carte. | La carte/métriques sont secondaires, à la demande ; les résultats restent prioritaires. |
| NAV-L3-06 | Filtrer les résultats, sélectionner une ligne puis vérifier la sélection globale ; sélectionner/désélectionner tout ce qui est affiché. | Compteur exact, état partiel visible, filtre sans requête Google supplémentaire. |
| NAV-L3-07 | Sélectionner un établissement, cliquer Ajouter la sélection sans nom CRM. | Focus dirigé vers le premier nom interne manquant ; aucune écriture CRM, aucun nom Google prérempli/copié. |
| NAV-L3-08 | Saisir `UX-<nom>` pour les établissements sélectionnés puis ajouter. | Création/état CRM explicite, une écriture par sélection autorisée ; résultat lisible et sélection mise à jour. |
| NAV-L3-09 | Provoquer ou simuler erreur réseau/quota, puis relancer une recherche valide. | Erreur compréhensible, aucune donnée CRM écrite ; récupération possible sans rechargement ; pas de recherche implicite. |
| NAV-L3-10 | Changer d’organisation pendant que des résultats et une sélection existent. | Résultats temporaires, brouillon associé et sélection sont purgés ; aucune donnée de l’ancienne organisation ne reste visible. |
| NAV-L3-11 | Rejouer NAV-L3-01 à 05 en en-CA et avec clavier virtuel. | Libellés EN corrects, focus et action de recherche accessibles, aucun chevauchement avec la barre mobile. |

## 7. Clôture

1. Reporter tous les statuts dans cette grille ou dans le registre de recette choisi par l’équipe.
2. Un `FAIL`, `BLOCKED` ou `NOT RUN` sur un scénario applicable empêche le verdict global PASS.
3. Si une anomalie est observée, noter l’ID, la largeur/appareil, le rôle, l’organisation, le chemin, les étapes minimales, le résultat observé et une capture assainie.
4. Après la recette applicative, relancer le verrou qualité local et relier son résultat au rapport des lots.

## Verdict

| Lot | Statut | Commentaire / preuve |
| --- | --- | --- |
| NAV-L1 | PASS | 26 septembre 2026 — NAV-L1-01 à NAV-L1-07 validés sur application réelle : catégories, repères actifs, droits, Plateforme/Audit, organisation, compte et pages métier. |
| NAV-L2 | PASS | 26 septembre 2026 — NAV-L2-01 à NAV-L2-07 et NAV-L2-COR-01 validés sur application réelle. Les catégories et leurs sous-menus sont visibles et activables dans `Plus` sur mobile. |
| NAV-L3 | PASS | 26 septembre 2026 — NAV-L3-01 à NAV-L3-11 validés sur application réelle : paramètres, recherche appliquée/brouillon, carte, résultats, erreurs, sélection et ajout CRM explicite. |
| Relooking UX global | PASS | 26 septembre 2026 — NAV-L1, NAV-L2 et NAV-L3 sont validés sur application réelle. La recette de relooking UX est clôturée. |
