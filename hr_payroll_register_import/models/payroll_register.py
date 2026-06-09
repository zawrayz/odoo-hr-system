from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrPayrollRegisterLine(models.Model):
    _name = 'hr.payroll.register.line'
    _description = 'HR Payroll Register Line'
    _order = 'month_date desc, employee_id asc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )

    employee_code = fields.Char(
        string='Employee Code',
        related='employee_id.employee_code',
        store=True,
        readonly=True,
    )

    employee_name_text = fields.Char(string='Employee Name')
    fiscal_year_label = fields.Char(string='Fiscal Year', required=True)
    month_date = fields.Date(string='Month', required=True, index=True)
    month_label = fields.Char(string='Month Label', compute='_compute_month_label', store=True)

    designation = fields.Char(string='Designation')
    payment_method = fields.Char(string='Payment Method / Bank')

    # Manual / imported salary inputs
    basic_salary = fields.Float(string='Basic Salary')
    basic_actual = fields.Float(string='Basic Actual')
    medical_allowance = fields.Float(string='Medical Allowance')
    advertised_salary = fields.Float(string='Advertised Salary')

    # Project salary / allowance
    project_salary = fields.Float(string='Project Salary / Allowance')
    project_detail = fields.Char(string='Project / Allowance Detail')

    # Bonus
    bonus = fields.Float(string='Bonus')
    bonus_detail = fields.Char(string='Bonus Detail')

    # Old allowance fields kept for backward compatibility
    allowance = fields.Float(string='Allowance')
    allowance_detail = fields.Char(string='Allowance Detail')

    # Optional overtime fields. Keep them zero unless business confirms overtime payroll use.
    overtime = fields.Float(string='Overtime')
    overtime_detail = fields.Char(string='Overtime Detail')

    taxable_income = fields.Float(string='Taxable Income')
    yearly_income = fields.Float(string='Yearly Income')
    income_tax_deduction = fields.Float(string='Income Tax Deduction')
    other_deductions = fields.Float(string='Other Deductions')
    deduction_detail = fields.Char(string='Deductions For')

    total = fields.Float(string='Total')
    total_round = fields.Float(string='Total Round')
    total_salary = fields.Float(string='Net Salary')
    loans_from_cash = fields.Float(string='Loans from Cash')

    payment_date = fields.Date(string='Payment Date')
    payment = fields.Float(string='Payment')
    inclusive_of_tax = fields.Char(string='Inclusive of Tax')
    remaining = fields.Float(string='Remaining')

    period_label = fields.Char(string='For the Period of')
    paid_at = fields.Char(string='Paid At')
    comments = fields.Text(string='Comments')

    source = fields.Selection(
        [
            ('sheet_import', 'Sheet Import'),
            ('manual', 'Manual'),
        ],
        string='Source',
        default='sheet_import',
        required=True,
    )

    is_manually_adjusted = fields.Boolean(string='Manually Adjusted', default=False)
    manual_update_user_id = fields.Many2one(
        'res.users',
        string='Last Manual Update By',
        readonly=True,
    )
    manual_update_date = fields.Datetime(
        string='Last Manual Update Date',
        readonly=True,
    )

    _sql_constraints = [
        (
            'unique_employee_month_payroll',
            'unique(employee_id, month_date)',
            'Payroll already exists for this employee and month.'
        ),
    ]

    @api.depends('employee_id', 'month_date')
    def _compute_display_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Employee'
            month_text = rec.month_date.strftime('%b %Y') if rec.month_date else ''
            rec.display_name = f"{employee_name} - {month_text}"

    @api.depends('month_date')
    def _compute_month_label(self):
        for rec in self:
            rec.month_label = rec.month_date.strftime('%B %Y') if rec.month_date else ''

    def _round_amount(self, amount):
        try:
            return round(float(amount or 0.0), 2)
        except (TypeError, ValueError):
            return 0.0

    def action_recalculate_manual_payroll(self):
        """
        Recalculate automatic payroll fields after admin manual edits.

        Manual inputs:
        - basic_salary
        - basic_actual
        - project_salary
        - bonus
        - income_tax_deduction
        - other_deductions
        - loans_from_cash

        Automatic outputs:
        - medical_allowance
        - taxable_income
        - yearly_income
        - total
        - total_round
        - total_salary
        - payment
        - remaining

        Important:
        This is intentionally NOT called automatically on sheet import.
        Imported historical sheet totals should not be silently overwritten.
        """
        for rec in self:
            basic_salary = rec.basic_salary or 0.0
            basic_actual = rec.basic_actual or 0.0

            medical_allowance = self._round_amount(basic_salary * 0.10)
            taxable_income = self._round_amount(
                basic_actual
                + rec.project_salary
                + rec.bonus
                + rec.overtime
            )

            yearly_income = self._round_amount(taxable_income * 12.0)

            total = self._round_amount(
                basic_actual
                + medical_allowance
                + rec.project_salary
                + rec.bonus
                + rec.overtime
                - rec.income_tax_deduction
                - rec.other_deductions
                - rec.loans_from_cash
            )

            total_round = round(total)

            rec.write({
                'medical_allowance': medical_allowance,
                'taxable_income': taxable_income,
                'yearly_income': yearly_income,
                'total': total,
                'total_round': total_round,
                'total_salary': total_round,
                'payment': total_round,
                'remaining': 0.0,
                'source': 'manual',
                'is_manually_adjusted': True,
                'manual_update_user_id': self.env.user.id,
                'manual_update_date': fields.Datetime.now(),
            })

    @api.model
    def create_or_update_payroll_line(self, employee, month_date, vals):
        if not employee:
            raise ValidationError("Employee is required.")
        if not month_date:
            raise ValidationError("Month is required.")

        existing = self.search([
            ('employee_id', '=', employee.id),
            ('month_date', '=', month_date),
        ], limit=1)

        final_vals = dict(vals or {})
        final_vals.update({
            'employee_id': employee.id,
            'month_date': month_date,
        })

        if existing:
            existing.write(final_vals)
            return existing, 'updated'

        return self.create(final_vals), 'created'