from fastapi import FastAPI, HTTPException, Form
import sqlite3

DB = "weather_api.db"

app = FastAPI()

@app.put("/upgrade")
def upgrade(api_key: str = Form(...), new_plan: str = Form(...)):
    if new_plan not in ("Free", "Pro"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT key FROM users WHERE key = ?", (api_key,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="API Key not found")

    c.execute("UPDATE users SET plan = ? WHERE key = ?", (new_plan, api_key))
    conn.commit()
    conn.close()

    return {"message": f"Plan updated to {new_plan}"}