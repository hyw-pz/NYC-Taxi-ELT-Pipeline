-- ──────────────────────────────────────────────────────────────────────────────
-- FILE: 01_create_tables.sql
-- PURPOSE: One-time initialization script. Run this manually in the Snowflake
--          UI before triggering the Airflow DAG for the first time.
-- ORDER: Warehouse → Database → Schema → Table → Stage
-- ──────────────────────────────────────────────────────────────────────────────


-- ── 1. Virtual Warehouse (compute layer) ─────────────────────────────────────
-- In Snowflake, compute and storage are fully separated.
-- The warehouse is pure CPU/memory — it holds no data.
-- X-SMALL is sufficient for a portfolio project.
-- AUTO_SUSPEND = 60 means the warehouse shuts down after 60 seconds of
-- inactivity and stops billing. AUTO_RESUME brings it back automatically
-- when a query arrives. This is the key cost-saving mechanism in Snowflake.
CREATE WAREHOUSE IF NOT EXISTS NYC_TAXI_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND   = 60
    AUTO_RESUME    = TRUE
    COMMENT        = 'Warehouse for NYC taxi pipeline';


-- ── 2. Database (top-level container) ────────────────────────────────────────
-- A Snowflake account can hold multiple databases, e.g. SALES_DB, FINANCE_DB.
-- Each database is completely independent.
CREATE DATABASE IF NOT EXISTS NYC_TAXI_DB;
USE DATABASE NYC_TAXI_DB;


-- ── 3. Schemas (sub-containers inside the database) ──────────────────────────
-- We use two schemas to implement a data layering pattern.
-- This is a fundamental concept in data engineering:
--
--   RAW_LAYER        Raw data loaded as-is, never modified after ingestion.
--                    Acts as the single source of truth. If a transform has
--                    a bug, the raw data is still intact and can be reprocessed.
--
--   ANALYTICS_LAYER  Cleaned, transformed, and aggregated data ready for
--                    analysis. This is what analysts and dashboards query.
--
CREATE SCHEMA IF NOT EXISTS RAW_LAYER;
CREATE SCHEMA IF NOT EXISTS ANALYTICS_LAYER;


-- ── 4. Raw trips table ────────────────────────────────────────────────────────
-- Column names match the NYC TLC parquet file schema exactly so that
-- COPY INTO can use MATCH_BY_COLUMN_NAME without manual mapping.
-- All source columns are kept here untouched.
-- _loaded_at is a metadata column added by the pipeline — not in the source.
CREATE OR REPLACE TABLE RAW_LAYER.RAW_TRIPS (
    VendorID                NUMBER,
    tpep_pickup_datetime    TIMESTAMP_NTZ,
    tpep_dropoff_datetime   TIMESTAMP_NTZ,
    passenger_count         NUMBER,
    trip_distance           FLOAT,
    RatecodeID              NUMBER,
    store_and_fwd_flag      VARCHAR(1),
    PULocationID            NUMBER,
    DOLocationID            NUMBER,
    payment_type            NUMBER,
    fare_amount             FLOAT,
    extra                   FLOAT,
    mta_tax                 FLOAT,
    tip_amount              FLOAT,
    tolls_amount            FLOAT,
    improvement_surcharge   FLOAT,
    total_amount            FLOAT,
    congestion_surcharge    FLOAT,
    airport_fee             FLOAT,

    -- Metadata: timestamp of when this row was loaded into Snowflake
    _loaded_at              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);


-- ── 5. Internal Stage (Snowflake's inbox) ─────────────────────────────────────
-- Snowflake cannot reach into your local machine to read files directly.
-- The Stage is a temporary holding area inside Snowflake's cloud storage.
-- Files are PUT here first, then COPY INTO reads from the Stage into the table.
-- The Stage is free to use — storage costs only apply to actual table data.
CREATE STAGE IF NOT EXISTS NYC_TAXI_STAGE
    FILE_FORMAT = (TYPE = 'PARQUET')
    COMMENT     = 'Staging area for NYC taxi parquet files';
