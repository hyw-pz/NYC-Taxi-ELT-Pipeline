-- ──────────────────────────────────────────────────────────────────────────────
-- FILE: 02_create_views.sql
-- PURPOSE: Create analytical views on top of the raw table.
--
-- A VIEW stores no data — it is a saved SQL query. Every time you SELECT
-- from a view, Snowflake re-executes the underlying query against the latest
-- raw data. This means views always reflect the most current state of RAW_TRIPS.
--
-- Benefits over querying the raw table directly:
--   1. Reusability  — write the aggregation logic once, reuse everywhere
--   2. Abstraction  — analysts query clean views without touching raw millions
--   3. Safety       — views are read-only; analysts cannot accidentally mutate raw data
-- ──────────────────────────────────────────────────────────────────────────────

USE DATABASE NYC_TAXI_DB;


-- ── View 1: Daily summary ─────────────────────────────────────────────────────
-- Answers: How did revenue and trip volume look each day?
-- This view is also rebuilt as a TABLE by the Airflow transform task.
-- The view version here is useful for ad-hoc queries that need the latest data
-- without waiting for the next scheduled DAG run.
CREATE OR REPLACE VIEW ANALYTICS_LAYER.V_DAILY_SUMMARY AS
SELECT
    DATE_TRUNC('day', tpep_pickup_datetime)                         AS trip_date,
    COUNT(*)                                                         AS total_trips,
    ROUND(AVG(trip_distance), 2)                                    AS avg_distance_miles,
    ROUND(AVG(fare_amount), 2)                                      AS avg_fare_usd,
    ROUND(SUM(total_amount), 2)                                     AS total_revenue_usd,
    ROUND(AVG(tip_amount / NULLIF(fare_amount, 0)) * 100, 1)       AS avg_tip_pct
FROM RAW_LAYER.RAW_TRIPS
WHERE tpep_pickup_datetime IS NOT NULL
  AND fare_amount > 0
GROUP BY 1;


-- ── View 2: Hourly pickup patterns ───────────────────────────────────────────
-- Answers: What time of day do people take the most trips?
-- Useful for identifying morning and evening rush hour peaks.
CREATE OR REPLACE VIEW ANALYTICS_LAYER.V_HOURLY_PATTERNS AS
SELECT
    HOUR(tpep_pickup_datetime)   AS pickup_hour,
    COUNT(*)                      AS trip_count,
    ROUND(AVG(fare_amount), 2)   AS avg_fare,
    ROUND(AVG(trip_distance), 2) AS avg_distance
FROM RAW_LAYER.RAW_TRIPS
WHERE fare_amount > 0
GROUP BY 1
ORDER BY 1;


-- ── View 3: Payment method breakdown ─────────────────────────────────────────
-- Answers: How do passengers prefer to pay? What is the average tip per method?
--
-- payment_type reference:
--   1 = Credit card
--   2 = Cash
--   3 = No charge
--   4 = Dispute
--   5 = Unknown
--
-- SUM(COUNT(*)) OVER () is a window function that computes the grand total
-- across all rows, allowing us to calculate each method's share as a percentage.
CREATE OR REPLACE VIEW ANALYTICS_LAYER.V_PAYMENT_BREAKDOWN AS
SELECT
    CASE payment_type
        WHEN 1 THEN 'Credit Card'
        WHEN 2 THEN 'Cash'
        WHEN 3 THEN 'No Charge'
        WHEN 4 THEN 'Dispute'
        ELSE        'Unknown'
    END                                                                     AS payment_method,
    COUNT(*)                                                                AS trip_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)                    AS pct_of_total,
    ROUND(AVG(tip_amount), 2)                                              AS avg_tip
FROM RAW_LAYER.RAW_TRIPS
GROUP BY 1
ORDER BY 2 DESC;
