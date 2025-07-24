import sqlite3

conn = sqlite3.connect("weather_api.db")
c = conn.cursor()
c.execute("SELECT * FROM users")
rows = c.fetchall()
conn.close()

for row in rows:
    print(row)
