from fastapi import FastAPI, Request, HTTPException, Depends, Form, Query 
from fastapi.responses import HTMLResponse
from auth import validate_api_key, get_plan_limits
from openmeteo import fetch_weather
import secrets
import sqlite3
from datetime import date
from database import get_user_by_key, get_plan_limit, reset_usage
import stripe
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi.staticfiles import StaticFiles
import os
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = "weather_api.db"

# Stripe setup
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_ENDPOINT_SECRET")

# Email sender
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

@app.get("/")
def root():
    return {"message": "Hello from Weather API!"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    try:
        with open("dashboard.html", "r", encoding="utf-8") as file:
            html_content = file.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard file not found")


def send_email(subject, body, to_email):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)

@app.on_event("startup")
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        key TEXT PRIMARY KEY,
        email TEXT,
        plan TEXT DEFAULT 'Free',
        requests_today INTEGER DEFAULT 0,
        date TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS plans (
        name TEXT PRIMARY KEY,
        max_requests_per_day INTEGER
    )
    """)
    c.execute("INSERT OR IGNORE INTO plans (name, max_requests_per_day) VALUES ('Free', 1000)")
    c.execute("INSERT OR IGNORE INTO plans (name, max_requests_per_day) VALUES ('Pro', 10000)")
    c.execute("INSERT OR IGNORE INTO users (key, email, plan, requests_today, date) VALUES ('test123', 'demo@example.com', 'Free', 0, '')")
    conn.commit()
    conn.close()

@app.get("/weather")
async def get_weather(lat: float, lon: float, api_key: str = Depends(validate_api_key)):
    data = await fetch_weather(lat, lon)
    return {"lat": lat, "lon": lon, "forecast": data}

# @app.post("/register")
# def register(email: str = Form(...), plan: str = Form("Free")):
#     new_key = secrets.token_hex(16)
#     today = str(date.today())
#     if plan not in ("Free", "Pro"):
#         raise HTTPException(status_code=400, detail="Invalid plan name.")
#     conn = sqlite3.connect(DB)
#     c = conn.cursor()
#     c.execute("INSERT INTO users (key, email, plan, requests_today, date) VALUES (?, ?, ?, ?, ?)",
#               (new_key, email, plan, 0, today))
#     conn.commit()
#     conn.close()
#     send_email("Welcome to Weather API", f"Your API Key: {new_key}", email)
#     return {"api_key": new_key, "email": email, "plan": plan}

@app.post("/register")
def register(email: str = Form(...), plan: str = Form("Free")):
    today = str(date.today())

    if plan not in ("Free", "Pro"):
        raise HTTPException(status_code=400, detail="Invalid plan name.")
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # 🔽 Sprawdź, czy użytkownik już istnieje
    c.execute("SELECT key FROM users WHERE email = ?", (email,))
    row = c.fetchone()

    if row:
        conn.close()
        return {"api_key": row[0], "email": email, "plan": plan}

    # 🔽 Jeśli nie istnieje, generuj nowy klucz
    new_key = secrets.token_hex(16)
    c.execute("INSERT INTO users (key, email, plan, requests_today, date) VALUES (?, ?, ?, ?, ?)",
              (new_key, email, plan, 0, today))
    conn.commit()
    conn.close()

    return {"api_key": new_key, "email": email, "plan": plan}


@app.put("/upgrade")
def upgrade(api_key: str = Form(...), new_plan: str = Form(...)):
    if new_plan not in ("Free", "Pro"):
        raise HTTPException(status_code=400, detail="Invalid plan")
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT key, email FROM users WHERE key = ?", (api_key,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="API Key not found")
    c.execute("UPDATE users SET plan = ? WHERE key = ?", (new_plan, api_key))
    conn.commit()
    conn.close()
    send_email("Your Weather API Plan was upgraded", f"Your plan is now: {new_plan}", row[1])
    return {"message": f"Plan updated to {new_plan}"}

@app.get("/upgrade-success")
def upgrade_after_payment(api_key: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET plan = 'Pro' WHERE key = ?", (api_key,))
    conn.commit()
    c.execute("SELECT email FROM users WHERE key = ?", (api_key,))
    row = c.fetchone()
    conn.close()
    if row:
        send_email("Thank you for upgrading", "Your plan has been upgraded to Pro.", row[0])
    return {"message": "Plan upgraded to Pro. Thank you!"}

@app.get("/status")
def get_status(api_key: str = Query(...)):
    user = get_user_by_key(api_key)
    if not user:
        raise HTTPException(status_code=404, detail="API Key not found")
    max_requests = get_plan_limit(user["plan"])
    return {
        "email": user["email"],
        "plan": user["plan"],
        "requests_today": user["requests_today"],
        "limit": max_requests
    }

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    data = await request.json()
    api_key = data.get("api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 990,
                    "product_data": {"name": "Pro Plan – Weather API"}
                },
                "quantity": 1
            }],
            mode="payment",
            success_url=f"http://127.0.0.1:8000/upgrade-success?api_key={api_key}",
            cancel_url="http://127.0.0.1:8000/dashboard",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        api_key = session.get("success_url", "").split("api_key=")[-1]
        if api_key:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("UPDATE users SET plan = 'Pro' WHERE key = ?", (api_key,))
            c.execute("SELECT email FROM users WHERE key = ?", (api_key,))
            row = c.fetchone()
            conn.commit()
            conn.close()
            if row:
                send_email("Payment Received", "Your Pro Plan is now active.", row[0])
    return {"status": "success"}

@app.post("/reset-api-key")
def reset_api_key(email: str = Form(...)):
    new_key = secrets.token_hex(16)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT key FROM users WHERE email = ?", (email,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    c.execute("UPDATE users SET key = ? WHERE email = ?", (new_key, email))
    conn.commit()
    conn.close()
    send_email("API Key Reset", f"Your new API Key is: {new_key}", email)
    return {"message": "API key reset successfully", "new_api_key": new_key}

@app.get("/admin/users")
def get_all_users():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT email, plan, requests_today, key FROM users")
    rows = c.fetchall()
    conn.close()
    return [
        {"email": r[0], "plan": r[1], "requests_today": r[2], "key": r[3]}
        for r in rows
    ]
@app.post("/admin/update-plan")
def admin_update_plan(email: str = Form(...), new_plan: str = Form(...)):
    if new_plan not in ("Free", "Pro"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE email = ?", (email,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    c.execute("UPDATE users SET plan = ? WHERE email = ?", (new_plan, email))
    conn.commit()
    conn.close()
    return {"message": f"Plan for {email} updated to {new_plan}"}

@app.post("/admin/delete-user")
def delete_user(email: str = Form(...)):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    c.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return {"message": f"User {email} deleted successfully."}


