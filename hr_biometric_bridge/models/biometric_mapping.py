from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrBiometricEmployeeMap(models.Model):
    _name = "hr.biometric.employee.map"
    _description = "Biometric Employee Mapping"
    _order = "device_code, biometric_code"
    _rec_name = "biometric_code"

    biometric_code = fields.Char(
        string="Biometric User ID",
        required=True,
        index=True,
        help="User identifier sent by the biometric device.",
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Odoo Employee",
        required=True,
        ondelete="cascade",
        index=True,
    )

    device_code = fields.Char(
        string="Device",
        index=True,
        help=(
            "Optional device identifier. Leave empty when this mapping "
            "should apply to every biometric device."
        ),
    )

    active = fields.Boolean(
        default=True,
        index=True,
    )

    notes = fields.Text(
        string="Notes",
    )

    @api.constrains(
        "biometric_code",
        "device_code",
        "active",
    )
    def _check_unique_active_mapping(self):
        for record in self:
            if not record.active:
                continue

            biometric_code = (
                record.biometric_code or ""
            ).strip()

            if not biometric_code:
                raise ValidationError(
                    _("Biometric User ID cannot be empty.")
                )

            domain = [
                ("id", "!=", record.id),
                ("active", "=", True),
                ("biometric_code", "=", biometric_code),
            ]

            if record.device_code:
                domain.append(
                    ("device_code", "=", record.device_code.strip())
                )
            else:
                domain.append(
                    ("device_code", "=", False)
                )

            if self.search_count(domain):
                raise ValidationError(
                    _(
                        "An active mapping already exists for "
                        "biometric user ID %(code)s on this device.",
                        code=biometric_code,
                    )
                )
