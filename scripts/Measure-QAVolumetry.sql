-- Phase 4.3: mesure agrégée, en lecture seule, sur une photographie cohérente de QA.
-- Aucune valeur métier, aucun nom d'organisation, aucune ligne CSV ne quitte PostgreSQL.
-- Les tailles sont des majorants indicatifs : tous les champs sont cités en CSV,
-- avec une marge d'un octet par champ pour la neutralisation des formules et
-- 256 octets par fichier pour BOM/en-têtes. Les droits de provenance et filtres
-- d'export ne sont pas appliqués : le résultat est une borne de capacité.
-- p50/p95/max sont calculés entre organisations actives, y compris celles à zéro.

\pset pager off
\pset format csv
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';

WITH datasets(dataset) AS (
    VALUES ('prospects'), ('contacts'), ('contact_channels'),
           ('activities'), ('tasks'), ('opportunities')
),
raw AS (
    SELECT p.organization_id, 'prospects'::text AS dataset,
           ARRAY[p.id::text, p.internal_alias, p.stage_code, p.owner_id::text,
                 p.priority::text, p.tags::text, p.created_at::text]::text[] AS default_cells,
           ARRAY[p.id::text, p.internal_alias, p.stage_code, p.owner_id::text,
                 p.priority::text, p.tags::text, p.industry_label, p.segment_code,
                 p.size_band, p.address_line_1, p.address_line_2, p.city,
                 p.region, p.postal_code, p.country_code, p.created_at::text,
                 p.updated_at::text]::text[] AS wide_cells
      FROM prospects AS p WHERE p.archived_at IS NULL
    UNION ALL
    SELECT c.organization_id, 'contacts',
           ARRAY[c.id::text, c.prospect_id::text, c.display_name,
                 c.created_at::text]::text[],
           ARRAY[c.id::text, c.prospect_id::text, c.display_name,
                 c.role_label, c.created_at::text]::text[]
      FROM contacts AS c WHERE c.archived_at IS NULL
    UNION ALL
    SELECT ch.organization_id, 'contact_channels',
           ARRAY[ch.id::text, ch.prospect_id::text, ch.contact_id::text,
                 ch.channel_type, ch.value, ch.purpose]::text[],
           ARRAY[ch.id::text, ch.prospect_id::text, ch.contact_id::text,
                 ch.channel_type, ch.value, ch.purpose, 'do_not_contact',
                 ch.obtained_at::text]::text[]
      FROM contact_channels AS ch WHERE ch.archived_at IS NULL
    UNION ALL
    SELECT a.organization_id, 'activities',
           ARRAY[a.id::text, a.prospect_id::text, a.activity_type,
                 a.direction, a.summary, a.occurred_at::text]::text[],
           ARRAY[a.id::text, a.prospect_id::text, a.contact_id::text,
                 a.activity_type, a.direction, a.summary, a.occurred_at::text,
                 a.actor_id::text]::text[]
      FROM prospect_activities AS a
    UNION ALL
    SELECT t.organization_id, 'tasks',
           ARRAY[t.id::text, t.prospect_id::text, t.assigned_membership_id::text,
                 t.title, t.priority, t.status, t.due_at::text]::text[],
           ARRAY[t.id::text, t.prospect_id::text, t.assigned_membership_id::text,
                 t.title, t.priority, t.status, t.due_at::text,
                 t.completed_at::text]::text[]
      FROM prospect_tasks AS t
    UNION ALL
    SELECT o.organization_id, 'opportunities',
           ARRAY[o.id::text, o.prospect_id::text, o.owner_membership_id::text,
                 o.name, o.amount::text, o.currency_code, o.probability::text,
                 o.stage_code, o.expected_close_on::text]::text[],
           ARRAY[o.id::text, o.prospect_id::text, o.owner_membership_id::text,
                 o.name, o.amount::text, o.currency_code, o.probability::text,
                 o.stage_code, o.expected_close_on::text, o.closed_at::text]::text[]
      FROM opportunities AS o
),
row_sizes AS (
    SELECT r.organization_id, r.dataset,
           (1 + 4 * cardinality(r.default_cells) +
            (SELECT coalesce(sum(octet_length(replace(coalesce(cell, ''), '"', '""'))), 0)
               FROM unnest(r.default_cells) AS cell))::bigint AS default_bytes,
           (1 + 4 * cardinality(r.wide_cells) +
            (SELECT coalesce(sum(octet_length(replace(coalesce(cell, ''), '"', '""'))), 0)
               FROM unnest(r.wide_cells) AS cell))::bigint AS wide_bytes
      FROM raw AS r
),
per_org AS (
    SELECT org.id AS organization_id, d.dataset,
           count(s.organization_id)::bigint AS record_count,
           (256 + coalesce(sum(s.default_bytes), 0))::bigint AS default_bytes,
           (256 + coalesce(sum(s.wide_bytes), 0))::bigint AS wide_bytes
      FROM organizations AS org
      CROSS JOIN datasets AS d
      LEFT JOIN row_sizes AS s
        ON s.organization_id = org.id AND s.dataset = d.dataset
     WHERE org.status = 'active'
     GROUP BY org.id, d.dataset
),
summary AS (
    SELECT dataset,
           count(*)::bigint AS organization_count,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY record_count) AS p50_rows,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY record_count) AS p95_rows,
           max(record_count) AS max_rows,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY wide_bytes) AS p50_wide_bytes,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY wide_bytes) AS p95_wide_bytes,
           max(wide_bytes) AS max_wide_bytes
      FROM per_org GROUP BY dataset
)
SELECT 'organization' AS scope, p.dataset, p.organization_id::text AS organization_id,
       p.record_count, round(p.default_bytes::numeric / 1048576, 3) AS default_mib,
       round(p.wide_bytes::numeric / 1048576, 3) AS wide_mib,
       NULL::bigint AS organization_count, NULL::numeric AS p50_rows,
       NULL::numeric AS p95_rows, NULL::bigint AS max_rows,
       NULL::numeric AS p50_wide_mib, NULL::numeric AS p95_wide_mib,
       NULL::numeric AS max_wide_mib
  FROM per_org AS p
UNION ALL
SELECT 'summary', s.dataset, NULL, NULL, NULL, NULL,
       s.organization_count, round(s.p50_rows::numeric, 1),
       round(s.p95_rows::numeric, 1), s.max_rows,
       round(s.p50_wide_bytes::numeric / 1048576, 3),
       round(s.p95_wide_bytes::numeric / 1048576, 3),
       round(s.max_wide_bytes::numeric / 1048576, 3)
  FROM summary AS s
 ORDER BY scope, dataset, organization_id;

COMMIT;
