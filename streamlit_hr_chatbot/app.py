import json
import os
import re
import time
from datetime import datetime, date

import streamlit as st
import hmac
import hashlib
import time
from dotenv import load_dotenv
from google import genai

from prompt import SYSTEM_PROMPT
from utils import (
    get_employee_by_number,
    get_employee_numbers,
    prepare_employee_data,
    get_attendance_by_employee_name,
    get_payroll_by_employee_number,
    build_task_report_response,
    build_latest_task_report_response,
    build_task_report_attendance_comparison_response,
    build_performance_response,
    build_tax_calculator_response,
    build_tax_rates_response,
    build_hr_request_response,
    build_department_response,
    build_all_departments_response,
    build_invoice_response,
)

load_dotenv()

st.set_page_config(page_title="Blimp Employee Chatbot", layout="wide")

# CHATBOT_TOKEN_GUARD_START
def _chatbot_query_param(name, default=""):
    try:
        value = st.query_params.get(name, default)
        if isinstance(value, list):
            return str(value[0] if value else default).strip()
        return str(value or default).strip()
    except Exception:
        return str(default).strip()

def _validate_chatbot_token(expected_role):
    secret = os.environ.get("CHATBOT_SHARED_SECRET", "").strip()
    if not secret:
        st.error("Chatbot security is not configured.")
        st.stop()

    ts = _chatbot_query_param("ts")
    sig = _chatbot_query_param("sig")

    try:
        ts_int = int(ts)
    except Exception:
        st.error("Chatbot access denied.")
        st.stop()

    if abs(int(time.time()) - ts_int) > 600:
        st.error("Chatbot session expired. Please refresh the HR portal and open chatbot again.")
        st.stop()

    if expected_role == "employee":
        employee_code = _chatbot_query_param("employee_code")
        if not employee_code:
            st.error("Chatbot access denied.")
            st.stop()
        payload = f"employee|{employee_code}|{ts}"
    else:
        payload = f"admin|{ts}"

    expected_sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, sig):
        st.error("Chatbot access denied.")
        st.stop()

_validate_chatbot_token("employee")
# CHATBOT_TOKEN_GUARD_END

st.markdown("""
<style>
html, body, .stApp {
    height: 100% !important;
    overflow-x: hidden !important;
    background: linear-gradient(135deg, #071a66 0%, #0d3ea8 45%, #18c6d9 100%) !important;
    color: white !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"], footer {
    background: transparent !important;
}

[data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}

[data-testid="stToolbar"] * {
    visibility: visible !important;
}

#MainMenu {
    visibility: visible !important;
}

footer {
    visibility: hidden !important;
}

section[data-testid="stSidebar"] {
    background: rgba(5, 18, 70, 0.95) !important;
}

section[data-testid="stSidebar"] * {
    color: white !important;
}

.block-container {
    padding-top: 0.75rem !important;
    padding-left: 0.9rem !important;
    padding-right: 0.9rem !important;
    padding-bottom: 5rem !important;
    max-width: 100% !important;
}

[data-testid="stAppViewContainer"] {
    overflow-x: hidden !important;
}

[data-testid="stSidebar"] {
    min-width: 220px !important;
    max-width: 260px !important;
}

h1 {
    font-size: 1.45rem !important;
    margin-bottom: 0.8rem !important;
    color: white !important;
}

h2, h3 {
    font-size: 1.05rem !important;
    color: white !important;
}

p, li, span, label {
    color: white !important;
}

.stButton > button,
.stFormSubmitButton > button {
    width: 100%;
    height: 48px !important;
    min-height: 48px !important;
    background: rgba(255,255,255,0.08);
    color: white;
    border: 1px solid rgba(255,255,255,0.20);
    border-radius: 12px !important;
    font-weight: 600;
    font-size: 13px !important;
    white-space: nowrap !important;
    overflow: hidden;
    text-overflow: ellipsis;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0 8px !important;
}

.stButton > button *,
.stFormSubmitButton > button * {
    white-space: nowrap !important;
    overflow: hidden;
    text-overflow: ellipsis;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background: rgba(36, 210, 220, 0.18);
    border-color: #24d2dc;
    color: white;
}

[data-testid="stChatMessage"] {
    background: rgba(8, 25, 70, 0.30) !important;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 18px;
    padding: 0.55rem 0.7rem !important;
    margin-bottom: 0.55rem !important;
}

.summary-card {
    padding: 10px 12px !important;
    border-radius: 14px !important;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    margin-bottom: 10px !important;
    max-width: 100% !important;
    font-size: 14px !important;
}

div[data-testid="stTextInput"] input {
    height: 42px !important;
    background: rgba(8, 25, 70, 0.25) !important;
    color: white !important;
    border-radius: 14px !important;
    font-size: 14px !important;
}

div[data-baseweb="select"] {
    z-index: 999999 !important;
}

div[data-baseweb="popover"] {
    z-index: 9999999 !important;
    max-height: 45vh !important;
    overflow-y: auto !important;
}

div[data-baseweb="menu"] {
    max-height: 45vh !important;
    overflow-y: auto !important;
}

.custom-chat-wrap {
    margin-top: 0.7rem;
}

@media (max-width: 900px) {
    .block-container {
        padding-top: 0.55rem !important;
        padding-left: 0.55rem !important;
        padding-right: 0.55rem !important;
        padding-bottom: 5rem !important;
    }

    [data-testid="stSidebar"] {
        min-width: 200px !important;
        max-width: 240px !important;
    }

    h1 {
        font-size: 1.25rem !important;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        height: 44px !important;
        min-height: 44px !important;
        font-size: 12px !important;
        padding: 0 8px !important;
    }

    .summary-card {
        font-size: 13px !important;
    }

    [data-testid="stChatMessage"] {
        padding: 0.5rem 0.6rem !important;
        margin-bottom: 0.5rem !important;
    }
}
</style>
""", unsafe_allow_html=True)
APP_VERSION = "2026-05-13-range-fix-v2"

st.title("Blimp Employee Chatbot")
st.caption(f"Version: {APP_VERSION}")

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "input_counter" not in st.session_state:
    st.session_state.input_counter = 0

if "last_attendance_metrics" not in st.session_state:
    st.session_state.last_attendance_metrics = []

if st.session_state.get("app_version") != APP_VERSION:
    st.session_state.messages = []
    st.session_state.input_counter = 0
    st.session_state.last_attendance_metrics = []
    st.session_state.app_version = APP_VERSION

def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = text.replace("kitnay", "kitne")
    text = text.replace("kitni", "kitne")
    text = text.replace("kitny", "kitne")
    text = text.replace("ktny", "ktne")
    text = text.replace("chutti", "chuti")
    text = text.replace("chuttiyan", "chutian")
    text = text.replace("chuttiyain", "chutian")
    text = re.sub(r"[^a-z0-9\s/\\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def normalize_question_for_intent(text: str) -> str:
    q = normalize_text(text)

    replacements = {
        "holidy": "holiday",
        "holidys": "holidays",
        "attandance": "attendance",
        "attendence": "attendance",
        "absentees": "absent",
        "absenties": "absent",
        "salery": "salary",
        "sallary": "salary",
        "aproved": "approved",
        "approveed": "approved",
        "rejcted": "rejected",

        "kitne": "how many",
        "ktne": "how many",
        "kitna": "how many",
        "kitni": "how many",
        "mere": "my",
        "meri": "my",
        "mera": "my",
        "mujhe": "my",
        "mae": "in",
        "mein": "in",
        "main": "in",
        "chuti": "leave",
        "chutian": "leave",
        "chutay": "leave",
        "ghar se kam": "wfh",
        "work from home": "wfh",
        "remote work": "wfh",
    }

    for wrong, right in replacements.items():
        q = q.replace(wrong, right)

    q = re.sub(r"\s+", " ", q).strip()
    return q


ATTENDANCE_INTENTS = {
    "present_days": [
        "present",
        "present days",
        "office days",
        "how many present",
        "present count",
    ],
    "remote_days": [
        "wfh",
        "remote",
        "remote days",
        "work from home",
        "wfh days",
        "how many wfh",
    ],
    "holiday_days": [
        "holiday",
        "holidays",
        "holiday days",
        "off days",
        "how many holiday",
        "holidays can",
    ],
    "sick_leave_days": [
        "sick",
        "sick leave",
        "sick days",
    ],
    "casual_leave_days": [
        "casual",
        "casual leave",
        "casual days",
    ],
    "unpaid_leave_days": [
        "unpaid",
        "unpaid leave",
        "unpaid days",
    ],
    "late_submitted_days": [
        "late submitted",
        "data late",
        "late submission",
    ],
    "absent_days": [
        "absent",
        "absent days",
        "absent count",
        "how many absent",
    ],
    "leave_days": [
        "leave",
        "leaves",
        "leave days",
    ],
    "overtime_count": [
        "overtime",
        "ot",
    ],
    "total_counted_days": [
        "total counted",
        "total days",
        "counted days",
    ],
}


PAYROLL_INTENTS = {
    "net_salary": [
        "net salary",
        "take home",
        "final salary",
        "total salary",
    ],
    "basic_salary": [
        "basic salary",
        "basic",
    ],
    "gross_salary": [
        "gross salary",
        "gross",
    ],
    "medical_allowance": [
        "medical allowance",
        "medical",
    ],
    "income_tax": [
        "income tax",
        "monthly tax",
        "tax",
    ],
    "taxable_income": [
        "taxable income",
    ],
    "yearly_income": [
        "yearly income",
        "annual income",
    ],
    "bonus": [
        "bonus",
    ],
    "deduction": [
        "deduction",
        "deductions",
        "other deductions",
    ],
    "payment_date": [
        "payment date",
        "salary date",
        "paid date",
    ],
    "payment_method": [
        "payment method",
        "salary method",
    ],
}


REQUEST_KEYWORDS = [
    "request",
    "hr request",
    "leave request",
    "wfh request",
    "request status",
    "approved",
    "rejected",
    "accept",
    "reject",
    "accepted",
    "approval",
    "my request",
    "my leave status",
    "my wfh status",
]


def detect_attendance_metrics_from_question(question: str) -> list[str]:
    q = normalize_question_for_intent(question)
    detected = []

    for metric, keywords in ATTENDANCE_INTENTS.items():
        if has_any(q, keywords):
            detected.append(metric)

    return list(dict.fromkeys(detected))


def detect_payroll_metric_from_question(question: str) -> str | None:
    q = normalize_question_for_intent(question)

    for metric, keywords in PAYROLL_INTENTS.items():
        if has_any(q, keywords):
            return metric

    return None


def is_hr_request_question(question: str) -> bool:
    q = normalize_question_for_intent(question)
    return has_any(q, REQUEST_KEYWORDS)


def is_attendance_question(question: str) -> bool:
    q = normalize_question_for_intent(question)

    return (
        "attendance" in q
        or bool(detect_attendance_metrics_from_question(q))
    )


def is_payroll_question(question: str) -> bool:
    q = normalize_question_for_intent(question)

    return (
        "payroll" in q
        or "salary" in q
        or "payslip" in q
        or bool(detect_payroll_metric_from_question(q))
    )


def not_available(value):
    if value is None or value == "":
        return "N/A"

    clean_value = str(value).strip()
    if clean_value.lower() in [
        "none",
        "nan",
        "n/a",
        "na",
        "not available",
        "not available in record.",
    ]:
        return "N/A"

    return value


def get_employee_code_from_url():
    try:
        employee_code = st.query_params.get("employee_code")
        if employee_code:
            return str(employee_code).strip()

        employee_number = st.query_params.get("employee_number")
        if employee_number:
            return str(employee_number).strip()

        emp_code = st.query_params.get("emp_code")
        if emp_code:
            return str(emp_code).strip()
    except Exception:
        pass

    return None


def get_attendance_message(attendance: dict) -> str:
    if not attendance:
        return ""

    monthly = attendance.get("monthly_summary", {})

    message = (
        monthly.get("unavailable_message")
        or attendance.get("unavailable_message")
        or monthly.get("message")
        or attendance.get("attendance_status")
    )

    if not_available(message) != "N/A":
        message_text = str(message).strip()

        if "attendance data is not available" in message_text.lower():
            return message_text

        if "attendance file is not available" in message_text.lower():
            return message_text

        if "attendance database error" in message_text.lower():
            return message_text

    return ""


def get_payroll_message(payroll: dict) -> str:
    if not payroll:
        return ""

    message = payroll.get("message") or payroll.get("payslip_status")

    if not_available(message) != "N/A":
        message_text = str(message).strip()

        if "payroll data is not available" in message_text.lower():
            return message_text

        if "payroll file is not available" in message_text.lower():
            return message_text

        if "payroll database error" in message_text.lower():
            return message_text

    return ""


def is_gemini_error(text: str) -> bool:
    t = (text or "").lower()
    keywords = [
        "quota",
        "rate limit",
        "unavailable",
        "busy",
        "api key",
        "gemini error",
        "temporarily",
        "429",
        "503",
        "no response returned from gemini",
        "something went wrong while calling gemini",
    ]
    return any(k in t for k in keywords)


def build_full_profile_response(employee_data: dict) -> str:
    main = employee_data.get("main", {})
    record = employee_data.get("employee_record", {})
    bank = employee_data.get("bank_account", {})
    personal = employee_data.get("personal_details", {})
    emergency = employee_data.get("emergency_contact", {})
    payroll = employee_data.get("payroll", {})
    attendance = employee_data.get("attendance", {})
    monthly = attendance.get("monthly_summary", {})

    payroll_message = get_payroll_message(payroll)
    attendance_message = get_attendance_message(attendance)

    if payroll_message:
        payroll_section = f"""
### Payroll
{payroll_message}
"""
    else:
        payroll_section = f"""
### Payroll
- **Fiscal Year:** {not_available(payroll.get('fiscal_year'))}
- **Payroll Month:** {not_available(payroll.get('month'))}
- **Employee Number:** {not_available(payroll.get('employee_number'))}
- **Employee Name:** {not_available(payroll.get('employee_name'))}
- **Designation:** {not_available(payroll.get('designation'))}
- **Bank:** {not_available(payroll.get('bank'))}
- **Payment Method:** {not_available(payroll.get('payment_method'))}
- **Basic Salary:** {not_available(payroll.get('basic_salary'))}
- **Basic Actual:** {not_available(payroll.get('basic_actual'))}
- **Medical Allowance:** {not_available(payroll.get('medical_allowance'))}
- **Advertised Salary:** {not_available(payroll.get('advertised_salary'))}
- **Project Salary:** {not_available(payroll.get('project_salary'))}
- **Allowance Detail:** {not_available(payroll.get('allowance_detail'))}
- **Allowance:** {not_available(payroll.get('allowance'))}
- **Bonus:** {not_available(payroll.get('bonus'))}
- **Gross Salary:** {not_available(payroll.get('gross_salary'))}
- **Net Salary:** {not_available(payroll.get('net_salary'))}
- **Income Tax:** {not_available(payroll.get('income_tax') or payroll.get('tax'))}
- **Tax:** {not_available(payroll.get('tax'))}
- **Other Deductions:** {not_available(payroll.get('other_deductions') or payroll.get('deduction'))}
- **Deduction:** {not_available(payroll.get('deduction'))}
- **Taxable Income:** {not_available(payroll.get('taxable_income'))}
- **Yearly Income:** {not_available(payroll.get('yearly_income'))}
- **Total:** {not_available(payroll.get('total'))}
- **Total Round:** {not_available(payroll.get('total_round'))}
- **Total Salary:** {not_available(payroll.get('total_salary'))}
- **Rounded:** {not_available(payroll.get('rounded'))}
- **Payment Date:** {not_available(payroll.get('payment_date'))}
- **Pay Period:** {not_available(payroll.get('pay_period'))}
- **Payslip Status:** {not_available(payroll.get('payslip_status'))}
- **Total Days:** {not_available(payroll.get('total_days'))}
- **Comments:** {not_available(payroll.get('comments'))}
"""

    if attendance_message:
        attendance_section = f"""
### Attendance
{attendance_message}
"""
    else:
        attendance_section = f"""
### Attendance
- **Attendance Status:** {not_available(attendance.get('attendance_status'))}
- **Attendance Month:** {not_available(monthly.get('month') or attendance.get('attendance_date'))}
- **Fiscal Year:** {not_available(monthly.get('fiscal_year'))}
- **Present Days:** {not_available(monthly.get('present_days'))}
- **Remote / WFH Days:** {not_available(monthly.get('remote_days'))}
- **Holiday Days:** {not_available(monthly.get('holiday_days'))}
- **Sick Leave Days:** {not_available(monthly.get('sick_leave_days'))}
- **Casual Leave Days:** {not_available(monthly.get('casual_leave_days'))}
- **Unpaid Leave Days:** {not_available(monthly.get('unpaid_leave_days'))}
- **Late Submitted Days:** {not_available(monthly.get('late_submitted_days'))}
- **Absent Days:** {not_available(monthly.get('absent_days'))}
- **Total Leave Days:** {not_available(monthly.get('leave_days'))}
- **Overtime Count:** {not_available(monthly.get('overtime_count'))}
- **Total Counted Days:** {not_available(monthly.get('total_counted_days'))}
"""

    return f"""
## Complete Profile

### Main Information
- **Status:** {not_available(main.get('status'))}
- **Employee Number:** {not_available(main.get('employee_number'))}
- **Employee Name:** {not_available(main.get('employee_name'))}

### Employee Record
- **Father Name:** {not_available(record.get('father_name'))}
- **Designation:** {not_available(record.get('designation'))}
- **Date of Joining:** {not_available(record.get('doj'))}
- **Contract Start:** {not_available(record.get('contract_start'))}
- **Contract End:** {not_available(record.get('contract_end'))}
- **Employment Type:** {not_available(record.get('employment_type'))}

### Bank Account
- **Account Title:** {not_available(bank.get('account_title'))}
- **Bank Name:** {not_available(bank.get('bank_name'))}
- **Bank Branch:** {not_available(bank.get('bank_branch'))}
- **Account Number:** {not_available(bank.get('account_number'))}

### Personal Details
- **Mobile:** {not_available(personal.get('mobile'))}
- **Residence Number:** {not_available(personal.get('residence_number'))}
- **Personal Email:** {not_available(personal.get('personal_email'))}
- **Office Email:** {not_available(personal.get('office_email'))}
- **CNIC:** {not_available(personal.get('cnic'))}
- **Address:** {not_available(personal.get('address'))}
- **NTN Number:** {not_available(personal.get('ntn_number'))}
- **Date of Birth:** {not_available(personal.get('dob'))}

### Emergency Contact
- **Contact Name:** {not_available(emergency.get('name'))}
- **Number:** {not_available(emergency.get('number'))}
- **Relation:** {not_available(emergency.get('relation'))}

{payroll_section}

{attendance_section}
"""


def build_attendance_response(attendance: dict) -> str:
    attendance_message = get_attendance_message(attendance)

    if attendance_message:
        return attendance_message

    monthly = attendance.get("monthly_summary", {})

    return f"""
## Attendance Details

- **Attendance Status:** {not_available(attendance.get('attendance_status'))}
- **Attendance Month:** {not_available(monthly.get('month') or attendance.get('attendance_date'))}
- **Fiscal Year:** {not_available(monthly.get('fiscal_year'))}
- **Employee Name:** {not_available(monthly.get('employee_name'))}

### Monthly Summary
- **Present Days:** {not_available(monthly.get('present_days'))}
- **Remote / WFH Days:** {not_available(monthly.get('remote_days'))}
- **Holiday Days:** {not_available(monthly.get('holiday_days'))}
- **Sick Leave Days:** {not_available(monthly.get('sick_leave_days'))}
- **Casual Leave Days:** {not_available(monthly.get('casual_leave_days'))}
- **Unpaid Leave Days:** {not_available(monthly.get('unpaid_leave_days'))}
- **Late Submitted Days:** {not_available(monthly.get('late_submitted_days'))}
- **Absent Days:** {not_available(monthly.get('absent_days'))}
- **Total Leave Days:** {not_available(monthly.get('leave_days'))}
- **Overtime Count:** {not_available(monthly.get('overtime_count'))}
- **Total Counted Days:** {not_available(monthly.get('total_counted_days'))}
"""


def build_payroll_response(payroll: dict) -> str:
    payroll_message = get_payroll_message(payroll)

    if payroll_message:
        return payroll_message

    return f"""
## Payroll Details

- **Fiscal Year:** {not_available(payroll.get('fiscal_year'))}
- **Payroll Month:** {not_available(payroll.get('month'))}
- **Employee Number:** {not_available(payroll.get('employee_number'))}
- **Employee Name:** {not_available(payroll.get('employee_name'))}
- **Designation:** {not_available(payroll.get('designation'))}
- **Bank:** {not_available(payroll.get('bank'))}
- **Payment Method:** {not_available(payroll.get('payment_method'))}

### Salary
- **Basic Salary:** {not_available(payroll.get('basic_salary'))}
- **Basic Actual:** {not_available(payroll.get('basic_actual'))}
- **Medical Allowance:** {not_available(payroll.get('medical_allowance'))}
- **Advertised Salary:** {not_available(payroll.get('advertised_salary'))}
- **Project Salary:** {not_available(payroll.get('project_salary'))}
- **Allowance Detail:** {not_available(payroll.get('allowance_detail'))}
- **Allowance:** {not_available(payroll.get('allowance'))}
- **Bonus:** {not_available(payroll.get('bonus'))}
- **Gross Salary:** {not_available(payroll.get('gross_salary'))}
- **Net Salary:** {not_available(payroll.get('net_salary'))}

### Deductions / Tax
- **Income Tax:** {not_available(payroll.get('income_tax') or payroll.get('tax'))}
- **Tax:** {not_available(payroll.get('tax'))}
- **Other Deductions:** {not_available(payroll.get('other_deductions') or payroll.get('deduction'))}
- **Deduction:** {not_available(payroll.get('deduction'))}
- **Taxable Income:** {not_available(payroll.get('taxable_income'))}
- **Yearly Income:** {not_available(payroll.get('yearly_income'))}

### Payment
- **Total:** {not_available(payroll.get('total'))}
- **Total Round:** {not_available(payroll.get('total_round'))}
- **Total Salary:** {not_available(payroll.get('total_salary'))}
- **Rounded:** {not_available(payroll.get('rounded'))}
- **Payment Date:** {not_available(payroll.get('payment_date'))}
- **Pay Period:** {not_available(payroll.get('pay_period'))}
- **Payslip Status:** {not_available(payroll.get('payslip_status'))}
- **Total Days:** {not_available(payroll.get('total_days'))}
- **Comments:** {not_available(payroll.get('comments'))}
"""


def build_bank_response(bank: dict) -> str:
    return f"""
## Bank Account Details
- **Account Title:** {not_available(bank.get('account_title'))}
- **Bank Name:** {not_available(bank.get('bank_name'))}
- **Bank Branch:** {not_available(bank.get('bank_branch'))}
- **Account Number:** {not_available(bank.get('account_number'))}
"""


def build_personal_response(personal: dict) -> str:
    return f"""
## Personal Details
- **Mobile:** {not_available(personal.get('mobile'))}
- **Residence Number:** {not_available(personal.get('residence_number'))}
- **Personal Email:** {not_available(personal.get('personal_email'))}
- **Office Email:** {not_available(personal.get('office_email'))}
- **CNIC:** {not_available(personal.get('cnic'))}
- **Address:** {not_available(personal.get('address'))}
- **NTN Number:** {not_available(personal.get('ntn_number'))}
- **Date of Birth:** {not_available(personal.get('dob'))}
"""


def build_emergency_response(emergency: dict) -> str:
    return f"""
## Emergency Contact
- **Contact Name:** {not_available(emergency.get('name'))}
- **Number:** {not_available(emergency.get('number'))}
- **Relation:** {not_available(emergency.get('relation'))}
"""


def build_company_tenure_response(record: dict, is_admin: bool = False) -> str:
    doj_value = not_available(record.get("doj"))
    subject = "Employee" if is_admin else "Your"

    if doj_value == "N/A":
        return f"{subject} date of joining is not available, so company tenure cannot be calculated."

    parsed_date = None

    try:
        if hasattr(doj_value, "date"):
            parsed_date = doj_value.date()
    except Exception:
        parsed_date = None

    if not parsed_date:
        doj_text = str(doj_value).strip()

        for fmt in [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d %b %Y",
            "%d %B %Y",
        ]:
            try:
                parsed_date = datetime.strptime(doj_text, fmt).date()
                break
            except Exception:
                continue

    if not parsed_date:
        return (
            f"{subject} date of joining is: {doj_value}. "
            "I could not calculate the exact tenure from this date format."
        )

    today = date.today()

    if parsed_date > today:
        return (
            f"{subject} date of joining is: {doj_value}. "
            "This date is in the future, so tenure cannot be calculated."
        )

    years = today.year - parsed_date.year
    months = today.month - parsed_date.month
    days = today.day - parsed_date.day

    if days < 0:
        months -= 1

        previous_month = today.month - 1
        previous_month_year = today.year

        if previous_month == 0:
            previous_month = 12
            previous_month_year -= 1

        if previous_month == 12:
            days_in_previous_month = 31
        else:
            current_month_first_day = date(previous_month_year, previous_month, 1)
            next_month_first_day = date(previous_month_year, previous_month + 1, 1)
            days_in_previous_month = (next_month_first_day - current_month_first_day).days

        days += days_in_previous_month

    if months < 0:
        years -= 1
        months += 12

    if is_admin:
        return (
            f"Employee date of joining is: {doj_value}. "
            f"The employee has completed approximately {years} years, {months} months, and {days} days in the company."
        )

    return (
        f"Your date of joining is: {doj_value}. "
        f"You have completed approximately {years} years, {months} months, and {days} days in the company."
    )


MONTH_NAME_TO_NUMBER = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
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

ATTENDANCE_METRIC_LABELS = {
    "present_days": "Present days",
    "remote_days": "Remote / WFH days",
    "holiday_days": "Holiday days",
    "sick_leave_days": "Sick leave days",
    "casual_leave_days": "Casual leave days",
    "unpaid_leave_days": "Unpaid leave days",
    "late_submitted_days": "Late submitted days",
    "absent_days": "Absent days",
    "leave_days": "Leave days",
    "overtime_count": "Overtime count",
    "total_counted_days": "Total counted days",
}


def detect_attendance_metrics(q: str) -> list[str]:
    return detect_attendance_metrics_from_question(q)


def extract_month_year_pairs(q: str) -> list[tuple[int, int]]:
    q = normalize_question_for_intent(q)
    pairs = []
    current_year = date.today().year

    short_matches = re.findall(r"\b(0?[1-9]|1[0-2])\s*[/-]\s*(\d{2,4})\b", q)
    for month_text, year_text in short_matches:
        month_num = int(month_text)
        year_num = int(year_text)

        if year_num < 100:
            year_num += 2000

        pairs.append((month_num, year_num))

    month_aliases = sorted(MONTH_NAME_TO_NUMBER.keys(), key=len, reverse=True)
    month_pattern = "|".join(re.escape(m) for m in month_aliases)

    matches = re.finditer(
        rf"\b({month_pattern})\b(?:\s+(20\d{{2}}))?",
        q,
        flags=re.IGNORECASE,
    )

    for match in matches:
        month_name = match.group(1).lower()
        month_num = MONTH_NAME_TO_NUMBER.get(month_name)

        if not month_num:
            continue

        year_text = match.group(2)
        year_num = int(year_text) if year_text else current_year

        pairs.append((month_num, year_num))

    return list(dict.fromkeys(pairs))

def extract_month_range(q: str) -> list[tuple[int, int]]:
    q = normalize_question_for_intent(q)

    range_words = ["to", "till", "til", "until", "se", "sa", "sy", "tak"]
    has_range_word = any(f" {word} " in f" {q} " for word in range_words)

    if not has_range_word:
        return []

    month_aliases = sorted(MONTH_NAME_TO_NUMBER.keys(), key=len, reverse=True)
    month_pattern = "|".join(re.escape(m) for m in month_aliases)

    # Finds month + optional year pairs in order:
    # Example: Dec 2025 To April 2026 -> [(12, 2025), (4, 2026)]
    matches = list(
        re.finditer(
            rf"\b({month_pattern})\b(?:\s+(20\d{{2}}))?",
            q,
            flags=re.IGNORECASE,
        )
    )

    if len(matches) < 2:
        return []

    start_match = matches[0]
    end_match = matches[-1]

    start_month_name = start_match.group(1).lower()
    end_month_name = end_match.group(1).lower()

    start_month = MONTH_NAME_TO_NUMBER.get(start_month_name)
    end_month = MONTH_NAME_TO_NUMBER.get(end_month_name)

    if not start_month or not end_month:
        return []

    current_year = date.today().year

    start_year = int(start_match.group(2)) if start_match.group(2) else current_year
    end_year = int(end_match.group(2)) if end_match.group(2) else start_year

    # If user says Dec to March without end year, assume next year.
    if end_year == start_year and end_month < start_month:
        end_year += 1

    if end_year < start_year:
        return []

    month_pairs = []
    year = start_year
    month = start_month

    while True:
        month_pairs.append((month, year))

        if month == end_month and year == end_year:
            break

        month += 1

        if month > 12:
            month = 1
            year += 1

        # safety guard
        if len(month_pairs) > 24:
            break

    return month_pairs

def build_smart_attendance_response(employee_name: str, question: str) -> str | None:
    q = normalize_question_for_intent(question)

    metrics = detect_attendance_metrics_from_question(q)

    if not metrics and has_any(q, ["also", "same", "again", "bhi", "be"]):
        metrics = st.session_state.get("last_attendance_metrics", [])

    if not metrics:
        return None

    month_range = extract_month_range(q)
    month_pairs = month_range or extract_month_year_pairs(q)

    if not month_pairs:
        return None

    st.session_state["last_attendance_metrics"] = metrics

    rows = []
    unavailable_messages = []

    for month_num, year_num in month_pairs:
        month_name = MONTH_NUMBER_TO_NAME.get(month_num)
        lookup_question = f"{month_name} {year_num} attendance"

        attendance_data = get_attendance_by_employee_name(
            employee_name,
            lookup_question,
        )

        if not attendance_data:
            unavailable_messages.append(f"{month_name} {year_num} attendance data is not available.")
            continue

        attendance_message = get_attendance_message(attendance_data)

        if attendance_message:
            unavailable_messages.append(attendance_message)
            continue

        monthly = attendance_data.get("monthly_summary", {})

        row_parts = []

        for metric in metrics:
            label = ATTENDANCE_METRIC_LABELS.get(metric, metric)
            value = not_available(monthly.get(metric))
            row_parts.append(f"**{label}:** {value}")

        rows.append(f"- **{month_name} {year_num}:** " + " | ".join(row_parts))

    if rows:
        return "## Attendance Summary\n\n" + "\n".join(rows)

    if unavailable_messages:
        return unavailable_messages[0]

    return None


def get_local_answer(question: str, employee_data: dict):
    q = normalize_question_for_intent(question)

    main = employee_data.get("main", {})
    record = employee_data.get("employee_record", {})
    bank = employee_data.get("bank_account", {})
    personal = employee_data.get("personal_details", {})
    emergency = employee_data.get("emergency_contact", {})
    payroll = employee_data.get("payroll", {})
    attendance = employee_data.get("attendance", {})
    monthly = attendance.get("monthly_summary", {})

    question_attendance = get_attendance_by_employee_name(
        main.get("employee_name"),
        q,
    )

    if question_attendance:
        attendance = question_attendance
        monthly = attendance.get("monthly_summary", {})

    question_payroll = get_payroll_by_employee_number(
        employee_number=main.get("employee_number"),
        employee_name=main.get("employee_name"),
        question=q,
    )

    if question_payroll:
        payroll = question_payroll

    employee_number = main.get("employee_number")


    if has_any(q, ["invoice", "invoices", "client invoice", "paid invoice", "unpaid invoice", "amount due", "receivable"]):
        return build_invoice_response(q, is_admin=False)

    if has_any(q, ["department", "dept"]):
        return build_department_response(employee_number, is_admin=False)

    if is_hr_request_question(q):
        return build_hr_request_response(
            employee_number,
            question=q,
            is_admin=False,
        )

    attendance_related_keywords = [
        "attendance", "hazri", "check in", "check out",
        "working hours", "present", "present days", "present how many",
        "remote", "remote days", "wfh", "wfh days", "work from home",
        "holiday", "holidays", "holiday days", "holidays can",
        "sick leave", "sick leaves", "casual leave", "casual leaves",
        "unpaid leave", "unpaid leaves", "late submitted", "late submission",
        "data late", "overtime", "ot", "total counted", "total days",
        "counted days", "absent", "absent days", "leave", "leaves",
    ]

    payroll_related_keywords = [
        "payroll", "payslip", "salary", "basic salary", "basic actual",
        "gross salary", "net salary", "take home", "final salary",
        "medical allowance", "allowance", "allowance detail",
        "advertised salary", "project salary", "bonus", "deduction",
        "other deductions", "tax", "income tax", "taxable income",
        "yearly income", "payment date", "payment method",
        "pay period", "total salary", "total round", "rounded", "total days",
    ]

    attendance_message = get_attendance_message(attendance)

    if attendance_message and has_any(q, attendance_related_keywords):
        return attendance_message

    payroll_message = get_payroll_message(payroll)

    if payroll_message and has_any(q, payroll_related_keywords):
        return payroll_message

    smart_attendance_answer = build_smart_attendance_response(
        employee_name=main.get("employee_name"),
        question=q,
    )

    if smart_attendance_answer:
        return smart_attendance_answer

    payroll_metric = detect_payroll_metric_from_question(q)

    if payroll_metric:
        payroll_metric_labels = {
            "net_salary": "net salary",
            "basic_salary": "basic salary",
            "gross_salary": "gross salary",
            "medical_allowance": "medical allowance",
            "income_tax": "income tax",
            "taxable_income": "taxable income",
            "yearly_income": "yearly income",
            "bonus": "bonus",
            "deduction": "deduction",
            "payment_date": "payment date",
            "payment_method": "payment method",
        }

        value = payroll.get(payroll_metric)

        if payroll_metric == "income_tax":
            value = payroll.get("income_tax") or payroll.get("tax")

        if payroll_metric == "deduction":
            value = payroll.get("deduction") or payroll.get("other_deductions")

        return f"Your {payroll_metric_labels.get(payroll_metric, payroll_metric)} is: {not_available(value)}"

    if q in ["hi", "hello", "hey", "salam", "aoa"]:
        return (
            f"Hello {not_available(main.get('employee_name'))}! "
            "How can I assist you with your HR record today?"
        )

    if has_any(q, [
        "kis date par task report submit nahi ki",
        "kis date ki daily report submit nahi hui",
        "kis date par report submit nahi ki",
        "daily report submit nahi hui",
        "report submit nahi ki",
        "report jama nahi ki",
        "report submit nahi",
        "task report submit nahi",
        "missing report",
        "report missing",
        "missing task report",
        "maine kis date par report jama nahi ki",
        "meri kis date ki task report missing hai",
        "attendance task report",
        "attendance vs task report",
        "compare attendance task report",
        "compare my attendance task report",
        "my missing task report",
    ]):
        return build_task_report_attendance_comparison_response(
            employee_number,
            question=q,
            is_admin=False,
        )

    if has_any(q, [
        "profile", "full profile", "complete profile", "complete record",
        "my profile", "show my full profile",
    ]):
        return build_full_profile_response(employee_data)

    if has_any(q, [
        "latest task report", "last task report", "previous task report",
        "latest daily report",
    ]):
        return build_latest_task_report_response(employee_number, question=q, is_admin=False)

    if has_any(q, [
        "task report", "daily report", "daily working", "work report",
        "report submit", "report status", "report jama",
    ]):
        return build_task_report_response(employee_number, question=q, is_admin=False)

    if has_any(q, [
        "performance", "rating", "review", "completion",
        "meri performance", "mera completion",
    ]):
        return build_performance_response(
            employee_number,
            is_admin=False,
            question=q,
        )

    if has_any(q, [
        "tax calculator", "tax calculation", "monthly tax", "yearly tax",
        "taxable income", "medical allowance",
    ]):
        return build_tax_calculator_response(employee_number, question=q, is_admin=False)

    if has_any(q, [
        "tax rates", "tax rate", "tax slab", "tax slabs", "salary tax slabs",
    ]):
        return build_tax_rates_response()

    if has_any(q, ["designation", "post", "position", "job title"]):
        return f"Your designation is: {not_available(record.get('designation'))}"

    if has_any(q, ["employee number", "employee id", "emp id", "employee code"]):
        return f"Your employee number is: {not_available(main.get('employee_number'))}"

    if has_any(q, ["name", "my name", "naam"]):
        return f"Your name is: {not_available(main.get('employee_name'))}"

    if has_any(q, ["joining", "doj", "joining date"]):
        return f"Your date of joining is: {not_available(record.get('doj'))}"

    if has_any(q, [
        "kitna time ho gaya", "kitna time hogaya", "ktna time ho gaya",
        "ktna time hogaya", "kitna time ho gya", "ktna time ho gya",
        "company in how many time", "company tenure", "my tenure",
        "service duration", "job duration", "company experience",
        "company duration", "employment duration", "employment experience",
        "how long in company", "how long have i been in company",
        "how long have i worked here", "how many years in company",
        "years completed in company", "years completed", "working here",
        "been working here",
    ]):
        return build_company_tenure_response(record, is_admin=False)

    if has_any(q, ["bank", "account"]):
        return build_bank_response(bank)

    if has_any(q, ["personal", "cnic", "mobile", "phone", "address", "email", "ntn", "dob"]):
        return build_personal_response(personal)

    if has_any(q, ["emergency", "emergency contact", "emergency number"]):
        return build_emergency_response(emergency)

    if is_payroll_question(q):
        return build_payroll_response(payroll)

    if is_attendance_question(q):
        return build_attendance_response(attendance)

    hr_related_keywords = [
        "profile", "employee", "employee number", "employee code", "name",
        "designation", "post", "position", "job", "joining", "doj", "tenure",
        "service", "duration", "company", "bank", "account", "personal",
        "cnic", "mobile", "phone", "email", "address", "emergency",
        "attendance", "hazri", "present", "remote", "wfh",
        "holiday", "leave", "leaves", "absent", "overtime",
        "salary", "payroll", "payslip", "basic", "gross", "net", "bonus",
        "deduction", "tax", "payment", "performance", "rating", "review",
        "completion", "task", "task report", "daily report", "report",
        "request", "leave request", "wfh request", "request status",
    ]

    if has_any(q, hr_related_keywords):
        return None

    return (
        "I can assist you with HR-related information only. Please ask about your profile, "
        "payroll, attendance, bank details, personal details, emergency contact, task report, "
        "performance, request status, or tax details."
    )


def call_gemini_with_retry(prompt: str, retries: int = 2, delay: int = 2) -> str:
    if not client:
        return "Gemini API key is not configured."

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if getattr(response, "text", None):
                return response.text.strip()
            return "No response returned from Gemini."
        except Exception as e:
            error_text = str(e).lower()

            if "429" in error_text or "quota" in error_text or "rate limit" in error_text:
                return "Gemini API quota is currently reached. Local fallback is being used."

            if "503" in error_text or "unavailable" in error_text:
                if attempt < retries - 1:
                    time.sleep(delay)
                    continue
                return "Gemini API is temporarily busy. Local fallback is being used."

            if "401" in error_text or "403" in error_text or "api key" in error_text:
                return "There is an API key or access issue. Local fallback is being used."

            return f"Gemini error: {e}"

    return "Something went wrong while calling Gemini."


def process_user_question(question: str, employee_data: dict) -> str:
    local_answer = get_local_answer(question, employee_data)

    if local_answer:
        return local_answer

    prompt = f"""
{SYSTEM_PROMPT}

Logged in employee:
- employee_number: {employee_data['main']['employee_number']}
- employee_name: {employee_data['main']['employee_name']}
- role: employee

Available employee record data:
{json.dumps(employee_data, indent=2)}

User question:
{question}

Instructions:
- You are answering as an employee HR assistant.
- Answer only from the logged-in employee data above.
- Do not guess.
- If the field is empty or missing, say: N/A.
- Keep the answer concise.
- Reply in the same language as the user.
"""

    answer = call_gemini_with_retry(prompt)

    if is_gemini_error(answer):
        answer = get_local_answer(question, employee_data)

    if str(answer).strip().lower() in ["none", "null", "n/a", ""]:
        answer = (
            "I could not find a clear answer for that in your HR record. "
            "Please ask about profile, attendance, payroll, bank details, joining date, company tenure, or request status."
        )

    return answer


employee_numbers = get_employee_numbers()

if not employee_numbers:
    st.error("No employee records found. Please check database connection, DATA_SOURCE, or employee records.")
    st.stop()

URL_EMPLOYEE_CODE = get_employee_code_from_url()

CURRENT_EMPLOYEE_NUMBER = (
    URL_EMPLOYEE_CODE
    or employee_numbers[0]
)

raw_employee_data = get_employee_by_number(CURRENT_EMPLOYEE_NUMBER)

if not raw_employee_data:
    st.error(
        f"Employee record not found for employee code: {CURRENT_EMPLOYEE_NUMBER}. "
        "Please check that Odoo is passing the correct employee_code and that the employee exists in the configured HR data source."
    )
    st.stop()

employee_data = prepare_employee_data(raw_employee_data)

if not employee_data:
    st.error(f"Employee record not found for: {CURRENT_EMPLOYEE_NUMBER}")
    st.stop()

with st.sidebar:
    st.markdown("### Employee Chatbot")
    st.markdown(
        "Ask about your profile, payroll, attendance, bank details, task report, "
        "performance, request status, or tax details."
    )

    st.info(
        f"Current Employee: {employee_data['main'].get('employee_number')} "
        f"- {employee_data['main'].get('employee_name')}"
    )
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.input_counter += 1
        st.rerun()

    if URL_EMPLOYEE_CODE:
        st.caption("Employee context received from Odoo URL.")
    else:
        st.caption("Employee context loaded from configured fallback employee code.")

    sidebar_query = st.text_input("Search HR Help", placeholder="e.g. show my payroll")

    if st.button("Ask from Sidebar"):
        if sidebar_query.strip():
            user_q = sidebar_query.strip()
            st.session_state.messages.append({"role": "user", "content": user_q})
            answer = process_user_question(user_q, employee_data)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.rerun()

st.markdown(
    f"""
    <div class="summary-card">
        <strong>Employee:</strong> {not_available(employee_data['main'].get('employee_name'))}<br>
        <strong>Employee #:</strong> {not_available(employee_data['main'].get('employee_number'))}<br>
        <strong>Status:</strong> {not_available(employee_data['main'].get('status'))}<br>
        <strong>Designation:</strong> {not_available(employee_data['employee_record'].get('designation'))}
    </div>
    """,
    unsafe_allow_html=True,
)

button_rows = [
    [
        ("Profile", "Show my full profile"),
        ("Designation", "What is my designation?"),
        ("Bank", "Show my bank details"),
    ],
    [
        ("Attendance", "Show my attendance"),
        ("Payroll", "Show my payroll"),
        ("Task Report", "Show my task report status"),
    ],
    [
        ("HR Request", "Show my HR request status"),
        ("Performance", "Show my performance"),
        ("Tax Calculator", "Show my tax calculator"),
    ],
    [
        ("Tax Rates", "Show tax rates"),
    ],
]

for row in button_rows:
    cols = st.columns(3)

    for col, (label, query) in zip(cols, row):
        with col:
            if st.button(label, use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": query})
                answer = process_user_question(query, employee_data)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.markdown('<div class="custom-chat-wrap">', unsafe_allow_html=True)

input_key = f"employee_chat_text_input_{st.session_state.input_counter}"

with st.form(key=f"employee_chat_form_{st.session_state.input_counter}", clear_on_submit=True):
    input_col, send_col = st.columns([10, 1])

    with input_col:
        user_input = st.text_input(
            "Ask something about your HR record",
            label_visibility="collapsed",
            placeholder="Ask something about your HR record",
            key=input_key,
        )

    with send_col:
        send_now = st.form_submit_button("➜")

st.markdown("</div>", unsafe_allow_html=True)

if send_now and user_input.strip():
    user_q = user_input.strip()
    st.session_state.messages.append({"role": "user", "content": user_q})
    answer = process_user_question(user_q, employee_data)
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.input_counter += 1
    st.rerun()