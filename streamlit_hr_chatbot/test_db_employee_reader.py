import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "disable"),
    )


def show_employee_columns(cur):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'hr_employee'
        ORDER BY ordinal_position;
    """)
    columns = [row[0] for row in cur.fetchall()]
    print("\nhr_employee columns:")
    print(columns)
    return columns


def main():
    employee_code = os.getenv("CURRENT_EMPLOYEE_NUMBER", "BLMP63")

    conn = get_connection()
    cur = conn.cursor()

    print("PostgreSQL connected successfully.")

    columns = show_employee_columns(cur)

    if "employee_code" not in columns:
        print("\nERROR: employee_code column not found in hr_employee.")
        print("Check your actual employee code field name in Odoo.")
        return

    cur.execute("""
        SELECT id, name, employee_code, work_email, mobile_phone, department_id, job_id
        FROM hr_employee
        WHERE employee_code = %s
        LIMIT 1;
    """, (employee_code,))

    employee = cur.fetchone()

    if not employee:
        print(f"\nNo employee found for code: {employee_code}")
    else:
        print("\nEmployee found:")
        print("ID:", employee[0])
        print("Name:", employee[1])
        print("Code:", employee[2])
        print("Work Email:", employee[3])
        print("Mobile:", employee[4])
        print("Department ID:", employee[5])
        print("Job ID:", employee[6])

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()