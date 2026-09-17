from odoo import api, fields, models


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
        compute='_compute_medical_allowance',
        store=True,
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
        compute='_compute_income_tax_values',
        store=True,
    )

    yearly_income = fields.Float(
        string='Yearly Income',
        digits=(16, 2),
        compute='_compute_income_tax_values',
        store=True,
    )

    income_tax_deduction = fields.Float(
        string='Income Tax Deduction',
        digits=(16, 2),
        compute='_compute_income_tax_values',
        store=True,
    )

    other_deductions = fields.Float(
        string='Other Deductions',
        digits=(16, 2),
    )

    deductions_for = fields.Char(string='Deductions For')

    total = fields.Float(
        string='Total',
        digits=(16, 2),
        compute='_compute_payroll_totals',
        store=True,
    )

    total_round = fields.Float(
        string='Total Round',
        digits=(16, 2),
        compute='_compute_payroll_totals',
        store=True,
    )

    _unique_month_employee = models.Constraint(
        'unique(payroll_month, employee_code)',
        'Only one payroll row is allowed per employee per payroll month.',
    )

    @api.depends('basic_actual')
    def _compute_medical_allowance(self):
        for rec in self:
            rec.medical_allowance = round(
                (rec.basic_actual or 0.0) * 0.10,
                2,
            )

    @api.depends(
        'basic_actual',
        'medical_allowance',
        'project_salary',
        'reimbursements',
        'bonus',
        'overtime',
        'income_tax_deduction',
        'other_deductions',
    )
    def _compute_payroll_totals(self):
        for rec in self:
            total = round(
                (rec.basic_actual or 0.0)
                + (rec.medical_allowance or 0.0)
                + (rec.project_salary or 0.0)
                + (rec.reimbursements or 0.0)
                + (rec.bonus or 0.0)
                + (rec.overtime or 0.0)
                - (rec.income_tax_deduction or 0.0)
                - (rec.other_deductions or 0.0),
                2,
            )

            rec.total = total
            rec.total_round = round(total)

    @api.depends(
        'basic_actual',
        'project_salary',
        'bonus',
        'overtime',
    )
    def _compute_income_tax_values(self):
        for rec in self:
            values = rec.calculate_income_tax_values(
                basic_actual=rec.basic_actual,
                project_salary=rec.project_salary,
                bonus=rec.bonus,
                overtime=rec.overtime,
            )

            rec.taxable_income = values['taxable_income']
            rec.yearly_income = values['yearly_income']
            rec.income_tax_deduction = values['income_tax_deduction']

    @api.model
    def calculate_income_tax_values(
        self,
        basic_actual=0.0,
        project_salary=0.0,
        bonus=0.0,
        overtime=0.0,
    ):
        """
        Calculate payroll taxable income and salary income tax.

        Existing payroll business rules:
        - Medical Allowance is excluded from WHT.
        - Reimbursements are excluded from WHT.
        - Project Salary is taxable.
        - Bonus is taxable.
        - Overtime is taxable.
        """

        taxable_income = round(
            (basic_actual or 0.0)
            + (project_salary or 0.0)
            + (bonus or 0.0)
            + (overtime or 0.0),
            2,
        )

        yearly_income = round(taxable_income * 12.0, 2)

        if yearly_income <= 600000:
            yearly_tax = 0.0

        elif yearly_income <= 1200000:
            yearly_tax = (yearly_income - 600000) * 0.01

        elif yearly_income <= 2200000:
            yearly_tax = 6000 + ((yearly_income - 1200000) * 0.11)

        elif yearly_income <= 3200000:
            yearly_tax = 116000 + ((yearly_income - 2200000) * 0.23)

        elif yearly_income <= 4100000:
            yearly_tax = 346000 + ((yearly_income - 3200000) * 0.30)

        else:
            yearly_tax = 616000 + ((yearly_income - 4100000) * 0.35)

        yearly_tax = round(yearly_tax, 2)
        monthly_tax = round(yearly_tax / 12.0, 2)

        return {
            'taxable_income': taxable_income,
            'yearly_income': yearly_income,
            'yearly_tax': yearly_tax,
            'income_tax_deduction': monthly_tax,
        }
