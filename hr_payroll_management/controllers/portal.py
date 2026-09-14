from odoo import fields, http
from odoo.http import request


class HrPayrollPortal(http.Controller):

    PAYROLL_ACCESS_EMPLOYEE_CODES = {
        'BPL001',
        'BLMP43',
        'BLMP44',
    }

    PAYROLL_COLUMNS = [
        '#',
        'Employee ID',
        'Employee Name',
        'Bank',
        'Designation',
        'Payment method',
        'Basic Salary',
        'Basic Actual',
        'Medical Allowance (No WHT)',
        'Advertised Salary',
        'Project Salary',
        'Project',
        'reimbursements (No WHT)',
        '',
        'Bonus',
        'For',
        'Overtime',
        'OT Detail',
        'Taxable Income',
        'Yearly Income',
        'Income Tax Deduction',
        'Other Deductions',
        'Deductions for',
        'Total',
        'Total Round',
    ]

    def _is_hr_manager(self):
        return request.env.user.has_group('hr.group_hr_manager')

    def _get_current_employee_code(self):
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.user.id)],
            limit=1,
        )
        return (
            (employee.employee_code or '').strip().upper()
            if employee
            else ''
        )

    def _can_view_payroll(self):
        return (
            self._is_hr_manager()
            or self._get_current_employee_code()
            in self.PAYROLL_ACCESS_EMPLOYEE_CODES
        )

    @http.route(
        [
            '/my/hr/finance/hr/payroll',
            '/my/hr/admin/finance/hr/payroll',
        ],
        type='http',
        auth='user',
        website=True,
    )
    def payroll_page(self, **kwargs):
        if not self._can_view_payroll():
            return request.redirect('/my/hr')

        is_hr_manager = self._is_hr_manager()

        today = fields.Date.context_today(request.env.user)
        month_value = (kwargs.get('month') or '').strip()

        try:
            payroll_month = (
                fields.Date.to_date('%s-01' % month_value)
                if month_value
                else today.replace(day=1)
            )
        except Exception:
            payroll_month = today.replace(day=1)

        month_options = []
        for month_number in range(1, 13):
            month_date = payroll_month.replace(
                month=month_number,
                day=1,
            )
            month_options.append({
                'value': month_date.strftime('%Y-%m'),
                'label': month_date.strftime('%B %Y'),
            })

        entries = request.env['hr.payroll.entry'].sudo().search([
            ('payroll_month', '=', payroll_month),
        ], order='sequence asc, id asc')

        def money(value):
            value = value or 0.0
            if float(value).is_integer():
                return '{:,.0f}'.format(value)
            return '{:,.2f}'.format(value)

        payroll_rows = []

        for index, entry in enumerate(entries, start=1):
            payroll_rows.append([
                str(index),
                entry.employee_code or '',
                entry.employee_name or '',
                entry.bank or '',
                entry.designation or '',
                entry.payment_method or '',
                money(entry.basic_salary),
                money(entry.basic_actual),
                money(entry.medical_allowance),
                money(entry.advertised_salary),
                money(entry.project_salary),
                entry.project or '',
                money(entry.reimbursements),
                '',
                money(entry.bonus),
                entry.bonus_for or '',
                money(entry.overtime),
                entry.ot_detail or '',
                money(entry.taxable_income),
                money(entry.yearly_income),
                money(entry.income_tax_deduction),
                money(entry.other_deductions),
                entry.deductions_for or '',
                money(entry.total),
                money(entry.total_round),
            ])

        return request.render(
            'hr_payroll_management.hr_finance_payroll_page',
            {
                'current_page': 'admin_finance_payroll',
                'is_hr_manager': is_hr_manager,
                'payroll_columns': self.PAYROLL_COLUMNS,
                'payroll_rows': payroll_rows,
                'payroll_month_value': payroll_month.strftime('%Y-%m'),
                'payroll_month_options': month_options,
            },
        )
