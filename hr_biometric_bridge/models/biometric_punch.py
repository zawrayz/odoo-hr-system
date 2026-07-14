from odoo import fields, models


class HrBiometricPunch(models.Model):
    _name = "hr.biometric.punch"
    _description = "Biometric Punch Staging"
    _order = "received_at desc, id desc"
    _rec_name = "employee_code"

    device_code = fields.Char(
        string="Device",
        required=True,
        index=True,
    )
    employee_code = fields.Char(
        string="Biometric Employee Code",
        required=True,
        index=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Matched Employee",
        ondelete="set null",
        index=True,
    )
    event_type = fields.Selection(
        [
            ("check_in", "Check In"),
            ("check_out", "Check Out"),
            ("unknown", "Unknown"),
        ],
        required=True,
        default="unknown",
        index=True,
    )
    punch_time = fields.Datetime(
        string="Punch Time",
        required=True,
        index=True,
    )
    received_at = fields.Datetime(
        string="Received At",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    source_ip = fields.Char(string="Source IP")
    request_hash = fields.Char(
        string="Request Hash",
        required=True,
        copy=False,
        index=True,
    )
    raw_payload = fields.Text(string="Raw Payload")
    state = fields.Selection(
        [
            ("received", "Received"),
            ("mapped", "Employee Mapped"),
            ("error", "Error"),
        ],
        required=True,
        default="received",
        index=True,
    )
    error_message = fields.Text(string="Error")
