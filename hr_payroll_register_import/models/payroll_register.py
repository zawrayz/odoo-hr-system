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

    basic_salary = fields.Float(string='Basic Salary')
    basic_actual = fields.Float(string='Basic Actual')
    medical_allowance = fields.Float(string='Medical Allowance')
    advertised_salary = fields.Float(string='Advertised Salary')
    project_salary = fields.Float(string='Project Salary')
    bonus = fields.Float(string='Bonus')
    allowance = fields.Float(string='Allowance')
    allowance_detail = fields.Char(string='Allowance Detail')

    taxable_income = fields.Float(string='Taxable Income')
    yearly_income = fields.Float(string='Yearly Income')
    income_tax_deduction = fields.Float(string='Income Tax Deduction')
    other_deductions = fields.Float(string='Other Deductions')

    total = fields.Float(string='Total')
    total_round = fields.Float(string='Total Round')
    total_salary = fields.Float(string='Total Salary')
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