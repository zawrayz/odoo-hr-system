import base64
from io import BytesIO
from datetime import datetime, date

from openpyxl import load_workbook

from odoo import fields, models
from odoo.exceptions import ValidationError


class HrPayrollRegisterImportWizard(models.TransientModel):
    _name = 'hr.payroll.register.import.wizard'
    _description = 'Payroll Register Import Wizard'

    file_name = fields.Char(string='File Name')
    file_data = fields.Binary(string='Excel File', required=True)
    result_html = fields.Html(string='Import Result', readonly=True)

    def _to_float(self, value):
        if value in (None, '', False):
            return 0.0
        try:
            return float(value)
        except Exception:
            return 0.0

    def _to_date(self, value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return False

    def _parse_text_month(self, value):
        if not value:
            return False

        text = str(value).strip()
        if not text:
            return False

        for fmt in (
            '%b %Y', '%B %Y', '%b-%y', '%b-%Y',
            '%Y-%m-%d', '%d-%b-%y', '%d-%b-%Y'
        ):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        return False

    def _clean_header(self, value):
        if value in (None, False):
            return ''
        return str(value).replace('\n', ' ').strip()

    def _build_header_map(self, row1, row2):
        header_map = {}

        row1_vals = [self._clean_header(v) for v in row1]
        row2_vals = [self._clean_header(v) for v in row2]

        for idx in range(len(row1_vals)):
            top = row1_vals[idx]
            sub = row2_vals[idx]

            if top and not sub:
                header_map[top] = idx
            elif not top and sub:
                header_map[sub] = idx
            elif top and sub:
                header_map[f"{top} / {sub}"] = idx
                header_map[sub] = idx

        return header_map

    def _get_col(self, header_map, *names):
        for name in names:
            if name in header_map:
                return header_map[name]
        return False

    def action_import_payroll_register(self):
        self.ensure_one()

        if not self.file_data:
            raise ValidationError("Please upload an Excel file.")

        file_content = base64.b64decode(self.file_data)
        workbook = load_workbook(BytesIO(file_content), data_only=True)
        sheet = workbook.active

        employee_env = self.env['hr.employee'].sudo()
        payroll_env = self.env['hr.payroll.register.line'].sudo()

        created_count = 0
        updated_count = 0
        skipped_count = 0
        unknown_employee_count = 0
        details = []

        # This file has a fixed 2-row header structure:
        # Row 1 = main labels
        # Row 2 = sub labels
        # Row 3/4 = separators / first month header rows
        row1 = [cell for cell in next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))]
        row2 = [cell for cell in next(sheet.iter_rows(min_row=2, max_row=2, values_only=True))]
        header_map = self._build_header_map(row1, row2)

        fy_idx = self._get_col(header_map, 'FY Selection', 'Fiscal Year')
        month_idx = self._get_col(header_map, 'Month')
        employee_code_idx = self._get_col(header_map, 'Employee ID')
        employee_name_idx = self._get_col(header_map, 'Employee Name')
        designation_idx = self._get_col(header_map, 'Designation')
        payment_method_idx = self._get_col(header_map, 'Payment Method', 'Bank')
        basic_salary_idx = self._get_col(header_map, 'Basic Salary')
        basic_actual_idx = self._get_col(header_map, 'Basic Actual')
        medical_allowance_idx = self._get_col(header_map, 'Medical Allowance')
        advertised_salary_idx = self._get_col(header_map, 'Advertised Salary')
        project_salary_idx = self._get_col(header_map, 'Project Salary')
        bonus_idx = self._get_col(header_map, 'Bonus')
        allowance_idx = self._get_col(header_map, 'Allowance')
        allowance_detail_idx = self._get_col(header_map, 'Allowance Detail')
        taxable_income_idx = self._get_col(header_map, 'Taxable Income')
        yearly_income_idx = self._get_col(header_map, 'Yearly Income')
        income_tax_idx = self._get_col(header_map, 'Income Tax  Deduction', 'Income Tax Deduction')
        other_deduction_idx = self._get_col(header_map, 'Other Deductions')
        total_idx = self._get_col(header_map, 'Total')
        total_round_idx = self._get_col(header_map, 'Total Round')
        total_salary_idx = self._get_col(header_map, 'Total Salary')
        loans_idx = self._get_col(header_map, 'Loans from Cash')
        payment_date_idx = self._get_col(header_map, 'Payment Date')
        payment_idx = self._get_col(header_map, 'Payment')
        inclusive_tax_idx = self._get_col(header_map, 'Inclusive of Tax')
        remaining_idx = self._get_col(header_map, 'Remaining')
        period_idx = self._get_col(header_map, 'For the period of')
        paid_at_idx = self._get_col(header_map, 'and payed at')
        comments_idx = self._get_col(header_map, 'Comments')

        if employee_code_idx is False or employee_name_idx is False or fy_idx is False or month_idx is False:
            raise ValidationError(
                "Payroll sheet header could not be detected. Please check that FY Selection, Month, Employee ID, and Employee Name columns exist."
            )

        # Data starts after row 4 in your file
        for row_idx, row in enumerate(sheet.iter_rows(min_row=5, values_only=True), start=5):
            row_vals = list(row)

            if not any(row_vals):
                continue

            fiscal_year = str(row_vals[fy_idx] or '').strip() if fy_idx is not False else ''
            month_raw = row_vals[month_idx] if month_idx is not False else None
            employee_code = str(row_vals[employee_code_idx] or '').strip() if employee_code_idx is not False else ''
            employee_name = str(row_vals[employee_name_idx] or '').strip() if employee_name_idx is not False else ''

            # skip month divider rows like FY-24/25 + month date but no employee code/name
            if not employee_code and not employee_name:
                skipped_count += 1
                details.append(f"Row {row_idx} skipped: no employee code/name.")
                continue

            month_date = self._to_date(month_raw)
            if not month_date and month_raw:
                month_date = self._parse_text_month(month_raw)

            if not fiscal_year or not month_date:
                skipped_count += 1
                details.append(f"Row {row_idx} skipped: missing fiscal year or month.")
                continue

            employee = False
            if employee_code:
                employee = employee_env.search([('employee_code', '=', employee_code)], limit=1)

            if not employee and employee_name:
                employee = employee_env.search([('name', '=', employee_name)], limit=1)

            if not employee:
                unknown_employee_count += 1
                skipped_count += 1
                details.append(
                    f"Row {row_idx} skipped: employee not found for code '{employee_code}' / name '{employee_name}'."
                )
                continue

            def get_val(index, default=''):
                if index is False:
                    return default
                if index >= len(row_vals):
                    return default
                return row_vals[index]

            vals = {
                'employee_name_text': employee_name,
                'fiscal_year_label': fiscal_year,
                'designation': str(get_val(designation_idx) or '').strip(),
                'payment_method': str(get_val(payment_method_idx) or '').strip(),
                'basic_salary': self._to_float(get_val(basic_salary_idx, 0)),
                'basic_actual': self._to_float(get_val(basic_actual_idx, 0)),
                'medical_allowance': self._to_float(get_val(medical_allowance_idx, 0)),
                'advertised_salary': self._to_float(get_val(advertised_salary_idx, 0)),
                'project_salary': self._to_float(get_val(project_salary_idx, 0)),
                'bonus': self._to_float(get_val(bonus_idx, 0)),
                'allowance': self._to_float(get_val(allowance_idx, 0)),
                'allowance_detail': str(get_val(allowance_detail_idx) or '').strip(),
                'taxable_income': self._to_float(get_val(taxable_income_idx, 0)),
                'yearly_income': self._to_float(get_val(yearly_income_idx, 0)),
                'income_tax_deduction': self._to_float(get_val(income_tax_idx, 0)),
                'other_deductions': self._to_float(get_val(other_deduction_idx, 0)),
                'total': self._to_float(get_val(total_idx, 0)),
                'total_round': self._to_float(get_val(total_round_idx, 0)),
                'total_salary': self._to_float(get_val(total_salary_idx, 0)),
                'loans_from_cash': self._to_float(get_val(loans_idx, 0)),
                'payment_date': self._to_date(get_val(payment_date_idx)),
                'payment': self._to_float(get_val(payment_idx, 0)),
                'inclusive_of_tax': str(get_val(inclusive_tax_idx) or '').strip(),
                'remaining': self._to_float(get_val(remaining_idx, 0)),
                'period_label': str(get_val(period_idx) or '').strip(),
                'paid_at': str(get_val(paid_at_idx) or '').strip(),
                'comments': str(get_val(comments_idx) or '').strip(),
                'source': 'sheet_import',
            }

            rec, status = payroll_env.create_or_update_payroll_line(employee, month_date, vals)
            if status == 'created':
                created_count += 1
            else:
                updated_count += 1

        self.result_html = f"""
            <h3>Payroll Register Import Summary</h3>
            <ul>
                <li><strong>Created Lines:</strong> {created_count}</li>
                <li><strong>Updated Lines:</strong> {updated_count}</li>
                <li><strong>Skipped Rows:</strong> {skipped_count}</li>
                <li><strong>Unknown Employees:</strong> {unknown_employee_count}</li>
            </ul>
            <h4>Details</h4>
            <ul>
                {''.join(f'<li>{item}</li>' for item in details[:100])}
            </ul>
        """

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.register.import.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }