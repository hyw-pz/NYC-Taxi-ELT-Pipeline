from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from datetime import datetime, timedelta
import requests
import os

# ── Default arguments applied to all tasks ────────────────────────────────────
default_args = {
    "owner": "your_name",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ── DAG definition ─────────────────────────────────────────────────────────────
with DAG(
    dag_id="nyc_taxi_elt_pipeline",
    default_args=default_args,
    description="Download NYC TLC taxi data → load to Snowflake → transform",
    schedule_interval="@monthly",       # Trigger automatically on the 1st of each month
    start_date=datetime(2024, 1, 1),
    catchup=False,                      # Do not backfill historical runs
    tags=["elt", "snowflake", "portfolio"],
) as dag:

    # ── Task 1: Download CSV from NYC TLC ─────────────────────────────────────
    def download_taxi_data(**context):
        """
        Download Yellow Taxi trip data from the NYC TLC public dataset.
        Source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
        Using January 2024 data as a demonstration.
        """
        url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
        local_path = "/tmp/nyc_taxi_data.parquet"

        print(f"Downloading from: {url}")
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Downloaded successfully → {local_path}")

        # Pass the file path to the next task via XCom
        return local_path

    task_download = PythonOperator(
        task_id="download_taxi_data",
        python_callable=download_taxi_data,
    )

    # ── Task 2: Upload the file to Snowflake Internal Stage ───────────────────
    # Think of the Stage as Snowflake's inbox — files must land here before
    # they can be loaded into a table.
    UPLOAD_TO_STAGE_SQL = """
    PUT file:///tmp/nyc_taxi_data.parquet @NYC_TAXI_STAGE
        AUTO_COMPRESS=TRUE
        OVERWRITE=TRUE;
    """

    task_upload_stage = SnowflakeOperator(
        task_id="upload_to_stage",
        snowflake_conn_id="snowflake_default",  # Configure this in Airflow Connections
        sql=UPLOAD_TO_STAGE_SQL,
    )

    # ── Task 3: COPY the staged file into the raw table ───────────────────────
    # COPY INTO parses the parquet file, validates columns against the table
    # schema, converts to Snowflake's internal micro-partition format,
    # and writes the data to permanent cloud storage (S3/Azure/GCS).
    COPY_INTO_RAW_SQL = """
    COPY INTO RAW_LAYER.RAW_TRIPS
    FROM @NYC_TAXI_STAGE/nyc_taxi_data.parquet.gz
    FILE_FORMAT = (TYPE = 'PARQUET')
    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
    ON_ERROR = 'CONTINUE';
    """

    task_load_raw = SnowflakeOperator(
        task_id="load_raw_data",
        snowflake_conn_id="snowflake_default",
        sql=COPY_INTO_RAW_SQL,
    )

    # ── Task 4: Transform — aggregate raw rows into a summary table ───────────
    # This is the T in ELT. The transformation happens inside Snowflake
    # rather than in Python, so we leverage the warehouse's compute power.
    TRANSFORM_SQL = """
    CREATE OR REPLACE TABLE ANALYTICS_LAYER.DAILY_SUMMARY AS
    SELECT
        DATE_TRUNC('day', tpep_pickup_datetime)                          AS trip_date,
        COUNT(*)                                                          AS total_trips,
        ROUND(AVG(trip_distance), 2)                                     AS avg_distance_miles,
        ROUND(AVG(fare_amount), 2)                                       AS avg_fare_usd,
        ROUND(SUM(total_amount), 2)                                      AS total_revenue_usd,
        ROUND(AVG(tip_amount / NULLIF(fare_amount, 0)) * 100, 1)        AS avg_tip_pct
    FROM RAW_LAYER.RAW_TRIPS
    WHERE tpep_pickup_datetime IS NOT NULL
      AND fare_amount > 0
    GROUP BY 1
    ORDER BY 1;
    """

    task_transform = SnowflakeOperator(
        task_id="transform_data",
        snowflake_conn_id="snowflake_default",
        sql=TRANSFORM_SQL,
    )

    # ── Task 5: Clean up the local temp file ──────────────────────────────────
    # The file in /tmp is no longer needed once it has been loaded into
    # Snowflake. Remove it to avoid disk accumulation across monthly runs.
    task_cleanup = BashOperator(
        task_id="cleanup_temp_files",
        bash_command="rm -f /tmp/nyc_taxi_data.parquet && echo 'Cleanup done'",
    )

    # ── Task dependencies: strict serial execution ────────────────────────────
    # Each task only starts if the previous one succeeded.
    # If load_raw fails, transform will not run on incomplete data.
    task_download >> task_upload_stage >> task_load_raw >> task_transform >> task_cleanup
