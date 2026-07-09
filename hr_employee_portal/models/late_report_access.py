from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrLateReportAccess(models.Model):
    _name = 'hr.late.report.access'
    _description = 'HR Late Report Temporary Access'
    _order = 'create_date desc, id desc'

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

    report_date = fields.Date(
        string='Missed Report Date',
        required=True,
    )

    expires_at = fields.Datetime(
        string='Access Expires At',
        required=True,
    )

    state = fields.Selection(
        [
            ('active', 'Active'),
            ('used', 'Used'),
            ('expired', 'Expired'),
            ('revoked', 'Revoked'),
        ],
        string='Status',
        required=True,
        default='active',
    )

    granted_by_id = fields.Many2one(
        'res.users',
        string='Granted By',
        default=lambda self: self.env.user,
        readonly=True,
    )

    used_report_id = fields.Many2one(
        'hr.daily.work.report',
        string='Used Report',
        readonly=True,
    )

    notes = fields.Text(string='Notes')

    @api.depends('employee_id', 'report_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s - %s' % (
                rec.employee_id.name or 'Employee',
                rec.report_date or ''
            )

    @api.constrains('report_date')
    def _check_report_date(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.report_date and rec.report_date >= today:
                raise ValidationError('Temporary access is only for older missed report dates.')

    @api.constrains('expires_at')
    def _check_expires_at(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.expires_at and rec.expires_at <= now:
                raise ValidationError('Expiry time must be in the future.')
