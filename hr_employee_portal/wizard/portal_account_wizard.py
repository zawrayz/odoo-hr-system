from odoo import fields, models, _
from odoo.exceptions import UserError


class HrPortalAccountWizard(models.TransientModel):
    _name = 'hr.portal.account.wizard'
    _description = 'Create / Update Employee Portal Account'

    employee_code = fields.Char(string='Employee Code', required=True)
    employee_name = fields.Char(string='Employee Name', required=True)
    work_email = fields.Char(string='Official Email', required=True)
    temp_password = fields.Char(string='Temporary Password', required=True)
    department_name = fields.Char(string='Department')
    job_title = fields.Char(string='Job Position')

    def action_create_update_account(self):
        self.ensure_one()

        employee_code = (self.employee_code or '').strip()
        employee_name = (self.employee_name or '').strip()
        work_email = (self.work_email or '').strip().lower()
        temp_password = (self.temp_password or '').strip()
        department_name = (self.department_name or '').strip()
        job_title = (self.job_title or '').strip()

        if not employee_code or not employee_name or not work_email or not temp_password:
            raise UserError(_('Employee code, name, official email, and temporary password are required.'))

        if '@' not in work_email or '.' not in work_email:
            raise UserError(_('Please enter a valid official email.'))

        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        User = self.env['res.users'].sudo().with_context(
            active_test=False,
            no_reset_password=True,
            tracking_disable=True,
            mail_notrack=True,
            mail_create_nosubscribe=True,
            mail_notify_noemail=True,
        )

        Department = self.env['hr.department'].sudo()
        Job = self.env['hr.job'].sudo()

        employee = Employee.search([('employee_code', '=', employee_code)], limit=1)

        department = False
        if department_name:
            department = Department.search([('name', '=ilike', department_name)], limit=1)
            if not department:
                department = Department.create({'name': department_name})

        job = False
        if job_title:
            job = Job.search([('name', '=ilike', job_title)], limit=1)
            if not job:
                job = Job.create({'name': job_title})

        emp_vals = {
            'name': employee_name,
            'employee_code': employee_code,
            'work_email': work_email,
            'active': True,
        }
        if department:
            emp_vals['department_id'] = department.id
        if job:
            emp_vals['job_id'] = job.id

        if employee:
            employee.write(emp_vals)
            employee_action = 'updated'
        else:
            employee = Employee.create(emp_vals)
            employee_action = 'created'

        existing_user = employee.user_id or User.search(['|', ('login', '=', work_email), ('email', '=', work_email)], limit=1)

        if existing_user and not existing_user.share:
            employee.write({'user_id': existing_user.id})
            raise UserError(_('Employee updated, but linked user is internal/admin. Portal role was not changed for safety.'))

        portal_group = self.env.ref('base.group_portal')
        company = employee.company_id or self.env.company

        user_vals = {
            'name': employee.name,
            'login': work_email,
            'email': work_email,
            'active': True,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [portal_group.id])],
            'password': temp_password,
        }

        if existing_user:
            existing_user.write(user_vals)
            user = existing_user
            user_action = 'updated'
        else:
            user = User.create(user_vals)
            user_action = 'created'

        employee.write({'user_id': user.id})

        blocked_subject_parts = ['Welcome', 'Password Changed', 'Login Changed', 'Your account', 'Security Update']
        mails = self.env['mail.mail'].sudo().search([('email_to', 'ilike', work_email)])
        for mail in mails:
            subject = (mail.mail_message_id.subject or '')
            if any(part.lower() in subject.lower() for part in blocked_subject_parts):
                mail.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Account Ready'),
                'message': _('Employee %s and portal account %s for %s. No account email was sent.') % (
                    employee_action, user_action, employee.name
                ),
                'type': 'success',
                'sticky': False,
            }
        }
