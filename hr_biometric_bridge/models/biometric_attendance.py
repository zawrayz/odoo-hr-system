import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrBiometricPunchAttendance(models.Model):
    _inherit = "hr.biometric.punch"

    attendance_id = fields.Many2one(
        "hr.attendance",
        string="Odoo Attendance",
        ondelete="set null",
        copy=False,
        readonly=True,
        index=True,
    )

    attendance_result = fields.Selection(
        [
            ("not_processed", "Not Processed"),
            ("disabled", "Attendance Disabled"),
            ("check_in", "Check In Created"),
            ("check_out", "Check Out Created"),
            ("duplicate", "Duplicate Ignored"),
            ("error", "Attendance Error"),
        ],
        string="Attendance Result",
        required=True,
        default="not_processed",
        copy=False,
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            try:
                record._process_real_attendance()
            except Exception as exc:
                _logger.exception(
                    "Biometric attendance processing failed for punch %s",
                    record.id,
                )

                record.sudo().write({
                    "state": "error",
                    "attendance_result": "error",
                    "error_message": str(exc),
                })

        return records

    def _attendance_config(self):
        self.ensure_one()

        config = self.env[
            "ir.config_parameter"
        ].sudo()

        enabled = str(
            config.get_param(
                "hr_biometric_bridge.real_attendance_enabled",
                "false",
            )
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        try:
            duplicate_seconds = int(
                config.get_param(
                    "hr_biometric_bridge.duplicate_seconds",
                    "120",
                )
                or 120
            )
        except (TypeError, ValueError):
            duplicate_seconds = 120

        duplicate_seconds = max(
            0,
            min(duplicate_seconds, 3600),
        )

        return (
            enabled,
            duplicate_seconds,
        )

    def _recent_processed_punch(
        self,
        duplicate_seconds,
    ):
        self.ensure_one()

        if (
            not self.employee_id
            or duplicate_seconds <= 0
        ):
            return self.browse()

        punch_time = fields.Datetime.to_datetime(
            self.punch_time
        )

        cutoff = punch_time - timedelta(
            seconds=duplicate_seconds
        )

        return self.sudo().search(
            [
                ("id", "!=", self.id),
                (
                    "employee_id",
                    "=",
                    self.employee_id.id,
                ),
                (
                    "employee_code",
                    "=",
                    self.employee_code,
                ),
                (
                    "device_code",
                    "=",
                    self.device_code,
                ),
                (
                    "punch_time",
                    ">=",
                    fields.Datetime.to_string(cutoff),
                ),
                (
                    "punch_time",
                    "<=",
                    fields.Datetime.to_string(
                        punch_time
                    ),
                ),
                (
                    "attendance_result",
                    "in",
                    [
                        "check_in",
                        "check_out",
                        "duplicate",
                    ],
                ),
            ],
            order="punch_time desc, id desc",
            limit=1,
        )

    def _process_real_attendance(self):
        self.ensure_one()

        (
            enabled,
            duplicate_seconds,
        ) = self._attendance_config()

        Mapping = self.env[
            "hr.biometric.employee.map"
        ].sudo()

        biometric_code = (
            self.employee_code or ""
        ).strip()

        device_code = (
            self.device_code or ""
        ).strip()

        attendance_mapping = Mapping.search(
            [
                ("active", "=", True),
                (
                    "biometric_code",
                    "=",
                    biometric_code,
                ),
                (
                    "device_code",
                    "=",
                    device_code,
                ),
            ],
            limit=1,
        )

        if not attendance_mapping:
            attendance_mapping = Mapping.search(
                [
                    ("active", "=", True),
                    (
                        "biometric_code",
                        "=",
                        biometric_code,
                    ),
                    ("device_code", "=", False),
                ],
                limit=1,
            )

        if (
            not enabled
            or not attendance_mapping
            or not attendance_mapping.attendance_enabled
        ):
            self.sudo().write({
                "attendance_result": "disabled",
            })
            return

        if not self.employee_id:
            self.sudo().write({
                "state": "error",
                "attendance_result": "error",
                "error_message": (
                    "Real attendance is enabled, but "
                    "this biometric user is not mapped "
                    "to an Odoo employee."
                ),
            })
            return

        previous = self._recent_processed_punch(
            duplicate_seconds
        )

        if previous:
            values = {
                "attendance_result": "duplicate",
                "attendance_id": (
                    previous.attendance_id.id
                    or False
                ),
                "error_message": (
                    "Ignored as a repeated scan within "
                    f"{duplicate_seconds} seconds of "
                    f"biometric punch {previous.id}."
                ),
            }

            if previous.event_type in {
                "check_in",
                "check_out",
            }:
                values["event_type"] = (
                    previous.event_type
                )

            self.sudo().write(values)
            return

        Attendance = self.env[
            "hr.attendance"
        ].sudo()

        open_attendance = Attendance.search(
            [
                (
                    "employee_id",
                    "=",
                    self.employee_id.id,
                ),
                ("check_out", "=", False),
            ],
            order="check_in desc, id desc",
            limit=1,
        )

        effective_event = self.event_type

        if effective_event == "unknown":
            effective_event = (
                "check_out"
                if open_attendance
                else "check_in"
            )

        punch_time = fields.Datetime.to_datetime(
            self.punch_time
        )

        if effective_event == "check_in":
            if open_attendance:
                raise ValueError(
                    "The employee already has an "
                    "open attendance."
                )

            attendance = Attendance.create({
                "employee_id": self.employee_id.id,
                "check_in": punch_time,
            })

            self.sudo().write({
                "event_type": "check_in",
                "attendance_result": "check_in",
                "attendance_id": attendance.id,
                "state": "mapped",
                "error_message": False,
            })
            return

        if effective_event == "check_out":
            if not open_attendance:
                raise ValueError(
                    "The employee has no open "
                    "attendance to check out."
                )

            check_in = fields.Datetime.to_datetime(
                open_attendance.check_in
            )

            if punch_time <= check_in:
                raise ValueError(
                    "The biometric check-out must be "
                    "later than check-in."
                )

            open_attendance.write({
                "check_out": punch_time,
            })

            self.sudo().write({
                "event_type": "check_out",
                "attendance_result": "check_out",
                "attendance_id": open_attendance.id,
                "state": "mapped",
                "error_message": False,
            })
            return

        raise ValueError(
            f"Unsupported biometric event: "
            f"{effective_event}"
        )
