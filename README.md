# NYC Taxi ELT Pipeline

> An end-to-end ELT pipeline using **Apache Airflow** + **Snowflake** to process
> NYC Yellow Taxi trip data and surface business insights.

## Architecture

```
NYC TLC (Public CSV/Parquet)
        │ HTTP Download
        ▼
  Apache Airflow DAG
  (monthly schedule)
        │ COPY INTO
        ▼
  Snowflake — RAW_LAYER.RAW_TRIPS
        │ SQL Transform
        ▼
  Snowflake — ANALYTICS_LAYER views
        │
        ▼
  Business Insights (SQL queries)
```

## Tech Stack

| Tool | Role |
|------|------|
| Apache Airflow 2.x | Orchestration, scheduling, retry logic |
| Snowflake | Cloud data warehouse (compute + storage) |
| Python 3.10+ | DAG logic, HTTP download |
| SQL | ELT transforms, analytics |

## Key Concepts Demonstrated

- **ELT pattern**: Load raw data first, transform inside the warehouse
- **Data layering**: `RAW_LAYER` → `ANALYTICS_LAYER` separation
- **Snowflake Time Travel**: Query historical snapshots with `AT (OFFSET => ...)`
- **Auto-suspend Warehouse**: Cost optimization via `AUTO_SUSPEND = 60`
- **Airflow XCom**: Passing file paths between tasks

## Setup

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/nyc-taxi-elt-pipeline
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in your Snowflake credentials

# 3. Initialize Snowflake objects
python scripts/setup_snowflake.py

# 4. Start Airflow (local)
astro dev start   # requires Astronomer Astro CLI
```

## Sample Insights

- Peak trip hours: **6–9 AM** and **4–7 PM**
- Credit cards account for ~70% of all payments
- Average fare increases ~$1.80 per mile for trips over 10 miles
