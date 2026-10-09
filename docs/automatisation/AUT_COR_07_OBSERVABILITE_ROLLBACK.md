# AUT-COR-07 — Observabilité, flags et retour arrière

## Objet

Ce lot rend la correction Automatisation observable et réversible sans activer de
commande métier. Il ne crée aucune donnée CRM, aucun job et aucune communication
externe. Il complète les garde-fous d’AUT-COR-01 à AUT-COR-06.

## Événements et confidentialité

Le journal technique accepte uniquement les cinq événements versionnés suivants :

| Événement | Déclencheur | Labels métriques bornés |
|---|---|---|
| `automation.surface_opened.v1` | ouverture de Aujourd’hui, Playbooks ou Exceptions | surface, résultat |
| `automation.playbook_preflighted.v1` | Prévol accepté ou rejoué | `preflight`, résultat |
| `automation.playbook_state_changed.v1` | activation, suspension ou reprise acceptée | commande, état, résultat |
| `automation.exception_resolved.v1` | commande d’exception acceptée | commande, état, résultat |
| `automation.first_value_reached.v1` | réservé à la première valeur métier validée | résultat |

Les champs de log sont une allow-list fermée (`operation`, `state`, `outcome`,
`replayed`, `reason_code`). Aucun texte de l’assistant, nom, adresse, UUID métier,
secret, note CRM ou preuve brute de permission n’est envoyé dans la télémétrie.
L’audit métier existant conserve les références nécessaires côté serveur, sous RLS.

L’export Prometheus expose `marketteo_automation_event_total` avec les seuls labels
`event`, `operation` et `outcome`. Il est accessible uniquement via le bearer interne
déjà configuré sur `/internal/metrics`; le navigateur ne doit jamais l’appeler.

## Flags et stratégie de sortie

| Variable | Valeur sûre | Rôle |
|---|---|---|
| `AUTOMATION_ENABLED` | `false` | arrêt global et garde serveur finale |
| `AUTOMATION_ROLLOUT_MODE` | `off` en staging/production | `off`, `pilot` ou `all` |
| `AUTOMATION_PILOT_ORGANIZATION_IDS` | vide | UUID séparés par virgules quand le mode est `pilot` |

Le serveur recalcule l’autorisation à chaque lecture de capacité, Prévol et commande
de cycle de vie. Une valeur forgée dans le navigateur est ignorée. Le mode `pilot`
ne change pas les droits et ne contourne ni l’organisation active, ni le Prévol,
ni `If-Match`, ni l’idempotence. Les exceptions restent consultables et résolubles
selon leurs capacités afin de permettre une remédiation sûre pendant un arrêt.

## Prévol et activation progressive

1. conserver `AUTOMATION_ENABLED=false` et `AUTOMATION_ROLLOUT_MODE=off` pendant les
   contrôles QA, Sécurité et Données ;
2. activer d’abord le mode `pilot`, avec une seule organisation synthétique ;
3. vérifier les métriques, journaux et audits avant chaque ajout d’organisation ;
4. ne jamais passer à `all` dans la Pré-Phase 5.1 sans décision Produit formelle.

## Procédure de rollback

1. positionner `AUTOMATION_ENABLED=false` (et conserver `AUTOMATION_ROLLOUT_MODE=off`) ;
2. suspendre les Playbooks actifs via les commandes versionnées avec le motif fermé
   `rollback`, si l’accès de remédiation est disponible ;
3. vérifier que `prepare_enabled=false`, que la génération de suspension a progressé
   et que les nouveaux Prévols/activations sont refusés ;
4. contrôler les métriques et l’audit avec le `request_id` de l’opération ;
5. ne supprimer ni Prévol, ni exception, ni audit : ils sont conservés pour analyse ;
6. consigner l’incident et ne réautoriser le pilote qu’après nouvelle revue.

Le rollback est conçu pour être idempotent : rejouer l’arrêt global ou la suspension
ne doit produire aucun effet CRM, pipeline, tâche, job ou communication externe.

## Preuves attendues

- capture de configuration effective sans secret ;
- sortie `/internal/metrics` filtrée sur `marketteo_automation_event_total` ;
- extrait de journaux structurés montrant un événement allow-listé et l’absence de PII ;
- audit des transitions avec corrélation, version et motif ;
- résultat des tests `AUT-COR-R18`, `AUT-COR-R19` et `AUT-COR-R20` ;
- preuve de retour à `off` et de conservation des données.

