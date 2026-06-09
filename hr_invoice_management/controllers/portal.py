from datetime import datetime, timedelta
from io import BytesIO
from math import ceil

from openpyxl import Workbook
from werkzeug.urls import url_encode

from odoo import http, fields
from odoo.http import request, content_disposition


class HrInvoicePortal(http.Controller):

    STATUS_OPTIONS = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    ITEM_TYPE_OPTIONS = [
        ('service', 'Service'),
        ('product', 'Product'),
        ('other', 'Other'),
    ]

    def _is_hr_manager(self):
        return request.env.user.has_group('hr.group_hr_manager')

    def _manager_redirect(self):
        if not self._is_hr_manager():
            return request.redirect('/my/hr')
        return None

    def _parse_date(self, value):
        try:
            return datetime.strptime(value or '', '%Y-%m-%d').date()
        except Exception:
            return False

    def _parse_float(self, value):
        try:
            value = str(value or '').replace(',', '').strip()
            return float(value) if value else 0.0
        except Exception:
            return 0.0

    def _format_amount(self, amount):
        return 'Rs. %.2f' % (amount or 0.0)

    def _get_active_clients(self):
        return request.env['hr.invoice.client'].sudo().search([
            ('active', '=', True)
        ], order='name asc')

    def _build_invoice_list_url(self, state_filter='', month_value='', search_text='', page=1):
        params = {}

        if state_filter:
            params['state'] = state_filter

        if month_value:
            params['month'] = month_value

        if search_text:
            params['search'] = search_text

        if page and page > 1:
            params['page'] = page

        query_string = url_encode(params)

        if query_string:
            return '/my/hr/admin/invoices?' + query_string

        return '/my/hr/admin/invoices'

    def _get_invoice_domain(self, state_filter=None, month_value=None, search_text=None):
        domain = []

        if state_filter in dict(self.STATUS_OPTIONS):
            domain.append(('state', '=', state_filter))

        if month_value:
            try:
                month_start = datetime.strptime(month_value, '%Y-%m').date().replace(day=1)
                next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
                domain += [
                    ('issue_date', '>=', month_start),
                    ('issue_date', '<', next_month),
                ]
            except Exception:
                pass

        if search_text:
            search_text = search_text.strip()
            if search_text:
                domain += [
                    '|', '|', '|',
                    ('invoice_number', 'ilike', search_text),
                    ('client_name', 'ilike', search_text),
                    ('client_id.name', 'ilike', search_text),
                    ('subject', 'ilike', search_text),
                ]

        return domain

    def _get_invoice_or_redirect(self, invoice_id):
        invoice = request.env['hr.invoice.management'].sudo().search([
            ('id', '=', invoice_id)
        ], limit=1)

        return invoice or False

    def _get_line_commands_from_post(self, post):
        commands = []
        valid_item_types = dict(self.ITEM_TYPE_OPTIONS)

        for index in range(1, 31):
            item_type = post.get(f'line_item_type_{index}') or 'service'
            description = (post.get(f'line_description_{index}') or '').strip()
            quantity = self._parse_float(post.get(f'line_quantity_{index}'))
            unit_price = self._parse_float(post.get(f'line_unit_price_{index}'))

            if not description:
                continue

            if item_type not in valid_item_types:
                item_type = 'service'

            if quantity <= 0:
                quantity = 1.0

            commands.append((0, 0, {
                'item_type': item_type,
                'description': description,
                'quantity': quantity,
                'unit_price': unit_price,
            }))

        return commands

    def _prepare_line_rows(self, invoice=False, post=None):
        rows = []

        if post:
            for index in range(1, 31):
                item_type = post.get(f'line_item_type_{index}') or 'service'
                description = post.get(f'line_description_{index}') or ''
                quantity = post.get(f'line_quantity_{index}') or '1.0'
                unit_price = post.get(f'line_unit_price_{index}') or ''

                has_any_value = (
                    description.strip()
                    or str(quantity).strip()
                    or str(unit_price).strip()
                )

                if not has_any_value:
                    continue

                rows.append({
                    'item_type': item_type,
                    'description': description,
                    'quantity': quantity,
                    'unit_price': unit_price,
                })

        elif invoice:
            for line in invoice.line_ids:
                rows.append({
                    'item_type': line.item_type or 'service',
                    'description': line.description or '',
                    'quantity': line.quantity or 1.0,
                    'unit_price': line.unit_price or 0.0,
                })

        if not rows:
            rows.append({
                'item_type': 'service',
                'description': '',
                'quantity': 1.0,
                'unit_price': 0.0,
            })

        return rows

    def _default_notes(self):
        return """Please pay via a cheque made payable to “Blimp” or via account transfer to:

Bank: Habib Bank Limited (HBL)
Account Title: Blimp
Account Number: 23237900196001
Branch Code: 2323
Branch Address: Shop No.1, Ground Floor, Mumtaz Tower, Warsak Road, Peshawar
IBAN: PK28HABB0023237900196001
Swift Code: HABBPKKA"""

    def _prepare_form_values(self, invoice=False, post=None):
        today = fields.Date.context_today(request.env.user)

        if post:
            return {
                'client_id': post.get('client_id') or '',
                'client_name': post.get('client_name') or '',
                'subject': post.get('subject') or '',
                'issue_date': post.get('issue_date') or '',
                'due_date': post.get('due_date') or '',
                'sales_tax_percent': post.get('sales_tax_percent') or '5.0',
                'apply_discount': post.get('apply_discount') == 'on',
                'discount_mode': post.get('discount_mode') or 'manual',
                'discount_manual_amount': post.get('discount_manual_amount') or '0.0',
                'discount_percentage': post.get('discount_percentage') or '0.0',
                'notes': post.get('notes') or '',
            }

        if invoice:
            return {
                'client_id': invoice.client_id.id if invoice.client_id else '',
                'client_name': invoice.client_name or '',
                'subject': invoice.subject or '',
                'issue_date': invoice.issue_date.strftime('%Y-%m-%d') if invoice.issue_date else '',
                'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else '',
                'sales_tax_percent': invoice.sales_tax_percent or 0.0,
                'apply_discount': invoice.apply_discount,
                'discount_mode': invoice.discount_mode or 'manual',
                'discount_manual_amount': invoice.discount_manual_amount or 0.0,
                'discount_percentage': invoice.discount_percentage or 0.0,
                'notes': invoice.notes or '',
            }

        return {
            'client_id': '',
            'client_name': '',
            'subject': '',
            'issue_date': today.strftime('%Y-%m-%d'),
            'due_date': today.strftime('%Y-%m-%d'),
            'sales_tax_percent': 5.0,
            'apply_discount': False,
            'discount_mode': 'manual',
            'discount_manual_amount': 0.0,
            'discount_percentage': 0.0,
            'notes': self._default_notes(),
        }

    def _build_invoice_vals(self, post, invoice=False):
        client_id = False
        client_id_raw = (post.get('client_id') or '').strip()

        if client_id_raw:
            try:
                client_id = int(client_id_raw)
            except Exception:
                client_id = False

        selected_client = False

        if client_id:
            selected_client = request.env['hr.invoice.client'].sudo().search([
                ('id', '=', client_id),
                ('active', '=', True),
            ], limit=1)

        client_name = (post.get('client_name') or '').strip()

        if selected_client:
            client_name = selected_client.name

        subject = (post.get('subject') or '').strip()
        issue_date = self._parse_date(post.get('issue_date'))
        due_date = self._parse_date(post.get('due_date'))
        sales_tax_percent = self._parse_float(post.get('sales_tax_percent'))

        apply_discount = post.get('apply_discount') == 'on'
        discount_mode = post.get('discount_mode') or 'manual'
        discount_manual_amount = self._parse_float(post.get('discount_manual_amount'))
        discount_percentage = self._parse_float(post.get('discount_percentage'))

        amount_paid = invoice.amount_paid if invoice else 0.0
        notes = post.get('notes') or ''

        if not selected_client:
            return False, False, 'Please select Invoice For / Client.'

        if not client_name:
            return False, False, 'Client / Invoice For is required.'

        if not subject:
            return False, False, 'Subject is required.'

        if not issue_date:
            return False, False, 'Issue Date is required.'

        if not due_date:
            return False, False, 'Due Date is required.'

        if due_date < issue_date:
            return False, False, 'Due Date cannot be earlier than Issue Date.'

        if sales_tax_percent < 0:
            return False, False, 'Sales Tax cannot be negative.'

        if discount_mode not in ['manual', 'percentage']:
            discount_mode = 'manual'

        if apply_discount:
            if discount_mode == 'manual' and discount_manual_amount < 0:
                return False, False, 'Manual discount amount cannot be negative.'

            if discount_mode == 'percentage':
                if discount_percentage < 0:
                    return False, False, 'Discount percentage cannot be negative.'

                if discount_percentage > 100:
                    return False, False, 'Discount percentage cannot be greater than 100%.'
        else:
            discount_manual_amount = 0.0
            discount_percentage = 0.0

        line_commands = self._get_line_commands_from_post(post)

        if not line_commands:
            return False, False, 'At least one invoice item/service is required.'

        vals = {
            'client_id': selected_client.id,
            'client_name': client_name,
            'subject': subject,
            'issue_date': issue_date,
            'due_date': due_date,
            'sales_tax_percent': sales_tax_percent,
            'amount_paid': amount_paid,
            'apply_discount': apply_discount,
            'discount_mode': discount_mode,
            'discount_manual_amount': discount_manual_amount,
            'discount_percentage': discount_percentage,
            'notes': notes,
        }

        return vals, line_commands, False

    @http.route('/my/hr/admin/invoices', type='http', auth='user', website=True)
    def admin_invoices(self, **kwargs):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        state_filter = kwargs.get('state') or ''
        month_value = kwargs.get('month') or ''
        search_text = kwargs.get('search') or ''

        try:
            invoice_page = int(kwargs.get('page') or 1)
        except Exception:
            invoice_page = 1

        if invoice_page < 1:
            invoice_page = 1

        invoices_per_page = 10

        domain = self._get_invoice_domain(
            state_filter=state_filter,
            month_value=month_value,
            search_text=search_text,
        )

        Invoice = request.env['hr.invoice.management'].sudo()

        total_invoices = Invoice.search_count(domain)
        total_pages = max(ceil(total_invoices / invoices_per_page), 1)

        if invoice_page > total_pages:
            invoice_page = total_pages

        offset = (invoice_page - 1) * invoices_per_page

        invoices = Invoice.search(
            domain,
            limit=invoices_per_page,
            offset=offset,
            order='issue_date desc, id desc',
        )

        query_params = {}
        if state_filter:
            query_params['state'] = state_filter
        if month_value:
            query_params['month'] = month_value
        if search_text:
            query_params['search'] = search_text

        query_string = url_encode(query_params)
        download_url = '/my/hr/admin/invoices/download'
        if query_string:
            download_url += '?' + query_string

        page_start = max(invoice_page - 2, 1)
        page_end = min(invoice_page + 2, total_pages)

        pagination_pages = []
        for page_number in range(page_start, page_end + 1):
            pagination_pages.append({
                'number': page_number,
                'url': self._build_invoice_list_url(
                    state_filter=state_filter,
                    month_value=month_value,
                    search_text=search_text,
                    page=page_number,
                ),
            })

        prev_url = False
        next_url = False

        if invoice_page > 1:
            prev_url = self._build_invoice_list_url(
                state_filter=state_filter,
                month_value=month_value,
                search_text=search_text,
                page=invoice_page - 1,
            )

        if invoice_page < total_pages:
            next_url = self._build_invoice_list_url(
                state_filter=state_filter,
                month_value=month_value,
                search_text=search_text,
                page=invoice_page + 1,
            )

        showing_from = offset + 1 if total_invoices else 0
        showing_to = min(offset + len(invoices), total_invoices)

        values = {
            'current_page': 'admin_invoices',
            'is_hr_manager': True,
            'invoices': invoices,
            'status_options': self.STATUS_OPTIONS,
            'state_filter': state_filter,
            'month_value': month_value,
            'search_text': search_text,
            'download_url': download_url,
            'success_message': kwargs.get('success') or '',
            'error_message': kwargs.get('error') or '',
            'format_amount': self._format_amount,
            'invoice_page': invoice_page,
            'total_pages': total_pages,
            'total_invoices': total_invoices,
            'pagination_pages': pagination_pages,
            'prev_url': prev_url,
            'next_url': next_url,
            'showing_from': showing_from,
            'showing_to': showing_to,
        }

        return request.render('hr_invoice_management.hr_admin_invoice_page', values)

    @http.route('/my/hr/admin/invoices/create', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def admin_invoice_create(self, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        error_message = ''

        if request.httprequest.method == 'POST':
            vals, line_commands, error_message = self._build_invoice_vals(post)

            if not error_message:
                vals['line_ids'] = line_commands
                invoice = request.env['hr.invoice.management'].sudo().create(vals)
                return request.redirect(f'/my/hr/admin/invoices/{invoice.id}?success=Invoice created successfully.')

        form_values = self._prepare_form_values(
            post=post if request.httprequest.method == 'POST' else None
        )

        if request.httprequest.method == 'GET' and post.get('new_client_id'):
            form_values['client_id'] = post.get('new_client_id')

        values = {
            'current_page': 'admin_invoices',
            'is_hr_manager': True,
            'mode': 'create',
            'page_title': 'Create Invoice',
            'form_action': '/my/hr/admin/invoices/create',
            'invoice': False,
            'form_values': form_values,
            'line_rows': self._prepare_line_rows(post=post if request.httprequest.method == 'POST' else None),
            'item_type_options': self.ITEM_TYPE_OPTIONS,
            'clients': self._get_active_clients(),
            'error_message': error_message,
            'quick_client_error': post.get('quick_client_error') or '',
        }

        return request.render('hr_invoice_management.hr_admin_invoice_form_page', values)

    @http.route('/my/hr/admin/invoices/<int:invoice_id>', type='http', auth='user', website=True)
    def admin_invoice_view(self, invoice_id, **kwargs):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        invoice = self._get_invoice_or_redirect(invoice_id)
        if not invoice:
            return request.redirect('/my/hr/admin/invoices?error=Invoice not found.')

        values = {
            'current_page': 'admin_invoices',
            'is_hr_manager': True,
            'invoice': invoice,
            'success_message': kwargs.get('success') or '',
            'error_message': kwargs.get('error') or '',
            'format_amount': self._format_amount,
        }

        return request.render('hr_invoice_management.hr_admin_invoice_view_page', values)

    @http.route('/my/hr/admin/invoices/<int:invoice_id>/edit', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def admin_invoice_edit(self, invoice_id, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        invoice = self._get_invoice_or_redirect(invoice_id)
        if not invoice:
            return request.redirect('/my/hr/admin/invoices?error=Invoice not found.')

        error_message = ''

        if request.httprequest.method == 'POST':
            vals, line_commands, error_message = self._build_invoice_vals(post, invoice=invoice)

            if not error_message:
                vals['line_ids'] = [(5, 0, 0)] + line_commands
                invoice.sudo().write(vals)
                return request.redirect(f'/my/hr/admin/invoices/{invoice.id}?success=Invoice updated successfully.')

        form_values = self._prepare_form_values(
            invoice=invoice,
            post=post if request.httprequest.method == 'POST' else None,
        )

        if request.httprequest.method == 'GET' and post.get('new_client_id'):
            form_values['client_id'] = post.get('new_client_id')

        values = {
            'current_page': 'admin_invoices',
            'is_hr_manager': True,
            'mode': 'edit',
            'page_title': f'Edit Invoice {invoice.invoice_number}',
            'form_action': f'/my/hr/admin/invoices/{invoice.id}/edit',
            'invoice': invoice,
            'form_values': form_values,
            'line_rows': self._prepare_line_rows(
                invoice=invoice,
                post=post if request.httprequest.method == 'POST' else None,
            ),
            'item_type_options': self.ITEM_TYPE_OPTIONS,
            'clients': self._get_active_clients(),
            'error_message': error_message,
            'quick_client_error': post.get('quick_client_error') or '',
        }

        return request.render('hr_invoice_management.hr_admin_invoice_form_page', values)

    @http.route('/my/hr/admin/invoices/<int:invoice_id>/mark-sent', type='http', auth='user', website=True, methods=['POST'])
    def admin_invoice_mark_sent(self, invoice_id, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        invoice = self._get_invoice_or_redirect(invoice_id)
        if invoice:
            invoice.sudo().action_mark_sent()
            return request.redirect(f'/my/hr/admin/invoices/{invoice.id}?success=Invoice marked as sent.')

        return request.redirect('/my/hr/admin/invoices?error=Invoice not found.')

    @http.route('/my/hr/admin/invoices/<int:invoice_id>/mark-paid', type='http', auth='user', website=True, methods=['POST'])
    def admin_invoice_mark_paid(self, invoice_id, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        invoice = self._get_invoice_or_redirect(invoice_id)
        if invoice:
            invoice.sudo().action_mark_paid()
            return request.redirect(f'/my/hr/admin/invoices/{invoice.id}?success=Invoice marked as paid.')

        return request.redirect('/my/hr/admin/invoices?error=Invoice not found.')

    @http.route('/my/hr/admin/invoices/<int:invoice_id>/reset-draft', type='http', auth='user', website=True, methods=['POST'])
    def admin_invoice_reset_draft(self, invoice_id, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        invoice = self._get_invoice_or_redirect(invoice_id)
        if invoice:
            invoice.sudo().action_reset_draft()
            return request.redirect(f'/my/hr/admin/invoices/{invoice.id}?success=Invoice reset to draft.')

        return request.redirect('/my/hr/admin/invoices?error=Invoice not found.')

    @http.route('/my/hr/admin/invoices/<int:invoice_id>/cancel', type='http', auth='user', website=True, methods=['POST'])
    def admin_invoice_cancel(self, invoice_id, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        invoice = self._get_invoice_or_redirect(invoice_id)
        if invoice:
            invoice.sudo().action_cancel()
            return request.redirect(f'/my/hr/admin/invoices/{invoice.id}?success=Invoice cancelled.')

        return request.redirect('/my/hr/admin/invoices?error=Invoice not found.')

    @http.route('/my/hr/admin/invoice-clients/create-quick', type='http', auth='user', website=True, methods=['POST'])
    def admin_invoice_client_create_quick(self, **post):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        client_name = (post.get('quick_client_name') or '').strip()
        client_email = (post.get('quick_client_email') or '').strip()
        client_phone = (post.get('quick_client_phone') or '').strip()
        client_ntn = (post.get('quick_client_ntn') or '').strip()
        return_url = post.get('return_url') or '/my/hr/admin/invoices/create'

        if not client_name:
            separator = '&' if '?' in return_url else '?'
            return request.redirect(
                return_url + separator + url_encode({
                    'quick_client_error': 'Client name is required.'
                })
            )

        existing_client = request.env['hr.invoice.client'].sudo().search([
            ('name', '=ilike', client_name),
        ], limit=1)

        if existing_client:
            client = existing_client
            if not client.active:
                client.write({'active': True})
        else:
            client = request.env['hr.invoice.client'].sudo().create({
                'name': client_name,
                'email': client_email,
                'phone': client_phone,
                'ntn': client_ntn,
                'active': True,
            })

        separator = '&' if '?' in return_url else '?'
        return request.redirect(
            return_url + separator + url_encode({
                'new_client_id': client.id
            })
        )

    @http.route('/my/hr/admin/invoices/download', type='http', auth='user', website=True)
    def admin_invoice_download_excel(self, **kwargs):
        redirect = self._manager_redirect()
        if redirect:
            return redirect

        state_filter = kwargs.get('state') or ''
        month_value = kwargs.get('month') or ''
        search_text = kwargs.get('search') or ''

        domain = self._get_invoice_domain(
            state_filter=state_filter,
            month_value=month_value,
            search_text=search_text,
        )

        invoices = request.env['hr.invoice.management'].sudo().search(domain)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Invoices'

        headers = [
            'Invoice Number',
            'Client',
            'Subject',
            'Issue Date',
            'Due Date',
            'Status',
            'Gross Amount',
            'Discount Applied',
            'Discount Type',
            'Discount Amount',
            'Sales Tax',
            'Net Amount',
            'Total',
            'Paid',
            'Balance',
        ]
        sheet.append(headers)

        for invoice in invoices:
            sheet.append([
                invoice.invoice_number or '',
                invoice.client_name or '',
                invoice.subject or '',
                invoice.issue_date.strftime('%Y-%m-%d') if invoice.issue_date else '',
                invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else '',
                dict(invoice._fields['state'].selection).get(invoice.state, invoice.state),
                invoice.amount_gross or 0.0,
                'Yes' if invoice.apply_discount else 'No',
                dict(invoice._fields['discount_mode'].selection).get(invoice.discount_mode, invoice.discount_mode),
                invoice.amount_discount or 0.0,
                invoice.amount_tax or 0.0,
                invoice.amount_net or 0.0,
                invoice.amount_total or 0.0,
                invoice.amount_paid or 0.0,
                invoice.amount_due or 0.0,
            ])

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        filename = 'hr_invoice_management.xlsx'

        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ]

        return request.make_response(output.getvalue(), headers=headers)