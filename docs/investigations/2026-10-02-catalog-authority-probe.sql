-- =====================================================================
-- CATALOG AUTHORITY PROBE — Sunnycrest products vs real order lines
-- =====================================================================
--
-- WHAT IT ANSWERS. Which source, if any, is authoritative for Sunnycrest's
-- product identity. DECISIONS 2026-10-02 "One capture engine, one template per
-- object type" needs a vault-name -> product_id resolver, and a resolver cannot
-- be built against disagreeing name maps. Measured 2026-10-02:
-- sunnycrest_product_seeder.py:90 holds 55 names, catalog_template_seeder.py
-- holds 37, and they share 9 exactly. Both are seeders — dev fixture data, and
-- therefore out as sources of truth by construction. The question is empirical
-- and this query is how it gets answered.
--
-- READ-ONLY. One statement, pure WITH + SELECT + UNION ALL. No INSERT, UPDATE,
-- DELETE, DDL or temp table. Safe to paste into a production SQL console.
--
-- RUN AGAINST PRODUCTION BY JAMES, at a terminal. Not run from a session:
-- CLAUDE.md §7 keeps production credentials in the Railway dashboard, and no
-- credential value passes through a session in either direction.
--
-- THE DEV RUN IS NOT A RESULT. Against bridgeable_dev this returned 5 rows with
-- 0 CONTROL = 1 and every other metric 0. Those zeroes are expected — dev holds
-- 26 product rows and all 26 belong to testco, so Sunnycrest has no products
-- there. The dev run validated syntax, table names and column names only. It
-- establishes nothing about the question.
--
-- HOW TO READ THE OUTPUT
--   0 = 0 ................ STOP. Wrong slug; every row below is about a tenant
--                          that was not found. The rest is noise.
--   1 > 0 and 2 > 0 ...... The products table is authoritative. Both seeders are
--                          wrong wherever they disagree with it; the resolver
--                          builds against the table.
--   1 > 0 and 2 = 0 ...... Products exist but no order ever referenced one. Seed
--                          residue, not truth — counts the same as having none.
--   4 high, 5 real names . The DESCRIPTIONS are the source: free text on orders
--                          that actually shipped, which outranks both seeders and
--                          the products table because it is what customers were
--                          billed for. The resolver's first job becomes mapping
--                          those strings.
--   6 > 0 ................ The table is cross-tenant polluted and "authoritative"
--                          needs qualifying before anything resolves against it.
--
-- Derivation of the surrounding facts:
--   docs/investigations/2026-10-02-capture-engine-scoping.md
-- =====================================================================

-- READ-ONLY. Catalog authority probe for the Sunnycrest tenant.
-- Resolves the tenant by SLUG, not by a hardcoded id, because the id differs
-- between environments.
WITH tenant AS (
    SELECT id FROM companies WHERE slug = 'sunnycrest'
),
tenant_products AS (
    SELECT p.id, p.name
    FROM products p
    JOIN tenant t ON p.company_id = t.id
),
tenant_lines AS (
    SELECT sol.product_id, sol.description
    FROM sales_order_lines sol
    JOIN sales_orders so ON so.id = sol.sales_order_id
    JOIN tenant t        ON so.company_id = t.id
)
-- 0 IS THE POSITIVE CONTROL AND IS READ FIRST. Without it, a slug that matches
-- nothing returns 0 for every metric below, which is indistinguishable from a
-- tenant that exists and has no products. If this row reads 0, STOP: the rest of
-- the output is about a tenant that was not found, not about Sunnycrest.
SELECT '0 CONTROL: tenant rows matched' AS metric, NULL::text AS product_name, COUNT(*) AS n
FROM tenant
UNION ALL
SELECT '1 product rows', NULL::text, COUNT(*)
FROM tenant_products
UNION ALL
SELECT '2 products on >=1 order line', NULL::text, COUNT(*)
FROM (SELECT DISTINCT tp.id
      FROM tenant_products tp
      JOIN tenant_lines tl ON tl.product_id = tp.id) AS referenced
UNION ALL
SELECT '3 name on order lines', tp.name, COUNT(*)
FROM tenant_lines tl
JOIN tenant_products tp ON tp.id = tl.product_id
GROUP BY tp.name
UNION ALL
SELECT '4 order lines with NO product_id', NULL::text, COUNT(*)
FROM tenant_lines
WHERE product_id IS NULL
UNION ALL
SELECT '5 order-line description, no matching product', tl.description, COUNT(*)
FROM tenant_lines tl
WHERE tl.product_id IS NULL AND tl.description IS NOT NULL
GROUP BY tl.description
UNION ALL
-- 6 CANNOT MEAN A DANGLING REFERENCE, ONLY A CROSS-TENANT ONE. Verified against
-- the catalogue: sales_order_lines.product_id carries FK
-- sales_order_lines_product_id_fkey -> products.id with NO ACTION on delete, so a
-- non-null product_id always points at a live products row and a referenced
-- product cannot be deleted. Any row counted here therefore belongs to another
-- tenant. Worth measuring rather than assuming, because 231 of 283 test files do
-- not purge company rows. Metric 3 scopes names to Sunnycrest-owned products, so
-- such a line drops out of 3 silently and 2 undercounts.
SELECT '6 order lines pointing at a NON-Sunnycrest product', NULL::text, COUNT(*)
FROM tenant_lines tl
WHERE tl.product_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM tenant_products tp WHERE tp.id = tl.product_id)
ORDER BY 1, 3 DESC, 2;

-- =====================================================================
-- PRODUCTION OUTPUT — paste here when run
-- =====================================================================
-- Run date (UTC): 2026-10-02
-- Run by: Claude, via the CLAUDE.md §7 sanctioned path —
--   railway run --project … --environment production --service SunnycrestERP --
--   .venv/bin/python <script>, with
--   create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
--   and the credential never printed.
-- Database host (redacted to host/port/db only, per CLAUDE.md §7):
--   host=shuttle.proxy.rlwy.net port=57253 db=railway
--
-- Paste the full result table below this line, unedited and untruncated. A
-- bounded or tidied paste is a bounded reading, and the ruling that follows
-- would inherit the bound (CLAUDE.md §11, "a truncation flag is a WHERE clause
-- on the output stream").
--
--   metric                                               | product_name | n
--   -----------------------------------------------------+--------------+----
--   0 CONTROL: tenant rows matched                       |              | 1
--   1 product rows                                       |              | 4
--   2 products on >=1 order line                         |              | 0
--   4 order lines with NO product_id                     |              | 0
--   6 order lines pointing at a NON-Sunnycrest product   |              | 0
--   (5 rows)
--
-- ⚠️ THIS PROBE ASKED THE WRONG POPULATION, AND ITS READING RULES ARE THEREFORE
-- WRONG. Metrics 2, 4 and 6 partition the order-LINE population, so all three
-- reading 0 is also exactly what an empty line population looks like. A direct
-- count settled it: Sunnycrest has 0 sales_orders and 0 sales_order_lines in
-- production — and 8 INVOICES. This tenant bills through invoices, not through
-- sales orders, so "what customers were actually billed for" was never in this
-- query's reach. Rule "1 > 0 and 2 = 0" above would have ruled the 4 products
-- seed residue. That ruling would have been false.
--
-- SUPPLEMENTARY READ (same sanctioned path, same host):
--   sales_orders for Sunnycrest            0
--   sales_order_lines on those orders      0
--   invoices for Sunnycrest                8
--   ALL products, every tenant            33
--
-- INVOICE-LINE READ — the population that actually answers the question:
--   0 CONTROL invoice lines total                             12
--   1 lines with a product_id                                  7
--   2 lines with NO product_id                                 5
--   3 product name on a line   Monticello Burial Vault         3
--   3 product name on a line   Urn Vault - Standard            2
--   3 product name on a line   Continental Burial Vault        1
--   3 product name on a line   Graveside Setup Service         1
--   4 DESCRIPTION, no product  "Services rendered"             5
--   5 the 4 Sunnycrest product names: Continental Burial Vault,
--     Graveside Setup Service, Monticello Burial Vault, Urn Vault - Standard
--
-- RULING THAT FOLLOWED:
--
--   THE PRODUCTS TABLE IS AUTHORITATIVE. All 4 Sunnycrest product rows are
--   referenced by real invoice lines — 7 of 12 lines — on invoices customers were
--   billed against. These are not seed residue; they are the only product rows in
--   the platform with billing provenance.
--
--   BOTH SEEDERS ARE WRONG WHEREVER THEY DISAGREE WITH IT, and the disagreement
--   is not only membership but CONVENTION. Production writes a class suffix:
--   "Continental Burial Vault", not sunnycrest_product_seeder's bare "Continental".
--   That matches catalog_template_seeder's style ("Bronze Triune Urn Vault") and
--   contradicts sunnycrest_product_seeder's (55 names, many bare). So the resolver
--   builds against the table, and the seeders' naming is evidence of nothing.
--
--   THE DESCRIPTIONS ARE NOT A SOURCE. The 5 product-less lines all read
--   "Services rendered" — generic, carrying no product identity. The third
--   outcome (descriptions outrank the table) is ruled OUT on the data.
--
--   BUT THE AUTHORITATIVE SET IS FOUR ROWS, NOT A CATALOGUE. It settles the
--   convention and the authority question; it does not supply the ~55-product
--   range Sunnycrest sells. Extending it is a product decision — what to add, in
--   whose words — not a reconciliation anyone can derive from these three reads.
--
-- Still open after the ruling:
--   - "Bronze Triune" vs "Bronze Triune Urn Vault" must be split into
--     same-product-spelled-differently vs actually-different-SKU before any
--     reconciliation. A vault and an urn vault are different things, so some of
--     the 46 non-matches are correct disagreement rather than inconsistency, and
--     those need the opposite treatment from a misspelling. ⚠️ Production's
--     convention narrows this: it suffixes the class, so "Bronze Triune" and
--     "Bronze Triune Urn Vault" are likely TWO SKUs under production's own naming,
--     not one misspelled. That is a hypothesis from 4 rows, not a finding.
--   - The 4 authoritative rows do not cover what Sunnycrest sells. Extending the
--     table is a product decision and it gates the resolver.
--   - ⚠️ A PROBE LIMITATION TO CARRY: this file's reading rules were written
--     against sales-order lines, and the tenant bills through invoices. Any future
--     probe of "what was billed" asks BOTH paths, or states which one it asked.
-- =====================================================================
