import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "disable"),
    )

    cur = conn.cursor()
    cur.execute("SELECT current_database(), current_user;")
    print("DB connected successfully:")
    print(cur.fetchone())

    cur.execute("SELECT COUNT(*) FROM hr_employee;")
    print("Total employees:")
    print(cur.fetchone()[0])

    cur.close()
    conn.close()

except Exception as e:
    print("DB connection failed:")
    print(e)