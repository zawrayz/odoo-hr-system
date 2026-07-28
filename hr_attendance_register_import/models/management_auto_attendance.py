from datetime import date, datetime, timedelta, timezone
import logging


from odoo import api, models


_logger = logging.getLogger(__name__)

PAKISTAN_TIMEZONE = timezone(timedelta(hours=5))
MANAGEMENT_ATTENDANCE_START = date(2026, 7, 6)

MANAGEMENT_EMPLOYEE_NAMES = (
    "Muhammad Uzair",
    "Shahan Ahmed",
    "Tufail Ahmad",
    "Darakhshan Uzair",
    "Faiza Saleem",
    "Administrator",
)


class HrAttendanceRegisterLine(models.Model):
    _inherit = "hr.attendance.register.line"

    @api.model
    def _management_fiscal_year_label(self, attendance_date):
        if attendance_date.month >= 7:
            start_year = attendance_date.year
        else:
            start_year = attendance_date.year - 1

        return "FY-%02d/%02d" % (
            start_year % 100,
            (start_year + 1) % 100,
        )

    @api.model
    def cron_fill_management_attendance(self):
        """
        Fill missing completed dates for management employees.

        Monday-Friday: P
        Saturday-Sunday: H

        Existing attendance is never overwritten.
        The current Pakistan date is never generated.
        """
        pakistan_today = (
            datetime.now(timezone.utc)
            .astimezone(PAKISTAN_TIMEZONE)
            .date()
        )

        final_date = pakistan_today - timedelta(days=1)

        result = {
            "created": 0,
            "existing": 0,
            "employees": 0,
            "missing_employees": [],
            "skipped_inactive_without_date": [],
            "start_date": MANAGEMENT_ATTENDANCE_START,
            "final_date": final_date,
        }

        if final_date < MANAGEMENT_ATTENDANCE_START:
            return result

        employee_env = (
            self.env["hr.employee"]
            .sudo()
            .with_context(active_test=False)
        )

        register_env = self.sudo()

        for employee_name in MANAGEMENT_EMPLOYEE_NAMES:
            employee = employee_env.search(
                [("name", "=ilike", employee_name)],
                limit=1,
            )

            if not employee:
                result["missing_employees"].append(employee_name)
                continue

            # Do not automatically continue an old inactive employee
            # when no final working date was recorded.
            if not employee.active and not employee.last_working_date:
                result["skipped_inactive_without_date"].append(
                    employee.name
                )
                continue

            effective_start = MANAGEMENT_ATTENDANCE_START

            if (
                employee.joining_date
                and employee.joining_date > effective_start
            ):
                effective_start = employee.joining_date

            effective_end = final_date

            if (
                employee.last_working_date
                and employee.last_working_date < effective_end
            ):
                effective_end = employee.last_working_date

            if effective_start > effective_end:
                continue

            result["employees"] += 1

            existing_lines = register_env.search([
                ("employee_id", "=", employee.id),
                ("attendance_date", ">=", effective_start),
                ("attendance_date", "<=", effective_end),
            ])

            existing_dates = set(
                existing_lines.mapped("attendance_date")
            )

            current_date = effective_start

            while current_date <= effective_end:
                if current_date in existing_dates:
                    result["existing"] += 1
                    current_date += timedelta(days=1)
                    continue

                attendance_code = (
                    "H" if current_date.weekday() >= 5 else "P"
                )

                register_env.create_or_update_attendance_line(
                    employee=employee,
                    attendance_date=current_date,
                    attendance_code=attendance_code,
                    fiscal_year_label=(
                        self._management_fiscal_year_label(
                            current_date
                        )
                    ),
                    month_label=current_date.strftime("%B %Y"),
                    source="manual",
                    notes=(
                        "Automatically generated for management "
                        "attendance after completion of the day."
                    ),
                )

                result["created"] += 1
                current_date += timedelta(days=1)

        _logger.info(
            "Management automatic attendance completed: %s",
            result,
        )

        return result
