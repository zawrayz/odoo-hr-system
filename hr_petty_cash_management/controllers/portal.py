from datetime import date, datetime
from urllib.parse import urlencode, urlparse

from odoo import fields, http
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.http import request


class HrPettyCashPortal(http.Controller):

    FISCAL_YEAR_WINDOW = 5
    PAGE_SIZE = 10

    FULL_ACCESS_EMPLOYEE_CODES = {
        'BPL001',
        'BLMP43',
    }

    ENTRY_ACCESS_EMPLOYEE_CODES = set()

    def _is_hr_manager(self):
        return request.env.user.has_group(
            'hr.group_hr_manager'
        )

    def _get_current_employee(self):
        return request.env[
            'hr.employee'
        ].sudo().search(
            [
                (
                    'user_id',
                    '=',
                    request.env.user.id,
                ),
            ],
            limit=1,
        )

    def _get_current_employee_code(self):
        employee = self._get_current_employee()

        if not employee:
            return ''

        return (
            employee.employee_code or ''
        ).strip().upper()

    def _is_uzair(self):
        return (
            request.env.user.login or ''
        ).strip().lower() == 'uzair@blimpglobal.com'

    def _is_irfan(self):
        return (
            request.env.user.login or ''
        ).strip().lower() == (
            'irfan.saifullah@blimpglobal.com'
        )

    def _get_allowed_cash_holders(self):
        if self._is_uzair():
            return {
                'irfan',
                'hammad',
                'irfan_personal',
            }

        if self._is_irfan():
            return {
                'irfan',
                'irfan_personal',
            }

        if self._get_current_employee_code() == 'BLMP43':
            return {'hammad'}

        if self._get_finance_access() != 'none':
            return {'irfan'}

        return set()

    def _resolve_cash_holder(self, value=None):
        allowed_holders = self._get_allowed_cash_holders()
        requested_holder = (value or '').strip().lower()

        if requested_holder in allowed_holders:
            return requested_holder

        if len(allowed_holders) == 1:
            return next(iter(allowed_holders))

        if self._is_irfan() and not requested_holder:
            return 'irfan'

        return False

    def _get_cash_holder_label(self, cash_holder):
        return {
            'irfan': 'Irfan (Office)',
            'hammad': 'Hammad',
            'irfan_personal': 'Irfan (Personal)',
        }.get(cash_holder, '')

    def _get_hammad_user_id(self):
        employee = request.env[
            'hr.employee'
        ].sudo().search(
            [
                ('employee_code', '=', 'BLMP43'),
            ],
            limit=1,
        )

        return (
            employee.user_id.id
            if employee and employee.user_id
            else False
        )

    def _get_cash_holder_domain(self, cash_holder):
        hammad_user_id = self._get_hammad_user_id()

        if cash_holder == 'hammad':
            if not hammad_user_id:
                return [('id', '=', 0)]

            return [
                ('create_uid', '=', hammad_user_id),
            ]

        if cash_holder == 'irfan_personal':
            return [
                ('cash_holder', '=', 'irfan_personal'),
            ]

        if cash_holder == 'irfan':
            domain = [
                ('cash_holder', '!=', 'irfan_personal'),
            ]

            if hammad_user_id:
                domain.append(
                    ('create_uid', '!=', hammad_user_id)
                )

            return domain

        return [('id', '=', 0)]

    def _get_finance_access(self):
        if self._is_hr_manager():
            return 'full'

        employee = self._get_current_employee()

        if not employee:
            return 'none'

        employee_code = (
            employee.employee_code or ''
        ).strip().upper()

        if employee_code in self.FULL_ACCESS_EMPLOYEE_CODES:
            return 'full'

        if employee_code in self.ENTRY_ACCESS_EMPLOYEE_CODES:
            return 'entry'

        return 'none'

    def _can_view_petty_cash(self):
        return self._get_finance_access() in {
            'full',
            'entry',
        }

    def _can_add_petty_cash(self):
        return self._get_finance_access() in {
            'full',
            'entry',
        }

    def _can_edit_petty_cash(self):
        return self._get_finance_access() == 'full'

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

    def _is_valid_invoice_url(self, value):
        invoice_url = (value or '').strip()

        if not invoice_url:
            return False

        try:
            parsed_url = urlparse(invoice_url)
        except (TypeError, ValueError):
            return False

        hostname = (
            parsed_url.hostname or ''
        ).lower()

        return (
            parsed_url.scheme == 'https'
            and hostname in {
                'drive.google.com',
                'docs.google.com',
            }
        )

    def _finance_redirect(self, params=None):
        if self._is_hr_manager():
            url = '/my/hr/admin/finance/petty-cash'
        else:
            url = '/my/hr/finance/petty-cash'

        if params:
            url = '%s?%s' % (url, urlencode(params))

        return request.redirect(url)

    def _build_cash_holder_ledger(
        self,
        petty_cash_entry_model,
        cash_holder,
        fiscal_year_start,
        fiscal_year_end,
        selected_month,
        page=1,
    ):
        try:
            page = max(int(page or 1), 1)
        except (TypeError, ValueError):
            page = 1

        domain = [
            (
                'company_id',
                '=',
                request.env.company.id,
            ),
            *self._get_cash_holder_domain(
                cash_holder
            ),
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

        entry_count = petty_cash_entry_model.search_count(
            domain
        )

        page_count = max(
            (
                entry_count + self.PAGE_SIZE - 1
            ) // self.PAGE_SIZE,
            1,
        )

        page = min(page, page_count)

        offset = (page - 1) * self.PAGE_SIZE

        entries = petty_cash_entry_model.search(
            domain,
            order='transaction_date asc, id asc',
            limit=self.PAGE_SIZE,
            offset=offset,
        )

        filtered_entries = (
            petty_cash_entry_model.search(domain)
        )

        global_entries = petty_cash_entry_model.search([
            (
                'company_id',
                '=',
                request.env.company.id,
            ),
            *self._get_cash_holder_domain(
                cash_holder
            ),
        ])

        total_received = sum(
            global_entries.mapped('received')
        )

        total_expense = sum(
            global_entries.mapped('expense_paid')
        )

        return {
            'cash_holder': cash_holder,
            'label': self._get_cash_holder_label(
                cash_holder
            ),
            'entries': entries,
            'entry_count': entry_count,
            'page': page,
            'page_count': page_count,
            'first_entry': (
                offset + 1
                if entry_count
                else 0
            ),
            'last_entry': min(
                offset + len(entries),
                entry_count,
            ),
            'balance': (
                total_received - total_expense
            ),
            'monthly_expense': sum(
                filtered_entries.mapped(
                    'expense_paid'
                )
            ),
        }

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
            [
                (
                    'company_id',
                    '=',
                    request.env.company.id,
                ),
            ]
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
            '/my/hr/finance',
            '/my/hr/admin/finance',
        ],
        type='http',
        auth='user',
        website=True,
    )
    def finance_home_page(self, **kwargs):
        finance_access = self._get_finance_access()

        if finance_access == 'none':
            return request.redirect('/my/hr')

        is_hr_manager = self._is_hr_manager()

        return request.render(
            'hr_petty_cash_management.hr_finance_home_page',
            {
                'is_hr_manager': is_hr_manager,
                'finance_access': finance_access,
            },
        )

    @http.route(
        [
            '/my/hr/finance/petty-cash',
            '/my/hr/finance/petty-cash/page/<int:page>',
            '/my/hr/admin/finance/petty-cash',
            '/my/hr/admin/finance/petty-cash/page/<int:page>',
        ],
        type='http',
        auth='user',
        website=True,
    )
    def admin_petty_cash_page(
        self,
        page=1,
        fy=None,
        month=None,
        holder=None,
        h_page=1,
        i_page=1,
        **kwargs
    ):
        finance_access = self._get_finance_access()

        if finance_access == 'none':
            return request.redirect('/my/hr')

        is_hr_manager = self._is_hr_manager()
        is_uzair = self._is_uzair()

        requested_holder = (
            holder or ''
        ).strip().lower()

        combined_cash_view = (
            is_uzair
            and not requested_holder
        )

        if combined_cash_view:
            cash_holder = 'irfan'
        else:
            cash_holder = self._resolve_cash_holder(
                requested_holder
            )

        if not cash_holder:
            return request.redirect('/my/hr')

        finance_page_url = (
            '/my/hr/admin/finance/petty-cash'
            if is_hr_manager
            else '/my/hr/finance/petty-cash'
        )

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
            if selected_fiscal_year == current_fiscal_year:
                selected_month = today.strftime('%Y-%m')
            elif month_options:
                selected_month = month_options[0]['value']
            else:
                selected_month = ''

        if combined_cash_view:
            selected_month_label = next(
                (
                    option['label']
                    for option in month_options
                    if option['value'] == selected_month
                ),
                selected_month,
            )

            cash_summaries = []

            for holder_code in (
                'hammad',
                'irfan',
                'irfan_personal',
            ):
                summary = self._build_cash_holder_ledger(
                    petty_cash_entry_model,
                    holder_code,
                    fiscal_year_start,
                    fiscal_year_end,
                    selected_month,
                    1,
                )

                summary['detail_url'] = '%s?%s' % (
                    finance_page_url,
                    urlencode({
                        'holder': holder_code,
                        'fy': selected_fiscal_year,
                        'month': selected_month,
                    }),
                )

                cash_summaries.append(summary)

            return request.render(
                'hr_petty_cash_management.'
                'hr_petty_cash_overview_page',
                {
                    'is_hr_manager':
                        is_hr_manager,
                    'finance_access':
                        finance_access,
                    'finance_page_url':
                        finance_page_url,
                    'cash_summaries':
                        cash_summaries,
                    'fiscal_year_options':
                        fiscal_year_options,
                    'selected_fiscal_year':
                        selected_fiscal_year,
                    'month_options':
                        month_options,
                    'selected_month':
                        selected_month,
                },
            )

        domain = [
            (
                'company_id',
                '=',
                request.env.company.id,
            ),
            *self._get_cash_holder_domain(
                cash_holder
            ),
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

        entry_count = petty_cash_entry_model.search_count(
            domain
        )

        pager_url_args = {
            'fy': selected_fiscal_year,
            'holder': cash_holder,
        }

        if selected_month:
            pager_url_args['month'] = selected_month

        pager = portal_pager(
            url=finance_page_url,
            total=entry_count,
            page=page,
            step=self.PAGE_SIZE,
            url_args=pager_url_args,
        )

        entries = petty_cash_entry_model.search(
            domain,
            order='transaction_date asc, id asc',
            limit=self.PAGE_SIZE,
            offset=pager['offset'],
        )

        all_filtered_entries = (
            petty_cash_entry_model.search(domain)
        )

        global_entries = petty_cash_entry_model.search([
            (
                'company_id',
                '=',
                request.env.company.id,
            ),
            *self._get_cash_holder_domain(
                cash_holder
            ),
        ])

        total_received = sum(
            global_entries.mapped('received')
        )

        total_expense = sum(
            global_entries.mapped('expense_paid')
        )

        balance = total_received - total_expense

        monthly_expense = sum(
            all_filtered_entries.mapped('expense_paid')
        )

        selected_month_label = next(
            (
                option['label']
                for option in month_options
                if option['value'] == selected_month
            ),
            selected_month,
        )

        page_first_entry = (
            pager['offset'] + 1
            if entry_count
            else 0
        )

        page_last_entry = min(
            pager['offset'] + len(entries),
            entry_count,
        )

        values = {
            'is_hr_manager': is_hr_manager,
            'is_uzair': is_uzair,
            'cash_holder': cash_holder,
            'cash_holder_label':
                self._get_cash_holder_label(cash_holder),
            'finance_access': finance_access,
            'can_edit_entries':
                finance_access == 'full',

            'finance_page_url':
                finance_page_url,

            'entries': entries,

            'pager': pager,
            'entry_count': entry_count,
            'page_first_entry': page_first_entry,
            'page_last_entry': page_last_entry,

            'balance': balance,
            'total_received': total_received,
            'total_expense': total_expense,
            'monthly_expense': monthly_expense,

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
            'selected_month_label': selected_month_label,

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
        [
            '/my/hr/finance/petty-cash/add',
            '/my/hr/admin/finance/petty-cash/add',
        ],
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
        csrf=True,
    )
    def admin_petty_cash_add(self, **post):
        if not self._can_add_petty_cash():
            return request.redirect('/my/hr')

        cash_holder = self._resolve_cash_holder(
            post.get('cash_holder')
        )

        if not cash_holder:
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

        redirect_params = {'holder': cash_holder}

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

        transaction_type = (
            post.get('transaction_type') or ''
        ).strip()

        if transaction_type not in {
            'check_in',
            'check_out',
        }:
            redirect_params['entry_error'] = (
                'Please select Cash In or Cash Out.'
            )

            return self._finance_redirect(
                redirect_params
            )

        try:
            amount = self._parse_amount(
                post.get('amount')
            )

        except (TypeError, ValueError):
            redirect_params['entry_error'] = (
                'Amount must be a valid number.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if amount <= 0:
            redirect_params['entry_error'] = (
                'Amount must be greater than zero.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if transaction_type == 'check_in':
            received = amount
            expense_paid = 0.0
        else:
            received = 0.0
            expense_paid = amount

        invoice_shared = (
            post.get('invoice_shared') == '1'
        )

        invoice_url = (
            post.get('invoice_url') or ''
        ).strip()

        if invoice_url:
            if not self._is_valid_invoice_url(
                invoice_url
            ):
                redirect_params['entry_error'] = (
                    'Please enter a valid Google Drive '
                    'invoice link.'
                )

                return self._finance_redirect(
                    redirect_params
                )

            # A real invoice link means the invoice
            # has been shared and the entry must lock.
            invoice_shared = True

        elif invoice_shared:
            redirect_params['entry_error'] = (
                'Please add the Google Drive invoice '
                'link before setting Invoice Sharing '
                'Status to Yes.'
            )

            return self._finance_redirect(
                redirect_params
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
            'invoice_url': invoice_url or False,
            'cash_holder': cash_holder,
            'company_id': request.env.company.id,
        })

        entry_fiscal_year = (
            self._get_fiscal_year_start_year(
                transaction_date
            )
        )

        return self._finance_redirect({
            'holder': cash_holder,
            'fy': str(entry_fiscal_year),
            'month': transaction_date.strftime(
                '%Y-%m'
            ),
            'entry_added': '1',
        })
    @http.route(
        [
            '/my/hr/finance/petty-cash/'
            '<int:entry_id>/invoice-link',
            '/my/hr/admin/finance/petty-cash/'
            '<int:entry_id>/invoice-link',
        ],
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
        csrf=True,
    )
    def petty_cash_invoice_link(
        self,
        entry_id,
        **post
    ):
        if not self._can_edit_petty_cash():
            return self._finance_redirect({
                'entry_error': (
                    'You do not have permission to '
                    'manage invoice links.'
                ),
            })

        cash_holder = self._resolve_cash_holder(
            post.get('cash_holder')
        )

        if not cash_holder:
            return request.redirect('/my/hr')

        selected_fiscal_year = (
            post.get('selected_fiscal_year') or ''
        ).strip()

        selected_month = (
            post.get('selected_month') or ''
        ).strip()

        redirect_params = {'holder': cash_holder}

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
                (
                    'cash_holder',
                    '=',
                    cash_holder,
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

        invoice_url = (
            post.get('invoice_url') or ''
        ).strip()

        if not self._is_valid_invoice_url(
            invoice_url
        ):
            redirect_params['entry_error'] = (
                'Please enter a valid Google Drive '
                'invoice link.'
            )

            return self._finance_redirect(
                redirect_params
            )

        entry.write({
            'invoice_url': invoice_url,
            'invoice_shared': True,
        })

        redirect_params['entry_updated'] = '1'

        return self._finance_redirect(
            redirect_params
        )

    @http.route(
        [
            '/my/hr/finance/petty-cash/'
            '<int:entry_id>/edit',
            '/my/hr/admin/finance/petty-cash/'
            '<int:entry_id>/edit',
        ],
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
        finance_access = self._get_finance_access()

        if finance_access == 'none':
            return request.redirect('/my/hr')

        if finance_access != 'full':
            return self._finance_redirect({
                'entry_error': (
                    'You have view and add access only. '
                    'Editing petty cash entries is not allowed.'
                ),
            })

        cash_holder = self._resolve_cash_holder(
            post.get('cash_holder')
        )

        if not cash_holder:
            return request.redirect('/my/hr')

        selected_fiscal_year = (
            post.get('selected_fiscal_year') or ''
        ).strip()

        selected_month = (
            post.get('selected_month') or ''
        ).strip()

        redirect_params = {'holder': cash_holder}

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
                (
                    'cash_holder',
                    '=',
                    cash_holder,
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

        transaction_type = (
            post.get('transaction_type') or ''
        ).strip()

        if transaction_type not in {
            'check_in',
            'check_out',
        }:
            redirect_params['entry_error'] = (
                'Please select Cash In or Cash Out.'
            )

            return self._finance_redirect(
                redirect_params
            )

        try:
            amount = self._parse_amount(
                post.get('amount')
            )

        except (TypeError, ValueError):
            redirect_params['entry_error'] = (
                'Amount must be a valid number.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if amount <= 0:
            redirect_params['entry_error'] = (
                'Amount must be greater than zero.'
            )

            return self._finance_redirect(
                redirect_params
            )

        if transaction_type == 'check_in':
            received = amount
            expense_paid = 0.0
        else:
            received = 0.0
            expense_paid = amount

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
