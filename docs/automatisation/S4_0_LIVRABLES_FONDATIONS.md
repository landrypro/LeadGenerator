# S4-0 — Livrables réalisés et preuves de préparation

> **Statut : livrables de préparation réalisés — validation statique D2 obtenue**  
> **Périmètre :** artefacts synthétiques, aucune exécution CRM  
> **Contre-validation associée :** [CONTRE-VALIDATION-S4-0](./CONTRE_VALIDATION_S4_0.md)

## 1. Cadre d’exécution

| Élément | Valeur constatée |
|---|---|
| Branche de travail | `codex/phase-2.4.3-audit` — branche de travail non-production |
| Environnement | Python `.venv`, validation locale hors réseau et hors worker |
| Données | Manifeste synthétique, deux organisations, aucune PII |
| IA réelle | Désactivée et non configurée |
| Worker Automation | Non branché |
| Base client | Non utilisée et non modifiée |
| Responsables fonctionnels | Produit, Ingénierie, QA et Sécurité — propriétaires de contrôle définis ; noms individuels à confirmer avant construction |

La branche courante est suffisante pour les artefacts statiques S4-0. Une branche dédiée à l’implémentation active devra
être créée avant S4-1 ou tout changement de code produit.

## 2. `AUT-4001` — Constantes et versions V2.1

| Domaine | Version | Règle gelée | Effet S4-0 |
|---|---|---|---|
| Point d’entrée | `RF-AUT-2.1` | Une intention IA structurée, jamais une écriture directe | Préparer uniquement |
| Mode | `PREPARER-1` | Prévol et approbation avant effet | Actif par défaut |
| Playbooks | `PB-1.0` | Nouveau prospect, Proposition en attente, Occasion oubliée | Catalogue fermé |
| Feu | `FEU-1.0` | Rouge > Jaune > Vert ; inconnu jamais Vert | Décision explicable |
| Passeport | `PASS-1.0` | Origine, permission, responsable, prochaine action, historique | Lecture canonique |

Une modification matérielle de cette table impose une nouvelle version de `RF-AUT` et une nouvelle décision de porte.

## 3. `AUT-4002` — Flags et suspension

| Niveau | Flag | Valeur S4-0 | Priorité | Arrêt déclenché |
|---|---|---:|---:|---|
| Global | `automation_global` | `false` | 1 | Toute préparation Automation refusée côté serveur |
| Organisation | `automation_organization` | `false` | 2 | Toute commande de l’organisation refusée |
| Playbook | `playbook_new_prospect` | `false` | 3 | Le Playbook ciblé reste indisponible |

La valeur la plus restrictive gagne. L’interface ne peut jamais réactiver un flag désactivé côté serveur. La suspension
générationnelle prévue par T3 reste obligatoire avant tout effet futur.

## 4. `AUT-4003` — Capabilities par rôle

| Rôle | Préparer | Approuver interne | Approuver externe | Résoudre exception |
|---|---:|---:|---:|---:|
| Administrateur | Oui | Oui | Oui, selon permissions | Oui |
| Commercial | Oui | Oui | Non par défaut | Non par défaut |
| Membre révoqué | Non | Non | Non | Non |

Le rôle ne suffit jamais à lui seul : organisation, membre actif, Playbook, Feu, suspension et état CRM sont revérifiés
au moment de la demande puis juste avant l’effet.

## 5. `AUT-4004` — Principal `automation-system`

Les bornes préparées sont :

- principal désactivé par défaut (`enabled=false`) ;
- origine unique `automation_preparer` ;
- portée maximale d’une organisation ;
- TTL maximal de 900 secondes ;
- acteur humain requis ;
- envoi externe interdit ;
- audit de toute utilisation et refus d’une portée excessive.

Le principal n’est donc pas un contournement des capacités. Son activation future nécessitera une décision de sécurité
distincte et une preuve serveur.

## 6. `AUT-4005` — Migrations et rollback

Le plan isolé prévoit les tables Automation suivantes :

- `automation_playbooks` ;
- `automation_playbook_versions` ;
- `automation_decisions` ;
- `automation_exceptions`.

Contraintes définies :

1. `organization_id` obligatoire et protégé par RLS ;
2. aucune table CRM canonique modifiée par S4-0 ;
3. migration additive et réversible ;
4. rollback : désactiver les flags, supprimer les tables Automation de test et réconcilier les traces ;
5. aucune migration client avant Porte 4 et preuve D3.

Le manifeste synthétique matérialisant ce contrat se trouve dans [`fixtures/s4-0/manifest.json`](./fixtures/s4-0/manifest.json).

## 7. `AUT-4006` — Corrélation, événements et audit minimal

Chaque commande future devra porter : `decision_id`, `correlation_id`, `organization_id`, `actor_id`, `playbook_version`,
`outcome` et `reason_code`.

Événements prévus :

- `automation.decision.prepared` ;
- `automation.decision.refused` ;
- `automation.exception.quarantined` ;
- `automation.execution.to_verify`.

La phrase libre, le brouillon complet et les données personnelles inutiles ne font pas partie des labels ou de l’audit
minimal S4-0.

## 8. `AUT-4007` — Métriques et cardinalité

Métriques retenues :

- `automation_decisions_total{organization_id,playbook,outcome}` ;
- `automation_exceptions_total{organization_id,exception_code}`.

Les labels sont fermés, bornés et dépourvus de phrase libre, adresse électronique, payload ou token. Les seuils de
rétention et d’alerte seront confirmés avant l’intégration au dashboard du worker.

## 9. Preuve D2 statique

Le script [`validate_manifest.py`](./fixtures/s4-0/validate_manifest.py) vérifie sans réseau et sans base :

- deux organisations isolées et des identifiants uniques ;
- flags désactivés par défaut ;
- absence de PII et de secrets fournisseur ;
- capacités minimales et révocation ;
- principal système désactivé, borné et soumis à un acteur humain ;
- migration RLS sans mutation CRM et rollback déclaré ;
- métriques avec organisation et sans labels sensibles.

Cette preuve est **D2 artefact statique**. Elle ne vaut pas preuve d’exécution serveur, de RLS réel, de migration réelle,
de charge ou de worker ; ces éléments restent D3/D4.

Résultat exécuté le 1er octobre 2026 :

```text
S4-0 D2 artifact validation: PASS
tenants=2 prospects=3 metrics=2
crm_tables_mutated=false flags_default=false system_principal_enabled=false
```

## 10. État de réalisation

| Prescription S4-0 | État |
|---|---|
| Propriétaires fonctionnels | Référencés ; noms individuels à confirmer avant construction |
| Branche et environnement isolés | Confirmés pour validation statique |
| Fixtures synthétiques | Produites et validables |
| Livrables `AUT-4001..4007` | Produits dans ce dossier |
| Preuves D2 statiques P0 | Produites par le script de validation |
| Flags, suspension, rollback exécutés sur produit | Non — procédure définie, exécution serveur réservée |
| Registre Porte 4 | À mettre à jour avec ces artefacts |
| IA réelle et worker actif | Interdits |

## 11. Sortie attendue de la contre-validation

La réalisation documentaire et statique de S4-0 est acceptée sous réserve de confirmer les noms des responsables et de
produire les preuves serveur D2/D3 avant la Porte 4. La définition de S4-1 est autorisée dans son dossier dédié ; son
exécution runtime n’est pas ouverte par ce dossier.
