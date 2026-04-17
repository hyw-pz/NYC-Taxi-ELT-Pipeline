-- ──────────────────────────────────────────────────────────────────────────────
-- FILE: 03_analysis_queries.sql
-- PURPOSE: Business analysis queries that demonstrate SQL proficiency.
--          Run these manually in the Snowflake UI to explore the data.
--          Each query is designed to showcase a different SQL technique.
-- ──────────────────────────────────────────────────────────────────────────────

USE DATABASE NYC_TAXI_DB;


-- ── Query 1: Top 10 highest-revenue days ─────────────────────────────────────
-- Technique: simple aggregation + ORDER BY
-- Reads from the pre-built view so the aggregation logic is not duplicated here.
SELECT
    trip_date,
    total_trips,
    total_revenue_usd,
    avg_fare_usd
FROM ANALYTICS_LAYER.V_DAILY_SUMMARY
ORDER BY total_revenue_usd DESC
LIMIT 10;


-- ── Query 2: Morning rush vs evening rush comparison ─────────────────────────
-- Technique: CTE (Common Table Expression) + CASE WHEN bucketing
--
-- CTEs break a complex query into readable named steps.
-- Here we first label each hour as a period, then aggregate by period.
-- This is cleaner than a nested subquery and easier to maintain.
WITH peak_hours AS (
    SELECT
        pickup_hour,
        trip_count,
        avg_fare,
        CASE
            WHEN pickup_hour BETWEEN 7  AND 9  THEN 'Morning Rush'
            WHEN pickup_hour BETWEEN 17 AND 19 THEN 'Evening Rush'
            ELSE 'Off-peak'
        END AS period
    FROM ANALYTICS_LAYER.V_HOURLY_PATTERNS
)
SELECT
    period,
    SUM(trip_count)         AS total_trips,
    ROUND(AVG(avg_fare), 2) AS avg_fare
FROM peak_hours
GROUP BY 1
ORDER BY 2 DESC;


-- ── Query 3: Snowflake Time Travel ────────────────────────────────────────────
-- Technique: Snowflake-specific feature — querying a historical snapshot
--
-- Snowflake automatically retains historical versions of every table.
-- AT (OFFSET => -86400) queries the table as it existed 86400 seconds
-- (24 hours) ago. This is useful for:
--   - Auditing: "what did the data look like before yesterday's load?"
--   - Recovery: restoring accidentally deleted or corrupted rows
--   - Debugging: comparing current state against a known-good snapshot
--
-- This is a strong talking point in interviews — it is unique to Snowflake
-- and demonstrates awareness of enterprise data quality practices.
SELECT COUNT(*) AS row_count_24h_ago
FROM RAW_LAYER.RAW_TRIPS
AT (OFFSET => -86400);


-- ── Query 4: Fare analysis by trip distance bucket ───────────────────────────
-- Technique: CASE WHEN bucketing + derived metric (fare per mile)
--
-- Rather than analyzing raw trip_distance as a continuous number, we group
-- trips into meaningful distance ranges. This is a standard technique in
-- data analysis called binning or bucketing.
-- NULLIF(trip_distance, 0) prevents division-by-zero errors.
SELECT
    CASE
        WHEN trip_distance < 1  THEN '0-1 mile'
        WHEN trip_distance < 3  THEN '1-3 miles'
        WHEN trip_distance < 10 THEN '3-10 miles'
        ELSE                         '10+ miles'
    END                                                              AS distance_bucket,
    COUNT(*)                                                         AS trip_count,
    ROUND(AVG(fare_amount), 2)                                      AS avg_fare,
    ROUND(AVG(tip_amount), 2)                                       AS avg_tip,
    ROUND(AVG(fare_amount / NULLIF(trip_distance, 0)), 2)          AS fare_per_mile
FROM RAW_LAYER.RAW_TRIPS
WHERE trip_distance > 0
  AND fare_amount   > 0
GROUP BY 1
ORDER BY MIN(trip_distance);
