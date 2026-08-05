from datetime import date, datetime
from urllib.parse import urlencode

from odoo import fields, http
from odoo.http import request


class HrPettyCashPortal(http.Controller):

    FISCAL_YEAR_WINDOW = 5

    def _is_hr_manager(self):
        return request.env.user.has_group('hr.group_hr_manager')

    def _parse_amount(self, value):
        cleaned_value = (
            (value or '')
            .replace(',', '')
            .replace('Rs.', '')
            .replace('Rs', '')
            .strip()
        )

        if not cleaned_value:
            return 0.0

        return round(float(cleaned_value), 2)

    def _finance_redirect(self, params=None):
        url = '/my/hr/admin/finance'

        if params:
            url = '%s?%s' % (url, urlencode(params))

        return request.redirect(url)

    def _get_fiscal_year_start_year(self, target_date):
        if target_date.month >= 7:
            return target_date.year

        return target_date.year - 1

    def _get_fiscal_year_label(self, start_year):
        return 'FY %s-%s' % (
            start_year,
            str(start_year + 1)[-2:],
        )

    def _get_fiscal_year_options(self, petty_cash_entry_model):
        today = fields.Date.context_today(request.env.user)

        current_start_year = (
            self._get_fiscal_year_start_year(today)
        )

        start_years = {
            current_start_year - offset
            for offset in range(self.FISCAL_YEAR_WINDOW)
        }

        transaction_dates = petty_cash_entry_model.search(
            []
        ).mapped('transaction_date')

        for transaction_date in transaction_dates:
            if transaction_date:
                start_years.add(
                    self._get_fiscal_year_start_year(
                        transaction_date
                    )
                )

        return [
            {
                'value': str(start_year),
                'label': self._get_fiscal_year_label(
                    start_year
                ),
            }
            for start_year in sorted(
                start_years,
                reverse=True,
            )
        ]

    def _get_month_options(self, fiscal_year_start_year):
        month_options = []

        for offset in range(12):
            month_number = 7 + offset
            month_year = fiscal_year_start_year

            if month_number > 12:
                month_number -= 12
                month_year += 1

            month_start = date(
                month_year,
                month_number,
                1,
            )

            month_options.append({
                'value': month_start.strftime('%Y-%m'),
                'label': month_start.strftime('%b-%y'),
            })

        return month_options

    @http.route(
        [
            '/my/hr/admin/finance',
            '/my/hr/admin/finance/petty-cash',
        ],
        type='http',
        auth='user',
        website=True,
    )
    def admin_petty_cash_page(
        self,
        fy=None,
        month=None,
        **kwargs
    ):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        petty_cash_entry_model = request.env[
            'hr.petty.cash.entry'
        ].sudo()

        fiscal_year_options = (
            self._get_fiscal_year_options(
                petty_cash_entry_model
            )
        )

        valid_fiscal_years = {
            option['value']
            for option in fiscal_year_options
        }

        today = fields.Date.context_today(
            request.env.user
        )

        current_fiscal_year = str(
            self._get_fiscal_year_start_year(today)
        )

        selected_fiscal_year = (fy or '').strip()

        if selected_fiscal_year not in valid_fiscal_years:
            selected_fiscal_year = current_fiscal_year

        fiscal_year_start_year = int(
            selected_fiscal_year
        )

        fiscal_year_start = date(
            fiscal_year_start_year,
            7,
            1,
        )

        fiscal_year_end = date(
            fiscal_year_start_year + 1,
            6,
            30,
        )

        month_options = self._get_month_options(
            fiscal_year_start_year
        )

        valid_months = {
            option['value']
            for option in month_options
        }

        selected_month = (month or '').strip()

        if selected_month not in valid_months:
            selected_month = ''

        domain = [
            (
                'transaction_date',
                '>=',
                fiscal_year_start,
            ),
            (
                'transaction_date',
                '<=',
                fiscal_year_end,
            ),
        ]

        if selected_month:
            selected_month_date = datetime.strptime(
                selected_month,
                '%Y-%m',
            ).date()

            domain.append(
                (
                    'month_start',
                    '=',
                    selected_month_date,
                )
            )

        entries = petty_cash_entry_model.search(
            domain,
            order='transaction_date asc, id asc',
        )

        total_received = sum(
            entries.mapped('received')
        )

        total_expense = sum(
            entries.mapped('expense_paid')
        )

        balance = total_received - total_expense

        values = {
            'is_hr_manager': True,
            'entries': entries,

            'balance': balance,
            'total_received': total_received,
            'total_expense': total_expense,

            'fiscal_year_options':
                fiscal_year_options,

            'selected_fiscal_year':
                selected_fiscal_year,

            'selected_fiscal_year_label':
                self._get_fiscal_year_label(
                    fiscal_year_start_year
                ),

            'month_options': month_options,
            'selected_month': selected_month,

            'today_value': today.strftime(
                '%Y-%m-%d'
            ),

            'entry_added':
                kwargs.get('entry_added') == '1',

            'entry_updated':
                kwargs.get('entry_updated') == '1',

            'entry_error': (
                kwargs.get('entry_error') or ''
            ).strip(),
        }

        return request.render(
            'hr_petty_cash_management.'
            'hr_admin_petty_cash_page',
            values,
        )

    @http.route(
        '/my/hr/admin/finance/petty-cash/add',
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
        csrf=True,
    )
    def admin_petty_cash_add(self, **post):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        transaction_date_value = (
            post.get('transaction_date') or ''
        ).strip()

        description = (
            post.get('description') or ''
        ).strip()

        remarks = (
            post.get('remarks') or ''
        ).strip()

        selected_fiscal_year = (
            post.get('selected_fiscal_year') or ''
        ).strip()

        selected_month = (
            post.get('selected_month') or ''
        ).strip()

        redirect_params = {}

        if selected_fiscal_year:
            redirect_params['fy'] = (
                selected_fiscal_year
            )

        if selected_month:
            redirect_params['month'] = (
                selected_month
            )

        if not transaction_date_value:
            redirect_params['entry_error'] = (
                'Transaction date is required.'
            )
            return self._finance_redirect(
                redirect_params
            )

        try:
            transaction_date = fields.Date.to_date(
                transaction_date_value
            )
        except (TypeError, ValueError):
            transaction_date = False

        if not transaction_date:
            redirect_params['entry_error'] = (
                'Please enter a valid transaction date.'
            )
            return self._finance_redirect(
                redirect_params
            )

        if not description:
            redirect_params['entry_error'] = (
                'Description is required.'
            )
            return self._finance_redirect(
                redirect_params
            )

        try:
            received = self._parse_amount(
                post.get('received')
            )

            expense_paid = self._parse_amount(
                post.get('expense_paid')
            )

        except (TypeError, ValueError):
            redirect_params['entry_error'] = (
                'Received and Expense/Paid must '
                'be valid numbers.'
            )
            return self._finance_redirect(
                redirect_params
            )

        if received < 0 or expense_paid < 0:
            redirect_params['entry_error'] = (
                'Received and Expense/Paid '
                'cannot be negative.'
            )
            return self._finance_redirect(
                redirect_params
            )

        if received == 0 and expense_paid == 0:
            redirect_params['entry_error'] = (
                'Enter an amount in Received '
                'or Expense/Paid.'
            )
            return self._finance_redirect(
                redirect_params
            )

        invoice_shared = (
            post.get('invoice_shared') == '1'
        )

        request.env[
            'hr.petty.cash.entry'
        ].sudo().create({
            'transaction_date': transaction_date,
            'description': description,
            'received': received,
            'expense_paid': expense_paid,
            'remarks': remarks,
            'invoice_shared': invoice_shared,
            'company_id': request.env.company.id,
        })

        entry_fiscal_year = (
            self._get_fiscal_year_start_year(
                transaction_date
            )
        )

        return self._finance_redirect({
            'fy': str(entry_fiscal_year),
            'month': transaction_date.strftime(
                '%Y-%m'
            ),
            'entry_added': '1',
        })
    @http.route(
        '/my/hr/admin/finance/petty-cash/'
        '<int:entry_id>/edit',
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
        csrf=True,
    )
    def admin_petty_cash_edit(
        self,
        entry_id,
        **post
    ):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        selected_fiscal_year = (
            post.get('selected_fiscal_year') or ''
        ).strip()

        selected_month = (
            post.get('selected_month') or ''
        ).strip()

        redirect_params = {}

        if selected_fiscal_year:
            redirect_params['fy'] = (
                selected_fiscal_year
            )

        if selected_month:
            redirect_params['month'] = (
                selected_month
            )

        entry = request.env[
            'hr.petty.cash.entry'
        ].sudo().search(
            [
                ('id', '=', entry_id),
                (
                    'company_id',
                    '=',
                    request.env.company.id,
                ),
            ],
            limit=1,
        )

        if not entry:
            redirect_params['entry_error'] = (
                'The petty cash entry could not be found.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if entry.invoice_shared:
            redirect_params['entry_error'] = (
                'This entry is locked because its '
                'invoice has already been shared.'
            )

            return self._finance_redirect(
                redirect_params
            )

        transaction_date_value = (
            post.get('transaction_date') or ''
        ).strip()

        description = (
            post.get('description') or ''
        ).strip()

        remarks = (
            post.get('remarks') or ''
        ).strip()

        if not transaction_date_value:
            redirect_params['entry_error'] = (
                'Transaction date is required.'
            )

            return self._finance_redirect(
                redirect_params
            )

        try:
            transaction_date = fields.Date.to_date(
                transaction_date_value
            )
        except (TypeError, ValueError):
            transaction_date = False

        if not transaction_date:
            redirect_params['entry_error'] = (
                'Please enter a valid transaction date.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if not description:
            redirect_params['entry_error'] = (
                'Description is required.'
            )

            return self._finance_redirect(
                redirect_params
            )

        try:
            received = self._parse_amount(
                post.get('received')
            )

            expense_paid = self._parse_amount(
                post.get('expense_paid')
            )

        except (TypeError, ValueError):
            redirect_params['entry_error'] = (
                'Received and Expense/Paid must '
                'be valid numbers.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if received < 0 or expense_paid < 0:
            redirect_params['entry_error'] = (
                'Received and Expense/Paid '
                'cannot be negative.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if received == 0 and expense_paid == 0:
            redirect_params['entry_error'] = (
                'Enter an amount in Received '
                'or Expense/Paid.'
            )

            return self._finance_redirect(
                redirect_params
            )

        invoice_shared = (
            post.get('invoice_shared') == '1'
        )

        entry.write({
            'transaction_date': transaction_date,
            'description': description,
            'received': received,
            'expense_paid': expense_paid,
            'remarks': remarks,
            'invoice_shared': invoice_shared,
        })

        entry_fiscal_year = (
            self._get_fiscal_year_start_year(
                transaction_date
            )
        )

        return self._finance_redirect({
            'fy': str(entry_fiscal_year),
            'month': transaction_date.strftime(
                '%Y-%m'
            ),
            'entry_updated': '1',
        })
