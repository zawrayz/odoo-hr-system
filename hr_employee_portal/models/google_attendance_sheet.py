import calendar
import os
import re
import time
from urllib.parse import parse_qs, urlparse

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    service_account = None
    build = None


class HrAttendanceSheetConnection(models.Model):
    _name = 'hr.attendance.sheet.connection'
    _description = 'Google Attendance Sheet Connection'
    _order = 'month_start desc'

    month_start = fields.Date(
        string='Attendance Month',
        required=True,
        index=True,
    )

    spreadsheet_url = fields.Char(
        string='Google Sheet URL',
        required=True,
    )

    spreadsheet_id = fields.Char(
        string='Spreadsheet ID',
        required=True,
        index=True,
    )

    spreadsheet_title = fields.Char(
        string='Spreadsheet Title',
        readonly=True,
    )

    worksheet_title = fields.Char(
        string='Worksheet',
        readonly=True,
    )

    worksheet_gid = fields.Char(
        string='Worksheet GID',
        readonly=True,
    )

    active = fields.Boolean(
        string='Connected',
        default=True,
        index=True,
    )

    sync_pending = fields.Boolean(
        string='Sync Pending',
        default=False,
        index=True,
    )

    last_sync_at = fields.Datetime(
        string='Last Sync',
        readonly=True,
    )

    last_sync_status = fields.Selection(
        [
            ('success', 'Success'),
            ('error', 'Error'),
        ],
        string='Last Sync Status',
        readonly=True,
    )

    last_sync_message = fields.Char(
        string='Last Sync Message',
        readonly=True,
    )

    last_sync_error = fields.Text(
        string='Last Sync Error',
        readonly=True,
    )

    _sql_constraints = [
        (
            'unique_attendance_sheet_month',
            'unique(month_start)',
            'Only one Google attendance sheet connection is allowed per month.',
        ),
    ]

    # ---------------------------------------------------------
    # Connection lookup
    # ---------------------------------------------------------
    @api.model
    def get_for_month(self, month_start):
        month_start = fields.Date.to_date(month_start)
        if not month_start:
            return self.browse()

        month_start = month_start.replace(day=1)

        return self.sudo().with_context(active_test=False).search(
            [('month_start', '=', month_start)],
            limit=1,
        )

    # ---------------------------------------------------------
    # Google credential / API helpers
    # ---------------------------------------------------------
    @api.model
    def _get_credentials_path(self):
        env_path = (
            os.environ.get('ODOO_GOOGLE_ATTENDANCE_CREDENTIALS')
            or ''
        ).strip()

        if env_path:
            return env_path

        return (
            self.env['ir.config_parameter']
            .sudo()
            .get_param(
                'hr_employee_portal.google_attendance_credentials_path',
                '',
            )
            or ''
        ).strip()

    @api.model
    def _get_google_service(self):
        if not service_account or not build:
            raise UserError(
                _(
                    'Google API Python libraries are not installed. '
                    'Install google-auth and google-api-python-client.'
                )
            )

        credentials_path = self._get_credentials_path()

        if not credentials_path:
            raise UserError(
                _(
                    'Google attendance credentials path is not configured.'
                )
            )

        if not os.path.isfile(credentials_path):
            raise UserError(
                _(
                    'Google attendance credentials file was not found: %s'
                )
                % credentials_path
            )

        credentials = (
            service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                ],
            )
        )

        return build(
            'sheets',
            'v4',
            credentials=credentials,
            cache_discovery=False,
        )

    # ---------------------------------------------------------
    # Spreadsheet URL parsing
    # ---------------------------------------------------------
    @api.model
    def _parse_spreadsheet_url(self, spreadsheet_url):
        spreadsheet_url = (spreadsheet_url or '').strip()

        match = re.search(
            r'/spreadsheets/d/([A-Za-z0-9_-]+)',
            spreadsheet_url,
        )

        if not match:
            raise UserError(
                _('Please enter a valid Google Sheets URL.')
            )

        spreadsheet_id = match.group(1)
        parsed = urlparse(spreadsheet_url)

        gid = ''

        query_values = parse_qs(parsed.query)
        if query_values.get('gid'):
            gid = query_values['gid'][0]

        if not gid and parsed.fragment:
            fragment_values = parse_qs(parsed.fragment)
            if fragment_values.get('gid'):
                gid = fragment_values['gid'][0]

        return spreadsheet_id, str(gid or '')

    @api.model
    def _get_spreadsheet_metadata(
        self,
        spreadsheet_id,
        requested_gid='',
    ):
        service = self._get_google_service()

        metadata = (
            service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id)
            .execute()
        )

        spreadsheet_title = (
            metadata.get('properties', {}).get('title') or ''
        )

        sheets = metadata.get('sheets', [])

        if not sheets:
            raise UserError(
                _('The Google spreadsheet has no worksheets.')
            )

        selected_sheet = False

        if requested_gid:
            for sheet in sheets:
                properties = sheet.get('properties', {})
                if str(properties.get('sheetId')) == str(requested_gid):
                    selected_sheet = sheet
                    break

            if not selected_sheet:
                raise UserError(
                    _(
                        'The worksheet referenced by the Sheet URL '
                        'could not be found.'
                    )
                )

        if not selected_sheet:
            selected_sheet = sheets[0]

        properties = selected_sheet.get('properties', {})

        return {
            'spreadsheet_title': spreadsheet_title,
            'worksheet_title': properties.get('title') or 'Sheet1',
            'worksheet_gid': str(properties.get('sheetId') or ''),
        }

    # ---------------------------------------------------------
    # Connect / Disconnect
    # ---------------------------------------------------------
    @api.model
    def connect_for_month(self, month_start, spreadsheet_url):
        month_start = fields.Date.to_date(month_start)

        if not month_start:
            raise UserError(_('Attendance month is required.'))

        month_start = month_start.replace(day=1)

        spreadsheet_id, requested_gid = (
            self._parse_spreadsheet_url(spreadsheet_url)
        )

        metadata = False

        for retry_count in range(3):
            try:
                metadata = self._get_spreadsheet_metadata(
                    spreadsheet_id,
                    requested_gid=requested_gid,
                )
                break
            except UserError:
                raise
            except Exception as error:
                status = getattr(
                    getattr(error, 'resp', None),
                    'status',
                    None,
                )

                if status and status not in [429, 500, 502, 503, 504]:
                    raise

                if retry_count >= 2:
                    raise UserError(
                        _(
                            'Google Sheets is temporarily unreachable. '
                            'Please try again in a moment.'
                        )
                    ) from error

                time.sleep(1 if retry_count == 0 else 2)

        connection = self.get_for_month(month_start)

        vals = {
            'month_start': month_start,
            'spreadsheet_url': spreadsheet_url.strip(),
            'spreadsheet_id': spreadsheet_id,
            'spreadsheet_title': metadata['spreadsheet_title'],
            'worksheet_title': metadata['worksheet_title'],
            'worksheet_gid': metadata['worksheet_gid'],
            'active': True,
            'sync_pending': False,
            'last_sync_error': False,
        }

        if connection:
            connection.write(vals)
        else:
            connection = self.sudo().create(vals)

        return connection

    def disconnect_sheet(self):
        self.ensure_one()

        self.sudo().write({
            'active': False,
            'sync_pending': False,
        })

        return True

    # ---------------------------------------------------------
    # Odoo attendance data for one month
    # Mirrors the current Admin Attendance matrix resolution:
    # last working date -> leave overlay -> register -> weekend
    # ---------------------------------------------------------
    def _get_month_employees(self):
        self.ensure_one()

        month_start = fields.Date.to_date(self.month_start)
        total_days = calendar.monthrange(
            month_start.year,
            month_start.month,
        )[1]
        month_end = month_start.replace(day=total_days)

        employee_env = (
            self.env['hr.employee']
            .sudo()
            .with_context(active_test=False)
        )

        register_env = (
            self.env['hr.attendance.register.line'].sudo()
        )

        month_lines = register_env.search([
            ('attendance_date', '>=', month_start),
            ('attendance_date', '<=', month_end),
        ])

        inactive_month_employee_ids = {
            line.employee_id.id
            for line in month_lines
            if line.employee_id
            and (
                not line.employee_id.last_working_date
                or line.attendance_date
                <= line.employee_id.last_working_date
            )
        }

        return employee_env.search([
            ('employee_code', '!=', False),
            '|',
            ('active', '=', True),
            ('id', 'in', list(inactive_month_employee_ids)),
        ], order='name asc')

    def _build_month_attendance_rows(self):
        self.ensure_one()

        month_start = fields.Date.to_date(self.month_start)
        total_days = calendar.monthrange(
            month_start.year,
            month_start.month,
        )[1]
        month_end = month_start.replace(day=total_days)

        employees = self._get_month_employees()
        employee_ids = employees.ids

        register_map = {}

        if employee_ids:
            register_lines = (
                self.env['hr.attendance.register.line']
                .sudo()
                .search([
                    ('employee_id', 'in', employee_ids),
                    ('attendance_date', '>=', month_start),
                    ('attendance_date', '<=', month_end),
                ])
            )

            for line in register_lines:
                register_map[
                    (line.employee_id.id, line.attendance_date)
                ] = line.attendance_code

        leave_overlay = {}

        if (
            employee_ids
            and 'hr.employee.portal.request' in self.env
        ):
            leave_requests = (
                self.env['hr.employee.portal.request']
                .sudo()
                .search([
                    ('employee_id', 'in', employee_ids),
                    (
                        'request_type',
                        'in',
                        ['sick_leave', 'casual_leave', 'wfh'],
                    ),
                    ('state', 'in', ['submitted', 'approved']),
                    ('date_from', '<=', month_end),
                    ('date_to', '>=', month_start),
                ])
            )

            leave_requests = leave_requests.sorted(
                key=lambda record: (
                    0 if record.state == 'submitted' else 1
                )
            )

            for leave_request in leave_requests:
                if (
                    leave_request.request_type == 'wfh'
                    and leave_request.state != 'approved'
                ):
                    continue

                approved_code = (
                    'S'
                    if leave_request.request_type == 'sick_leave'
                    else (
                        'C'
                        if leave_request.request_type == 'casual_leave'
                        else 'R'
                    )
                )

                display_code = (
                    'LR'
                    if leave_request.state == 'submitted'
                    else approved_code
                )

                date_cursor = max(
                    leave_request.date_from,
                    month_start,
                )
                date_end = min(
                    leave_request.date_to,
                    month_end,
                )

                while date_cursor <= date_end:
                    key = (
                        leave_request.employee_id.id,
                        date_cursor,
                    )

                    if (
                        key not in leave_overlay
                        or display_code != 'LR'
                    ):
                        leave_overlay[key] = display_code

                    date_cursor += fields.Date.to_date(
                        '1970-01-02'
                    ) - fields.Date.to_date(
                        '1970-01-01'
                    )

        today = fields.Date.context_today(self)
        rows = []

        for employee in employees:
            day_codes = []

            for day_number in range(1, 32):
                if day_number > total_days:
                    day_codes.append('')
                    continue

                target_date = month_start.replace(
                    day=day_number
                )

                after_last_working_date = bool(
                    employee.last_working_date
                    and target_date
                    > employee.last_working_date
                )

                if after_last_working_date:
                    code = '-'
                else:
                    code = leave_overlay.get(
                        (employee.id, target_date)
                    )

                    if not code:
                        code = register_map.get(
                            (employee.id, target_date)
                        )

                if (
                    not after_last_working_date
                    and not code
                    and target_date.weekday() >= 5
                    and target_date < today
                ):
                    code = 'H'

                code = code or '-'

                day_codes.append(
                    '' if code == '-' else code
                )

            rows.append({
                'employee_id': employee.id,
                'employee_name': employee.name or '',
                'day_codes': day_codes,
            })

        return rows

    # ---------------------------------------------------------
    # Google Sheet validation
    # ---------------------------------------------------------
    def _sheet_range(self, cell_range):
        self.ensure_one()

        worksheet_title = (
            self.worksheet_title or 'Sheet1'
        ).replace("'", "''")

        return "'%s'!%s" % (
            worksheet_title,
            cell_range,
        )

    def _validate_sheet_layout(self, service):
        self.ensure_one()

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=self._sheet_range('A1:AO4'),
                valueRenderOption='FORMULA',
            )
            .execute()
        )

        rows = result.get('values', [])

        if not rows:
            raise UserError(
                _('The attendance Google Sheet is empty.')
            )

        header = rows[0] if rows else []

        for day_number in range(1, 32):
            column_index = day_number

            if column_index >= len(header):
                raise UserError(
                    _(
                        'The Google Sheet does not contain '
                        'attendance day columns 1 to 31.'
                    )
                )

            try:
                header_day = int(header[column_index])
            except (TypeError, ValueError):
                header_day = False

            if header_day != day_number:
                raise UserError(
                    _(
                        'Google Sheet attendance layout mismatch. '
                        'Expected day %s in the standard day column.'
                    )
                    % day_number
                )

        return True

    # ---------------------------------------------------------
    # Full month sync: Odoo -> Google Sheet
    # Only B:AF are written. Names, styles and formulas remain.
    # ---------------------------------------------------------
    def sync_now(self):
        self.ensure_one()

        if not self.active:
            return {
                'ok': False,
                'message': 'Google Sheet is disconnected.',
            }

        try:
            service = self._get_google_service()
            self._validate_sheet_layout(service)

            name_result = (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.spreadsheet_id,
                    range=self._sheet_range('A4:A1000'),
                    valueRenderOption='UNFORMATTED_VALUE',
                )
                .execute()
            )

            sheet_name_rows = name_result.get(
                'values',
                [],
            )

            sheet_employee_rows = {}

            for row_number, row in enumerate(
                sheet_name_rows,
                start=4,
            ):
                if not row:
                    continue

                employee_name = str(row[0] or '').strip()

                if not employee_name:
                    continue

                normalized_name = employee_name.casefold()

                if normalized_name in sheet_employee_rows:
                    raise UserError(
                        _(
                            'Duplicate employee name found in '
                            'Google Sheet: %s'
                        )
                        % employee_name
                    )

                sheet_employee_rows[
                    normalized_name
                ] = row_number

            attendance_rows = (
                self._build_month_attendance_rows()
            )

            odoo_name_count = {}

            for attendance_row in attendance_rows:
                normalized_name = (
                    attendance_row['employee_name']
                    .strip()
                    .casefold()
                )

                if normalized_name:
                    odoo_name_count[normalized_name] = (
                        odoo_name_count.get(
                            normalized_name,
                            0,
                        )
                        + 1
                    )

            duplicate_odoo_names = [
                attendance_row['employee_name']
                for attendance_row in attendance_rows
                if (
                    attendance_row['employee_name']
                    .strip()
                    .casefold()
                )
                and odoo_name_count.get(
                    attendance_row['employee_name']
                    .strip()
                    .casefold(),
                    0,
                ) > 1
            ]

            if duplicate_odoo_names:
                raise UserError(
                    _(
                        'Duplicate employee names exist in Odoo. '
                        'Cannot safely match the Google Sheet: %s'
                    )
                    % ', '.join(
                        sorted(set(duplicate_odoo_names))
                    )
                )

            batch_data = []
            missing_employees = []

            for attendance_row in attendance_rows:
                employee_name = (
                    attendance_row['employee_name']
                    .strip()
                )

                normalized_name = employee_name.casefold()

                row_number = sheet_employee_rows.get(
                    normalized_name
                )

                if not row_number:
                    missing_employees.append(employee_name)
                    continue

                batch_data.append({
                    'range': self._sheet_range(
                        'B%s:AF%s'
                        % (row_number, row_number)
                    ),
                    'values': [
                        attendance_row['day_codes']
                    ],
                })

            if batch_data:
                (
                    service.spreadsheets()
                    .values()
                    .batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body={
                            'valueInputOption': 'RAW',
                            'data': batch_data,
                        },
                    )
                    .execute()
                )

            matched_count = len(batch_data)

            message = (
                '%s employee attendance row(s) synced.'
                % matched_count
            )

            if missing_employees:
                message += (
                    ' %s Odoo employee(s) were not found '
                    'in the Google Sheet.'
                    % len(missing_employees)
                )

            self.sudo().write({
                'sync_pending': False,
                'last_sync_at': fields.Datetime.now(),
                'last_sync_status': 'success',
                'last_sync_message': message,
                'last_sync_error': False,
            })

            return {
                'ok': True,
                'message': message,
                'matched_count': matched_count,
                'missing_employees': missing_employees,
            }

        except Exception as error:
            retry_count = int(self.env.context.get(
                'google_attendance_sync_retry_count',
                0,
            ))

            if (
                not isinstance(error, UserError)
                and retry_count < 2
            ):
                time.sleep(1 if retry_count == 0 else 2)
                return self.with_context(
                    google_attendance_sync_retry_count=retry_count + 1,
                ).sync_now()

            error_message = str(error)

            self.sudo().write({
                'last_sync_at': fields.Datetime.now(),
                'last_sync_status': 'error',
                'last_sync_message': (
                    'Google Sheet sync failed.'
                ),
                'last_sync_error': error_message,
            })

            return {
                'ok': False,
                'message': error_message,
            }
