import sqlite3
from datetime import date

DB = "weather_api.db"

def get_user_by_key(api_key: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = str(date.today())
    c.execute("SELECT key, email, plan, requests_today, date FROM users WHERE key = ?", (api_key,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    if row[4] != today:
        reset_usage(api_key)
        return {"key": row[0], "email": row[1], "plan": row[2], "requests_today": 0}
    return {"key": row[0], "email": row[1], "plan": row[2], "requests_today": row[3]}

def get_plan_limit(plan_name: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT max_requests_per_day FROM plans WHERE name = ?", (plan_name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 1000  # fallback

def increment_usage(api_key: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = str(date.today())
    c.execute("UPDATE users SET requests_today = requests_today + 1, date = ? WHERE key = ?", (today, api_key))
    conn.commit()
    conn.close()

def reset_usage(api_key: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = str(date.today())
    c.execute("UPDATE users SET requests_today = 0, date = ? WHERE key = ?", (today, api_key))
    conn.commit()
    conn.close()