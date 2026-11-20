import logging
import os
from datetime import date, timedelta

import pandas as pd
import requests
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# Defaults to SQLite so it runs instantly; switch to PostgreSQL via env var:
# export DB_URL="postgresql://user:password@localhost:5432/weather"
DB_URL = os.getenv("DB_URL", "sqlite:///weather.db")

CITIES = {
    "Bengaluru": (12.97, 77.59),
    "Hyderabad": (17.39, 78.49),
    "Mumbai": (19.08, 72.88),
    "Delhi": (28.61, 77.21),
}
API_URL = "https://archive-api.open-meteo.com/v1/archive"


def extract(city, lat, lon, start, end):
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    daily = resp.json()["daily"]
    df = pd.DataFrame(daily)
    df["city"] = city
    log.info("Extracted %d rows for %s", len(df), city)
    return df


def transform(df):
    df = df.rename(columns={
        "time": "obs_date",
        "temperature_2m_max": "temp_max_c",
        "temperature_2m_min": "temp_min_c",
        "precipitation_sum": "rain_mm",
    })
    df["obs_date"] = pd.to_datetime(df["obs_date"]).dt.date

    # Data profiling / quality checks
    before = len(df)
    df = df.drop_duplicates(subset=["city", "obs_date"])
    missing = df[["temp_max_c", "temp_min_c", "rain_mm"]].isna().sum()
    log.info("Duplicates removed: %d | Missing values:\n%s",
             before - len(df), missing.to_string())

    # Handle missing values: drop rows with no temperature, rain NaN -> 0
    df = df.dropna(subset=["temp_max_c", "temp_min_c"])
    df["rain_mm"] = df["rain_mm"].fillna(0)

    # Validation: remove physically impossible records
    invalid = (df["temp_max_c"] < df["temp_min_c"]) | (df["temp_max_c"] > 55)
    if invalid.any():
        log.warning("Dropping %d invalid rows", invalid.sum())
        df = df[~invalid]

    # Derived features
    df["temp_range_c"] = (df["temp_max_c"] - df["temp_min_c"]).round(1)
    df["is_rainy"] = df["rain_mm"] > 1
    return df


def load(df, engine):
    create_sql = """
    CREATE TABLE IF NOT EXISTS daily_weather (
        city VARCHAR(50),
        obs_date DATE,
        temp_max_c FLOAT,
        temp_min_c FLOAT,
        rain_mm FLOAT,
        temp_range_c FLOAT,
        is_rainy BOOLEAN,
        PRIMARY KEY (city, obs_date)
    )"""
    with engine.begin() as conn:  # one transaction: all or nothing
        conn.execute(text(create_sql))
        # Idempotent load: delete the date range being reloaded, then insert
        for city in df["city"].unique():
            sub = df[df["city"] == city]
            conn.execute(
                text("DELETE FROM daily_weather WHERE city = :c "
                     "AND obs_date BETWEEN :s AND :e"),
                {"c": city, "s": sub["obs_date"].min(), "e": sub["obs_date"].max()},
            )
        df.to_sql("daily_weather", conn, if_exists="append", index=False)
    log.info("Loaded %d rows", len(df))


def run(days_back=30):
    end = date.today() - timedelta(days=2)  # archive lags by a couple of days
    start = end - timedelta(days=days_back)
    engine = create_engine(DB_URL)
    frames = []
    for city, (lat, lon) in CITIES.items():
        try:
            raw = extract(city, lat, lon, start.isoformat(), end.isoformat())
            frames.append(transform(raw))
        except Exception as e:
            log.error("Failed for %s: %s", city, e)
    if frames:
        load(pd.concat(frames, ignore_index=True), engine)
    log.info("Pipeline finished")


if __name__ == "__main__":
    run()
