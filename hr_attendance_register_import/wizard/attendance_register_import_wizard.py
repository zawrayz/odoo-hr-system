import base64
from io import BytesIO
from calendar import monthrange
from datetime import date, datetime

from openpyxl import load_workbook

from odoo import fields, models
from odoo.exceptions import ValidationError


class HrAttendanceRegisterImportWizard(models.TransientModel):
    _name = 'hr.attendance.register.import.wizard'
    _description = 'Attendance Register Import Wizard'

    file_name = fields.Char(string='File Name')
    file_data = fields.Binary(string='Excel File', required=True)
    result_html = fields.Html(string='Import Result', readonly=True)

    def _normalize_code(self, raw_value):
        if raw_value is None:
            return False

        value = str(raw_value).strip().upper()
        if not value or value == '-':
            return False

        aliases = {
            'P': 'P',
            'R': 'R',
            'WFH': 'R',
            'H': 'H',
            'S': 'S',
            'SL': 'S',
            'C': 'C',
            'CL': 'C',
            'U': 'U',
            'UL': 'U',
            'D': 'D',
            'OT': 'OT',
        }
        return aliases.get(value, False)

    def _is_date_like(self, value):
        return isinstance(value, (date, datetime))

    def _extract_month_date(self, value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return False

    def action_import_attendance_register(self):
        self.ensure_one()

        if not self.file_data:
            raise ValidationError("Please upload an Excel file.")

        file_content = base64.b64decode(self.file_data)
        workbook = load_workbook(BytesIO(file_content), data_only=True)
        sheet = workbook.active

        employee_env = self.env['hr.employee'].sudo()
        register_env = self.env['hr.attendance.register.line'].sudo()

        created_count = 0
        updated_count = 0
        skipped_count = 0
        unknown_employee_count = 0
        unknown_code_count = 0
        details = []

        # Expected real file structure:
        # Row 1: FY title/header
        # Row 2: day numbers
        # Row 3: weekday labels
        # Row 4: sample/template row
        # Row 5 onward: employee rows
        #
        # Columns:
        # A = Fiscal Year
        # B = Month (Excel date or date-like value)
        # C = Employee Name
        # D onward = day 1, day 2, day 3 ...

        for row_idx, row in enumerate(sheet.iter_rows(min_row=1, values_only=True), start=1):
            if not row or not any(row):
                continue

            fiscal_year_cell = row[0] if len(row) > 0 else None
            month_cell = row[1] if len(row) > 1 else None
            employee_name = row[2] if len(row) > 2 else None

            # Skip title/header-like first row
            if row_idx == 1 and fiscal_year_cell and not month_cell and not employee_name:
                continue

            # Skip day-number row and weekday row and sample row
            # We only process rows where column C has a real employee name (text)
            if not employee_name or self._is_date_like(employee_name):
                continue

            month_date = self._extract_month_date(month_cell)
            if not month_date:
                skipped_count += 1
                details.append(f"Row {row_idx} skipped: invalid month value.")
                continue

            current_year_number = month_date.year
            current_month_number = month_date.month
            fiscal_year_label = str(fiscal_year_cell).strip() if fiscal_year_cell else ''
            month_label = month_date.strftime('%B %Y')

            employee_name_text = str(employee_name).strip()
            employee = employee_env.search([
                ('name', '=', employee_name_text)
            ], limit=1)

            if not employee:
                unknown_employee_count += 1
                skipped_count += 1
                details.append(f"Row {row_idx} skipped: employee '{employee_name_text}' not found.")
                continue

            max_day = monthrange(current_year_number, current_month_number)[1]

            # D column = day 1
            # zero-based row tuple index => D = 3
            for day_no in range(1, max_day + 1):
                col_index = 3 + (day_no - 1)
                if col_index >= len(row):
                    continue

                raw_code = row[col_index]
                attendance_code = self._normalize_code(raw_code)

                if raw_code not in (None, '', '-') and not attendance_code:
                    unknown_code_count += 1
                    details.append(
                        f"Row {row_idx}, day {day_no}: unknown code '{raw_code}' for {employee.name}."
                    )
                    continue

                if not attendance_code:
                    continue

                attendance_date = date(current_year_number, current_month_number, day_no)

                line, status = register_env.create_or_update_attendance_line(
                    employee=employee,
                    attendance_date=attendance_date,
                    attendance_code=attendance_code,
                    fiscal_year_label=fiscal_year_label,
                    month_label=month_label,
                    source='sheet_import',
                    notes=f"Imported from file {self.file_name or ''}",
                )

                if status == 'created':
                    created_count += 1
                else:
                    updated_count += 1

        self.result_html = f"""
            <h3>Attendance Register Import Summary</h3>
            <ul>
                <li><strong>Created Lines:</strong> {created_count}</li>
                <li><strong>Updated Lines:</strong> {updated_count}</li>
                <li><strong>Skipped Rows / Items:</strong> {skipped_count}</li>
                <li><strong>Unknown Employees:</strong> {unknown_employee_count}</li>
                <li><strong>Unknown Codes:</strong> {unknown_code_count}</li>
            </ul>
            <h4>Details</h4>
            <ul>
                {''.join(f'<li>{item}</li>' for item in details[:100])}
            </ul>
        """

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance.register.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }