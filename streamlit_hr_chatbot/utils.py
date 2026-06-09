import os
import re
from copy import deepcopy
from datetime import datetime, date

from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:
    psycopg2 = None
    RealDictCursor = None

load_dotenv()

DATA_SOURCE = os.environ.get("DATA_SOURCE", "postgres").strip().lower()

DB_HOST = os.environ.get("DB_HOST", "")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "")
DB_USER = os.environ.get("DB_USER", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_SSLMODE = os.environ.get("DB_SSLMODE", "disable")


# ============================================================
# General helpers
# ============================================================

def prepare_employee_data(employee_data: dict) -> dict:
    return deepcopy(employee_data)


def _clean_value(value):
    if value is None:
        return ""

    try:
        if str(value).lower() == "nan":
            return ""
    except Exception:
        pass

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    return str(value).strip()


def not_available(value):
    value = _clean_value(value)

    if value == "" or value.lower() in [
        "none",
        "nan",
        "n/a",
        "na",
        "not available",
        "not available in record.",
    ]:
        return "N/A"

    return value


def _format_date(value):
    if not value:
        return "N/A"

    try:
        return value.strftime("%Y-%m-%d")
    except Exception:
        return not_available(value)


def _format_datetime(value):
    if not value:
        return "N/A"

    try:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return not_available(value)


def _format_money(value):
    if value is None or value == "":
        return "N/A"

    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(round(number, 2))
    except Exception:
        return not_available(value)


def _to_number(value):
    value = _clean_value(value)

    if not value or value.upper() == "N/A":
        return 0.0

    try:
        return float(value.replace(",", ""))
    except Exception:
        return 0.0


def _short_task_text(value, limit=180):
    value = str(not_available(value)).strip()

    if value == "N/A":
        return "N/A"

    if len(value) <= limit:
        return value

    return value[:limit].rstrip() + "..."


MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


MONTH_NUMBER_TO_NAME = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def _month_number_to_name(month_number):
    try:
        return MONTH_NUMBER_TO_NAME.get(int(month_number), "Requested month")
    except Exception:
        return "Requested month"


def _format_month_year(month_number, year):
    if month_number and year:
        return f"{_month_number_to_name(month_number)} {year}"

    return "Requested month"


def _parse_requested_month_year(question):
    question = str(question or "").lower().strip()

    match = re.search(r"\b(0?[1-9]|1[0-2])\s*[/\-]\s*(\d{2}|\d{4})\b", question)
    if match:
        month = int(match.group(1))
        year = int(match.group(2))

        if year < 100:
            year = 2000 + year

        return month, year

    for month_name, month_number in MONTH_NAME_MAP.items():
        if re.search(rf"\b{re.escape(month_name)}\b", question):
            year_match = re.search(r"\b(20\d{2}|\d{2})\b", question)
            if year_match:
                year = int(year_match.group(1))

                if year < 100:
                    year = 2000 + year

                return month_number, year

    fy_match = re.search(r"fy\s*(\d{2})\s*/\s*(\d{2})", question)
    if fy_match:
        fy_start = 2000 + int(fy_match.group(1))
        fy_end = 2000 + int(fy_match.group(2))

        for month_name, month_number in MONTH_NAME_MAP.items():
            if month_name in question:
                if month_number >= 7:
                    return month_number, fy_start
                return month_number, fy_end

    return None, None


def _month_label_from_question(question):
    month, year = _parse_requested_month_year(question)

    if month and year:
        return _format_month_year(month, year)

    return None


def _month_bounds_from_question(question):
    month, year = _parse_requested_month_year(question)

    if not month or not year:
        return None, None, None

    start_date = date(year, month, 1)

    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    label = _format_month_year(month, year)
    return start_date, end_date, label


def _attendance_not_available_message(requested_month, requested_year, latest_available_month=None):
    requested_label = _format_month_year(requested_month, requested_year)

    if latest_available_month and latest_available_month != "N/A":
        return (
            f"{requested_label} attendance data is not available. "
            f"Latest available month is {latest_available_month}."
        )

    return f"{requested_label} attendance data is not available."


def _payroll_not_available_message(requested_month=None, requested_year=None, latest_available_month=None):
    requested_label = _format_month_year(requested_month, requested_year)

    if latest_available_month:
        return (
            f"{requested_label} payroll data is not available. "
            f"Latest available month is {latest_available_month}."
        )

    return f"{requested_label} payroll data is not available."


# ============================================================
# PostgreSQL helpers
# ============================================================

def _db_ready():
    return bool(
        psycopg2
        and RealDictCursor
        and DB_HOST
        and DB_PORT
        and DB_NAME
        and DB_USER
        and DB_PASSWORD
    )


def _connect():
    if not _db_ready():
        raise RuntimeError("PostgreSQL configuration is missing or psycopg2-binary is not installed.")

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode=DB_SSLMODE,
    )


def _fetchone(query, params=None):
    conn = _connect()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchone()
    finally:
        conn.close()


def _fetchall(query, params=None):
    conn = _connect()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    finally:
        conn.close()


# ============================================================
# Default objects
# ============================================================

def _get_default_attendance(message=None):
    return {
        "unavailable_message": message or "",
        "attendance_status": message or "N/A",
        "attendance_date": "N/A",
        "check_in": "N/A",
        "check_out": "N/A",
        "working_hours": "N/A",
        "late_minutes": "N/A",
        "overtime": "N/A",
        "monthly_summary": {
            "unavailable_message": message or "",
            "fiscal_year": "N/A",
            "month": "N/A",
            "employee_name": "N/A",
            "present_days": "N/A",
            "remote_days": "N/A",
            "holiday_days": "N/A",
            "sick_leave_days": "N/A",
            "casual_leave_days": "N/A",
            "unpaid_leave_days": "N/A",
            "late_submitted_days": "N/A",
            "absent_days": "N/A",
            "leave_days": "N/A",
            "overtime_count": "N/A",
            "total_counted_days": "N/A",
        },
    }


def _get_default_payroll(message=None):
    return {
        "basic_salary": "N/A",
        "basic_actual": "N/A",
        "gross_salary": "N/A",
        "net_salary": "N/A",
        "advertised_salary": "N/A",
        "project_salary": "N/A",
        "allowance_detail": "N/A",
        "allowance": "N/A",
        "medical_allowance": "N/A",
        "bonus": "N/A",
        "deduction": "N/A",
        "other_deductions": "N/A",
        "tax": "N/A",
        "income_tax": "N/A",
        "taxable_income": "N/A",
        "yearly_income": "N/A",
        "total": "N/A",
        "total_round": "N/A",
        "total_salary": "N/A",
        "rounded": "N/A",
        "payment_date": "N/A",
        "payment_method": "N/A",
        "pay_period": "N/A",
        "payslip_status": message or "N/A",
        "fiscal_year": "N/A",
        "month": "N/A",
        "employee_number": "N/A",
        "employee_name": "N/A",
        "bank": "N/A",
        "designation": "N/A",
        "comments": "N/A",
        "total_days": "N/A",
        "message": message or "N/A",
        "overtime": "N/A",
        "payment": "N/A",
        "remaining": "N/A",
        "project_detail": "N/A",
        "bonus_detail": "N/A",
        "overtime_detail": "N/A",
        "deduction_detail": "N/A",
    }


# ============================================================
# Employee readers
# ============================================================

def _get_employee_record_by_code(employee_code):
    employee_code = str(employee_code or "").strip()

    if not employee_code:
        return None

    return _fetchone(
        """
        SELECT
            id,
            name,
            employee_code,
            employment_status,
            father_name,
            joining_date,
            contract_start_date,
            contract_end_date,
            work_email,
            mobile_phone,
            private_phone,
            residence_number,
            personal_email,
            cnic_number,
            ntn_number,
            date_of_birth_custom,
            street_address,
            bank_account_title,
            bank_name_custom,
            bank_account_number,
            emergency_contact_name,
            emergency_contact_number,
            emergency_contact_relation
        FROM hr_employee
        WHERE active = true
          AND employee_code = %s
        LIMIT 1;
        """,
        (employee_code,),
    )


def _get_employee_record_by_name_or_code(value):
    value = str(value or "").strip()

    if not value:
        return None

    row = _get_employee_record_by_code(value)
    if row:
        return row

    return _fetchone(
        """
        SELECT
            id,
            name,
            employee_code,
            employment_status,
            father_name,
            joining_date,
            contract_start_date,
            contract_end_date,
            work_email,
            mobile_phone,
            private_phone,
            residence_number,
            personal_email,
            cnic_number,
            ntn_number,
            date_of_birth_custom,
            street_address,
            bank_account_title,
            bank_name_custom,
            bank_account_number,
            emergency_contact_name,
            emergency_contact_number,
            emergency_contact_relation
        FROM hr_employee
        WHERE active = true
          AND LOWER(TRIM(name)) = LOWER(TRIM(%s))
        LIMIT 1;
        """,
        (value,),
    )


def _get_latest_designation(employee_code):
    row = _fetchone(
        """
        SELECT designation
        FROM hr_payroll_register_line
        WHERE employee_code = %s
        ORDER BY month_date DESC, id DESC
        LIMIT 1;
        """,
        (employee_code,),
    )

    if not row:
        return "N/A"

    return not_available(row.get("designation"))


def get_employee_numbers():
    try:
        rows = _fetchall(
            """
            SELECT employee_code
            FROM hr_employee
            WHERE active = true
              AND employee_code IS NOT NULL
              AND TRIM(employee_code) != ''
            ORDER BY employee_code;
            """
        )

        return [row["employee_code"] for row in rows if row.get("employee_code")]
    except Exception:
        return []


def get_employee_by_number(employee_number: str):
    try:
        row = _get_employee_record_by_code(employee_number)

        if not row:
            return None

        return _employee_row_to_data(row)
    except Exception:
        return None


def _employee_row_to_data(row):
    employee_code = row.get("employee_code")
    employee_name = row.get("name")
    designation = _get_latest_designation(employee_code)

    payroll = get_payroll_by_employee_number(
        employee_number=employee_code,
        employee_name=employee_name,
    )

    attendance = get_attendance_by_employee_name(employee_code)

    return {
        "main": {
            "status": not_available(row.get("employment_status")),
            "employee_number": not_available(employee_code),
            "employee_name": not_available(employee_name),
        },
        "employee_record": {
            "father_name": not_available(row.get("father_name")),
            "designation": not_available(designation),
            "doj": _format_date(row.get("joining_date")),
            "contract_start": _format_date(row.get("contract_start_date")),
            "contract_end": _format_date(row.get("contract_end_date")),
            "employment_type": "N/A",
        },
        "bank_account": {
            "account_title": not_available(row.get("bank_account_title")),
            "bank_name": not_available(row.get("bank_name_custom")),
            "bank_branch": "N/A",
            "account_number": not_available(row.get("bank_account_number")),
        },
        "personal_details": {
            "mobile": not_available(row.get("mobile_phone") or row.get("private_phone")),
            "residence_number": not_available(row.get("residence_number")),
            "personal_email": not_available(row.get("personal_email")),
            "office_email": not_available(row.get("work_email")),
            "cnic": not_available(row.get("cnic_number")),
            "address": not_available(row.get("street_address")),
            "ntn_number": not_available(row.get("ntn_number")),
            "dob": _format_date(row.get("date_of_birth_custom")),
        },
        "emergency_contact": {
            "name": not_available(row.get("emergency_contact_name")),
            "number": not_available(row.get("emergency_contact_number")),
            "relation": not_available(row.get("emergency_contact_relation")),
        },
        "employment_history": [],
        "payroll": payroll,
        "attendance": attendance,
        "task_reports": [],
        "performance_records": [],
        "tax_calculator": {},
    }


def _get_employee_name_by_number(employee_number):
    employee = get_employee_by_number(employee_number)

    if not employee:
        return "N/A"

    return employee.get("main", {}).get("employee_name", "N/A")


# ============================================================
# Payroll reader
# ============================================================

def get_payroll_by_employee_number(employee_number, employee_name=None, question=None):
    employee_number = str(employee_number or "").strip()

    if not employee_number:
        return _get_default_payroll("Payroll data is not available.")

    month_label = _month_label_from_question(question)

    try:
        if month_label:
            row = _fetchone(
                """
                SELECT *
                FROM hr_payroll_register_line
                WHERE employee_code = %s
                  AND LOWER(TRIM(month_label)) = LOWER(TRIM(%s))
                ORDER BY month_date DESC, id DESC
                LIMIT 1;
                """,
                (employee_number, month_label),
            )
        else:
            row = _fetchone(
                """
                SELECT *
                FROM hr_payroll_register_line
                WHERE employee_code = %s
                ORDER BY month_date DESC, id DESC
                LIMIT 1;
                """,
                (employee_number,),
            )

        if not row:
            latest = _fetchone(
                """
                SELECT month_label
                FROM hr_payroll_register_line
                WHERE employee_code = %s
                ORDER BY month_date DESC, id DESC
                LIMIT 1;
                """,
                (employee_number,),
            )

            latest_month = latest.get("month_label") if latest else None
            requested_month, requested_year = _parse_requested_month_year(question)

            if requested_month and requested_year:
                message = _payroll_not_available_message(
                    requested_month=requested_month,
                    requested_year=requested_year,
                    latest_available_month=latest_month,
                )
            else:
                message = f"Payroll data is not available for {not_available(employee_name or employee_number)}."

            payroll = _get_default_payroll(message)
            payroll["employee_number"] = not_available(employee_number)
            payroll["employee_name"] = not_available(employee_name)

            if month_label:
                payroll["month"] = month_label
                payroll["pay_period"] = month_label

            return payroll

        net_salary = row.get("total_salary")
        if net_salary is None:
            net_salary = row.get("total_round")
        if net_salary is None:
            net_salary = row.get("total")

        gross_salary = row.get("total")
        if gross_salary is None:
            gross_salary = row.get("total_round")
        if gross_salary is None:
            gross_salary = row.get("total_salary")

        rounded = row.get("total_round")
        if rounded is None:
            rounded = row.get("total_salary")

        income_tax = row.get("income_tax_deduction")
        other_deductions = row.get("other_deductions")
        payslip_status = "Paid" if row.get("payment_date") or net_salary is not None else "N/A"

        return {
            "basic_salary": _format_money(row.get("basic_salary")),
            "basic_actual": _format_money(row.get("basic_actual")),
            "gross_salary": _format_money(gross_salary),
            "net_salary": _format_money(net_salary),
            "advertised_salary": _format_money(row.get("advertised_salary")),
            "project_salary": _format_money(row.get("project_salary")),
            "allowance_detail": not_available(row.get("allowance_detail")),
            "allowance": _format_money(row.get("allowance")),
            "medical_allowance": _format_money(row.get("medical_allowance")),
            "bonus": _format_money(row.get("bonus")),
            "deduction": _format_money(other_deductions),
            "other_deductions": _format_money(other_deductions),
            "tax": _format_money(income_tax),
            "income_tax": _format_money(income_tax),
            "taxable_income": _format_money(row.get("taxable_income")),
            "yearly_income": _format_money(row.get("yearly_income")),
            "total": _format_money(row.get("total")),
            "total_round": _format_money(row.get("total_round")),
            "total_salary": _format_money(row.get("total_salary")),
            "rounded": _format_money(rounded),
            "payment_date": _format_date(row.get("payment_date")),
            "payment_method": not_available(row.get("payment_method")),
            "pay_period": not_available(row.get("period_label") or row.get("month_label")),
            "payslip_status": payslip_status,
            "fiscal_year": not_available(row.get("fiscal_year_label")),
            "month": not_available(row.get("month_label")),
            "employee_number": not_available(row.get("employee_code")),
            "employee_name": not_available(row.get("employee_name_text") or employee_name),
            "bank": "N/A",
            "designation": not_available(row.get("designation")),
            "comments": not_available(row.get("comments")),
            "total_days": "N/A",
            "message": "N/A",
            "overtime": _format_money(row.get("overtime")),
            "payment": _format_money(row.get("payment")),
            "remaining": _format_money(row.get("remaining")),
            "project_detail": not_available(row.get("project_detail")),
            "bonus_detail": not_available(row.get("bonus_detail")),
            "overtime_detail": not_available(row.get("overtime_detail")),
            "deduction_detail": not_available(row.get("deduction_detail")),
        }

    except Exception as e:
        return _get_default_payroll(f"Payroll database error: {e}")


# ============================================================
# Attendance reader
# ============================================================

def _attendance_code_label(code):
    labels = {
        "P": "Present",
        "R": "Remote / WFH",
        "H": "Holiday",
        "S": "Sick Leave",
        "C": "Casual Leave",
        "U": "Unpaid Leave",
        "D": "Data Late Submitted",
        "OT": "Overtime",
    }

    return labels.get(str(code or "").strip().upper(), "N/A")


def _attendance_summary_from_rows(rows, employee_name="N/A", month_label="N/A", fiscal_year="N/A"):
    counts = {
        "P": 0,
        "R": 0,
        "H": 0,
        "S": 0,
        "C": 0,
        "U": 0,
        "D": 0,
        "OT": 0,
    }

    latest_status_code = "N/A"

    for row in rows:
        code = str(row.get("attendance_code") or "").strip().upper()

        if not code:
            continue

        if code in counts:
            counts[code] += 1

        if code != "OT":
            latest_status_code = code

    present_days = counts["P"]
    remote_days = counts["R"]
    holiday_days = counts["H"]
    sick_leave_days = counts["S"]
    casual_leave_days = counts["C"]
    unpaid_leave_days = counts["U"]
    late_submitted_days = counts["D"]
    overtime_count = counts["OT"]
    leave_days = sick_leave_days + casual_leave_days + unpaid_leave_days
    absent_days = unpaid_leave_days

    total_counted_days = (
        present_days
        + remote_days
        + holiday_days
        + sick_leave_days
        + casual_leave_days
        + unpaid_leave_days
        + late_submitted_days
    )

    return {
        "attendance_status": _attendance_code_label(latest_status_code),
        "attendance_date": not_available(month_label),
        "check_in": "N/A",
        "check_out": "N/A",
        "working_hours": "N/A",
        "late_minutes": str(late_submitted_days),
        "overtime": str(overtime_count),
        "monthly_summary": {
            "fiscal_year": not_available(fiscal_year),
            "month": not_available(month_label),
            "employee_name": not_available(employee_name),
            "present_days": str(present_days),
            "remote_days": str(remote_days),
            "holiday_days": str(holiday_days),
            "sick_leave_days": str(sick_leave_days),
            "casual_leave_days": str(casual_leave_days),
            "unpaid_leave_days": str(unpaid_leave_days),
            "late_submitted_days": str(late_submitted_days),
            "absent_days": str(absent_days),
            "leave_days": str(leave_days),
            "overtime_count": str(overtime_count),
            "total_counted_days": str(total_counted_days),
        },
    }


def _get_attendance_rows(employee_code, question=None):
    month_label = _month_label_from_question(question)

    if month_label:
        return month_label, _fetchall(
            """
            SELECT *
            FROM hr_attendance_register_line
            WHERE employee_code = %s
              AND LOWER(TRIM(month_label)) = LOWER(TRIM(%s))
            ORDER BY attendance_date ASC, id ASC;
            """,
            (employee_code, month_label),
        )

    latest = _fetchone(
        """
        SELECT month_label
        FROM hr_attendance_register_line
        WHERE employee_code = %s
        ORDER BY attendance_date DESC, id DESC
        LIMIT 1;
        """,
        (employee_code,),
    )

    month_label = latest.get("month_label") if latest else None

    if not month_label:
        return None, []

    rows = _fetchall(
        """
        SELECT *
        FROM hr_attendance_register_line
        WHERE employee_code = %s
          AND LOWER(TRIM(month_label)) = LOWER(TRIM(%s))
        ORDER BY attendance_date ASC, id ASC;
        """,
        (employee_code, month_label),
    )

    return month_label, rows


def get_attendance_by_employee_name(employee_name, question=None):
    try:
        employee = _get_employee_record_by_name_or_code(employee_name)

        if not employee:
            return _get_default_attendance()

        employee_code = employee.get("employee_code")
        month_label, rows = _get_attendance_rows(employee_code, question=question)

        if not rows:
            requested_month, requested_year = _parse_requested_month_year(question)
            latest = _fetchone(
                """
                SELECT month_label
                FROM hr_attendance_register_line
                WHERE employee_code = %s
                ORDER BY attendance_date DESC, id DESC
                LIMIT 1;
                """,
                (employee_code,),
            )

            latest_month = latest.get("month_label") if latest else None

            if requested_month and requested_year:
                message = _attendance_not_available_message(
                    requested_month,
                    requested_year,
                    latest_month,
                )
            else:
                message = f"Attendance data is not available for {not_available(employee.get('name') or employee_code)}."

            return _get_default_attendance(message)

        fiscal_year = rows[0].get("fiscal_year_label") or "N/A"
        month = rows[0].get("month_label") or month_label or "N/A"

        return _attendance_summary_from_rows(
            rows=rows,
            employee_name=employee.get("name"),
            month_label=month,
            fiscal_year=fiscal_year,
        )

    except Exception as e:
        return _get_default_attendance(f"Attendance database error: {e}")


def get_daily_attendance_codes_by_employee_name(employee_name, question=None):
    try:
        employee = _get_employee_record_by_name_or_code(employee_name)

        if not employee:
            return {
                "message": f"Attendance data is not available for {not_available(employee_name)}.",
                "days": [],
            }

        employee_code = employee.get("employee_code")
        month_label, rows = _get_attendance_rows(employee_code, question=question)

        if not rows:
            requested_month, requested_year = _parse_requested_month_year(question)
            latest = _fetchone(
                """
                SELECT month_label
                FROM hr_attendance_register_line
                WHERE employee_code = %s
                ORDER BY attendance_date DESC, id DESC
                LIMIT 1;
                """,
                (employee_code,),
            )
            latest_month = latest.get("month_label") if latest else None

            if requested_month and requested_year:
                message = _attendance_not_available_message(
                    requested_month,
                    requested_year,
                    latest_month,
                )
            else:
                message = f"Attendance data is not available for {not_available(employee.get('name') or employee_code)}."

            return {
                "message": message,
                "days": [],
            }

        days = []

        for row in rows:
            attendance_date = row.get("attendance_date")
            code = str(row.get("attendance_code") or "").strip().upper()

            if not attendance_date or not code:
                continue

            days.append(
                {
                    "date": attendance_date,
                    "date_text": _format_date(attendance_date),
                    "code": code,
                    "label": _attendance_code_label(code),
                    "raw_value": code,
                }
            )

        return {
            "message": "",
            "employee_name": not_available(employee.get("name")),
            "fiscal_year": not_available(rows[0].get("fiscal_year_label")),
            "month": not_available(rows[0].get("month_label")),
            "days": days,
        }

    except Exception as e:
        return {
            "message": f"Attendance database error: {e}",
            "days": [],
        }


# ============================================================
# Task report reader and responses
# ============================================================

def _task_report_status_label(state):
    labels = {
        "submitted": "Submitted",
        "late_submitted": "Late Submitted",
        "not_submitted": "Not Submitted",
        "missing": "Missing",
    }

    return labels.get(state, "Submitted")


def _normalize_task_report_state(state, task_report):
    state_text = str(state or "").strip().lower()
    task_text = str(task_report or "").strip()

    if not task_text:
        return "missing"

    if state_text in ["submitted", "approved", "done", "completed"]:
        return "submitted"

    if state_text in ["draft", "rejected", "not_submitted", "not submitted"]:
        return "not_submitted"

    if "late" in state_text:
        return "late_submitted"

    return "submitted"


def get_task_reports_by_employee(employee_number, question=None):
    try:
        employee = _get_employee_record_by_code(employee_number)

        if not employee:
            return []

        start_date, end_date, _month_label = _month_bounds_from_question(question)

        if start_date and end_date:
            rows = _fetchall(
                """
                SELECT *
                FROM hr_daily_work_report
                WHERE employee_id = %s
                  AND report_date >= %s
                  AND report_date < %s
                ORDER BY report_date DESC, id DESC;
                """,
                (employee["id"], start_date, end_date),
            )
        else:
            rows = _fetchall(
                """
                SELECT *
                FROM hr_daily_work_report
                WHERE employee_id = %s
                ORDER BY report_date DESC, id DESC
                LIMIT 50;
                """,
                (employee["id"],),
            )

        reports = []

        for row in rows:
            state = _normalize_task_report_state(row.get("state"), row.get("task_report"))

            reports.append(
                {
                    "source": "Odoo Daily Work Report",
                    "employee_name": not_available(employee.get("name")),
                    "report_date": row.get("report_date"),
                    "submitted_at": _format_datetime(row.get("submitted_at")),
                    "work_mode": not_available(row.get("work_mode")),
                    "state": state,
                    "status": _task_report_status_label(state),
                    "task_report": not_available(row.get("task_report")),
                    "remarks": not_available(row.get("remarks")),
                }
            )

        return reports

    except Exception:
        return []


def _format_report_date(report_date):
    return _format_date(report_date)


def build_task_report_response(employee_number: str, report_date: str = None, question: str = None, is_admin: bool = False):
    reports = get_task_reports_by_employee(employee_number, question=question)
    employee_name = _get_employee_name_by_number(employee_number)
    requested_month, requested_year = _parse_requested_month_year(question)

    if requested_month and requested_year:
        month_label = _format_month_year(requested_month, requested_year)
    else:
        month_label = "latest available period"

    if not reports:
        return f"""
## Task Report Status

No task reports found for **{not_available(employee_name)}** for **{month_label}**.

Possible reasons:
- Task report was not submitted.
- Employee has no task report records for this period.
- Report exists in another source not connected yet.
"""

    submitted_count = len([r for r in reports if r.get("state") in ["submitted", "late_submitted"]])
    not_submitted_count = len([r for r in reports if r.get("state") in ["not_submitted", "missing"]])

    lines = [
        "## Task Report Status",
        "",
        f"- **Employee:** {not_available(employee_name)}",
        f"- **Period:** {month_label}",
        f"- **Total Reports Found:** {len(reports)}",
        f"- **Submitted / Late Submitted:** {submitted_count}",
        f"- **Not Submitted / Missing:** {not_submitted_count}",
        "",
        "### Reports",
    ]

    for report in reports[:15]:
        lines.append(
            f"""
- **Date:** {_format_report_date(report.get('report_date'))}
  - **Status:** {not_available(report.get('status'))}
  - **Work Mode:** {not_available(report.get('work_mode'))}
  - **Submitted At:** {not_available(report.get('submitted_at'))}
  - **Source:** {not_available(report.get('source'))}
  - **Task Report:** {_short_task_text(report.get('task_report'))}
  - **Remarks:** {not_available(report.get('remarks'))}
"""
        )

    if len(reports) > 15:
        lines.append(f"\nShowing latest 15 reports only. Total matching reports: {len(reports)}")

    return "\n".join(lines)


def build_latest_task_report_response(employee_number: str, question: str = None, is_admin: bool = False):
    reports = get_task_reports_by_employee(employee_number, question=question)
    employee_name = _get_employee_name_by_number(employee_number)

    if not reports:
        return f"""
## Latest Task Report

No task report found for **{not_available(employee_name)}**.
"""

    latest = reports[0]

    heading = "Latest Task Report for Selected Employee" if is_admin else "Your Latest Task Report"

    return f"""
## {heading}

- **Employee:** {not_available(employee_name)}
- **Report Date:** {_format_report_date(latest.get('report_date'))}
- **Submitted At:** {not_available(latest.get('submitted_at'))}
- **Work Mode:** {not_available(latest.get('work_mode'))}
- **Status:** {not_available(latest.get('status'))}
- **Source:** {not_available(latest.get('source'))}

### Task Report
{not_available(latest.get('task_report'))}

### Remarks
{not_available(latest.get('remarks'))}
"""


def build_task_report_attendance_comparison_response(employee_number: str, question: str = None, is_admin: bool = False):
    employee = _get_employee_record_by_code(employee_number)
    employee_name = employee.get("name") if employee else _get_employee_name_by_number(employee_number)

    attendance_data = get_daily_attendance_codes_by_employee_name(
        employee_name=employee_number,
        question=question,
    )

    attendance_message = attendance_data.get("message")

    if attendance_message:
        return attendance_message

    task_reports = get_task_reports_by_employee(
        employee_number=employee_number,
        question=question,
    )

    submitted_report_dates = set()
    late_report_dates = set()

    for report in task_reports:
        report_date = report.get("report_date")
        state = report.get("state")

        if not report_date:
            continue

        if state == "submitted":
            submitted_report_dates.add(report_date)

        if state == "late_submitted":
            submitted_report_dates.add(report_date)
            late_report_dates.add(report_date)

    required_codes = ["P", "R"]
    not_required_codes = ["H", "S", "C", "U"]

    submitted_rows = []
    missing_rows = []
    not_required_rows = []
    pending_rows = []

    for day in attendance_data.get("days", []):
        attendance_date = day.get("date")
        code = day.get("code")
        label = day.get("label")
        date_text = day.get("date_text")

        if code in required_codes:
            if attendance_date in submitted_report_dates:
                status = "Late Submitted" if attendance_date in late_report_dates else "Submitted"
                submitted_rows.append(
                    {
                        "date": date_text,
                        "attendance": label,
                        "status": status,
                    }
                )
            else:
                missing_rows.append(
                    {
                        "date": date_text,
                        "attendance": label,
                        "status": "Missing",
                    }
                )

        elif code in not_required_codes:
            not_required_rows.append(
                {
                    "date": date_text,
                    "attendance": label,
                    "status": "Not Required",
                }
            )

        elif code == "D":
            pending_rows.append(
                {
                    "date": date_text,
                    "attendance": label,
                    "status": "Pending business rule",
                }
            )

    subject = "Selected employee" if is_admin else "You"

    lines = [
        "## Attendance vs Task Report Comparison",
        "",
        f"- **Employee:** {not_available(employee_name)}",
        f"- **Month:** {not_available(attendance_data.get('month'))}",
        f"- **Fiscal Year:** {not_available(attendance_data.get('fiscal_year'))}",
        "",
        "### Summary",
        f"- **Task Report Required Days (P/R):** {len(submitted_rows) + len(missing_rows)}",
        f"- **Submitted:** {len(submitted_rows)}",
        f"- **Missing:** {len(missing_rows)}",
        f"- **Not Required (H/S/C/U):** {len(not_required_rows)}",
        f"- **Pending Rule (D):** {len(pending_rows)}",
    ]

    if missing_rows:
        lines.extend(["", "### Missing Task Reports"])
        for row in missing_rows[:31]:
            lines.append(
                f"- **{row['date']}** — {row['attendance']} → **{row['status']}**"
            )

        if len(missing_rows) > 31:
            lines.append(f"- Showing first 31 missing dates only. Total missing: {len(missing_rows)}")

    if submitted_rows:
        lines.extend(["", "### Submitted Task Reports"])
        for row in submitted_rows[:31]:
            lines.append(
                f"- **{row['date']}** — {row['attendance']} → **{row['status']}**"
            )

        if len(submitted_rows) > 31:
            lines.append(f"- Showing first 31 submitted dates only. Total submitted: {len(submitted_rows)}")

    if pending_rows:
        lines.extend(["", "### D Code / Pending Business Rule"])
        for row in pending_rows[:31]:
            lines.append(
                f"- **{row['date']}** — {row['attendance']} → **{row['status']}**"
            )

    if not missing_rows and not submitted_rows and not pending_rows:
        lines.append("")
        lines.append(f"{subject} had no P/R attendance days requiring task reports for this month.")

    return "\n".join(lines)


# ============================================================
# HR / Leave / WFH Request reader
# ============================================================

def _hr_request_status_label(state):
    state_text = str(state or "").strip().lower()

    labels = {
        "draft": "Draft",
        "submitted": "Submitted",
        "pending": "Pending",
        "approved": "Approved",
        "rejected": "Rejected",
        "refused": "Rejected",
        "cancelled": "Cancelled",
        "canceled": "Cancelled",
    }

    return labels.get(state_text, not_available(state))


def get_hr_requests_by_employee(employee_number, question=None):
    employee_number = str(employee_number or "").strip()

    if not employee_number:
        return []

    try:
        start_date, end_date, _month_label = _month_bounds_from_question(question)

        if start_date and end_date:
            rows = _fetchall(
                """
                SELECT
                    r.id,
                    r.employee_id,
                    e.name AS employee_name,
                    e.employee_code AS employee_code_from_employee,
                    r.employee_code AS employee_code_from_request,
                    r.display_name,
                    r.request_type,
                    r.request_type_label,
                    r.state,
                    r.date_from,
                    r.date_to,
                    r.reason,
                    r.admin_remarks,
                    r.submitted_at,
                    r.reviewed_at,
                    r.create_date,
                    r.write_date
                FROM hr_employee_portal_request r
                LEFT JOIN hr_employee e ON e.id = r.employee_id
                WHERE (
                    LOWER(TRIM(r.employee_code)) = LOWER(TRIM(%s))
                    OR LOWER(TRIM(e.employee_code)) = LOWER(TRIM(%s))
                )
                  AND r.date_from >= %s
                  AND r.date_from < %s
                ORDER BY r.submitted_at DESC NULLS LAST, r.create_date DESC NULLS LAST, r.id DESC;
                """,
                (employee_number, employee_number, start_date, end_date),
            )
        else:
            rows = _fetchall(
                """
                SELECT
                    r.id,
                    r.employee_id,
                    e.name AS employee_name,
                    e.employee_code AS employee_code_from_employee,
                    r.employee_code AS employee_code_from_request,
                    r.display_name,
                    r.request_type,
                    r.request_type_label,
                    r.state,
                    r.date_from,
                    r.date_to,
                    r.reason,
                    r.admin_remarks,
                    r.submitted_at,
                    r.reviewed_at,
                    r.create_date,
                    r.write_date
                FROM hr_employee_portal_request r
                LEFT JOIN hr_employee e ON e.id = r.employee_id
                WHERE (
                    LOWER(TRIM(r.employee_code)) = LOWER(TRIM(%s))
                    OR LOWER(TRIM(e.employee_code)) = LOWER(TRIM(%s))
                )
                ORDER BY r.submitted_at DESC NULLS LAST, r.create_date DESC NULLS LAST, r.id DESC
                LIMIT 10;
                """,
                (employee_number, employee_number),
            )

        return rows

    except Exception:
        return []


def build_hr_request_response(employee_number: str, question: str = None, is_admin: bool = False):
    requests = get_hr_requests_by_employee(employee_number, question=question)

    subject = "Selected employee" if is_admin else "Your"

    if not requests:
        return f"""
## HR Request Status

No HR / leave / WFH request found for **{not_available(employee_number)}**.
"""

    latest = requests[0]
    status = _hr_request_status_label(latest.get("state"))

    heading = "HR Request Status for Selected Employee" if is_admin else "Your HR Request Status"

    lines = [
        f"## {heading}",
        "",
        f"- **Employee:** {not_available(latest.get('employee_name'))}",
        f"- **Employee Code:** {not_available(latest.get('employee_code_from_employee') or latest.get('employee_code_from_request'))}",
        f"- **Latest Request:** {not_available(latest.get('request_type_label') or latest.get('request_type'))}",
        f"- **Status:** {status}",
        f"- **From:** {_format_date(latest.get('date_from'))}",
        f"- **To:** {_format_date(latest.get('date_to'))}",
        f"- **Reason:** {not_available(latest.get('reason'))}",
        f"- **Admin Remarks:** {not_available(latest.get('admin_remarks'))}",
        f"- **Submitted At:** {_format_datetime(latest.get('submitted_at'))}",
        f"- **Reviewed At:** {_format_datetime(latest.get('reviewed_at'))}",
    ]

    if str(status).lower() == "approved":
        lines.append("")
        lines.append(f"{subject} latest request is **approved**.")
    elif str(status).lower() == "rejected":
        lines.append("")
        lines.append(f"{subject} latest request is **rejected**.")
    else:
        lines.append("")
        lines.append(f"{subject} latest request status is **{status}**.")

    if len(requests) > 1:
        lines.extend(["", "### Previous Requests"])

        for request in requests[1:5]:
            lines.append(
                f"- **{_format_date(request.get('date_from'))} to {_format_date(request.get('date_to'))}** "
                f"— {not_available(request.get('request_type_label') or request.get('request_type'))} "
                f"→ **{_hr_request_status_label(request.get('state'))}**"
            )

    return "\n".join(lines)


# ============================================================
# Performance reader
# ============================================================

def _get_performance_records(employee_number, question=None):
    employee = _get_employee_record_by_code(employee_number)

    if not employee:
        return None, []

    start_date, end_date, _month_label = _month_bounds_from_question(question)

    if start_date and end_date:
        rows = _fetchall(
            """
            SELECT *
            FROM hr_daily_performance_plan
            WHERE employee_id = %s
              AND plan_date >= %s
              AND plan_date < %s
            ORDER BY plan_date DESC, id DESC;
            """,
            (employee["id"], start_date, end_date),
        )
    else:
        rows = _fetchall(
            """
            SELECT *
            FROM hr_daily_performance_plan
            WHERE employee_id = %s
            ORDER BY plan_date DESC, id DESC
            LIMIT 10;
            """,
            (employee["id"],),
        )

    return employee, rows


def build_performance_response(employee_number: str, is_admin: bool = False, question: str = None):
    heading = "Performance Record for Selected Employee" if is_admin else "Your Performance Record"

    try:
        employee, records = _get_performance_records(employee_number, question=question)

        if not employee:
            return "Performance data is not available in record."

        if not records:
            return f"""
## {heading}

- **Employee:** {not_available(employee.get('name'))}
- **Employee Number:** {not_available(employee_number)}
- **Review Date:** N/A
- **Task ID:** N/A
- **Project:** N/A
- **Task Description:** N/A
- **Priority:** N/A
- **Status:** N/A
- **Completion:** N/A
- **Rating:** N/A
- **Supervisor Remarks:** N/A

Performance data is not available in record.
"""

        lines = [
            f"## {heading}",
            "",
            f"- **Employee:** {not_available(employee.get('name'))}",
            f"- **Employee Number:** {not_available(employee_number)}",
            f"- **Total Performance Records:** {len(records)}",
            "",
            "### Records",
        ]

        for record in records[:10]:
            lines.append(
                f"""
- **Date:** {_format_date(record.get('plan_date'))}
  - **Task ID:** {not_available(record.get('task_id'))}
  - **Project:** {not_available(record.get('project_name'))}
  - **Priority:** {not_available(record.get('priority_level'))}
  - **Status:** {not_available(record.get('status'))}
  - **Completion:** {_format_money(record.get('completion_percent'))}%
  - **Task Description:** {not_available(record.get('task_description'))}
  - **Supervisor Remarks:** {not_available(record.get('supervisor_remarks'))}
"""
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Performance database error: {e}"


# ============================================================
# Tax calculator
# ============================================================

def build_tax_calculator_response(employee_number: str = None, question: str = None, is_admin: bool = False):
    heading = "Tax Calculator Summary for Selected Employee" if is_admin else "Your Tax Calculator Summary"

    payroll = get_payroll_by_employee_number(
        employee_number=employee_number,
        question=question,
    )

    payroll_message = payroll.get("message") or payroll.get("payslip_status")

    if payroll_message:
        payroll_message_text = str(payroll_message).lower()

        if "payroll data is not available" in payroll_message_text:
            return payroll_message

        if "payroll database error" in payroll_message_text:
            return payroll_message

        if "payroll file is not available" in payroll_message_text:
            return payroll_message

    month = not_available(payroll.get("month"))
    employee_number_value = not_available(payroll.get("employee_number"))
    employee_name = not_available(payroll.get("employee_name"))

    net_salary = _to_number(payroll.get("net_salary"))
    medical_allowance = _to_number(payroll.get("medical_allowance"))
    taxable_income = _to_number(payroll.get("taxable_income"))
    yearly_income = _to_number(payroll.get("yearly_income"))
    monthly_income_tax = _to_number(payroll.get("income_tax") or payroll.get("tax"))

    if taxable_income <= 0:
        taxable_income = max(net_salary - medical_allowance, 0)

    if yearly_income <= 0:
        yearly_income = taxable_income * 12

    yearly_tax = monthly_income_tax * 12

    return f"""
## {heading}

- **Payroll Month:** {month}
- **Employee Number:** {employee_number_value}
- **Employee Name:** {employee_name}

### Real Payroll Values
- **Net Salary:** {_format_money(net_salary)}
- **Medical Allowance:** {_format_money(medical_allowance)}
- **Taxable Income:** {_format_money(taxable_income)}
- **Yearly Income:** {_format_money(yearly_income)}

### Tax Calculation
- **Monthly Income Tax:** {_format_money(monthly_income_tax)}
- **Yearly Tax:** {_format_money(yearly_tax)}

### Source
Values are calculated from real payroll database data.
"""


def get_tax_rates():
    return [
        {
            "slab": "Slab 1",
            "range": "Taxable income does not exceed Rs600,000",
            "tax_rule": "0%",
        },
        {
            "slab": "Slab 2",
            "range": "600,001 to 1,200,000",
            "tax_rule": "1% of the amount exceeding Rs600,000",
        },
        {
            "slab": "Slab 3",
            "range": "1,200,001 to 2,200,000",
            "tax_rule": "Rs6,000 + 11% of the amount exceeding Rs1,200,000",
        },
        {
            "slab": "Slab 4",
            "range": "2,200,001 to 3,200,000",
            "tax_rule": "Rs116,000 + 23% of the amount exceeding Rs2,200,000",
        },
        {
            "slab": "Slab 5",
            "range": "3,200,001 to 4,100,000",
            "tax_rule": "Rs346,000 + 30% of the amount exceeding Rs3,200,000",
        },
        {
            "slab": "Slab 6",
            "range": "Taxable income exceeds Rs4,100,000",
            "tax_rule": "Rs616,000 + 35% of the amount exceeding Rs4,100,000",
        },
    ]


def build_tax_rates_response():
    rates = get_tax_rates()
    lines = ["## Tax Rates for Salary / Business Income - FY 25/26"]

    for rate in rates:
        lines.append(
            f"- **{rate.get('slab')}**: {rate.get('range')} - {rate.get('tax_rule')}"
        )

    return "\n".join(lines)