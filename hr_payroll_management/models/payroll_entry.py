from odoo import fields, models


class HrPayrollEntry(models.Model):
    _name = 'hr.payroll.entry'
    _description = 'HR Payroll Entry'
    _order = 'payroll_month desc, sequence asc, id asc'

    payroll_month = fields.Date(
        string='Payroll Month',
        required=True,
        index=True,
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    employee_code = fields.Char(
        string='Employee ID',
        required=True,
        index=True,
    )

    employee_name = fields.Char(
        string='Employee Name',
        required=True,
    )

    bank = fields.Char(string='Bank')
    designation = fields.Char(string='Designation')
    payment_method = fields.Char(string='Payment Method')

    basic_salary = fields.Float(string='Basic Salary', digits=(16, 2))
    basic_actual = fields.Float(string='Basic Actual', digits=(16, 2))
    medical_allowance = fields.Float(
        string='Medical Allowance (No WHT)',
        digits=(16, 2),
    )
    advertised_salary = fields.Float(
        string='Advertised Salary',
        digits=(16, 2),
    )
    project_salary = fields.Float(
        string='Project Salary',
        digits=(16, 2),
    )

    project = fields.Char(string='Project')

    reimbursements = fields.Float(
        string='Reimbursements (No WHT)',
        digits=(16, 2),
    )

    bonus = fields.Float(string='Bonus', digits=(16, 2))
    bonus_for = fields.Char(string='For')

    overtime = fields.Float(string='Overtime', digits=(16, 2))
    ot_detail = fields.Char(string='OT Detail')

    taxable_income = fields.Float(
        string='Taxable Income',
        digits=(16, 2),
    )
    yearly_income = fields.Float(
        string='Yearly Income',
        digits=(16, 2),
    )
    income_tax_deduction = fields.Float(
        string='Income Tax Deduction',
        digits=(16, 2),
    )
    other_deductions = fields.Float(
        string='Other Deductions',
        digits=(16, 2),
    )
    deductions_for = fields.Char(string='Deductions For')

    total = fields.Float(string='Total', digits=(16, 2))
    total_round = fields.Float(string='Total Round', digits=(16, 2))

    _unique_month_employee = models.Constraint(
        'unique(payroll_month, employee_code)',
        'Only one payroll row is allowed per employee per payroll month.',
    )
