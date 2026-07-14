from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrBiometricBridgeStatus(models.Model):
    _name = "hr.biometric.bridge.status"
    _description = "Biometric Bridge Status"
    _order = "last_seen desc, id desc"
    _rec_name = "bridge_name"

    bridge_id = fields.Char(
        string="Bridge ID",
        required=True,
        index=True,
    )

    bridge_name = fields.Char(
        string="Bridge Name",
        required=True,
    )

    device_code = fields.Char(
        string="Device",
        index=True,
    )

    last_seen = fields.Datetime(
        string="Last Seen",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    source_ip = fields.Char(
        string="Source IP",
    )

    app_version = fields.Char(
        string="Bridge Version",
    )

    machine_name = fields.Char(
        string="Windows PC",
    )

    last_message = fields.Char(
        string="Last Message",
    )

    active = fields.Boolean(
        default=True,
        index=True,
    )

    is_online = fields.Boolean(
        string="Online",
        compute="_compute_is_online",
    )

    @api.depends("last_seen")
    def _compute_is_online(self):
        now = fields.Datetime.to_datetime(
            fields.Datetime.now()
        )
        cutoff = now - timedelta(minutes=3)

        for record in self:
            last_seen = fields.Datetime.to_datetime(
                record.last_seen
            )

            record.is_online = bool(
                last_seen and last_seen >= cutoff
            )

    @api.constrains("bridge_id")
    def _check_bridge_id(self):
        for record in self:
            bridge_id = (
                record.bridge_id or ""
            ).strip()

            if not bridge_id:
                raise ValidationError(
                    _("Bridge ID cannot be empty.")
                )

            duplicate = self.search_count(
                [
                    ("id", "!=", record.id),
                    ("bridge_id", "=", bridge_id),
                ]
            )

            if duplicate:
                raise ValidationError(
                    _(
                        "A bridge with ID %(bridge_id)s "
                        "already exists.",
                        bridge_id=bridge_id,
                    )
                )
