# Daily Weather ETL Pipeline

An automated ETL pipeline that extracts daily weather data for four Indian cities (Bengaluru, Hyderabad, Mumbai, Delhi) from the free Open-Meteo API, cleans and validates it with Pandas, and loads it into a SQL database. Re-running the pipeline is safe: loads are idempotent and transactional, so no duplicates are created.

## Architecture

`Open-Meteo API -> Pandas (clean / validate) -> SQL DB (SQLite or PostgreSQL) -> analytical queries`

## Tech stack
Python, Pandas, Requests, SQLAlchemy, SQL (SQLite / PostgreSQL), GitHub Actions

## Data quality checks
- Duplicate removal on (city, date)
- Missing-value profiling, logged on every run
- Rows without temperature dropped; missing rainfall filled with 0
- Validation: removes impossible records (max temp < min temp, or max temp > 55 C)
- Derived features: daily temperature range, rainy-day flag

## Reliability
- Per-city error handling: one failed API call does not stop the run
- Logging for every stage
- Single transaction for loading (all or nothing)
- Idempotent load: the reloaded date range is deleted before insert

## How to run
```bash
pip install -r requirements.txt
python pipeline.py            # creates weather.db (SQLite)
```
Run it twice and confirm the row count does not change.

To use PostgreSQL:
```bash
export DB_URL="postgresql://user:password@localhost:5432/weather"
python pipeline.py
```

Then run the queries in `queries.sql` (monthly aggregates, hottest day per city using a window function, rainy-day counts). For PostgreSQL, replace `strftime('%Y-%m', obs_date)` with `TO_CHAR(obs_date, 'YYYY-MM')`.

## Scheduling
`.github/workflows/daily.yml` runs the pipeline daily via GitHub Actions and can also be triggered manually. Note: the SQLite file is uploaded as a run artifact; for persistent storage, point `DB_URL` at a hosted PostgreSQL database.

## Future improvements
- Orchestrate with Apache Airflow
- Containerise with Docker
- Store raw data in cloud storage (S3 / Azure Blob) and load into a cloud warehouse
- Add unit tests for the transform step
- Add more cities and weather variables
