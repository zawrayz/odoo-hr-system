from odoo import api, fields, models


class HrEmployeePortalRequest(models.Model):
    _name = 'hr.employee.portal.request'
    _description = 'HR Employee Portal Request'
    _order = 'submitted_at desc, id desc'
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
        index=True,
        ondelete='cascade',
    )

    employee_code = fields.Char(
        string='Employee Code',
        related='employee_id.employee_code',
        store=True,
        readonly=True,
    )

    request_type = fields.Selection(
        [
            ('short_leave', 'Request for Short Leave'),
            ('wfh', 'Request for WFH'),
            ('sick_leave', 'Request for Sick Leave'),
            ('casual_leave', 'Request for Casual Leave'),
        ],
        string='Request Type',
        required=True,
        index=True,
    )

    request_type_label = fields.Char(
        string='Request Type Label',
        compute='_compute_request_type_label',
        store=True,
    )

    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    reason = fields.Text(string='Reason / Details', required=True)

    state = fields.Selection(
        [
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='submitted',
        required=True,
        index=True,
    )

    submitted_at = fields.Datetime(
        string='Submitted At',
        default=fields.Datetime.now,
        required=True,
    )

    admin_remarks = fields.Text(string='Admin Remarks')

    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By',
        readonly=True,
    )

    reviewed_at = fields.Datetime(
        string='Reviewed At',
        readonly=True,
    )

    @api.depends('employee_id', 'request_type', 'date_from', 'date_to')
    def _compute_display_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Employee'
            request_label = rec.request_type_label or rec.request_type or 'Request'
            date_text = ''
            if rec.date_from and rec.date_to:
                date_text = f" - {rec.date_from} to {rec.date_to}"
            rec.display_name = f"{employee_name} - {request_label}{date_text}"

    @api.depends('request_type')
    def _compute_request_type_label(self):
        labels = dict(self._fields['request_type'].selection)
        for rec in self:
            rec.request_type_label = labels.get(rec.request_type, '')