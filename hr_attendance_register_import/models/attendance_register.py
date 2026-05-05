from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrAttendanceRegisterLine(models.Model):
    _name = 'hr.attendance.register.line'
    _description = 'HR Attendance Register Line'
    _order = 'attendance_date desc, employee_id asc'
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
        ondelete='cascade',
        index=True,
    )

    employee_code = fields.Char(
        string='Employee Code',
        related='employee_id.employee_code',
        store=True,
        readonly=True,
    )

    attendance_date = fields.Date(
        string='Attendance Date',
        required=True,
        index=True,
    )

    attendance_code = fields.Selection(
        [
            ('P', 'Present'),
            ('R', 'Remote / WFH'),
            ('H', 'Holiday'),
            ('S', 'Sick Leave'),
            ('C', 'Casual Leave'),
            ('U', 'Unpaid Leave'),
            ('D', 'Late / Data Delayed'),
            ('OT', 'Overtime'),
        ],
        string='Attendance Code',
        required=True,
        index=True,
    )

    fiscal_year_label = fields.Char(string='Fiscal Year')
    month_label = fields.Char(string='Month')
    source = fields.Selection(
        [
            ('sheet_import', 'Sheet Import'),
            ('daily_work_report', 'Daily Work Report'),
            ('manual', 'Manual'),
        ],
        string='Source',
        default='manual',
        required=True,
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_employee_attendance_date',
            'unique(employee_id, attendance_date)',
            'Attendance already exists for this employee on this date.',
        ),
    ]

    @api.depends('employee_id', 'attendance_date', 'attendance_code')
    def _compute_display_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Employee'
            date_text = rec.attendance_date or ''
            code = rec.attendance_code or ''
            rec.display_name = f"{employee_name} - {date_text} - {code}"

    @api.constrains('attendance_code')
    def _check_attendance_code(self):
        valid_codes = {'P', 'R', 'H', 'S', 'C', 'U', 'D', 'OT'}
        for rec in self:
            if rec.attendance_code not in valid_codes:
                raise ValidationError("Invalid attendance code.")

    @api.model
    def create_or_update_attendance_line(
        self,
        employee,
        attendance_date,
        attendance_code,
        fiscal_year_label=False,
        month_label=False,
        source='manual',
        notes=False,
    ):
        """Safe upsert helper for imports and task report sync."""
        if not employee:
            raise ValidationError("Employee is required.")
        if not attendance_date:
            raise ValidationError("Attendance date is required.")
        if not attendance_code:
            raise ValidationError("Attendance code is required.")

        existing = self.search([
            ('employee_id', '=', employee.id),
            ('attendance_date', '=', attendance_date),
        ], limit=1)

        vals = {
            'employee_id': employee.id,
            'attendance_date': attendance_date,
            'attendance_code': attendance_code,
            'fiscal_year_label': fiscal_year_label or '',
            'month_label': month_label or '',
            'source': source,
            'notes': notes or '',
        }

        if existing:
            existing.write(vals)
            return existing, 'updated'

        return self.create(vals), 'created'