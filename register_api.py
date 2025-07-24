from fastapi import FastAPI
import secrets
import sqlite3
from datetime import date

app = FastAPI()

DB = "weather_api.db"

@app.post("/register")
def register():
    new_key = secrets.token_hex(16)
    today = str(date.today())

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO users (key, requests_today, date) VALUES (?, ?, ?)", (new_key, 0, today))
    conn.commit()
    conn.close()

    return {"api_key": new_key}