from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrDailyWorkReport(models.Model):
    _name = 'hr.daily.work.report'
    _description = 'HR Daily Work Report'
    _order = 'report_date desc, submitted_at desc, id desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        related='employee_id.user_id',
        store=True,
        readonly=True,
    )

    report_date = fields.Date(
        string='Report Date',
        required=True,
        default=fields.Date.context_today,
    )

    submitted_at = fields.Datetime(
        string='Submitted At',
        default=fields.Datetime.now,
        required=True,
    )

    work_mode = fields.Selection(
        [
            ('office', 'Work from Office'),
            ('wfh', 'Work from Home'),
            ('field', 'Field Work'),
            ('leave', 'Leave'),
        ],
        string='Work Mode',
        required=True,
        default='office',
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        required=True,
        default='submitted',
    )

    task_report = fields.Text(
        string='Task Report',
        required=True,
    )

    remarks = fields.Text(
        string='Remarks',
    )

    _sql_constraints = [
        (
            'unique_employee_report_date',
            'unique(employee_id, report_date)',
            'Only one daily work report is allowed per employee per date.'
        ),
    ]

    @api.depends('employee_id', 'report_date')
    def _compute_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Employee'
            report_date = rec.report_date or ''
            rec.name = f"{employee_name} - {report_date}"

    @api.constrains('task_report')
    def _check_task_report(self):
        for rec in self:
            if not (rec.task_report or '').strip():
                raise ValidationError("Task Report is required.")

    @api.constrains('remarks')
    def _check_remarks(self):
        for rec in self:
            if rec.remarks and not rec.remarks.strip():
                raise ValidationError("Remarks cannot contain only spaces.")

    @api.constrains('report_date')
    def _check_report_date(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.report_date and rec.report_date > today:
                raise ValidationError("Report Date cannot be in the future.")

    def _sync_attendance_register_from_work_report(self):
        register_env = self.env['hr.attendance.register.line'].sudo()

        work_mode_code_map = {
            'office': 'P',
            'wfh': 'R',
            'field': 'P',
            'leave': 'C',
        }

        for rec in self:
            if not rec.employee_id or not rec.report_date:
                continue

            attendance_code = work_mode_code_map.get(rec.work_mode)
            if not attendance_code:
                continue

            month_label = rec.report_date.strftime('%B %Y') if rec.report_date else ''
            fiscal_year_label = ''

            register_env.create_or_update_attendance_line(
                employee=rec.employee_id,
                attendance_date=rec.report_date,
                attendance_code=attendance_code,
                fiscal_year_label=fiscal_year_label,
                month_label=month_label,
                source='daily_work_report',
                notes='Auto-synced from Daily Work Report',
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_attendance_register_from_work_report()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_attendance_register_from_work_report()
        return result