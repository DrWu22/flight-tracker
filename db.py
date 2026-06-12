import sqlite3
from datetime import datetime

DB_PATH = "flights.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create the prices table if it doesn't exist, adding new columns if upgrading."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_id           TEXT NOT NULL,
                combination_id      TEXT,
                fetched_at          TEXT NOT NULL,
                price               REAL,
                currency            TEXT,
                outbound_time       TEXT,
                outbound_airline    TEXT,
                return_time         TEXT,
                return_airline      TEXT,
                stops               INTEGER,
                total_duration      TEXT,
                error               TEXT
            )
        """)
        # Migrate existing DB: add new columns if they don't exist yet
        existing = [row[1] for row in conn.execute("PRAGMA table_info(prices)")]
        new_cols = {
            "combination_id":   "TEXT",
            "outbound_time":    "TEXT",
            "outbound_airline": "TEXT",
            "return_time":      "TEXT",
            "return_airline":   "TEXT",
            "total_duration":   "TEXT",
        }
        for col, coltype in new_cols.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE prices ADD COLUMN {col} {coltype}")
        conn.commit()


def insert_combination(flight_id, combination_id, price, currency,
                       outbound_time, outbound_airline,
                       return_time, return_airline,
                       stops, total_duration, error=None):
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prices (
                flight_id, combination_id, fetched_at, price, currency,
                outbound_time, outbound_airline,
                return_time, return_airline,
                stops, total_duration, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (flight_id, combination_id, fetched_at, price, currency,
             outbound_time, outbound_airline,
             return_time, return_airline,
             stops, total_duration, error),
        )
        conn.commit()


def get_combinations_for_flight(flight_id):
    """Return all distinct combination_ids seen for a flight."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT combination_id FROM prices WHERE flight_id = ? AND error IS NULL AND combination_id IS NOT NULL ORDER BY combination_id",
            (flight_id,)
        )
        return [row[0] for row in cursor.fetchall()]


def get_prices_for_combination(flight_id, combination_id):
    """Return price history rows for one specific combination."""
    with get_connection() as conn:
        cursor = conn.execute(
            """SELECT fetched_at, price, currency, outbound_time, outbound_airline,
                      return_time, return_airline, stops, total_duration
               FROM prices
               WHERE flight_id = ? AND combination_id = ? AND error IS NULL
               ORDER BY fetched_at ASC""",
            (flight_id, combination_id)
        )
        return cursor.fetchall()


def get_all_flight_ids():
    with get_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT flight_id FROM prices")
        return [row[0] for row in cursor.fetchall()]
