import sqlite3

def init_db():
    conn = sqlite3.connect("weather_api.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        key TEXT PRIMARY KEY,
        requests_today INTEGER DEFAULT 0,
        date TEXT
    )
    """)
    c.execute("INSERT OR IGNORE INTO users (key, requests_today, date) VALUES ('test123', 0, '')")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
