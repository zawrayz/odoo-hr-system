from datetime import datetime

from odoo import http
from odoo.http import request


class HrPettyCashPortal(http.Controller):

    def _is_hr_manager(self):
        return request.env.user.has_group('hr.group_hr_manager')

    @http.route(
        [
            '/my/hr/admin/finance',
            '/my/hr/admin/finance/petty-cash',
        ],
        type='http',
        auth='user',
        website=True,
    )
    def admin_petty_cash_page(self, month=None, **kwargs):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')

        PettyCashEntry = request.env['hr.petty.cash.entry'].sudo()

        selected_month = (month or '').strip()
        selected_month_date = False

        if selected_month:
            try:
                selected_month_date = datetime.strptime(
                    selected_month,
                    '%Y-%m',
                ).date().replace(day=1)
            except ValueError:
                selected_month = ''

        domain = []

        if selected_month_date:
            domain.append(('month_start', '=', selected_month_date))

        entries = PettyCashEntry.search(
            domain,
            order='transaction_date asc, id asc',
        )

        total_received = sum(entries.mapped('received'))
        total_expense = sum(entries.mapped('expense_paid'))
        balance = total_received - total_expense

        all_entries = PettyCashEntry.search(
            [('month_start', '!=', False)],
            order='month_start desc',
        )

        month_starts = sorted(
            {
                month_start
                for month_start in all_entries.mapped('month_start')
                if month_start
            },
            reverse=True,
        )

        month_options = [
            {
                'value': month_start.strftime('%Y-%m'),
                'label': month_start.strftime('%b-%y'),
            }
            for month_start in month_starts
        ]

        values = {
            'is_hr_manager': True,
            'entries': entries,
            'balance': balance,
            'total_received': total_received,
            'total_expense': total_expense,
            'selected_month': selected_month,
            'month_options': month_options,
        }

        return request.render(
            'hr_petty_cash_management.hr_admin_petty_cash_page',
            values,
        )