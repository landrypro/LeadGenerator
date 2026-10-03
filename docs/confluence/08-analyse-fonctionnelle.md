# Analyse fonctionnelle

## Objectif

Cette page consolide l'analyse fonctionnelle de Marketteo CRM. Elle decrit le perimetre metier, les acteurs, les modules, les parcours principaux, les regles de gestion et les limites fonctionnelles a respecter.

Elle ne remplace pas les specifications detaillees du depot. Elle sert de synthese Confluence pour les echanges produit, QA, support, formation et cadrage des evolutions.

## Vision produit

Marketteo CRM est un CRM SaaS destine aux petites equipes commerciales. Le produit aide a capter, qualifier, suivre et relancer des prospects tout en gardant une separation nette entre :

- les donnees CRM internes, persistantes et exportables ;
- les donnees Google affichees temporairement et non recopies en base ;
- les preuves de provenance, permissions de contact et decisions d'acquisition ;
- les traitements durables comme imports, exports, webhooks et futurs playbooks.

La promesse fonctionnelle consolidee est :

> Chaque prospect pris en charge. Chaque suivi maitrise.

## Acteurs et roles

| Role | Responsabilites fonctionnelles |
| --- | --- |
| Commercial | Gere ses prospects, contacts, activites, taches, opportunites et relances. |
| Gestionnaire | Supervise l'equipe, consulte les indicateurs, gere les affectations, imports, exports et certaines validations. |
| Administrateur d'organisation | Gere les membres, invitations, parametres, fournisseurs, conformite et journal d'activite. |
| Administrateur plateforme | Gere les organisations et l'audit plateforme lorsque le perimetre le prevoit. |
| Responsable produit / QA | Valide les parcours, la coherence fonctionnelle, les criteres d'acceptation et les reserves. |

Les capacites effectives restent verifiees cote serveur. Le masquage d'un bouton dans l'interface n'est jamais la seule barriere fonctionnelle.

## Perimetre fonctionnel V1

| Domaine | Capacites couvertes |
| --- | --- |
| Identite et acces | Connexion, deconnexion, sessions opaques, invitations, changement d'organisation, roles et preferences de langue. |
| Organisations et equipes | Membres, roles, quotas, langue par defaut, fuseau horaire et administration. |
| Recherche Google temporaire | Recherche limitee, resultats temporaires, attribution Google, ajout explicite au CRM par `place_id`. |
| Prospects et contacts | Creation manuelle, ajout depuis Google, import, connecteur approuve, contacts, canaux, origine, responsable et archivage. |
| Permissions et conformite | Provenance obligatoire, statut de permission, opposition, conservation, holds et audit. |
| Pipeline Kanban | Etapes commerciales, deplacement controle, conflits optimistes, filtres et historique. |
| Activites et taches | Notes, appels, rendez-vous, courriels declaratifs, rappels, echeances, assignation et fil chronologique. |
| Opportunites | Montant, devise, probabilite, echeance, responsable, etapes, cloture gagnee/perdue et reouverture. |
| Tableau de bord | Taches dues, prospects par etape, activites, opportunites, valeur de pipeline et usage. |
| Import CSV | Declaration de source, mapping, validation, confirmation, quarantaine, idempotence et rapport. |
| Export CSV | Demandes d'export, liste blanche de colonnes, fichiers prives, telechargement recontrole et audit. |
| Fournisseurs et connecteurs | Registre fournisseurs, acquisitions, pilote Meta Lead Ads conditionnel ou simule, webhooks signes. |
| Usage et quotas | Consommation Google, quotas par utilisateur et organisation, rapports d'usage. |
| Manuel et aide | Manuel utilisateur, procedures par role, limites connues et depannage de premier niveau. |

## Hors perimetre ou non disponible

| Sujet | Statut fonctionnel |
| --- | --- |
| Export des donnees Google descriptives | Exclu : les champs Google affiches en direct ne sont pas exportes en V1. |
| Scraping social ou connecteur LinkedIn non approuve | Interdit sans partenariat, licence et autorisation explicites. |
| Activation Meta reelle | Conditionnee aux autorisations externes ; le pilote reste simule ou bloque si les preconditions ne sont pas remplies. |
| Facturation et paiements | Cadres en Phase 5, non presentes comme livres. |
| Notifications externes autonomes | Non disponibles en V1. |
| Automatisation active | Preparation documentaire et preuves isolees seulement ; pas d'effet CRM integre avant decision de Porte 4. |
| Workflow libre cree par IA | Exclu : seules des recettes guidees et controlees sont prevues. |

## Modules fonctionnels

| Module | Finalite | Points d'attention |
| --- | --- | --- |
| Comptes et equipes | Securiser l'acces et gerer les roles. | Dernier administrateur protege ; sessions invalidees apres desactivation. |
| Etablissements prospects et contacts | Construire le portefeuille CRM. | Une personne, un etablissement et un canal restent trois concepts distincts. |
| Pipeline Kanban | Visualiser et piloter l'avancement commercial. | Etape commerciale separee des activites et relances. |
| Activites commerciales | Journaliser les interactions et prochaines actions. | Suppression logique et audit des changements. |
| Actions integrees | Faciliter les actions depuis la fiche. | Appels/liens externes ne persistent pas automatiquement les donnees Google. |
| Opportunites | Suivre les revenus potentiels. | Montants en decimal, devise explicite et transitions auditees. |
| Conformite commerciale | Controler permissions, provenance et conservation. | Opposition bloquante, levee justifiee par role autorise. |
| Tableau de bord | Donner une vision de pilotage. | Indicateurs fondes sur donnees internes et compteurs techniques. |
| Import / export conformes | Entrer et sortir des donnees sous controle. | Liste blanche, idempotence, fichiers temporaires et absence de champs Google exportes. |

## Parcours utilisateurs principaux

### Rechercher puis ajouter un prospect

1. L'utilisateur ouvre la recherche d'etablissements.
2. Il saisit le type d'entreprise, le lieu et le rayon.
3. L'API interroge Google de maniere bornee.
4. L'interface affiche des resultats temporaires avec attribution.
5. L'utilisateur choisit un resultat et saisit un nom interne CRM.
6. L'ajout cree un prospect avec `place_id`, origine, responsable et donnees internes.
7. Un doublon exact retourne ou signale la fiche existante au lieu de creer une seconde fiche active.

### Gerer une fiche prospect

1. L'utilisateur ouvre une fiche depuis Prospects ou Pipeline.
2. Les donnees CRM internes sont affichees en priorite.
3. Les details Google sont charges en direct uniquement lorsque necessaire.
4. L'utilisateur ajoute contacts, canaux, activites, taches ou opportunites selon ses droits.
5. Les actions significatives sont journalisees.

### Faire progresser le pipeline

1. L'utilisateur deplace une carte vers une nouvelle etape.
2. Le serveur verifie le role, le responsable, la version et les regles de transition.
3. Le changement est applique ou refuse en conflit.
4. Un evenement d'historique est cree.

### Realiser une relance

1. Le tableau de bord ou la fiche signale une tache due.
2. L'utilisateur consulte la fiche et les permissions.
3. Il effectue l'action autorisee.
4. Il journalise le resultat, cree la prochaine action ou cloture la tache.

### Importer des prospects et contacts

1. Un utilisateur autorise declare source, finalite, droits et restrictions.
2. Il televerse un CSV et mappe les colonnes.
3. Le systeme valide, detecte les doublons et met en quarantaine les lignes ambigues.
4. L'utilisateur corrige ou exclut les erreurs.
5. La confirmation ecrit les donnees valides de maniere idempotente.
6. Le rapport presente creations, doublons, quarantaines et rejets.

### Exporter des donnees internes

1. L'utilisateur autorise choisit un jeu exportable et une portee.
2. Le systeme cree une demande durable.
3. Le worker produit un fichier prive avec colonnes en liste blanche.
4. Le telechargement reverifie les droits.
5. L'audit conserve auteur, filtres, volume et statut.

## Regles de gestion structurantes

| Regle | Description |
| --- | --- |
| Organisation active | L'organisation vient de la session, jamais d'un parametre libre du navigateur. |
| Isolation locataire | Un utilisateur ne voit jamais les donnees d'une autre organisation. |
| Donnees Google | Les noms, adresses, telephones, sites et categories Google restent temporaires ; seul le `place_id` peut devenir reference durable. |
| Nom interne CRM | L'utilisateur choisit le nom CRM ; le nom Google n'est pas recopie automatiquement. |
| Permission par canal | Chaque canal persistant possede provenance et permission ; `unknown` est le defaut sans preuve. |
| Opposition | Une opposition bloque les actions de contact et ne peut pas etre contournee par un playbook ou l'IA. |
| Idempotence | Imports, webhooks, exports et actions durables doivent eviter les doublons au rejeu. |
| Archivage | L'archivage conserve l'historique et exclut les elements des vues actives. |
| Concurrence | Les prospects et opportunites utilisent une logique de version/conflit pour eviter l'ecrasement silencieux. |
| Audit | Les actions sensibles sont journalisees avec acteur, organisation, objet, action et metadata minimisee. |
| Bilinguisme | Les surfaces visibles visent `fr-CA` et `en-CA`, avec repli francais. |

## Analyse fonctionnelle de l'Automatisation

Le volet Automatisation reste un perimetre futur encadre. La reference `RF-AUT-2.1` fixe les comportements attendus sans autoriser la production.

Principes fonctionnels :

- point d'entree Assistant dans `Aujourd'hui` ;
- trois playbooks guides uniquement : Nouveau prospect, Proposition en attente, Occasion oubliee ;
- Feu relationnel deterministe par action, canal, prospect, instant et version de regles ;
- priorite `Rouge > Jaune > Vert` ;
- mode actif initial `Preparer` ;
- Prevol obligatoire, sans effet, utilisant les memes regles que l'execution ;
- brouillons et approbations liees a un contenu exact ;
- revalidation des droits avant effet differe ;
- aucune communication externe autonome ;
- aucun registre CRM parallele.

| Couleur | Sens fonctionnel | Effet attendu |
| --- | --- | --- |
| Vert | Action admissible selon les donnees et regles disponibles. | Preparation ou etape autorisee dans les limites du mode actif. |
| Jaune | Preuve absente, contradictoire, expiree ou approbation requise. | Verification, tache interne, brouillon ou demande d'approbation. |
| Rouge | Opposition ou interdiction deterministe. | Blocage, explication et journalisation. |

## Critères d'acceptation transverses

- Les parcours critiques sont utilisables par role autorise.
- Les operations sensibles sont bloquees cote serveur si les droits manquent.
- Les donnees Google ne deviennent pas des donnees CRM sans action explicite.
- Les imports et exports sont idempotents et auditables.
- Les oppositions et restrictions de contact sont visibles et bloquantes.
- Les erreurs publiques restent explicites sans exposer de secret.
- Les interfaces restent coherentes en francais canadien et anglais canadien.
- Les etats vides, erreurs reversibles et indisponibilites fournisseurs sont compréhensibles.
- Les preuves QA et le manuel utilisateur restent alignes avec le comportement livre.

## Sources consolidees

| Source locale | Usage dans cette analyse |
| --- | --- |
| `docs/SPECIFICATION_CRM_V1.md` | Modules, roles, parcours, regles, API cible, decisions produit et limites. |
| `docs/manuel-utilisateur/README.md` | Perimetre observe du manuel, roles, ecrans livres et limites non disponibles. |
| `docs/manuel-utilisateur/MANUEL_UTILISATEUR.md` | Procedures utilisateur detaillees. |
| `docs/manuel-utilisateur/MATRICE_COUVERTURE.md` | Couverture des ecrans et roles. |
| `docs/CAHIER_RECETTE_FONCTIONNELLE_QA.md` | Scenarios de recette utilisateur. |
| `docs/RECETTE_PHASE4.6_INTERACTIVE.md` | Parcours bout en bout Phase 4.6 et preuves fonctionnelles. |
| `docs/automatisation/REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md` | Contrat fonctionnel Automatisation. |
| `docs/automatisation/ETAPE_2_CONCEPTION_FONCTIONNELLE_UX.md` | Conception UX et parcours d'Automatisation. |

## Points ouverts

| Point | Impact |
| --- | --- |
| Preuve Azure du commit de cloture 4.6 | Requise avant entree effective en Phase 5. |
| Activation Meta reelle | Depend d'autorisations externes et d'une validation fournisseur. |
| Phase 5 | Preproduction, abonnements, paiements et lancement progressif restent a cadrer/livrer. |
| Automatisation | Construction active et effets CRM bloques tant que Porte 4 n'a pas rendu son verdict. |
| Manuel 1.0 | Necessite validation finale du canal support, de l'URL production et des consignes conformite. |
