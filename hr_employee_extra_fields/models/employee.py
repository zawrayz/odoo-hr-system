from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_code = fields.Char(
        string="Employee Code",
        readonly=True,
        copy=False
    )

    employment_status = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('probation', 'Probation'),
            ('resigned', 'Resigned'),
            ('terminated', 'Terminated'),
            ('on_leave', 'On Leave'),
        ],
        string="Employment Status",
        default='active',
        required=True
    )

    blood_group = fields.Selection([
        ('a+', 'A+'),
        ('a-', 'A-'),
        ('b+', 'B+'),
        ('b-', 'B-'),
        ('ab+', 'AB+'),
        ('ab-', 'AB-'),
        ('o+', 'O+'),
        ('o-', 'O-')
    ], string="Blood Group")

    joining_date = fields.Date(string="Joining Date")

    father_name = fields.Char(string="Father Name")
    contract_start_date = fields.Date(string="Contract Start Date")
    contract_end_date = fields.Date(string="Contract End Date")

    bank_account_title = fields.Char(string="Account Title")
    bank_name_custom = fields.Char(string="Bank Name")
    bank_account_number = fields.Char(string="Account Number")

    residence_number = fields.Char(string="Residence Number")
    personal_email = fields.Char(string="Personal Email")
    cnic_number = fields.Char(string="CNIC")
    street_address = fields.Text(string="Address")
    ntn_number = fields.Char(string="NTN Number")
    date_of_birth_custom = fields.Date(string="Date of Birth")

    emergency_contact_name = fields.Char(string="Emergency Contact Name")
    emergency_contact_number = fields.Char(string="Emergency Contact Number")
    emergency_contact_relation = fields.Char(string="Emergency Contact Relation")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('employee_code'):
                vals['employee_code'] = self.env['ir.sequence'].next_by_code('hr.employee.code') or '/'
            if not vals.get('employment_status'):
                vals['employment_status'] = 'active'
        return super().create(vals_list)