from odoo import api, fields, models
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
        index=True,
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
        index=True,
    )

    submitted_at = fields.Datetime(
        string='Submitted At',
        default=fields.Datetime.now,
        help='Actual date and time when the report was submitted.',
    )

    work_mode = fields.Selection(
        [
            ('office', 'Work from Office'),
            ('wfh', 'Work from Home'),
            ('leave', 'Leave'),
        ],
        string='Work Mode',
        required=True,
        default='office',
    )

    task_report = fields.Text(
        string='Task Report',
        required=True,
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='submitted',
        required=True,
    )

    remarks = fields.Text(string='Manager Remarks')

    @api.depends('employee_id', 'report_date')
    def _compute_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Employee'
            report_date = rec.report_date or ''
            rec.name = f"{employee_name} - {report_date}"

    @api.constrains('employee_id', 'report_date')
    def _check_one_report_per_day(self):
        for rec in self:
            if not rec.employee_id or not rec.report_date:
                continue

            existing = self.search(
                [
                    ('employee_id', '=', rec.employee_id.id),
                    ('report_date', '=', rec.report_date),
                    ('id', '!=', rec.id),
                ],
                limit=1,
            )
            if existing:
                raise ValidationError(
                    "Only one daily work report is allowed per employee per day."
                )

    @api.constrains('task_report')
    def _check_task_report_not_empty(self):
        for rec in self:
            if not (rec.task_report or '').strip():
                raise ValidationError("Task Report cannot be empty.")

    def _validate_portal_submission_rule(self, vals):
        """
        Enforce employee portal rule only when controller explicitly asks for it:
        employee can submit only for the current day.
        """
        if not self.env.context.get('enforce_employee_portal_rule'):
            return

        report_date = vals.get('report_date')
        if not report_date:
            report_date = fields.Date.context_today(self)

        if isinstance(report_date, str):
            report_date = fields.Date.to_date(report_date)

        today = fields.Date.context_today(self)
        if report_date != today:
            raise ValidationError(
                "You can submit a daily work report only for the current day."
            )

    @api.model_create_multi
    def create(self, vals_list):
        valid_work_modes = {'office', 'wfh', 'leave'}

        for vals in vals_list:
            task_report = (vals.get('task_report') or '').strip()
            if not task_report:
                raise ValidationError("Task Report cannot be empty.")
            vals['task_report'] = task_report

            if not vals.get('submitted_at'):
                vals['submitted_at'] = fields.Datetime.now()

            if not vals.get('state'):
                vals['state'] = 'submitted'

            if not vals.get('report_date'):
                vals['report_date'] = fields.Date.context_today(self)

            work_mode = vals.get('work_mode')
            if work_mode and work_mode not in valid_work_modes:
                raise ValidationError("Invalid work mode selected.")

            self._validate_portal_submission_rule(vals)

        return super().create(vals_list)

    def write(self, vals):
        valid_work_modes = {'office', 'wfh', 'leave'}

        if 'task_report' in vals:
            task_report = (vals.get('task_report') or '').strip()
            if not task_report:
                raise ValidationError("Task Report cannot be empty.")
            vals['task_report'] = task_report

        if 'work_mode' in vals and vals.get('work_mode') not in valid_work_modes:
            raise ValidationError("Invalid work mode selected.")

        self._validate_portal_submission_rule(vals)

        return super().write(vals)