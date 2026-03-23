-- ============================================================
-- Migration 007: Seed questions_bank for Learning Lab
-- Inserts 5 questions per topic (topics 1-5 => 25 total).
-- Idempotent via a dedupe unique index + ON CONFLICT DO NOTHING.
-- ============================================================

-- Dedupe index so rerunning this migration doesn't duplicate rows.
-- We consider a question uniquely identified by:
-- (topic_id, question_type, difficulty, question_text).
CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_bank_dedupe
  ON public.questions_bank (topic_id, question_type, difficulty, question_text);

-- ------------------------------------------------------------
-- Topic 1: SELECT Fundamentals (topic_number = 1)
-- Difficulty spread: 1,1,2,2,3
-- Mix: 2x write_query, 1x predict_output, 1x find_bug, 1x conceptual
-- ------------------------------------------------------------

-- Q1 (write_query, difficulty 1): filtering + LIMIT + alias
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  1,
  'write_query',
  'Write a SQL query to list customers who have placed at least 3 delivered orders in the last 30 days. Return: customer_name, recent_order_count. Sort by recent_order_count desc, then customer_name, and LIMIT 5.',
  $sd$
CREATE TABLE customers (
  id int PRIMARY KEY,
  customer_name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  customer_id int NOT NULL REFERENCES customers(id),
  order_date date NOT NULL,
  status text NOT NULL
);

INSERT INTO customers (id, customer_name) VALUES
  (1, 'Arianna'),
  (2, 'Marcus'),
  (3, 'Sofia'),
  (4, 'Noah');

INSERT INTO orders (id, customer_id, order_date, status) VALUES
  (101, 1, CURRENT_DATE - INTERVAL '10 days', 'delivered'),
  (102, 1, CURRENT_DATE - INTERVAL '20 days', 'delivered'),
  (103, 1, CURRENT_DATE - INTERVAL '25 days', 'delivered'),
  (104, 1, CURRENT_DATE - INTERVAL '40 days', 'delivered'),
  (201, 2, CURRENT_DATE - INTERVAL '5 days', 'delivered'),
  (202, 2, CURRENT_DATE - INTERVAL '15 days', 'delivered'),
  (203, 2, CURRENT_DATE - INTERVAL '50 days', 'delivered'),
  (301, 3, CURRENT_DATE - INTERVAL '2 days', 'delivered'),
  (302, 3, CURRENT_DATE - INTERVAL '8 days', 'shipped'),
  (401, 4, CURRENT_DATE - INTERVAL '3 days', 'delivered'),
  (402, 4, CURRENT_DATE - INTERVAL '12 days', 'delivered'),
  (403, 4, CURRENT_DATE - INTERVAL '18 days', 'delivered');
  $sd$,
  $ea$
SELECT
  c.customer_name AS customer_name,
  COUNT(*) AS recent_order_count
FROM customers c
JOIN orders o
  ON o.customer_id = c.id
WHERE o.status = 'delivered'
  AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY c.customer_name
HAVING COUNT(*) >= 3
ORDER BY recent_order_count DESC, c.customer_name
LIMIT 5;
  $ea$,
  $h$
Filter to `delivered` orders within the last 30 days, group by the customer, then use `HAVING` to keep only customers with at least 3 orders.
Remember to `LIMIT` after sorting.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 1
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q2 (write_query, difficulty 1): DISTINCT + alias
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  1,
  'write_query',
  'Write a SQL query to return a de-duplicated list of sales regions that have at least one completed order. Output a single column named sales_region. Order alphabetically and LIMIT 10.',
  $sd$
CREATE TABLE orders (
  id int PRIMARY KEY,
  region text NOT NULL,
  status text NOT NULL
);

INSERT INTO orders (id, region, status) VALUES
  (1, 'North America', 'completed'),
  (2, 'North America', 'completed'),
  (3, 'Europe', 'processing'),
  (4, 'Europe', 'completed'),
  (5, 'APAC', 'completed'),
  (6, 'APAC', 'cancelled'),
  (7, 'LATAM', 'completed');
  $sd$,
  $ea$
SELECT DISTINCT
  region AS sales_region
FROM orders
WHERE status = 'completed'
ORDER BY sales_region
LIMIT 10;
  $ea$,
  $h$
Use `DISTINCT` to remove duplicates, filter by `status = ''completed''`, then apply `ORDER BY` and `LIMIT`.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 1
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q3 (predict_output, difficulty 2): NULL handling with LEFT JOIN
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'predict_output',
  'Predict the output of the following query. Focus on how LEFT JOIN produces NULLs for missing bonus rows.',
  $sd$
CREATE TABLE employees (
  id int PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE bonuses (
  employee_id int NOT NULL REFERENCES employees(id),
  bonus_amount int NOT NULL
);

INSERT INTO employees (id, name) VALUES
  (1, 'Emily'),
  (2, 'Ethan'),
  (3, 'Carla');

INSERT INTO bonuses (employee_id, bonus_amount) VALUES
  (1, 1000),
  (3, 500);
  $sd$,
  $ea$
employee | bonus_amount
Carla     | 500
Emily     | 1000
Ethan     | NULL
  $ea$,
  $h$
Because it is a LEFT JOIN from `employees` to `bonuses`, every employee remains in the result.
Where there is no matching bonus row, `bonus_amount` will be NULL.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 1
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q4 (find_bug, difficulty 2): HAVING vs WHERE (aggregate in WHERE)
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'find_bug',
  'The query below attempts to find customers with at least 3 delivered orders, but it is incorrect. Identify the bug and write the corrected query.',
  $sd$
CREATE TABLE customers (
  id int PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  customer_id int NOT NULL REFERENCES customers(id),
  status text NOT NULL
);

INSERT INTO customers (id, name) VALUES
  (1, 'Arianna'),
  (2, 'Marcus');

INSERT INTO orders (id, customer_id, status) VALUES
  (101, 1, 'delivered'),
  (102, 1, 'delivered'),
  (103, 1, 'delivered'),
  (104, 2, 'delivered');
  $sd$,
  $ea$
-- BUGFIX: you cannot use COUNT(*) in the WHERE clause.
-- Move the aggregate filter to HAVING.
SELECT
  c.name AS customer_name,
  COUNT(o.id) AS delivered_orders
FROM customers c
JOIN orders o
  ON o.customer_id = c.id
WHERE o.status = 'delivered'
GROUP BY c.name
HAVING COUNT(o.id) >= 3
ORDER BY delivered_orders DESC;
  $ea$,
  $h$
This is a common aggregation mistake: filters on aggregated values belong in `HAVING`, not `WHERE`.
You still filter rows by status in `WHERE` before grouping.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 1
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q5 (conceptual, difficulty 3): WHERE vs HAVING + DISTINCT vs GROUP BY
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'conceptual',
  'Explain the difference between WHERE and HAVING in PostgreSQL. In your explanation, also clarify when you should use DISTINCT vs GROUP BY.',
  NULL,
  $ea$
In PostgreSQL, `WHERE` filters rows before grouping/aggregation happens. It can only reference columns (and scalar expressions) available on each individual row.

`HAVING` filters groups after aggregation is computed. It is the correct place to filter on aggregate results like `COUNT(*)`, `SUM(amount)`, or `AVG(value)`.

`DISTINCT` removes duplicate rows based on all selected columns (it does not compute aggregates). `GROUP BY` forms groups to compute aggregates (and then can remove duplicates via grouping keys), but it also allows summary calculations.
Use DISTINCT when you just need unique values; use GROUP BY when you need aggregation (or grouping by multiple keys).
  $ea$,
  $h$
Think about the query execution order: row filtering happens first, grouping happens next, then group filtering.
Use that order to decide where aggregate conditions belong.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 1
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- ------------------------------------------------------------
-- Topic 2: JOINs (topic_number = 2)
-- Difficulty spread: 1,2,2,3,3
-- Mix: 2x write_query, 1x predict_output, 1x find_bug, 1x conceptual
-- ------------------------------------------------------------

-- Q1 (write_query, difficulty 1): multi-condition LEFT JOIN
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  1,
  'write_query',
  'Write a SQL query to list delivered order items with customer name, product name, quantity, and the applicable discount percentage. Promotions apply only when BOTH the customer region and the product match; if there is no promotion, discount_pct should be 0.',
  $sd$
CREATE TABLE customers (
  id int PRIMARY KEY,
  customer_name text NOT NULL,
  region text NOT NULL
);

CREATE TABLE products (
  id int PRIMARY KEY,
  product_name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  customer_id int NOT NULL REFERENCES customers(id),
  status text NOT NULL
);

CREATE TABLE order_items (
  id int PRIMARY KEY,
  order_id int NOT NULL REFERENCES orders(id),
  product_id int NOT NULL REFERENCES products(id),
  quantity int NOT NULL
);

CREATE TABLE promotions (
  region text NOT NULL,
  product_id int NOT NULL REFERENCES products(id),
  discount_pct int NOT NULL
);

INSERT INTO customers (id, customer_name, region) VALUES
  (1, 'Acme Retail', 'NA'),
  (2, 'Globex Corp', 'EU');

INSERT INTO products (id, product_name) VALUES
  (1, 'Analytics Toolkit'),
  (2, 'Data Warehouse'),
  (3, 'BI Dashboard');

INSERT INTO orders (id, customer_id, status) VALUES
  (5001, 1, 'delivered'),
  (5002, 2, 'processing'),
  (5003, 1, 'delivered');

INSERT INTO order_items (id, order_id, product_id, quantity) VALUES
  (9001, 5001, 1, 2),
  (9002, 5001, 3, 5),
  (9003, 5003, 2, 1);

INSERT INTO promotions (region, product_id, discount_pct) VALUES
  ('NA', 1, 15),
  ('NA', 3, 10),
  ('EU', 2, 20);
  $sd$,
  $ea$
SELECT
  o.id AS order_id,
  c.customer_name,
  p.product_name,
  oi.quantity,
  COALESCE(pr.discount_pct, 0) AS discount_pct
FROM orders o
JOIN customers c
  ON c.id = o.customer_id
JOIN order_items oi
  ON oi.order_id = o.id
JOIN products p
  ON p.id = oi.product_id
LEFT JOIN promotions pr
  ON pr.region = c.region
 AND pr.product_id = p.id
WHERE o.status = 'delivered'
ORDER BY o.id, p.id;
  $ea$,
  $h$
Use LEFT JOIN to keep order items even when no promotion matches.
Place both join conditions (region AND product) in the ON clause so the match is exact.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 2
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q2 (write_query, difficulty 2): LEFT JOIN showing NULLs for missing matches
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'write_query',
  'Write a SQL query to show every customer and the id of their most recent delivered order (if any). Output columns: customer_name, delivered_order_id. If a customer has no delivered orders, delivered_order_id should be NULL.',
  $sd$
CREATE TABLE customers (
  id int PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  customer_id int NOT NULL REFERENCES customers(id),
  order_date date NOT NULL,
  status text NOT NULL
);

INSERT INTO customers (id, name) VALUES
  (1, 'Arianna'),
  (2, 'Marcus'),
  (3, 'Sofia');

INSERT INTO orders (id, customer_id, order_date, status) VALUES
  (101, 1, DATE '2026-03-01', 'delivered'),
  (102, 1, DATE '2026-03-10', 'delivered'),
  (103, 1, DATE '2026-03-15', 'processing'),
  (201, 2, DATE '2026-03-05', 'processing'),
  (202, 2, DATE '2026-03-20', 'delivered');
  $sd$,
  $ea$
WITH latest_delivered AS (
  SELECT
    o.customer_id,
    o.id AS delivered_order_id,
    ROW_NUMBER() OVER (
      PARTITION BY o.customer_id
      ORDER BY o.order_date DESC, o.id DESC
    ) AS rn
  FROM orders o
  WHERE o.status = 'delivered'
)
SELECT
  c.name AS customer_name,
  ld.delivered_order_id
FROM customers c
LEFT JOIN latest_delivered ld
  ON ld.customer_id = c.id
 AND ld.rn = 1
ORDER BY c.name;
  $ea$,
  $h$
Use a LEFT JOIN so customers without delivered orders still appear.
To find the most recent order, rank delivered orders per customer and keep only rank 1.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 2
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q3 (predict_output, difficulty 2): self-join manager lookup
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'predict_output',
  'Predict the output of this self-join query that looks up each employee''s manager.',
  $sd$
CREATE TABLE employees (
  id int PRIMARY KEY,
  name text NOT NULL,
  manager_id int NULL REFERENCES employees(id)
);

INSERT INTO employees (id, name, manager_id) VALUES
  (1, 'Ava', NULL),
  (2, 'Ben', 1),
  (3, 'Chen', 1),
  (4, 'Dana', 2);
  $sd$,
  $ea$
employee | manager
Ava      | NULL
Ben      | Ava
Chen     | Ava
Dana     | Ben
  $ea$,
  $h$
For employees whose `manager_id` is NULL, the LEFT JOIN will produce a NULL manager name.
Sort is alphabetical by employee.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 2
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q4 (find_bug, difficulty 3): missing multi-condition join predicate
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'find_bug',
  'The query below is intended to attach the correct promotion discount for each delivered order item. It is wrong. Identify the join bug and write the corrected query.',
  $sd$
CREATE TABLE customers (
  id int PRIMARY KEY,
  customer_name text NOT NULL,
  region text NOT NULL
);

CREATE TABLE products (
  id int PRIMARY KEY,
  product_name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  customer_id int NOT NULL REFERENCES customers(id),
  status text NOT NULL
);

CREATE TABLE order_items (
  id int PRIMARY KEY,
  order_id int NOT NULL REFERENCES orders(id),
  product_id int NOT NULL REFERENCES products(id),
  quantity int NOT NULL
);

CREATE TABLE promotions (
  region text NOT NULL,
  product_id int NOT NULL REFERENCES products(id),
  discount_pct int NOT NULL
);

INSERT INTO customers (id, customer_name, region) VALUES
  (1, 'Acme Retail', 'NA'),
  (2, 'Globex Corp', 'EU');

INSERT INTO products (id, product_name) VALUES
  (1, 'Analytics Toolkit'),
  (2, 'Data Warehouse'),
  (3, 'BI Dashboard');

INSERT INTO orders (id, customer_id, status) VALUES
  (5001, 1, 'delivered'),
  (5003, 1, 'delivered');

INSERT INTO order_items (id, order_id, product_id, quantity) VALUES
  (9001, 5001, 1, 2),
  (9002, 5001, 3, 5),
  (9003, 5003, 2, 1);

INSERT INTO promotions (region, product_id, discount_pct) VALUES
  ('NA', 1, 15),
  ('NA', 3, 10),
  ('EU', 2, 20);

-- BUGGY QUERY:
SELECT
  o.id AS order_id,
  p.product_name,
  pr.discount_pct
FROM orders o
JOIN customers c
  ON c.id = o.customer_id
JOIN order_items oi
  ON oi.order_id = o.id
JOIN products p
  ON p.id = oi.product_id
LEFT JOIN promotions pr
  ON pr.region = c.region
WHERE o.status = 'delivered'
  AND pr.discount_pct IS NOT NULL
ORDER BY order_id, p.product_name;
  $sd$,
  $ea$
-- FIX: promotions must match on BOTH region and product.
SELECT
  o.id AS order_id,
  p.product_name,
  pr.discount_pct
FROM orders o
JOIN customers c
  ON c.id = o.customer_id
JOIN order_items oi
  ON oi.order_id = o.id
JOIN products p
  ON p.id = oi.product_id
LEFT JOIN promotions pr
  ON pr.region = c.region
 AND pr.product_id = p.id
WHERE o.status = 'delivered'
  AND pr.discount_pct IS NOT NULL
ORDER BY order_id, p.product_name;
  $ea$,
  $h$
Your join needs to be specific enough to match the correct promotion.
If you only join on region, you may attach discounts meant for other products.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 2
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q5 (conceptual, difficulty 3): ON vs WHERE with LEFT JOIN
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'conceptual',
  'Explain how LEFT JOIN behaves differently from INNER JOIN. In your answer, include guidance on when to put conditions in the ON clause vs the WHERE clause.',
  NULL,
  $ea$
INNER JOIN returns only rows where the join condition matches in both tables.
LEFT JOIN returns all rows from the left table, and unmatched rows from the right table appear with NULL values in the right-table columns.

The placement of filters matters:
- Conditions in the ON clause affect which right-side rows are considered a match. This preserves unmatched left rows (so NULLs remain possible).
- Conditions in the WHERE clause are applied after the join. If a WHERE clause references right-table columns and requires a non-NULL value, it effectively filters out the NULL-extended rows, turning the LEFT JOIN behavior into something closer to an INNER JOIN.
  $ea$,
  $h$
Remember the conceptual flow: ON decides matches; WHERE then filters the final result set.
Think about what happens to the rows that had NULLs on the right.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 2
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- ------------------------------------------------------------
-- Topic 3: GROUP BY & Aggregation (topic_number = 3)
-- Difficulty spread: 1,2,2,3,3
-- Mix: 2x write_query, 1x predict_output, 1x find_bug, 1x conceptual
-- ------------------------------------------------------------

-- Q1 (write_query, difficulty 1): COUNT for high-value deals
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  1,
  'write_query',
  'Write a SQL query to list each sales rep and count how many closed-won deals they have with amount > 1000. Return rep_name and high_value_deals, sorted by high_value_deals desc, and LIMIT 5.',
  $sd$
CREATE TABLE sales_reps (
  id int PRIMARY KEY,
  rep_name text NOT NULL
);

CREATE TABLE deals (
  id int PRIMARY KEY,
  rep_id int NOT NULL REFERENCES sales_reps(id),
  amount numeric(10,2) NOT NULL,
  stage text NOT NULL
);

INSERT INTO sales_reps (id, rep_name) VALUES
  (1, 'Riley'),
  (2, 'Jordan'),
  (3, 'Taylor'),
  (4, 'Morgan');

INSERT INTO deals (id, rep_id, amount, stage) VALUES
  (1001, 1, 1200.00, 'closed_won'),
  (1002, 1, 800.00, 'closed_won'),
  (1003, 2, 2500.00, 'closed_won'),
  (1004, 2, 1500.00, 'closed_won'),
  (1005, 2, 300.00, 'closed_lost'),
  (1006, 3, 2000.00, 'closed_won'),
  (1007, 4, 900.00, 'closed_won');
  $sd$,
  $ea$
SELECT
  sr.rep_name,
  COUNT(*) AS high_value_deals
FROM sales_reps sr
JOIN deals d
  ON d.rep_id = sr.id
WHERE d.stage = 'closed_won'
  AND d.amount > 1000
GROUP BY sr.rep_name
ORDER BY high_value_deals DESC, sr.rep_name
LIMIT 5;
  $ea$,
  $h$
Filter deals first (stage + amount), then group by rep.
`COUNT(*)` counts matching deals per group.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 3
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q2 (write_query, difficulty 2): GROUP BY multiple columns + HAVING AVG
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'write_query',
  'For each (region, category) pair, compute total revenue and average deal amount for deals with stage = ''completed''. Only return groups where avg_deal_amount >= 800. Output: region, category, total_revenue, avg_deal_amount. Order by total_revenue desc.',
  $sd$
CREATE TABLE deals (
  id int PRIMARY KEY,
  region text NOT NULL,
  category text NOT NULL,
  amount numeric(10,2) NOT NULL,
  stage text NOT NULL
);

INSERT INTO deals (id, region, category, amount, stage) VALUES
  (1, 'NA', 'Analytics', 900, 'completed'),
  (2, 'NA', 'Analytics', 1200, 'completed'),
  (3, 'NA', 'Warehouse', 700, 'completed'),
  (4, 'EU', 'Analytics', 800, 'completed'),
  (5, 'EU', 'Analytics', 1600, 'completed'),
  (6, 'EU', 'Warehouse', 600, 'completed'),
  (7, 'EU', 'Warehouse', 900, 'completed');
  $sd$,
  $ea$
SELECT
  region,
  category,
  SUM(amount) AS total_revenue,
  AVG(amount) AS avg_deal_amount
FROM deals
WHERE stage = 'completed'
GROUP BY region, category
HAVING AVG(amount) >= 800
ORDER BY total_revenue DESC, region, category;
  $ea$,
  $h$
Aggregate first with `SUM` and `AVG`, group by both region and category, and use `HAVING` to filter based on the computed average.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 3
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q3 (predict_output, difficulty 2): HAVING COUNT >= 2
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'predict_output',
  'Predict the output of this GROUP BY + HAVING query.',
  $sd$
CREATE TABLE deals (
  id int PRIMARY KEY,
  region text NOT NULL,
  stage text NOT NULL
);

INSERT INTO deals (id, region, stage) VALUES
  (1, 'NA', 'completed'),
  (2, 'NA', 'completed'),
  (3, 'NA', 'processing'),
  (4, 'EU', 'completed'),
  (5, 'EU', 'completed'),
  (6, 'APAC', 'completed');

-- Query:
SELECT
  region,
  COUNT(*) AS deals_count
FROM deals
WHERE stage = 'completed'
GROUP BY region
HAVING COUNT(*) >= 2
ORDER BY deals_count DESC, region;
  $sd$,
  $ea$
region | deals_count
EU      | 2
NA      | 2
  $ea$,
  $h$
Only rows with `stage = ''completed''` participate.
Then group by region and keep only regions with at least 2 completed deals.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 3
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q4 (find_bug, difficulty 3): aggregate in WHERE
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'find_bug',
  'The query below tries to filter groups by COUNT(*) but uses the wrong clause. Identify the bug and provide the corrected SQL.',
  $sd$
CREATE TABLE deals (
  id int PRIMARY KEY,
  region text NOT NULL,
  stage text NOT NULL
);

INSERT INTO deals (id, region, stage) VALUES
  (1, 'NA', 'completed'),
  (2, 'NA', 'completed'),
  (3, 'EU', 'completed'),
  (4, 'EU', 'processing');

-- BUGGY QUERY:
SELECT
  region,
  COUNT(*) AS deals_count
FROM deals
WHERE stage = 'completed'
  AND COUNT(*) >= 2
GROUP BY region;
  $sd$,
  $ea$
SELECT
  region,
  COUNT(*) AS deals_count
FROM deals
WHERE stage = 'completed'
GROUP BY region
HAVING COUNT(*) >= 2;
  $ea$,
  $h$
Aggregates like `COUNT(*)` can''t be used in WHERE.
Use `HAVING` to filter after grouping.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 3
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q5 (conceptual, difficulty 3): WHERE vs HAVING + multiple GROUP BY keys
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'conceptual',
  'Conceptually explain when to use WHERE vs HAVING, and what happens when you group by multiple columns (for example, GROUP BY region, category).',
  NULL,
  $ea$
`WHERE` filters individual rows before any grouping happens. It''s appropriate for conditions that apply to columns on single rows (for example, `stage = ''completed''`).

`HAVING` filters groups after aggregates are computed. It''s appropriate for conditions based on aggregate values (for example, `COUNT(*) >= 2` or `AVG(amount) >= 800`).

When you `GROUP BY` multiple columns, PostgreSQL forms groups by the unique combinations of those columns. That means each distinct (region, category) pair becomes its own group, and aggregates are computed separately per pair.
  $ea$,
  $h$
Answer by referencing query execution order and the meaning of "group" in SQL.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 3
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- ------------------------------------------------------------
-- Topic 4: Subqueries & CTEs (topic_number = 4)
-- Difficulty spread: 2,2,3,3,3
-- Mix: 2x write_query, 1x predict_output, 1x find_bug, 1x conceptual
-- ------------------------------------------------------------

-- Q1 (write_query, difficulty 2): scalar subquery (company average)
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'write_query',
  'Write a SQL query to list employees whose salary is greater than the company-wide average salary. Output: name, salary. Sort by salary desc.',
  $sd$
CREATE TABLE employees (
  id int PRIMARY KEY,
  name text NOT NULL,
  department_id int NOT NULL,
  salary numeric(10,2) NOT NULL
);

INSERT INTO employees (id, name, department_id, salary) VALUES
  (1, 'Emily', 10, 90000),
  (2, 'Ethan', 10, 110000),
  (3, 'Carla', 20, 75000),
  (4, 'Ben',  20, 120000);
  $sd$,
  $ea$
SELECT
  name,
  salary
FROM employees
WHERE salary > (
  SELECT AVG(salary)
  FROM employees
)
ORDER BY salary DESC, name;
  $ea$,
  $h$
Use a scalar subquery that returns a single value (the average salary).
Then filter employees by comparing their salary to that value.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 4
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q2 (write_query, difficulty 2): EXISTS
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'write_query',
  'Write a SQL query to list department names that have at least one project with status = ''active''. Use EXISTS.',
  $sd$
CREATE TABLE departments (
  id int PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE projects (
  id int PRIMARY KEY,
  department_id int NOT NULL REFERENCES departments(id),
  project_name text NOT NULL,
  status text NOT NULL
);

INSERT INTO departments (id, name) VALUES
  (10, 'Data Platform'),
  (20, 'Analytics Lab'),
  (30, 'Automation');

INSERT INTO projects (id, department_id, project_name, status) VALUES
  (100, 10, 'Warehouse Refresh', 'active'),
  (101, 10, 'Legacy Cleanup', 'paused'),
  (200, 20, 'Attribution Model', 'paused'),
  (201, 20, 'Experimentation', 'active'),
  (300, 30, 'CI/CD Pipeline', 'paused');
  $sd$,
  $ea$
SELECT
  d.name AS department_name
FROM departments d
WHERE EXISTS (
  SELECT 1
  FROM projects p
  WHERE p.department_id = d.id
    AND p.status = 'active'
)
ORDER BY d.name;
  $ea$,
  $h$
In the subquery, correlate on `p.department_id = d.id` and filter to `p.status = ''active''`.
EXISTS checks whether at least one matching row exists.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 4
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q3 (predict_output, difficulty 3): WITH clause
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'predict_output',
  'Predict the output of this query that uses a CTE to compute per-department totals.',
  $sd$
CREATE TABLE departments (
  id int PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  department_id int NOT NULL REFERENCES departments(id),
  total_amount numeric(10,2) NOT NULL
);

INSERT INTO departments (id, name) VALUES
  (10, 'Data Platform'),
  (20, 'Analytics Lab'),
  (30, 'Automation');

INSERT INTO orders (id, department_id, total_amount) VALUES
  (1, 10, 2500.00),
  (2, 10, 1500.00),
  (3, 20,  800.00);

-- Query:
WITH dept_totals AS (
  SELECT
    department_id,
    SUM(total_amount) AS total_sales
  FROM orders
  GROUP BY department_id
)
SELECT
  d.name,
  dt.total_sales
FROM departments d
LEFT JOIN dept_totals dt
  ON dt.department_id = d.id
ORDER BY d.name;
  $sd$,
  $ea$
name             | total_sales
Analytics Lab    | 800
Automation       | NULL
Data Platform    | 4000
  $ea$,
  $h$
The CTE aggregates orders per department, then a LEFT JOIN keeps all departments.
Departments without orders will have NULL totals.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 4
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q4 (find_bug, difficulty 3): correlated subquery returns multiple rows
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'find_bug',
  'Find and fix the bug in this correlated subquery. The intention is to select employees who earn more than the average salary in their own department.',
  $sd$
CREATE TABLE employees (
  id int PRIMARY KEY,
  name text NOT NULL,
  department_id int NOT NULL,
  salary numeric(10,2) NOT NULL
);

INSERT INTO employees (id, name, department_id, salary) VALUES
  (1, 'Emily', 10, 90000),
  (2, 'Ethan', 10, 110000),
  (3, 'Carla', 20, 75000),
  (4, 'Ben',  20, 120000);

-- BUGGY QUERY:
SELECT
  e.name,
  e.salary
FROM employees e
WHERE e.salary > (
  SELECT salary
  FROM employees
  WHERE department_id = e.department_id
)
ORDER BY e.salary DESC;
  $sd$,
  $ea$
SELECT
  e.name,
  e.salary
FROM employees e
WHERE e.salary > (
  SELECT AVG(salary)
  FROM employees
  WHERE department_id = e.department_id
)
ORDER BY e.salary DESC;
  $ea$,
  $h$
The subquery must return exactly one value for a scalar comparison.
If there are multiple rows, wrap it in an aggregate like AVG/MIN/MAX.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 4
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q5 (conceptual, difficulty 3): correlated subquery + CTE usage
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'conceptual',
  'Explain what a correlated subquery is and why it differs from a non-correlated subquery. Also explain when you might prefer a WITH (CTE) over repeating a subquery.',
  NULL,
  $ea$
A correlated subquery references columns from the outer query. That means the inner query may need to be evaluated separately for each outer-row context. A non-correlated subquery is independent and can often be evaluated once.

You might prefer a WITH (CTE) when:
- You want to break a complex query into named steps for readability.
- You want to reuse the same sub-result in multiple places in the query (conceptually).
- You want to keep the main SELECT clause simpler.

Note: performance can vary depending on PostgreSQL planning. In modern Postgres versions, CTEs may be inlined in many cases, but the primary motivation early on is clarity and maintainability.
  $ea$,
  $h$
In your answer, explicitly mention that correlated subqueries depend on the outer query row.
Then describe CTE benefits in terms of readability and reuse.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 4
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- ------------------------------------------------------------
-- Topic 5: Window Functions (topic_number = 5)
-- Difficulty spread: 2,2,3,3,3
-- Mix: 2x write_query, 1x predict_output, 1x find_bug, 1x conceptual
-- ------------------------------------------------------------

-- Q1 (write_query, difficulty 2): ROW_NUMBER for most recent order per customer
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'write_query',
  'Write a SQL query to return each customer''s most recent order. Use ROW_NUMBER to pick the latest order per customer. Output: customer_name, order_id, order_date.',
  $sd$
CREATE TABLE customers (
  id int PRIMARY KEY,
  name text NOT NULL
);

CREATE TABLE orders (
  id int PRIMARY KEY,
  customer_id int NOT NULL REFERENCES customers(id),
  order_date date NOT NULL,
  total_amount numeric(10,2) NOT NULL
);

INSERT INTO customers (id, name) VALUES
  (1, 'Arianna'),
  (2, 'Marcus'),
  (3, 'Sofia');

INSERT INTO orders (id, customer_id, order_date, total_amount) VALUES
  (1001, 1, DATE '2026-02-01', 250.00),
  (1002, 1, DATE '2026-03-01', 900.00),
  (1003, 2, DATE '2026-03-05', 120.00),
  (1004, 2, DATE '2026-03-10', 300.00),
  (1005, 3, DATE '2026-01-20', 700.00);
  $sd$,
  $ea$
WITH ranked AS (
  SELECT
    o.id AS order_id,
    c.name AS customer_name,
    o.order_date,
    ROW_NUMBER() OVER (
      PARTITION BY o.customer_id
      ORDER BY o.order_date DESC, o.id DESC
    ) AS rn
  FROM orders o
  JOIN customers c
    ON c.id = o.customer_id
)
SELECT
  customer_name,
  order_id,
  order_date
FROM ranked
WHERE rn = 1
ORDER BY customer_name;
  $ea$,
  $h$
Partition by customer and order by order_date descending to rank newest orders first.
Then filter to rn = 1.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 5
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q2 (write_query, difficulty 2): running total with PARTITION BY
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  2,
  'write_query',
  'For each region and month, compute monthly revenue and a running total (cumulative) revenue over time. Use a window function with PARTITION BY region and ORDER BY month.',
  $sd$
CREATE TABLE region_orders (
  id int PRIMARY KEY,
  region text NOT NULL,
  order_date date NOT NULL,
  total_amount numeric(10,2) NOT NULL
);

INSERT INTO region_orders (id, region, order_date, total_amount) VALUES
  (1, 'NA', DATE '2026-01-15', 1000.00),
  (2, 'NA', DATE '2026-01-25', 500.00),
  (3, 'NA', DATE '2026-02-10', 800.00),
  (4, 'EU', DATE '2026-01-05', 700.00),
  (5, 'EU', DATE '2026-02-20', 900.00),
  (6, 'EU', DATE '2026-03-02', 400.00);
  $sd$,
  $ea$
SELECT
  region,
  date_trunc('month', order_date)::date AS month,
  SUM(total_amount) AS monthly_revenue,
  SUM(SUM(total_amount)) OVER (
    PARTITION BY region
    ORDER BY date_trunc('month', order_date)
  ) AS running_revenue
FROM region_orders
GROUP BY
  region,
  date_trunc('month', order_date)
ORDER BY region, month;
  $ea$,
  $h$
Aggregate to monthly revenue first (via GROUP BY), then compute the cumulative sum using a window over the ordered months.
Use PARTITION BY region so running totals do not mix regions.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 5
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q3 (predict_output, difficulty 3): RANK with ties
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'predict_output',
  'Predict the output. The query uses RANK() to rank product demand per region (ties share the same rank).',
  $sd$
CREATE TABLE product_sales (
  region text NOT NULL,
  product_name text NOT NULL,
  units_sold int NOT NULL
);

INSERT INTO product_sales (region, product_name, units_sold) VALUES
  ('NA', 'Analytics Toolkit', 120),
  ('NA', 'Data Warehouse', 120),
  ('NA', 'BI Dashboard', 80),
  ('EU', 'Analytics Toolkit', 60),
  ('EU', 'Data Warehouse', 90),
  ('EU', 'BI Dashboard', 90);

-- Query:
SELECT
  region,
  product_name,
  units_sold,
  RANK() OVER (
    PARTITION BY region
    ORDER BY units_sold DESC
  ) AS demand_rank
FROM product_sales
ORDER BY region, demand_rank, product_name;
  $sd$,
  $ea$
region | product_name       | units_sold | demand_rank
EU      | Data Warehouse      | 90          | 1
EU      | BI Dashboard        | 90          | 1
EU      | Analytics Toolkit   | 60          | 3
NA      | Analytics Toolkit   | 120         | 1
NA      | Data Warehouse      | 120         | 1
NA      | BI Dashboard        | 80          | 3
  $ea$,
  $h$
RANK() assigns the same rank to tied rows, and it skips the next rank number after a tie.
Because of PARTITION BY region, ranks are computed independently per region.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 5
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q4 (find_bug, difficulty 3): LAG without PARTITION BY
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'find_bug',
  'This LAG query is intended to show previous-month revenue within each region. It produces incorrect values because of a window framing mistake. Fix the query.',
  $sd$
CREATE TABLE monthly_revenue (
  region text NOT NULL,
  month date NOT NULL,
  total_revenue numeric(10,2) NOT NULL
);

INSERT INTO monthly_revenue (region, month, total_revenue) VALUES
  ('NA', DATE '2026-01-01', 1000.00),
  ('NA', DATE '2026-02-01', 1400.00),
  ('EU', DATE '2026-01-01',  800.00),
  ('EU', DATE '2026-02-01', 1200.00);

-- BUGGY QUERY:
SELECT
  region,
  month,
  total_revenue,
  LAG(total_revenue) OVER (ORDER BY month) AS prev_month_revenue
FROM monthly_revenue
ORDER BY region, month;
  $sd$,
  $ea$
SELECT
  region,
  month,
  total_revenue,
  LAG(total_revenue) OVER (
    PARTITION BY region
    ORDER BY month
  ) AS prev_month_revenue
FROM monthly_revenue
ORDER BY region, month;
  $ea$,
  $h$
LAG needs PARTITION BY region so it looks at the previous row within the same region''s timeline.
Without partitioning, rows from different regions affect the lag computation.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 5
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

-- Q5 (conceptual, difficulty 3): ROW_NUMBER vs RANK and PARTITION BY
INSERT INTO public.questions_bank (
  id,
  topic_id,
  difficulty,
  question_type,
  question_text,
  sample_data,
  expected_answer,
  hints
)
SELECT
  gen_random_uuid(),
  t.id,
  3,
  'conceptual',
  'Explain the differences between ROW_NUMBER(), RANK(), and DENSE_RANK(). Also explain what PARTITION BY does in window functions.',
  NULL,
  $ea$
`ROW_NUMBER()` assigns a unique sequential number to each row within a window partition. Even if values tie, every row still gets a different row number (based on the ORDER BY tie-breakers).

`RANK()` assigns the same rank to tied rows, and it skips rank numbers after a tie. That means if two rows tie for rank 1, the next rank is 3.

`DENSE_RANK()` also assigns the same rank to ties, but it does NOT skip rank numbers. After a tie for rank 1, the next rank is 2.

`PARTITION BY` defines independent groups (partitions) within the result set. Window functions are computed separately within each partition, rather than across the entire dataset.
  $ea$,
  $h$
Focus on how ties are handled and how the next rank behaves after a tie.
Then describe partitions as "independent mini-datasets" for window calculations.
  $h$
FROM public.curriculum_topics t
WHERE t.topic_number = 5
ON CONFLICT (topic_id, question_type, difficulty, question_text) DO NOTHING;

