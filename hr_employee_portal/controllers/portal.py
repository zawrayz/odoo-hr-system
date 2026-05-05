from datetime import datetime, time, timedelta, date
import calendar

from odoo import http, fields
from odoo.exceptions import ValidationError
from odoo.http import request
from werkzeug.urls import url_encode


class HrEmployeePortal(http.Controller):

    SICK_POLICY_DAYS = 10.0
    CASUAL_POLICY_DAYS = 20.0
    SICK_MONTHLY_EARN = round(SICK_POLICY_DAYS / 12.0, 2)
    CASUAL_MONTHLY_EARN = round(CASUAL_POLICY_DAYS / 12.0, 2)

    REQUEST_TYPE_OPTIONS = [
        ('short_leave', 'Request for Short Leave'),
        ('wfh', 'Request for WFH'),
        ('sick_leave', 'Request for Sick Leave'),
        ('casual_leave', 'Request for Casual Leave'),
    ]

    REQUEST_EMAIL_TO = 'zoraizzia9@gmail.com'

    ADMIN_PAYROLL_TAX_SLABS = [
        {
            'slab': 'Slab 1',
            'range_label': 'Taxable income does not exceed Rs600,000',
            'tax_rule': '0%',
        },
        {
            'slab': 'Slab 2',
            'range_label': '600,001 to 1,200,000',
            'tax_rule': '1% of the amount exceeding Rs600,000',
        },
        {
            'slab': 'Slab 3',
            'range_label': '1,200,001 to 2,200,000',
            'tax_rule': 'Rs6,000 + 11% of the amount exceeding 1,200,000',
        },
        {
            'slab': 'Slab 4',
            'range_label': '2,200,001 to 3,200,000',
            'tax_rule': 'Rs116,000 + 23% of the amount exceeding Rs2,200,000',
        },
        {
            'slab': 'Slab 5',
            'range_label': '3,200,001 to 4,100,000',
            'tax_rule': 'Rs346,000 + 30% of the amount exceeding Rs3,200,000',
        },
        {
            'slab': 'Slab 6',
            'range_label': 'Taxable income exceeds Rs4,100,000',
            'tax_rule': 'Rs616,000 + 35% of the amount exceeding Rs4,100,000',
        },
    ]

    # ---------------------------------------------------------
    # Helper: Check if user is HR Manager
    # ---------------------------------------------------------
    def _is_hr_manager(self):
        return request.env.user.has_group('hr.group_hr_manager')

    # ---------------------------------------------------------
    # Redirect /my safely for employee-linked users only
    # ---------------------------------------------------------
    @http.route('/my', type='http', auth='user', website=True)
    def redirect_my_portal(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        user = request.env.user
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)],
            limit=1
        )

        if employee:
            return request.redirect('/my/hr')

        return request.render('portal.portal_my_home', {})

    # ---------------------------------------------------------
    # Get logged in employee
    # ---------------------------------------------------------
    def _get_employee(self):
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)],
            limit=1
        )
        return employee

    # ---------------------------------------------------------
    # Format worked hours (1h 35m)
    # ---------------------------------------------------------
    def _format_hours(self, hours):
        if not hours:
            return "0h"

        total_minutes = int(round(hours * 60))
        hour_value = total_minutes // 60
        minute_value = total_minutes % 60

        if minute_value:
            return f"{hour_value}h {minute_value}m"
        return f"{hour_value}h"

    # ---------------------------------------------------------
    # Format amount safely
    # ---------------------------------------------------------
    def _to_amount(self, value):
        try:
            return round(float(value or 0.0), 2)
        except (TypeError, ValueError):
            return 0.0

    # ---------------------------------------------------------
    # Common page values
    # ---------------------------------------------------------
    def _prepare_portal_values(self, employee=None, extra_values=None):
        values = {
            'employee': employee,
            'is_hr_manager': self._is_hr_manager(),
            'request_type_options': self.REQUEST_TYPE_OPTIONS,
        }
        if extra_values:
            values.update(extra_values)
        return values

    # ---------------------------------------------------------
    # Redirect safely when employee is missing
    # ---------------------------------------------------------
    def _redirect_if_no_employee(self, employee):
        if not employee:
            return request.redirect('/my/hr/profile?missing_employee=1')
        return None

    # ---------------------------------------------------------
    # Parse month from query string (YYYY-MM)
    # ---------------------------------------------------------
    def _get_selected_month_date(self, month_value=None):
        if month_value:
            try:
                parsed = datetime.strptime(month_value, '%Y-%m').date()
                return parsed.replace(day=1)
            except ValueError:
                pass
        today = fields.Date.context_today(request.env.user)
        return today.replace(day=1)

    # ---------------------------------------------------------
    # Previous / Next month values
    # ---------------------------------------------------------
    def _get_month_navigation(self, month_start):
        previous_month_last_day = month_start - timedelta(days=1)
        next_month_first_day = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        return {
            'previous_month_value': previous_month_last_day.strftime('%Y-%m'),
            'next_month_value': next_month_first_day.strftime('%Y-%m'),
            'month_display': month_start.strftime('%B %Y'),
        }

    # ---------------------------------------------------------
    # Fiscal year helpers (July -> June)
    # ---------------------------------------------------------
    def _get_fiscal_year_bounds(self, target_date):
        if target_date.month >= 7:
            fy_start = date(target_date.year, 7, 1)
            fy_end = date(target_date.year + 1, 6, 30)
        else:
            fy_start = date(target_date.year - 1, 7, 1)
            fy_end = date(target_date.year, 6, 30)
        return fy_start, fy_end

    def _get_fiscal_year_label(self, target_date):
        fy_start, fy_end = self._get_fiscal_year_bounds(target_date)
        return f"FY-{str(fy_start.year)[-2:]}/{str(fy_end.year)[-2:]}"

    def _get_fiscal_year_code(self, target_date):
        fy_start, fy_end = self._get_fiscal_year_bounds(target_date)
        return f"{str(fy_start.year)[-2:]}/{str(fy_end.year)[-2:]}"

    def _get_fiscal_year_range_label(self, target_date):
        fy_start, fy_end = self._get_fiscal_year_bounds(target_date)
        return f"{fy_start.day} {fy_start.strftime('%B %Y')} to {fy_end.day} {fy_end.strftime('%B %Y')}"

    def _get_fiscal_year_month_starts(self, target_date):
        fy_start, _fy_end = self._get_fiscal_year_bounds(target_date)
        months = []
        current_month = fy_start
        for _i in range(12):
            months.append(current_month)
            current_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        return months

    def _get_fiscal_year_month_options(self, target_date):
        month_options = []
        for month_start in self._get_fiscal_year_month_starts(target_date):
            month_options.append({
                'value': month_start.strftime('%Y-%m'),
                'label': month_start.strftime('%B %Y'),
                'short_label': month_start.strftime('%b-%y'),
            })
        return month_options

    def _get_fiscal_year_context(self, target_date):
        fy_start, fy_end = self._get_fiscal_year_bounds(target_date)
        return {
            'fiscal_year_start': fy_start,
            'fiscal_year_end': fy_end,
            'fiscal_year_label': self._get_fiscal_year_label(target_date),
            'fiscal_year_code': self._get_fiscal_year_code(target_date),
            'fiscal_year_range_label': self._get_fiscal_year_range_label(target_date),
            'fiscal_year_month_options': self._get_fiscal_year_month_options(target_date),
        }

    # ---------------------------------------------------------
    # Payroll FY selection helpers
    # ---------------------------------------------------------
    def _get_payroll_fiscal_year_options(self):
        today = fields.Date.context_today(request.env.user)
        current_fy_start, _current_fy_end = self._get_fiscal_year_bounds(today)
        current_fy_start_year = current_fy_start.year

        options = []
        for start_year in range(current_fy_start_year - 2, current_fy_start_year + 1):
            end_year = start_year + 1
            options.append({
                'value': f'{start_year}-{end_year}',
                'label': f'{str(start_year)[-2:]}/{str(end_year)[-2:]}',
                'start_year': start_year,
                'end_year': end_year,
            })
        return options

    def _parse_payroll_fiscal_year_value(self, fy_value):
        if not fy_value:
            return False

        fy_value = str(fy_value).strip()

        try:
            if '-' in fy_value:
                parts = fy_value.split('-')
                if len(parts) == 2:
                    start_year = int(parts[0])
                    end_year = int(parts[1])
                    if end_year == start_year + 1:
                        return date(start_year, 7, 1), date(end_year, 6, 30)

            if '/' in fy_value:
                parts = fy_value.split('/')
                if len(parts) == 2:
                    start_two = int(parts[0])
                    end_two = int(parts[1])

                    if start_two <= 99 and end_two <= 99:
                        start_year = 2000 + start_two
                        end_year = 2000 + end_two

                        if end_year == start_year + 1:
                            return date(start_year, 7, 1), date(end_year, 6, 30)
        except (TypeError, ValueError):
            return False

        return False

    def _get_selected_payroll_period(self, fy_value=None, month_value=None):
        today = fields.Date.context_today(request.env.user)
        today_month = today.replace(day=1)

        parsed_fy = self._parse_payroll_fiscal_year_value(fy_value)
        parsed_month = self._get_selected_month_date(month_value) if month_value else False

        if parsed_fy:
            fy_start, fy_end = parsed_fy

            if parsed_month and fy_start <= parsed_month <= fy_end:
                selected_month = parsed_month
            else:
                if fy_start <= today_month <= fy_end:
                    selected_month = today_month
                else:
                    selected_month = fy_start
        else:
            if parsed_month:
                selected_month = parsed_month
                fy_start, fy_end = self._get_fiscal_year_bounds(selected_month)
            else:
                selected_month = today_month
                fy_start, fy_end = self._get_fiscal_year_bounds(selected_month)

        if selected_month < fy_start or selected_month > fy_end:
            selected_month = fy_start

        selected_fy_value = f'{fy_start.year}-{fy_end.year}'
        selected_fy_code = f'{str(fy_start.year)[-2:]}/{str(fy_end.year)[-2:]}'

        month_options = []
        current_month = fy_start
        for _i in range(12):
            month_options.append({
                'value': current_month.strftime('%Y-%m'),
                'label': current_month.strftime('%B %Y'),
                'short_label': current_month.strftime('%b-%y'),
            })
            current_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)

        fy_options = self._get_payroll_fiscal_year_options()

        return {
            'selected_month': selected_month,
            'selected_fy_start': fy_start,
            'selected_fy_end': fy_end,
            'selected_fy_value': selected_fy_value,
            'selected_fy_code': selected_fy_code,
            'selected_fy_label': selected_fy_code,
            'selected_fy_range_label': f'{fy_start.day} {fy_start.strftime("%B %Y")} to {fy_end.day} {fy_end.strftime("%B %Y")}',
            'fiscal_year_options': fy_options,
            'fiscal_year_month_options': month_options,
        }
    def _get_payroll_register_line(self, employee, selected_month):
        payroll_env = request.env['hr.payroll.register.line'].sudo()

        if not employee or not selected_month:
            return payroll_env

        month_start = selected_month.replace(day=1)

        payroll_line = payroll_env.search([
            ('employee_id', '=', employee.id),
            ('month_date', '=', month_start),
        ], limit=1)

        if payroll_line:
            return payroll_line

        employee_code = (employee.employee_code or '').strip()
        if employee_code:
            payroll_line = payroll_env.search([
                ('employee_code', '=', employee_code),
                ('month_date', '=', month_start),
            ], limit=1)
            if payroll_line:
                return payroll_line

        return payroll_env.browse()

    def _get_admin_payroll_register_lines(self, selected_month):
        if not selected_month:
            return request.env['hr.payroll.register.line'].sudo()

        month_start = selected_month.replace(day=1)
        return request.env['hr.payroll.register.line'].sudo().search([
            ('month_date', '=', month_start),
        ], order='employee_id asc')
    

    # ---------------------------------------------------------
    # Request helpers
    # ---------------------------------------------------------
    def _get_request_type_label(self, request_type):
        for option_value, option_label in self.REQUEST_TYPE_OPTIONS:
            if option_value == request_type:
                return option_label
        return ''

    def _parse_request_date(self, date_string):
        try:
            return datetime.strptime(date_string or '', '%Y-%m-%d').date()
        except ValueError:
            return False

    def _send_employee_request_email(self, employee, request_type, reason, date_from, date_to):
        if 'mail.mail' not in request.env:
            return False, 'Outgoing email is not available in this database yet.'

        request_type_label = self._get_request_type_label(request_type)
        employee_name = employee.name or 'Employee'
        employee_code = employee.employee_code or '-'
        department_name = employee.department_id.name or '-'
        designation_name = employee.job_id.name or '-'
        requester_email = request.env.user.email or employee.work_email or '-'

        mail_subject = f"HR Portal Request - {request_type_label} - {employee_name}"

        mail_body = f"""
            <div style="font-family: Arial, sans-serif; font-size: 14px; color: #222;">
                <h3 style="margin-bottom: 12px;">New HR Portal Request</h3>
                <table style="border-collapse: collapse; width: 100%; max-width: 700px;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Employee Name</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{employee_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Employee Code</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{employee_code}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Department</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{department_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Designation</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{designation_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Requester Email</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{requester_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Request Type</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{request_type_label}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{date_from}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{date_to}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; vertical-align: top;"><strong>Reason</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{reason}</td>
                    </tr>
                </table>
            </div>
        """

        mail_values = {
            'subject': mail_subject,
            'body_html': mail_body,
            'email_to': self.REQUEST_EMAIL_TO,
            'email_from': request.env.user.email or 'noreply@example.com',
            'reply_to': request.env.user.email or '',
        }

        mail = request.env['mail.mail'].sudo().create(mail_values)
        mail.send()

        return True, 'Your request has been sent successfully.'

    # ---------------------------------------------------------
    # Daily work report helpers
    # ---------------------------------------------------------
    def _get_valid_work_modes(self):
        return ['office', 'wfh', 'leave']

    def _build_redirect_url(self, base_path, params=None):
        params = params or {}
        clean_params = {}
        for key, value in params.items():
            if value in (False, None, ''):
                continue
            clean_params[key] = value

        if not clean_params:
            return base_path
        return '%s?%s' % (base_path, url_encode(clean_params))

    def _parse_portal_date(self, date_string):
        try:
            return datetime.strptime((date_string or '').strip(), '%Y-%m-%d').date()
        except ValueError:
            return False

    def _parse_portal_datetime_local(self, datetime_string):
        try:
            return datetime.strptime((datetime_string or '').strip(), '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            try:
                return datetime.strptime((datetime_string or '').strip(), '%Y-%m-%dT%H:%M')
            except ValueError:
                return False

    def _get_task_report_search_domain(self, employee_id=None, date_from=None, date_to=None):
        domain = []


        if employee_id:
            domain.append(('employee_id', '=', employee_id))

        if date_from:
            domain.append(('report_date', '>=', date_from))

        if date_to:
            domain.append(('report_date', '<=', date_to))

        return domain

    def _get_admin_performance_data(self, employee_id=None, date_from=None, date_to=None):
        performance_env = request.env['hr.daily.performance.plan'].sudo()
        employee_env = request.env['hr.employee'].sudo()

        domain = []

        if employee_id:
            domain.append(('employee_id', '=', employee_id))
        if date_from:
            domain.append(('plan_date', '>=', date_from))
        if date_to:
            domain.append(('plan_date', '<=', date_to))

        records = performance_env.search(domain, order='plan_date desc, id desc')
        employees = employee_env.search([], order='name asc')

        return {
            'employees': employees,
            'records': records,
        }

    def _get_valid_performance_priorities(self):
        return ['low', 'medium', 'high']

    def _get_valid_performance_statuses(self):
        return ['pending', 'underprocess', 'completed', 'hold']

    def _get_employee_performance_records(self, employee, date_from=None, date_to=None):
        if not employee:
            return request.env['hr.daily.performance.plan'].sudo()

        domain = [('employee_id', '=', employee.id)]

        if date_from:
            domain.append(('plan_date', '>=', date_from))
        if date_to:
            domain.append(('plan_date', '<=', date_to))

        return request.env['hr.daily.performance.plan'].sudo().search(
            domain,
            order='plan_date desc, id desc'
        )

    def _get_performance_search_domain(self, employee_id=None, date_from=None, date_to=None):
        domain = []

        if employee_id:
            domain.append(('employee_id', '=', employee_id))

        if date_from:
            domain.append(('plan_date', '>=', date_from))

        if date_to:
            domain.append(('plan_date', '<=', date_to))

        return domain

    def _get_all_performance_employees(self):
        return request.env['hr.employee'].sudo().search([], order='name asc')

        # ---------------------------------------------------------
    # Payroll helpers
    # ---------------------------------------------------------
    def _get_employee_payroll_period_label(self, selected_month):
        return selected_month.strftime('%B %Y')

    def _get_payroll_month_overview(self, selected_month):
        total_days_in_month = calendar.monthrange(selected_month.year, selected_month.month)[1]
        today = fields.Date.context_today(request.env.user)

        if selected_month.year == today.year and selected_month.month == today.month:
            elapsed_days = today.day
        else:
            elapsed_days = total_days_in_month

        payment_date = (selected_month + timedelta(days=32)).replace(day=5)
        fiscal_context = self._get_fiscal_year_context(selected_month)

        return {
            'month_label': selected_month.strftime('%b-%y'),
            'full_month_label': selected_month.strftime('%B %Y'),
            'payment_date': payment_date.strftime('%d-%b-%y'),
            'days_in_month_elapsed': elapsed_days,
            'days_in_month_total': total_days_in_month,
            'fiscal_year_label': fiscal_context['fiscal_year_label'],
            'fiscal_year_code': fiscal_context['fiscal_year_code'],
            'fiscal_year_range_label': fiscal_context['fiscal_year_range_label'],
        }

    def _get_payroll_register_line(self, employee, selected_month):
        if not employee or not selected_month:
            return request.env['hr.payroll.register.line']

        month_start = selected_month.replace(day=1)
        return request.env['hr.payroll.register.line'].sudo().search([
            ('employee_id', '=', employee.id),
            ('month_date', '=', month_start),
        ], limit=1)

    def _get_admin_payroll_register_lines(self, selected_month):
        if not selected_month:
            return request.env['hr.payroll.register.line'].sudo()

        month_start = selected_month.replace(day=1)
        return request.env['hr.payroll.register.line'].sudo().search([
            ('month_date', '=', month_start),
        ], order='employee_id asc')

    def _get_employee_payroll_data(self, employee, selected_month):
        payroll_line = self._get_payroll_register_line(employee, selected_month)
        payroll_overview = self._get_payroll_month_overview(selected_month)

        if not payroll_line:
            return {
                'period_label': self._get_employee_payroll_period_label(selected_month),
                'overview': payroll_overview,
                'fiscal_year_code': payroll_overview['fiscal_year_code'],
                'fiscal_year_range_label': payroll_overview['fiscal_year_range_label'],
                'has_payroll': False,
                'record': False,
                'earnings': {
                    'basic': 0.0,
                    'actual_basic_working': 0.0,
                    'medical_allowance': 0.0,
                    'advertised_salary': 0.0,
                    'project_salary': 0.0,
                    'bonus': 0.0,
                    'allowance': 0.0,
                    'total_earnings': 0.0,
                },
                'deductions': {
                    'income_tax': 0.0,
                    'other_deductions': 0.0,
                    'loans_from_cash': 0.0,
                    'total_deductions': 0.0,
                },
                'summary': {
                    'total': 0.0,
                    'total_round': 0.0,
                    'net_salary': 0.0,
                },
                'notes': {
                    'designation': '',
                    'payment_method': '',
                    'allowance_detail': '',
                    'period_label': '',
                    'paid_at': '',
                    'comments': '',
                    'payment_date': '',
                    'month_label': selected_month.strftime('%B %Y'),
                },
                'tax_slabs': self.ADMIN_PAYROLL_TAX_SLABS,
            }

        total_earnings = self._to_amount(
            payroll_line.basic_actual
            + payroll_line.medical_allowance
            + payroll_line.advertised_salary
            + payroll_line.project_salary
            + payroll_line.bonus
            + payroll_line.allowance
        )

        total_deductions = self._to_amount(
            payroll_line.income_tax_deduction
            + payroll_line.other_deductions
            + payroll_line.loans_from_cash
        )

        return {
            'period_label': payroll_line.month_label or self._get_employee_payroll_period_label(selected_month),
            'overview': payroll_overview,
            'fiscal_year_code': payroll_overview['fiscal_year_code'],
            'fiscal_year_range_label': payroll_overview['fiscal_year_range_label'],
            'has_payroll': True,
            'record': payroll_line,
            'earnings': {
                'basic': self._to_amount(payroll_line.basic_salary),
                'actual_basic_working': self._to_amount(payroll_line.basic_actual),
                'medical_allowance': self._to_amount(payroll_line.medical_allowance),
                'advertised_salary': self._to_amount(payroll_line.advertised_salary),
                'project_salary': self._to_amount(payroll_line.project_salary),
                'bonus': self._to_amount(payroll_line.bonus),
                'allowance': self._to_amount(payroll_line.allowance),
                'total_earnings': total_earnings,
            },
            'deductions': {
                'income_tax': self._to_amount(payroll_line.income_tax_deduction),
                'other_deductions': self._to_amount(payroll_line.other_deductions),
                'loans_from_cash': self._to_amount(payroll_line.loans_from_cash),
                'total_deductions': total_deductions,
            },
            'summary': {
                'total': self._to_amount(payroll_line.total),
                'total_round': self._to_amount(payroll_line.total_round),
                'net_salary': self._to_amount(payroll_line.total_salary),
            },
            'notes': {
                'designation': payroll_line.designation or '',
                'payment_method': payroll_line.payment_method or '',
                'allowance_detail': payroll_line.allowance_detail or '',
                'period_label': payroll_line.period_label or '',
                'paid_at': payroll_line.paid_at or '',
                'comments': payroll_line.comments or '',
                'payment_date': payroll_line.payment_date.strftime('%d-%b-%Y') if payroll_line.payment_date else '',
                'month_label': payroll_line.month_label or '',
            },
            'tax_slabs': self.ADMIN_PAYROLL_TAX_SLABS,
        }

    def _sum_row_values(self, rows, key):
        return self._to_amount(sum(self._to_amount(row.get(key, 0.0)) for row in rows))

    def _count_weekend_days(self, month_start, end_day):
        weekend_days = 0
        for day_number in range(1, end_day + 1):
            target_date = month_start.replace(day=day_number)
            if target_date.weekday() >= 5:
                weekend_days += 1
        return weekend_days

    def _get_admin_payroll_overview(self, selected_month):
        total_days_in_month = calendar.monthrange(selected_month.year, selected_month.month)[1]
        today = fields.Date.context_today(request.env.user)

        if selected_month.year == today.year and selected_month.month == today.month:
            elapsed_days = today.day
        else:
            elapsed_days = total_days_in_month

        holiday_weekend_days = self._count_weekend_days(selected_month, elapsed_days)
        work_days = max(elapsed_days - holiday_weekend_days, 0)

        payment_date = (selected_month + timedelta(days=32)).replace(day=5)
        fiscal_context = self._get_fiscal_year_context(selected_month)

        return {
            'month_label': selected_month.strftime('%b-%y'),
            'full_month_label': selected_month.strftime('%B %Y'),
            'payment_date': payment_date.strftime('%d-%b-%y'),
            'fiscal_year_label': fiscal_context['fiscal_year_label'],
            'fiscal_year_code': fiscal_context['fiscal_year_code'],
            'fiscal_year_range_label': fiscal_context['fiscal_year_range_label'],
            'work_days': work_days,
            'holiday_weekend_days': holiday_weekend_days,
            'days_in_month_elapsed': elapsed_days,
            'days_in_month_total': total_days_in_month,
        }

    def _get_admin_payroll_data(self, selected_month):
        payroll_lines = self._get_admin_payroll_register_lines(selected_month)

        rows = []
        for line in payroll_lines:
            rows.append({
                'employee_code': line.employee_code or '-',
                'employee_name': line.employee_id.name or line.employee_name_text or '-',
                'bank_name': line.payment_method or '-',
                'designation': line.designation or '-',
                'payment_method': line.payment_method or '-',
                'basic_salary': self._to_amount(line.basic_salary),
                'basic_actual': self._to_amount(line.basic_actual),
                'medical_allowance': self._to_amount(line.medical_allowance),
                'advertised_salary': self._to_amount(line.advertised_salary),
                'project_salary': self._to_amount(line.project_salary),
                'project_value': line.allowance_detail or '-',
                'bonus': self._to_amount(line.bonus),
                'for_value': line.period_label or '-',
                'overtime': 0.0,
                'ot_detail': '-',
                'taxable_income': self._to_amount(line.taxable_income),
                'yearly_income': self._to_amount(line.yearly_income),
                'income_tax_deduction': self._to_amount(line.income_tax_deduction),
                'other_deductions': self._to_amount(line.other_deductions),
                'deduction_for': line.comments or '-',
                'total': self._to_amount(line.total),
                'total_round': self._to_amount(line.total_round),
                'total_allowance': self._to_amount(line.allowance),
                'hr_cost_including_bonus': self._to_amount(line.total_salary),
                'hr_cost_rounded': self._to_amount(line.total_round),
                'payment_date': line.payment_date.strftime('%d-%b-%Y') if line.payment_date else '-',
                'month_label': line.month_label or '-',
            })

        totals = {
            'basic_salary': self._sum_row_values(rows, 'basic_salary'),
            'basic_actual': self._sum_row_values(rows, 'basic_actual'),
            'medical_allowance': self._sum_row_values(rows, 'medical_allowance'),
            'advertised_salary': self._sum_row_values(rows, 'advertised_salary'),
            'project_salary': self._sum_row_values(rows, 'project_salary'),
            'project_value': 0.0,
            'bonus': self._sum_row_values(rows, 'bonus'),
            'for_value': 0.0,
            'overtime': self._sum_row_values(rows, 'overtime'),
            'ot_detail': 0.0,
            'taxable_income': self._sum_row_values(rows, 'taxable_income'),
            'yearly_income': self._sum_row_values(rows, 'yearly_income'),
            'income_tax_deduction': self._sum_row_values(rows, 'income_tax_deduction'),
            'other_deductions': self._sum_row_values(rows, 'other_deductions'),
            'deduction_for': 0.0,
            'total': self._sum_row_values(rows, 'total'),
            'total_round': self._sum_row_values(rows, 'total_round'),
            'total_allowance': self._sum_row_values(rows, 'total_allowance'),
            'hr_cost_including_bonus': self._sum_row_values(rows, 'hr_cost_including_bonus'),
            'hr_cost_rounded': self._sum_row_values(rows, 'hr_cost_rounded'),
        }

        calculator_input = rows[0]['total_round'] if rows else 0.0
        calculator_medical = rows[0]['medical_allowance'] if rows else 0.0
        calculator_taxable_yearly = self._to_amount(calculator_input * 12.0)
        calculator_monthly_tax = rows[0]['income_tax_deduction'] if rows else 0.0
        calculator_yearly_tax = self._to_amount(calculator_monthly_tax * 12.0)

        overview = self._get_admin_payroll_overview(selected_month)

        return {
            'overview': overview,
            'fiscal_year_code': overview['fiscal_year_code'],
            'fiscal_year_range_label': overview['fiscal_year_range_label'],
            'rows': rows,
            'totals': totals,
            'tax_slabs': self.ADMIN_PAYROLL_TAX_SLABS,
            'calculator': {
                'put_net_salary': calculator_input,
                'medical_allowance': calculator_medical,
                'taxable_income_yearly': calculator_taxable_yearly,
                'monthly_tax': calculator_monthly_tax,
                'yearly_tax': calculator_yearly_tax,
            },
        }

    # ---------------------------------------------------------
    # Get leave code for a specific date
    # ---------------------------------------------------------
    def _get_leave_code_for_date(self, employee, target_date):
        leave_domain = [
            ('employee_id', '=', employee.id),
            ('state', 'in', ['validate', 'validate1']),
            ('request_date_from', '<=', target_date),
            ('request_date_to', '>=', target_date),
        ]
        leave = request.env['hr.leave'].sudo().search(leave_domain, limit=1)

        if not leave:
            target_start = datetime.combine(target_date, time.min)
            target_end = datetime.combine(target_date, time.max)
            leave = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['validate', 'validate1']),
                ('date_from', '<=', target_end),
                ('date_to', '>=', target_start),
            ], limit=1)

        if not leave:
            return False

        leave_name = (leave.holiday_status_id.name or '').strip().lower()

        if 'sick' in leave_name:
            return 'S'
        if 'casual' in leave_name:
            return 'C'
        if 'unpaid' in leave_name:
            return 'U'

        return 'U'

    # ---------------------------------------------------------
    # Check holiday/weekend/public holiday
    # ---------------------------------------------------------
    def _is_holiday_for_date(self, employee, target_date):
        if target_date.weekday() >= 5:
            return True

        if 'resource.calendar.leaves' in request.env:
            day_start = datetime.combine(target_date, time.min)
            day_end = datetime.combine(target_date, time.max)

            holiday_domain = [
                ('date_from', '<=', day_end),
                ('date_to', '>=', day_start),
                '|',
                ('resource_id', '=', False),
                ('resource_id', '=', employee.resource_id.id),
            ]
            holiday_exists = request.env['resource.calendar.leaves'].sudo().search_count(holiday_domain)
            if holiday_exists:
                return True

        return False

    # ---------------------------------------------------------
    # Get daily work report record for a specific date
    # ---------------------------------------------------------
    def _get_daily_report_for_date(self, employee, target_date):
        if 'hr.daily.work.report' not in request.env:
            return False

        report = request.env['hr.daily.work.report'].sudo().search([
            ('employee_id', '=', employee.id),
            ('report_date', '=', target_date),
            ('state', 'in', ['submitted', 'approved']),
        ], limit=1)

        return report or False

    # ---------------------------------------------------------
    # Check if submitted late
    # ---------------------------------------------------------
    def _is_late_submission(self, report):
        if not report or not report.create_date or not report.report_date:
            return False

        timestamp_source = report.submitted_at or report.create_date
        local_dt = fields.Datetime.context_timestamp(report, timestamp_source)
        report_date = report.report_date

        if local_dt.date() > report_date:
            return True

        if local_dt.date() == report_date and local_dt.hour >= 18:
            return True

        return False
    def _get_attendance_register_map(self, employee, month_start):
        register_map = {}
        overtime_days = set()

        if 'hr.attendance.register.line' not in request.env or not employee:
            return register_map, overtime_days

        total_days = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=total_days)

        register_lines = request.env['hr.attendance.register.line'].sudo().search([
            ('employee_id', '=', employee.id),
            ('attendance_date', '>=', month_start),
            ('attendance_date', '<=', month_end),
        ], order='attendance_date asc')

        for line in register_lines:
            register_map[line.attendance_date] = line.attendance_code
            if line.attendance_code == 'OT':
                overtime_days.add(line.attendance_date)

        return register_map, overtime_days

    # ---------------------------------------------------------
    # Build attendance matrix row for selected month
    # ---------------------------------------------------------
    def _build_attendance_matrix(self, employee, month_start):
        total_days = calendar.monthrange(month_start.year, month_start.month)[1]
        days = []
        summary = {
            'total': total_days,
            'P': 0,
            'R': 0,
            'H': 0,
            'S': 0,
            'C': 0,
            'U': 0,
            'D': 0,
            'OT': 0,
        }

        register_map, overtime_days = self._get_attendance_register_map(employee, month_start)

        for day_number in range(1, total_days + 1):
            target_date = month_start.replace(day=day_number)
            code = register_map.get(target_date, '-')
            title_parts = [target_date.strftime('%d %b %Y')]

            if code == 'P':
                title_parts.append('Present')
            elif code == 'R':
                title_parts.append('Remote / WFH')
            elif code == 'H':
                title_parts.append('Holiday')
            elif code == 'S':
                title_parts.append('Sick Leave')
            elif code == 'C':
                title_parts.append('Casual Leave')
            elif code == 'U':
                title_parts.append('Unpaid Leave')
            elif code == 'D':
                title_parts.append('Late Submission')
            elif code == 'OT':
                title_parts.append('Overtime')
            else:
                title_parts.append('No Record')

            if code in summary:
                summary[code] += 1

            if target_date in overtime_days:
                summary['OT'] += 1

            days.append({
                'day_number': day_number,
                'weekday_short': target_date.strftime('%a'),
                'code': code,
                'title': ' | '.join(title_parts),
                'is_weekend': target_date.weekday() >= 5,
            })

        return {
            'fiscal_year': self._get_fiscal_year_label(month_start),
            'fiscal_year_code': self._get_fiscal_year_code(month_start),
            'month_label': month_start.strftime('%b %Y'),
            'employee_name': employee.name or '-',
            'days': days,
            'summary': summary,
        }
    # ---------------------------------------------------------
    # Leave helpers
    # ---------------------------------------------------------
    def _get_leave_date_range(self, leave):
        date_from = leave.request_date_from or False
        date_to = leave.request_date_to or False

        if not date_from and leave.date_from:
            date_from = leave.date_from.date()
        if not date_to and leave.date_to:
            date_to = leave.date_to.date()

        return date_from, date_to

    def _calculate_overlap_days(self, range_start, range_end, month_start, month_end):
        overlap_start = max(range_start, month_start)
        overlap_end = min(range_end, month_end)
        if overlap_start > overlap_end:
            return 0.0
        return float((overlap_end - overlap_start).days + 1)

    def _sum_leave_days_for_month(self, employee, month_start, leave_keyword):
        total_days = 0.0
        month_end = month_start.replace(
            day=calendar.monthrange(month_start.year, month_start.month)[1]
        )

        leave_records = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['validate', 'validate1']),
            ('request_date_from', '<=', month_end),
            ('request_date_to', '>=', month_start),
        ])

        for leave in leave_records:
            leave_name = (leave.holiday_status_id.name or '').strip().lower()
            if leave_keyword not in leave_name:
                continue

            leave_start, leave_end = self._get_leave_date_range(leave)
            if not leave_start or not leave_end:
                continue

            total_days += self._calculate_overlap_days(leave_start, leave_end, month_start, month_end)

        return round(total_days, 2)

    # ---------------------------------------------------------
    # WFH / Late data helpers
    # ---------------------------------------------------------
    def _count_wfh_for_month(self, employee, month_start):
        if 'hr.daily.work.report' not in request.env:
            return 0

        month_end = month_start.replace(
            day=calendar.monthrange(month_start.year, month_start.month)[1]
        )

        return request.env['hr.daily.work.report'].sudo().search_count([
            ('employee_id', '=', employee.id),
            ('report_date', '>=', month_start),
            ('report_date', '<=', month_end),
            ('work_mode', '=', 'wfh'),
            ('state', 'in', ['submitted', 'approved']),
        ])

    def _count_late_reports_for_month(self, employee, month_start):
        if 'hr.daily.work.report' not in request.env:
            return 0

        month_end = month_start.replace(
            day=calendar.monthrange(month_start.year, month_start.month)[1]
        )

        reports = request.env['hr.daily.work.report'].sudo().search([
            ('employee_id', '=', employee.id),
            ('report_date', '>=', month_start),
            ('report_date', '<=', month_end),
            ('state', 'in', ['submitted', 'approved']),
        ])

        return len(reports.filtered(lambda rec: self._is_late_submission(rec)))

    # ---------------------------------------------------------
    # FY attendance summary ledger
    # ---------------------------------------------------------
    def _build_attendance_summary_ledger(self, employee, selected_month):
        months = self._get_fiscal_year_month_starts(selected_month)
        fiscal_year_label = self._get_fiscal_year_label(selected_month)

        sick_opening = 0.0
        casual_opening = 0.0
        rows = []

        total_sick_availed = 0.0
        total_sick_earned = 0.0
        total_casual_availed = 0.0
        total_casual_earned = 0.0
        total_wfh = 0
        total_late_data = 0

        for month_start in months:
            month_is_active = month_start <= selected_month

            sick_earned = self.SICK_MONTHLY_EARN if month_is_active else 0.0
            casual_earned = self.CASUAL_MONTHLY_EARN if month_is_active else 0.0

            sick_availed = self._sum_leave_days_for_month(employee, month_start, 'sick') if month_is_active else 0.0
            casual_availed = self._sum_leave_days_for_month(employee, month_start, 'casual') if month_is_active else 0.0
            wfh_count = self._count_wfh_for_month(employee, month_start) if month_is_active else 0
            late_data_count = self._count_late_reports_for_month(employee, month_start) if month_is_active else 0

            sick_closing = round(sick_opening + sick_earned - sick_availed, 2)
            casual_closing = round(casual_opening + casual_earned - casual_availed, 2)

            rows.append({
                'month_label': month_start.strftime('%b %Y'),
                'month_value': month_start.strftime('%Y-%m'),
                'sick_opening': round(sick_opening, 2),
                'sick_availed': round(sick_availed, 2),
                'sick_earned': round(sick_earned, 2),
                'sick_closing': round(sick_closing, 2),
                'casual_opening': round(casual_opening, 2),
                'casual_availed': round(casual_availed, 2),
                'casual_earned': round(casual_earned, 2),
                'casual_closing': round(casual_closing, 2),
                'wfh_count': wfh_count,
                'late_data_count': late_data_count,
                'is_selected_month': month_start == selected_month,
            })

            total_sick_availed += sick_availed
            total_sick_earned += sick_earned
            total_casual_availed += casual_availed
            total_casual_earned += casual_earned
            total_wfh += wfh_count
            total_late_data += late_data_count

            sick_opening = sick_closing
            casual_opening = casual_closing

        balance_row = {
            'sick_opening': round(rows[-1]['sick_opening'] if rows else 0.0, 2),
            'sick_availed': round(total_sick_availed, 2),
            'sick_earned': round(total_sick_earned, 2),
            'sick_closing': round(rows[-1]['sick_closing'] if rows else 0.0, 2),
            'casual_opening': round(rows[-1]['casual_opening'] if rows else 0.0, 2),
            'casual_availed': round(total_casual_availed, 2),
            'casual_earned': round(total_casual_earned, 2),
            'casual_closing': round(rows[-1]['casual_closing'] if rows else 0.0, 2),
            'wfh_count': total_wfh,
            'late_data_count': total_late_data,
        }

        return {
            'fiscal_year_label': fiscal_year_label,
            'fiscal_year_code': self._get_fiscal_year_code(selected_month),
            'fiscal_year_range_label': self._get_fiscal_year_range_label(selected_month),
            'policy_sick_leaves': self.SICK_POLICY_DAYS,
            'policy_casual_leaves': self.CASUAL_POLICY_DAYS,
            'rows': rows,
            'balance_row': balance_row,
        }
    def _get_present_today_from_register(self):
        today = fields.Date.context_today(request.env.user)

        register_lines = request.env['hr.attendance.register.line'].sudo().search([
            ('attendance_date', '=', today),
            ('attendance_code', 'in', ['P', 'R']),
    ])

        employee_ids = register_lines.mapped('employee_id').ids
        return len(set(employee_ids))

    # ---------------------------------------------------------
    # Attendance logs helper
    # ---------------------------------------------------------
    def _get_attendance_logs(self, employee):
        attendance_display = []
        if not employee:
            return attendance_display

        attendances = request.env['hr.attendance'].sudo().search(
            [('employee_id', '=', employee.id)],
            order='check_in desc'
        )

        for att in attendances:
            attendance_display.append({
                'check_in': att.check_in,
                'check_out': att.check_out,
                'worked_hours': self._format_hours(att.worked_hours),
            })

        return attendance_display
    @http.route('/my/hr/performance', type='http', auth='user', website=True)
    def my_hr_performance(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin/performance')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        date_from = self._parse_portal_date(kwargs.get('date_from'))
        date_to = self._parse_portal_date(kwargs.get('date_to'))

        performance_records = self._get_employee_performance_records(
            employee,
            date_from=date_from,
            date_to=date_to,
        )

        values = self._prepare_portal_values(employee, {
            'performance_records': performance_records,
            'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
            'performance_status': (kwargs.get('performance_status') or '').strip(),
            'performance_message': (kwargs.get('performance_message') or '').strip(),
        })
        return request.render('hr_employee_portal.hr_employee_performance_page', values)

    @http.route('/my/hr/performance/submit', type='http', auth='user', methods=['POST'], website=True)
    def my_hr_performance_submit(self, **post):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin/performance')

        employee = self._get_employee()
        if not employee:
            redirect_url = self._build_redirect_url('/my/hr', {
                'performance_status': 'error',
                'performance_message': 'Employee record not found.',
            })
            return request.redirect(redirect_url)

        if 'hr.daily.performance.plan' not in request.env:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Performance module is not available.',
            })
            return request.redirect(redirect_url)

        plan_date = self._parse_portal_date(post.get('plan_date'))
        task_id = (post.get('task_id') or '').strip()
        project_name = (post.get('project_name') or '').strip()
        task_description = (post.get('task_description') or '').strip()
        priority_level = (post.get('priority_level') or '').strip()
        status = (post.get('status') or '').strip()

        if not plan_date:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Please enter a valid date.',
            })
            return request.redirect(redirect_url)

        if not task_id or not project_name or not task_description:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Task ID, Project, and Task Description are required.',
            })
            return request.redirect(redirect_url)

        if priority_level not in self._get_valid_performance_priorities():
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Please select a valid priority level.',
            })
            return request.redirect(redirect_url)

        if status not in self._get_valid_performance_statuses():
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Please select a valid status.',
            })
            return request.redirect(redirect_url)

        try:
            request.env['hr.daily.performance.plan'].sudo().create({
                'employee_id': employee.id,
                'plan_date': plan_date,
                'task_id': task_id,
                'project_name': project_name,
                'task_description': task_description,
                'priority_level': priority_level,
                'status': status,
            })
        except ValidationError as error:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': str(error),
            })
            return request.redirect(redirect_url)
        except Exception:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Performance record could not be created.',
            })
            return request.redirect(redirect_url)

        redirect_url = self._build_redirect_url('/my/hr/performance', {
            'performance_status': 'success',
            'performance_message': 'Performance record created successfully.',
        })
        return request.redirect(redirect_url)

    @http.route('/my/hr/performance/update', type='http', auth='user', methods=['POST'], website=True)
    def my_hr_performance_update(self, **post):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin/performance')

        employee = self._get_employee()
        if not employee:
            return request.redirect('/my/hr')

        record_id_raw = (post.get('record_id') or '').strip()
        try:
            record_id = int(record_id_raw)
        except (TypeError, ValueError):
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Invalid performance record.',
            })
            return request.redirect(redirect_url)

        record = request.env['hr.daily.performance.plan'].sudo().browse(record_id).exists()
        if not record or record.employee_id.id != employee.id:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'You can only edit your own performance records.',
            })
            return request.redirect(redirect_url)

        plan_date = self._parse_portal_date(post.get('plan_date'))
        task_id = (post.get('task_id') or '').strip()
        project_name = (post.get('project_name') or '').strip()
        task_description = (post.get('task_description') or '').strip()
        priority_level = (post.get('priority_level') or '').strip()
        status = (post.get('status') or '').strip()

        if not plan_date or not task_id or not project_name or not task_description:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'All editable fields are required.',
            })
            return request.redirect(redirect_url)

        if priority_level not in self._get_valid_performance_priorities():
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Invalid priority level selected.',
            })
            return request.redirect(redirect_url)

        if status not in self._get_valid_performance_statuses():
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Invalid status selected.',
            })
            return request.redirect(redirect_url)

        try:
            record.with_context(employee_portal_edit=True).write({
                'plan_date': plan_date,
                'task_id': task_id,
                'project_name': project_name,
                'task_description': task_description,
                'priority_level': priority_level,
                'status': status,
            })
        except ValidationError as error:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': str(error),
            })
            return request.redirect(redirect_url)
        except Exception:
            redirect_url = self._build_redirect_url('/my/hr/performance', {
                'performance_status': 'error',
                'performance_message': 'Performance record could not be updated.',
            })
            return request.redirect(redirect_url)

        redirect_url = self._build_redirect_url('/my/hr/performance', {
            'performance_status': 'success',
            'performance_message': 'Performance record updated successfully.',
        })
        return request.redirect(redirect_url)

    # =========================================================
    # EMPLOYEE: Dashboard Request Submit
    # =========================================================
    @http.route('/my/hr/request/submit', type='http', auth='user', website=True, methods=['POST'])
    def my_hr_request_submit(self, **post):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        if not employee:
            return request.redirect('/my/hr?request_status=error&request_message=Employee+record+not+found')

        request_type = (post.get('request_type') or '').strip()
        reason = (post.get('reason') or '').strip()
        date_from_raw = (post.get('date_from') or '').strip()
        date_to_raw = (post.get('date_to') or '').strip()

        valid_request_types = [item[0] for item in self.REQUEST_TYPE_OPTIONS]

        if request_type not in valid_request_types:
            return request.redirect('/my/hr?request_status=error&request_message=Please+select+a+valid+request+type')

        if not reason:
            return request.redirect('/my/hr?request_status=error&request_message=Reason+is+required')

        date_from = self._parse_request_date(date_from_raw)
        date_to = self._parse_request_date(date_to_raw)

        if not date_from or not date_to:
            return request.redirect('/my/hr?request_status=error&request_message=Please+enter+valid+from+and+to+dates')

        if date_to < date_from:
            return request.redirect('/my/hr?request_status=error&request_message=To+date+cannot+be+earlier+than+from+date')

        try:
            email_sent, message = self._send_employee_request_email(
                employee=employee,
                request_type=request_type,
                reason=reason,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception:
            email_sent = False
            message = 'Request could not be sent. Please contact the administrator.'

        if email_sent:
            return request.redirect('/my/hr?request_status=success&request_message=Request+sent+successfully')

        safe_message = (message or 'Request could not be sent').replace(' ', '+')
        return request.redirect(f'/my/hr?request_status=error&request_message={safe_message}')

    # =========================================================
    # EMPLOYEE: HR Dashboard
    # =========================================================
    @http.route('/my/hr', type='http', auth='user', website=True)
    def my_hr_dashboard(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        attendance_count = 0
        leave_count = 0

        if employee:
            attendance_count = request.env['hr.attendance'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])
            leave_count = request.env['hr.leave'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])

        values = self._prepare_portal_values(employee, {
            'attendance_count': attendance_count,
            'leave_count': leave_count,
            'document_count': 0,
            'request_status': kwargs.get('request_status', ''),
            'request_message': kwargs.get('request_message', ''),
        })
        return request.render('hr_employee_portal.hr_employee_portal_page', values)

    # ---------------------------------------------------------
    # EMPLOYEE: Profile Pages
    # ---------------------------------------------------------
    @http.route('/my/hr/profile', type='http', auth='user', website=True)
    def my_hr_profile(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        missing_employee = True if kwargs.get('missing_employee') else False
        values = self._prepare_portal_values(employee, {
            'missing_employee': missing_employee,
        })
        return request.render('hr_employee_portal.hr_employee_profile_page', values)

    @http.route('/my/hr/profile/employee-record', type='http', auth='user', website=True)
    def my_hr_profile_employee_record(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        return request.render(
            'hr_employee_portal.hr_employee_profile_employee_record_page',
            self._prepare_portal_values(employee)
        )

    @http.route('/my/hr/profile/bank-account', type='http', auth='user', website=True)
    def my_hr_profile_bank_account(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        return request.render(
            'hr_employee_portal.hr_employee_profile_bank_account_page',
            self._prepare_portal_values(employee)
        )

    @http.route('/my/hr/profile/personal-details', type='http', auth='user', website=True)
    def my_hr_profile_personal_details(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        return request.render(
            'hr_employee_portal.hr_employee_profile_personal_details_page',
            self._prepare_portal_values(employee)
        )

    @http.route('/my/hr/profile/emergency-contact', type='http', auth='user', website=True)
    def my_hr_profile_emergency_contact(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        return request.render(
            'hr_employee_portal.hr_employee_profile_emergency_contact_page',
            self._prepare_portal_values(employee)
        )

    @http.route('/my/hr/profile/employment-history', type='http', auth='user', website=True)
    def my_hr_profile_employment_history(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        return request.render(
            'hr_employee_portal.hr_employee_profile_employment_history_page',
            self._prepare_portal_values(employee)
        )
    def _get_employee_attendance_fy_summary(self, employee, selected_month):
        summary = {
            'sick_opening': 0.0,
            'sick_availed': 0.0,
            'sick_earned': 0.0,
            'sick_closing': 0.0,
            'casual_opening': 0.0,
            'casual_availed': 0.0,
            'casual_earned': 0.0,
            'casual_closing': 0.0,
            'wfh_total': 0,
            'late_data_total': 0,
            'selected_month_code': selected_month.strftime('%Y-%m'),
            'selected_month_label': selected_month.strftime('%b %Y'),
        }

        if not employee:
            return summary

        payroll_period = self._get_selected_payroll_period(
            fy_value=None,
            month_value=selected_month.strftime('%Y-%m'),
        )
        fy_start = payroll_period['selected_fy_start']
        fy_end = payroll_period['selected_fy_end']

        register_env = request.env['hr.attendance.register.line'].sudo()
        register_lines = register_env.search([
            ('employee_id', '=', employee.id),
            ('attendance_date', '>=', fy_start),
            ('attendance_date', '<=', fy_end),
        ], order='attendance_date asc')

        leave_env = request.env['hr.leave'].sudo()
        sick_leaves = leave_env.search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('request_date_from', '>=', fy_start),
            ('request_date_from', '<=', fy_end),
        ])

        sick_availed = 0.0
        casual_availed = 0.0
        for leave in sick_leaves:
            leave_name = (leave.holiday_status_id.name or '').strip().lower()
            days = leave.number_of_days or 0.0
            if 'sick' in leave_name:
                sick_availed += days
            elif 'casual' in leave_name:
                casual_availed += days

        sick_yearly_policy = 10.0
        casual_yearly_policy = 20.0

        sick_monthly_earned = round(sick_yearly_policy / 12.0, 2)
        casual_monthly_earned = round(casual_yearly_policy / 12.0, 2)

        months_elapsed = ((selected_month.year - fy_start.year) * 12) + (selected_month.month - fy_start.month) + 1
        months_elapsed = max(1, min(months_elapsed, 12))

        sick_earned_total = round(sick_monthly_earned * months_elapsed, 2)
        casual_earned_total = round(casual_monthly_earned * months_elapsed, 2)

        summary.update({
            'sick_opening': round(max(sick_earned_total - sick_monthly_earned, 0.0), 2),
            'sick_availed': round(sick_availed, 2),
            'sick_earned': sick_monthly_earned,
            'sick_closing': round(max(sick_earned_total - sick_availed, 0.0), 2),
            'casual_opening': round(max(casual_earned_total - casual_monthly_earned, 0.0), 2),
            'casual_availed': round(casual_availed, 2),
            'casual_earned': casual_monthly_earned,
            'casual_closing': round(max(casual_earned_total - casual_availed, 0.0), 2),
            'wfh_total': len(register_lines.filtered(lambda l: l.attendance_code == 'R')),
            'late_data_total': len(register_lines.filtered(lambda l: l.attendance_code == 'D')),
        })
        return summary

    # ---------------------------------------------------------
    # EMPLOYEE: Attendance Page
    # ---------------------------------------------------------
        # ---------------------------------------------------------
    # EMPLOYEE: Attendance Page
    # ---------------------------------------------------------
    @http.route('/my/hr/attendance', type='http', auth='user', website=True)
    def my_hr_attendance(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        fy_value = (kwargs.get('fy') or '').strip()
        month_value = (kwargs.get('month') or '').strip()

        attendance_period = self._get_selected_payroll_period(
            fy_value=fy_value,
            month_value=month_value,
        )
        selected_month = attendance_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)

        attendance_matrix_row = self._build_attendance_matrix(employee, selected_month)
        attendance_days = attendance_matrix_row['days']
        attendance_display = self._get_attendance_logs(employee)
        attendance_fy_summary = self._get_employee_attendance_fy_summary(employee, selected_month)

        values = self._prepare_portal_values(employee, {
            'attendance_matrix_row': attendance_matrix_row,
            'attendance_days': attendance_days,
            'attendances': attendance_display,
            'month_display': month_navigation.get('month_display', ''),
            'previous_month_value': month_navigation.get('previous_month_value', ''),
            'next_month_value': month_navigation.get('next_month_value', ''),
            'selected_month_value': selected_month.strftime('%Y-%m'),
            'attendance_fy_summary': attendance_fy_summary,
            'fiscal_year_label': f"FY-{attendance_period['selected_fy_code']}",
            'fiscal_year_code': attendance_period['selected_fy_code'],
            'fiscal_year_range_label': attendance_period['selected_fy_range_label'],
            'fiscal_year_month_options': attendance_period['fiscal_year_month_options'],
            'fiscal_year_options': attendance_period['fiscal_year_options'],
            'selected_fiscal_year_value': attendance_period['selected_fy_value'],
            'selected_fiscal_year_code': attendance_period['selected_fy_code'],
        })

        return request.render('hr_employee_portal.hr_employee_attendance_page', values)
    # ---------------------------------------------------------
    # EMPLOYEE: Daily Work Report
    # ---------------------------------------------------------
    @http.route('/my/hr/daily-work-report', type='http', auth='user', website=True)
    def my_hr_daily_work_report(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        redirect_response = self._redirect_if_no_employee(employee)
        if redirect_response:
            return redirect_response

        today = fields.Date.context_today(request.env.user)
        existing_report = False

        if 'hr.daily.work.report' in request.env:
            existing_report = request.env['hr.daily.work.report'].sudo().search([
                ('employee_id', '=', employee.id),
                ('report_date', '=', today),
            ], limit=1)

        report_status = (kwargs.get('report_status') or '').strip()
        report_message = (kwargs.get('report_message') or '').strip()
        success = True if report_status == 'success' else False

        values = self._prepare_portal_values(employee, {
            'today': today,
            'existing_report': existing_report,
            'success': success,
            'report_status': report_status,
            'report_message': report_message,
        })
        return request.render('hr_employee_portal.hr_employee_daily_work_report_page', values)

    @http.route('/my/hr/daily-work-report/submit', type='http', auth='user', methods=['POST'], website=True)
    def my_hr_daily_work_report_submit(self, **post):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        if not employee:
            redirect_url = self._build_redirect_url('/my/hr', {
                'report_status': 'error',
                'report_message': 'Employee record not found.',
            })
            return request.redirect(redirect_url)

        if 'hr.daily.work.report' not in request.env:
            redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
                'report_status': 'error',
                'report_message': 'Daily Work Report module is not available.',
            })
            return request.redirect(redirect_url)

        work_mode = (post.get('work_mode') or '').strip()
        task_report = (post.get('task_report') or '').strip()
        report_date = fields.Date.context_today(request.env.user)

        valid_work_modes = self._get_valid_work_modes()
        if work_mode not in valid_work_modes:
            redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
                'report_status': 'error',
                'report_message': 'Please select a valid work mode.',
            })
            return request.redirect(redirect_url)

        if not task_report:
            redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
                'report_status': 'error',
                'report_message': 'Task Report is required.',
            })
            return request.redirect(redirect_url)

        existing_report = request.env['hr.daily.work.report'].sudo().search([
            ('employee_id', '=', employee.id),
            ('report_date', '=', report_date),
        ], limit=1)
        if existing_report:
            redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
                'report_status': 'error',
                'report_message': 'You have already submitted your report for today.',
            })
            return request.redirect(redirect_url)

        try:
            request.env['hr.daily.work.report'].sudo().with_context(
                enforce_employee_portal_rule=True
            ).create({
                'employee_id': employee.id,
                'report_date': report_date,
                'work_mode': work_mode,
                'task_report': task_report,
                'state': 'submitted',
                'submitted_at': fields.Datetime.now(),
            })
        except ValidationError as error:
            redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
                'report_status': 'error',
                'report_message': str(error),
            })
            return request.redirect(redirect_url)
        except Exception:
            redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
                'report_status': 'error',
                'report_message': 'Report could not be submitted. Please contact HR.',
            })
            return request.redirect(redirect_url)

        redirect_url = self._build_redirect_url('/my/hr/daily-work-report', {
            'report_status': 'success',
            'report_message': 'Daily work report submitted successfully.',
        })
        return request.redirect(redirect_url)
    @http.route('/my/hr/admin/performance', type='http', auth='user', website=True)
    def my_hr_admin_performance(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        performance_env = request.env['hr.daily.performance.plan'].sudo()
        employee_env = request.env['hr.employee'].sudo()

        employee_id_raw = (kwargs.get('employee_id') or '').strip()
        selected_employee_id = False
        if employee_id_raw:
            try:
                selected_employee_id = int(employee_id_raw)
            except (TypeError, ValueError):
                selected_employee_id = False

        date_from = self._parse_portal_date(kwargs.get('date_from'))
        date_to = self._parse_portal_date(kwargs.get('date_to'))

        domain = self._get_performance_search_domain(
            employee_id=selected_employee_id,
            date_from=date_from,
            date_to=date_to,
    )

        try:
            page = int(kwargs.get('page') or 1)
        except (TypeError, ValueError):
            page = 1

        page = max(page, 1)
        per_page = 20
        offset = (page - 1) * per_page

        performance_total = performance_env.search_count(domain)

        performance_records = performance_env.search(
            domain,
            order='plan_date desc, id desc',
            limit=per_page,
            offset=offset,
    )

        page_count = max((performance_total + per_page - 1) // per_page, 1)

        performance_start = offset + 1 if performance_total else 0
        performance_end = min(offset + per_page, performance_total)

        base_params = {
            'employee_id': selected_employee_id,
            'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
    }

        previous_page_url = False
        next_page_url = False

        if page > 1:
            previous_params = dict(base_params)
            previous_params['page'] = page - 1
            previous_page_url = self._build_redirect_url('/my/hr/admin/performance', previous_params)

        if page < page_count:
            next_params = dict(base_params)
            next_params['page'] = page + 1
            next_page_url = self._build_redirect_url('/my/hr/admin/performance', next_params)

        employees = employee_env.search([], order='name asc')

        return request.render(
            'hr_employee_portal.hr_admin_performance_page',
            self._prepare_portal_values(None, {
                'performance_records': performance_records,
                'employees': employees,
                'selected_employee_id': selected_employee_id,
                'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
                'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
                'performance_total': performance_total,
                'performance_page': page,
                'performance_page_count': page_count,
                'performance_per_page': per_page,
                'performance_offset': offset,
                'performance_start': performance_start,
                'performance_end': performance_end,
                'previous_page_url': previous_page_url,
                'next_page_url': next_page_url,
                'performance_status': (kwargs.get('performance_status') or '').strip(),
                'performance_message': (kwargs.get('performance_message') or '').strip(),
        })
    )
    @http.route('/my/hr/admin/performance/update', type='http', auth='user', methods=['POST'], website=True)
    def my_hr_admin_performance_update(self, **post):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        if 'hr.daily.performance.plan' not in request.env:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Performance module is not available.',
            }))

        record_id_raw = (post.get('record_id') or '').strip()
        try:
            record_id = int(record_id_raw)
        except (TypeError, ValueError):
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Invalid performance record selected.',
            }))

        record = request.env['hr.daily.performance.plan'].sudo().browse(record_id).exists()
        if not record:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Performance record not found.',
            }))

        employee_id_raw = (post.get('employee_id') or '').strip()
        try:
            employee_id = int(employee_id_raw)
        except (TypeError, ValueError):
            employee_id = False

        plan_date = self._parse_portal_date(post.get('plan_date'))
        task_id = (post.get('task_id') or '').strip()
        project_name = (post.get('project_name') or '').strip()
        task_description = (post.get('task_description') or '').strip()
        priority_level = (post.get('priority_level') or '').strip()
        status = (post.get('status') or '').strip()
        completion_raw = (post.get('completion_percent') or '').strip()
        supervisor_remarks = (post.get('supervisor_remarks') or '').strip()

        try:
            completion_percent = float(completion_raw or 0.0)
        except (TypeError, ValueError):
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Completion percent must be a valid number.',
            }))

        if not employee_id:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Please select a valid employee.',
            }))

        if not plan_date:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Please enter a valid date.',
            }))

        if not task_id or not project_name or not task_description:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Task ID, Project, and Task Description are required.',
            }))

        if priority_level not in self._get_valid_performance_priorities():
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Please select a valid priority level.',
            }))

        if status not in self._get_valid_performance_statuses():
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Please select a valid status.',
            }))

        try:
            record.write({
                'employee_id': employee_id,
                'plan_date': plan_date,
                'task_id': task_id,
                'project_name': project_name,
                'task_description': task_description,
                'priority_level': priority_level,
                'status': status,
                'completion_percent': completion_percent,
                'supervisor_remarks': supervisor_remarks,
            })
        except ValidationError as error:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': str(error),
            }))
        except Exception:
            return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
                'performance_status': 'error',
                'performance_message': 'Performance record could not be updated.',
            }))

        return request.redirect(self._build_redirect_url('/my/hr/admin/performance', {
            'performance_status': 'success',
            'performance_message': 'Performance record updated successfully.',
        }))

    # ---------------------------------------------------------
    # EMPLOYEE: Documents, Payroll, Leaves
    # ---------------------------------------------------------
    @http.route('/my/hr/documents', type='http', auth='user', website=True)
    def my_hr_documents(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        return request.render(
            'hr_employee_portal.hr_employee_documents_page',
            self._prepare_portal_values(self._get_employee())
        )

    @http.route('/my/hr/payroll', type='http', auth='user', website=True)
    def my_hr_payroll(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        fy_value = kwargs.get('fy')
        month_value = kwargs.get('month')

        payroll_period = self._get_selected_payroll_period(fy_value=fy_value, month_value=month_value)
        selected_month = payroll_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)

        payroll_data = False
        if employee:
            payroll_data = self._get_employee_payroll_data(employee, selected_month)

        return request.render(
            'hr_employee_portal.hr_employee_payslips_page',
            self._prepare_portal_values(employee, {
                'payroll_data': payroll_data,
                'month_display': month_navigation.get('month_display', ''),
                'previous_month_value': month_navigation.get('previous_month_value', ''),
                'next_month_value': month_navigation.get('next_month_value', ''),
                'selected_month_value': selected_month.strftime('%Y-%m'),
                'fiscal_year_label': f"FY-{payroll_period['selected_fy_code']}",
                'fiscal_year_code': payroll_period['selected_fy_code'],
                'fiscal_year_range_label': payroll_period['selected_fy_range_label'],
                'fiscal_year_month_options': payroll_period['fiscal_year_month_options'],
                'fiscal_year_options': payroll_period['fiscal_year_options'],
                'selected_fiscal_year_value': payroll_period['selected_fy_value'],
                'selected_fiscal_year_code': payroll_period['selected_fy_code'],
                'payroll_tax_section_id': 'employee-payroll-tax-section',
                'payroll_tax_rate_section_id': 'employee-payroll-tax-rate-section',
            })
        )

    @http.route('/my/hr/payslips', type='http', auth='user', website=True)
    def my_hr_payslips(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')
        return request.redirect('/my/hr/payroll')

    @http.route('/my/hr/leaves', type='http', auth='user', website=True)
    def my_hr_leaves(self, **kwargs):
        if self._is_hr_manager():
            return request.redirect('/my/hr/admin')

        employee = self._get_employee()
        leaves = []
        if employee:
            leaves = request.env['hr.leave'].sudo().search(
                [('employee_id', '=', employee.id)],
                order='request_date_from desc'
            )

        return request.render(
            'hr_employee_portal.hr_employee_leaves_page',
            self._prepare_portal_values(employee, {'leaves': leaves})
        )

        # =========================================================
    # ADMIN: Secure Manager Routes
    # =========================================================
    @http.route('/my/hr/admin', type='http', auth='user', website=True)
    def my_hr_admin_dashboard(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        hr_employee_env = request.env['hr.employee'].sudo()
        hr_task_report_env = request.env['hr.daily.work.report'].sudo()
        attendance_register_env = request.env['hr.attendance.register.line'].sudo()

        all_employees = hr_employee_env.search([], order='name asc')

        today = fields.Date.context_today(request.env.user)
        month_start = today.replace(day=1)
        total_days = calendar.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=total_days)

        today_start = datetime.combine(today, time.min)
        next_day_start = today_start + timedelta(days=1)

        total_employees = hr_employee_env.search_count([])

        month_register_lines = attendance_register_env.search([
            ('attendance_date', '>=', month_start),
            ('attendance_date', '<=', month_end),
            ('attendance_code', 'in', ['P', 'R']),
    ])
        present_employee_count = len(set(month_register_lines.mapped('employee_id').ids))

        task_reports_submitted_today = hr_task_report_env.search_count([
            ('submitted_at', '>=', fields.Datetime.to_string(today_start)),
            ('submitted_at', '<', fields.Datetime.to_string(next_day_start)),
    ])

        values = self._prepare_portal_values(None, {
            'employees': all_employees,
            'total_employees': total_employees,
            'present_employees': present_employee_count,
            'task_reports_submitted_today': task_reports_submitted_today,
    })
        return request.render('hr_employee_portal.hr_admin_dashboard_page', values)

    @http.route('/my/hr/admin/attendances', type='http', auth='user', website=True)
    def my_hr_admin_attendances(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        hr_employee_env = request.env['hr.employee'].sudo()
        employees = hr_employee_env.search([], order='name asc')

        selected_employee = False
        selected_employee_id = kwargs.get('employee_id')
        fy_value = kwargs.get('fy')
        month_value = kwargs.get('month')

        payroll_period = self._get_selected_payroll_period(fy_value=fy_value, month_value=month_value)
        selected_month = payroll_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)
        fiscal_context = self._get_fiscal_year_context(selected_month)

        if selected_employee_id:
            try:
                selected_employee_id = int(selected_employee_id)
                selected_employee = hr_employee_env.browse(selected_employee_id).exists()
            except (TypeError, ValueError):
                selected_employee = False

        if not selected_employee and employees:
            selected_employee = employees[0]
            selected_employee_id = selected_employee.id
        elif selected_employee:
            selected_employee_id = selected_employee.id
        else:
            selected_employee_id = False

        attendance_matrix_row = False
        attendance_days = []
        attendance_display = []

        if selected_employee:
            attendance_matrix_row = self._build_attendance_matrix(selected_employee, selected_month)
            attendance_days = attendance_matrix_row['days']
            attendance_display = self._get_attendance_logs(selected_employee)

        values = self._prepare_portal_values(None, {
            'employees': employees,
            'selected_employee': selected_employee,
            'selected_employee_id': selected_employee_id,
            'attendance_matrix_row': attendance_matrix_row,
            'attendance_days': attendance_days,
            'attendances': attendance_display,
            'month_display': month_navigation.get('month_display', ''),
            'previous_month_value': month_navigation.get('previous_month_value', ''),
            'next_month_value': month_navigation.get('next_month_value', ''),
            'selected_month_value': selected_month.strftime('%Y-%m'),
            'fiscal_year_label': fiscal_context['fiscal_year_label'],
            'fiscal_year_code': fiscal_context['fiscal_year_code'],
            'fiscal_year_range_label': fiscal_context['fiscal_year_range_label'],
            'fiscal_year_month_options': payroll_period['fiscal_year_month_options'],
            'fiscal_year_options': payroll_period['fiscal_year_options'],
            'selected_fiscal_year_value': payroll_period['selected_fy_value'],
            'selected_fiscal_year_code': payroll_period['selected_fy_code'],
    })

        return request.render(
            'hr_employee_portal.hr_admin_attendances_page',
        values
    )
    @http.route('/my/hr/admin/task-reports', type='http', auth='user', website=True)
    def my_hr_admin_task_reports(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        hr_employee_env = request.env['hr.employee'].sudo()
        report_env = request.env['hr.daily.work.report'].sudo()

        employees = hr_employee_env.search([], order='name asc')

        selected_employee_id = False
        employee_id_raw = (kwargs.get('employee_id') or '').strip()
        if employee_id_raw:
            try:
                selected_employee_id = int(employee_id_raw)
            except (TypeError, ValueError):
                selected_employee_id = False

        date_from = self._parse_portal_date(kwargs.get('date_from'))
        date_to = self._parse_portal_date(kwargs.get('date_to'))

        domain = self._get_task_report_search_domain(
            employee_id=selected_employee_id,
            date_from=date_from,
            date_to=date_to,
    )

        try:
            page = int(kwargs.get('page') or 1)
        except (TypeError, ValueError):
            page = 1

        page = max(page, 1)
        per_page = 20
        offset = (page - 1) * per_page

        task_report_total = report_env.search_count(domain)

        task_reports = report_env.search(
            domain,
            order='report_date desc, submitted_at desc, id desc',
            limit=per_page,
            offset=offset,
    )

        page_count = max((task_report_total + per_page - 1) // per_page, 1)

        task_report_start = offset + 1 if task_report_total else 0
        task_report_end = min(offset + per_page, task_report_total)

        base_params = {
            'employee_id': selected_employee_id,
            'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
    }

        previous_page_url = False
        next_page_url = False

        if page > 1:
            previous_params = dict(base_params)
            previous_params['page'] = page - 1
            previous_page_url = self._build_redirect_url('/my/hr/admin/task-reports', previous_params)

        if page < page_count:
            next_params = dict(base_params)
            next_params['page'] = page + 1
            next_page_url = self._build_redirect_url('/my/hr/admin/task-reports', next_params)

        values = self._prepare_portal_values(None, {
            'employees': employees,
            'selected_employee_id': selected_employee_id,
            'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
            'task_reports': task_reports,
            'task_report_total': task_report_total,
            'task_report_page': page,
            'task_report_page_count': page_count,
            'task_report_per_page': per_page,
            'task_report_offset': offset,
            'task_report_start': task_report_start,
            'task_report_end': task_report_end,
            'previous_page_url': previous_page_url,
            'next_page_url': next_page_url,
            'report_status': (kwargs.get('report_status') or '').strip(),
            'report_message': (kwargs.get('report_message') or '').strip(),
    })

        return request.render('hr_employee_portal.hr_admin_task_reports_page', values)

    @http.route('/my/hr/admin/task-reports/update', type='http', auth='user', methods=['POST'], website=True)
    def my_hr_admin_task_reports_update(self, **post):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        if 'hr.daily.work.report' not in request.env:
            redirect_url = self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Daily Work Report module is not available.',
            })
            return request.redirect(redirect_url)

        report_id_raw = (post.get('report_id') or '').strip()
        try:
            report_id = int(report_id_raw)
        except (TypeError, ValueError):
            redirect_url = self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Invalid report selected.',
            })
            return request.redirect(redirect_url)

        report = request.env['hr.daily.work.report'].sudo().browse(report_id).exists()
        if not report:
            redirect_url = self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Task report not found.',
            })
            return request.redirect(redirect_url)

        report_date = self._parse_portal_date(post.get('report_date'))
        submitted_at_naive = self._parse_portal_datetime_local(post.get('submitted_at'))
        work_mode = (post.get('work_mode') or '').strip()
        task_report = (post.get('task_report') or '').strip()
        remarks = (post.get('remarks') or '').strip()
        state = (post.get('state') or '').strip()

        if not report_date:
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Please enter a valid report date.',
            }))

        if not submitted_at_naive:
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Please enter a valid submitted time.',
            }))

        if work_mode not in self._get_valid_work_modes():
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Please select a valid work mode.',
            }))

        if not task_report:
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Task report is required.',
            }))

        if state not in ['draft', 'submitted', 'approved', 'rejected']:
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Please select a valid state.',
            }))

        try:
            report.write({
                'report_date': report_date,
                'submitted_at': fields.Datetime.to_string(submitted_at_naive),
                'work_mode': work_mode,
                'task_report': task_report,
                'remarks': remarks,
                'state': state,
            })
        except ValidationError as error:
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': str(error),
            }))
        except Exception:
            return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
                'report_status': 'error',
                'report_message': 'Task report could not be updated.',
            }))

        return request.redirect(self._build_redirect_url('/my/hr/admin/task-reports', {
            'report_status': 'success',
            'report_message': 'Task report updated successfully.',
        }))

    @http.route('/my/hr/admin/leaves', type='http', auth='user', website=True)
    def my_hr_admin_leaves(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')
        return request.render('hr_employee_portal.hr_admin_leaves_page', self._prepare_portal_values(None))

    @http.route('/my/hr/admin/documents', type='http', auth='user', website=True)
    def my_hr_admin_documents(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')
        return request.render('hr_employee_portal.hr_admin_documents_page', self._prepare_portal_values(None))

    @http.route('/my/hr/admin/payslips', type='http', auth='user', website=True)
    def my_hr_admin_payslips(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        fy_value = kwargs.get('fy')
        month_value = kwargs.get('month')

        payroll_period = self._get_selected_payroll_period(fy_value=fy_value, month_value=month_value)
        selected_month = payroll_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)
        admin_payroll_data = self._get_admin_payroll_data(selected_month)

        return request.render(
            'hr_employee_portal.hr_admin_payslips_page',
            self._prepare_portal_values(None, {
                'admin_payroll_data': admin_payroll_data,
                'month_display': month_navigation.get('month_display', ''),
                'previous_month_value': month_navigation.get('previous_month_value', ''),
                'next_month_value': month_navigation.get('next_month_value', ''),
                'selected_month_value': selected_month.strftime('%Y-%m'),
                'fiscal_year_label': f"FY-{payroll_period['selected_fy_code']}",
                'fiscal_year_code': payroll_period['selected_fy_code'],
                'fiscal_year_range_label': payroll_period['selected_fy_range_label'],
                'fiscal_year_month_options': payroll_period['fiscal_year_month_options'],
                'fiscal_year_options': payroll_period['fiscal_year_options'],
                'selected_fiscal_year_value': payroll_period['selected_fy_value'],
                'selected_fiscal_year_code': payroll_period['selected_fy_code'],
            })
        )

    @http.route('/my/hr/admin/leaves', type='http', auth='user', website=True)
    def my_hr_admin_leaves(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        return request.render(
            'hr_employee_portal.hr_admin_leaves_page',
            self._prepare_portal_values(None)
        )

    @http.route('/my/hr/admin/documents', type='http', auth='user', website=True)
    def my_hr_admin_documents(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        return request.render(
            'hr_employee_portal.hr_admin_documents_page',
            self._prepare_portal_values(None)
        )

    @http.route('/my/hr/admin/payslips', type='http', auth='user', website=True)
    def my_hr_admin_payslips(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        fy_value = kwargs.get('fy')
        month_value = kwargs.get('month')

        payroll_period = self._get_selected_payroll_period(fy_value=fy_value, month_value=month_value)
        selected_month = payroll_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)
        admin_payroll_data = self._get_admin_payroll_data(selected_month)

        return request.render(
            'hr_employee_portal.hr_admin_payslips_page',
            self._prepare_portal_values(None, {
                'admin_payroll_data': admin_payroll_data,
                'month_display': month_navigation.get('month_display', ''),
                'previous_month_value': month_navigation.get('previous_month_value', ''),
                'next_month_value': month_navigation.get('next_month_value', ''),
                'selected_month_value': selected_month.strftime('%Y-%m'),
                'fiscal_year_label': f"FY-{payroll_period['selected_fy_code']}",
                'fiscal_year_code': payroll_period['selected_fy_code'],
                'fiscal_year_range_label': payroll_period['selected_fy_range_label'],
                'fiscal_year_month_options': payroll_period['fiscal_year_month_options'],
                'fiscal_year_options': payroll_period['fiscal_year_options'],
                'selected_fiscal_year_value': payroll_period['selected_fy_value'],
                'selected_fiscal_year_code': payroll_period['selected_fy_code'],
            })
        )

    @http.route('/my/hr/admin/payslips/tax-calculator', type='http', auth='user', website=True)
    def my_hr_admin_payslips_tax_calculator(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        fy_value = kwargs.get('fy')
        month_value = kwargs.get('month')

        payroll_period = self._get_selected_payroll_period(fy_value=fy_value, month_value=month_value)
        selected_month = payroll_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)
        admin_payroll_data = self._get_admin_payroll_data(selected_month)

        return request.render(
            'hr_employee_portal.hr_admin_payslips_tax_calculator_page',
            self._prepare_portal_values(None, {
                'admin_payroll_data': admin_payroll_data,
                'month_display': month_navigation.get('month_display', ''),
                'previous_month_value': month_navigation.get('previous_month_value', ''),
                'next_month_value': month_navigation.get('next_month_value', ''),
                'selected_month_value': selected_month.strftime('%Y-%m'),
                'fiscal_year_label': f"FY-{payroll_period['selected_fy_code']}",
                'fiscal_year_code': payroll_period['selected_fy_code'],
                'fiscal_year_range_label': payroll_period['selected_fy_range_label'],
                'fiscal_year_month_options': payroll_period['fiscal_year_month_options'],
                'fiscal_year_options': payroll_period['fiscal_year_options'],
                'selected_fiscal_year_value': payroll_period['selected_fy_value'],
                'selected_fiscal_year_code': payroll_period['selected_fy_code'],
            })
        )

    @http.route('/my/hr/admin/payslips/tax-rates', type='http', auth='user', website=True)
    def my_hr_admin_payslips_tax_rates(self, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        fy_value = kwargs.get('fy')
        month_value = kwargs.get('month')

        payroll_period = self._get_selected_payroll_period(fy_value=fy_value, month_value=month_value)
        selected_month = payroll_period['selected_month']
        month_navigation = self._get_month_navigation(selected_month)
        admin_payroll_data = self._get_admin_payroll_data(selected_month)

        return request.render(
            'hr_employee_portal.hr_admin_payslips_tax_rates_page',
            self._prepare_portal_values(None, {
                'admin_payroll_data': admin_payroll_data,
                'month_display': month_navigation.get('month_display', ''),
                'previous_month_value': month_navigation.get('previous_month_value', ''),
                'next_month_value': month_navigation.get('next_month_value', ''),
                'selected_month_value': selected_month.strftime('%Y-%m'),
                'fiscal_year_label': f"FY-{payroll_period['selected_fy_code']}",
                'fiscal_year_code': payroll_period['selected_fy_code'],
                'fiscal_year_range_label': payroll_period['selected_fy_range_label'],
                'fiscal_year_month_options': payroll_period['fiscal_year_month_options'],
                'fiscal_year_options': payroll_period['fiscal_year_options'],
                'selected_fiscal_year_value': payroll_period['selected_fy_value'],
                'selected_fiscal_year_code': payroll_period['selected_fy_code'],
            })
        )