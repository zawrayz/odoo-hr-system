from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import file_open

import base64


class HrInvoiceManagement(models.Model):
    _name = 'hr.invoice.management'
    _description = 'HR Invoice Management'
    _order = 'issue_date desc, id desc'
    _rec_name = 'invoice_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    invoice_number = fields.Char(
        string='Invoice Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )

    # New proper client system for invoices.
    client_id = fields.Many2one(
        'hr.invoice.client',
        string='Invoice For / Client',
        tracking=True,
        help='Select a saved invoice client.',
    )

    # Kept only for old invoices/backward compatibility.
    client_employee_id = fields.Many2one(
        'hr.employee',
        string='Old Employee Client',
        tracking=True,
        help='Old employee-based client field kept for compatibility.',
    )

    client_name = fields.Char(
        string='Invoice For / Client Name',
        required=True,
        tracking=True,
    )

    subject = fields.Char(
        string='Subject',
        required=True,
        tracking=True,
    )

    issue_date = fields.Date(
        string='Issue Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    due_date = fields.Date(
        string='Due Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('paid', 'Paid'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company.id,
    )

    line_ids = fields.One2many(
        'hr.invoice.management.line',
        'invoice_id',
        string='Items / Services',
    )

    sales_tax_percent = fields.Float(
        string='Sales Tax (%)',
        default=5.0,
    )

    apply_discount = fields.Boolean(
        string='Apply Discount',
        default=False,
        tracking=True,
    )

    discount_mode = fields.Selection(
        [
            ('manual', 'Manual Amount'),
            ('percentage', 'Percentage'),
        ],
        string='Discount Type',
        default='manual',
        tracking=True,
    )

    discount_manual_amount = fields.Monetary(
        string='Discount Amount',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help='Enter any discount amount manually.',
    )

    discount_percentage = fields.Float(
        string='Discount Percentage',
        default=0.0,
        tracking=True,
        help='Enter discount percentage. Example: 2 for 2%.',
    )

    amount_gross = fields.Monetary(
        string='Gross Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Total before discount and tax.',
    )

    amount_discount = fields.Monetary(
        string='Discount Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    amount_net = fields.Monetary(
        string='Net Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Gross amount after discount.',
    )

    amount_untaxed = fields.Monetary(
        string='Subtotal',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help='Kept for old portal/PDF compatibility. Same as Net Amount.',
    )

    amount_tax = fields.Monetary(
        string='Sales Tax',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    amount_paid = fields.Monetary(
        string='Paid Amount',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
    )

    amount_due = fields.Monetary(
        string='Balance / Amount Due',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    notes = fields.Text(
        string='Notes / Payment Instructions',
        default="""Please pay via a cheque made payable to “Blimp” or via account transfer to:

Bank: Habib Bank Limited (HBL)
Account Title: Blimp
Account Number: 23237900196001
Branch Code: 2323
Branch Address: Shop No.1, Ground Floor, Mumtaz Tower, Warsak Road, Peshawar
IBAN: PK28HABB0023237900196001
Swift Code: HABBPKKA""",
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_invoice_management_attachment_rel',
        'invoice_id',
        'attachment_id',
        string='Attachments',
        help='Attach files related to this invoice.',
    )

    attachment_count = fields.Integer(
        string='Attachment Count',
        compute='_compute_attachment_count',
    )

    history_ids = fields.One2many(
        'hr.invoice.management.history',
        'invoice_id',
        string='Invoice History',
    )

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    def get_blimp_logo_data_uri(self):
        self.ensure_one()
        try:
            with file_open('hr_invoice_management/static/src/img/blimp_logo.png', 'rb') as logo_file:
                encoded_logo = base64.b64encode(logo_file.read()).decode('utf-8')
                return 'data:image/png;base64,%s' % encoded_logo
        except Exception:
            return False

    def get_report_notes(self):
        self.ensure_one()
        text = self.notes or '-'
        text = text.replace('“', '"').replace('”', '"').replace('ˮ', '"')
        text = text.replace('₨', 'Rs.')
        return text

    @api.depends('invoice_number')
    def _compute_name(self):
        for rec in self:
            if rec.invoice_number and rec.invoice_number != 'New':
                rec.name = rec.invoice_number
            else:
                rec.name = '/'

    @api.depends(
        'line_ids.amount',
        'sales_tax_percent',
        'amount_paid',
        'apply_discount',
        'discount_mode',
        'discount_manual_amount',
        'discount_percentage',
    )
    def _compute_amounts(self):
        for rec in self:
            gross_amount = sum(rec.line_ids.mapped('amount'))

            discount_amount = 0.0

            if rec.apply_discount:
                if rec.discount_mode == 'manual':
                    discount_amount = rec.discount_manual_amount or 0.0

                elif rec.discount_mode == 'percentage':
                    discount_percent = rec.discount_percentage or 0.0

                    if discount_percent < 0:
                        discount_percent = 0.0

                    if discount_percent > 100:
                        discount_percent = 100.0

                    discount_amount = gross_amount * discount_percent / 100.0

            if discount_amount < 0:
                discount_amount = 0.0

            if discount_amount > gross_amount:
                discount_amount = gross_amount

            net_amount = gross_amount - discount_amount

            sales_tax_percent = rec.sales_tax_percent or 0.0
            if sales_tax_percent < 0:
                sales_tax_percent = 0.0

            tax_amount = net_amount * sales_tax_percent / 100.0
            total_amount = net_amount + tax_amount

            paid_amount = rec.amount_paid or 0.0
            amount_due = total_amount - paid_amount

            rec.amount_gross = round(gross_amount, 2)
            rec.amount_discount = round(discount_amount, 2)
            rec.amount_net = round(net_amount, 2)

            # Old fields kept so current portal/PDF/list code does not break.
            rec.amount_untaxed = round(net_amount, 2)
            rec.amount_tax = round(tax_amount, 2)
            rec.amount_total = round(total_amount, 2)
            rec.amount_due = round(max(amount_due, 0.0), 2)

    @api.onchange('client_id')
    def _onchange_client_id(self):
        for rec in self:
            if rec.client_id:
                rec.client_name = rec.client_id.name

    @api.onchange('client_employee_id')
    def _onchange_client_employee_id(self):
        for rec in self:
            if rec.client_employee_id and not rec.client_id:
                rec.client_name = rec.client_employee_id.name

    @api.constrains('issue_date', 'due_date')
    def _check_invoice_dates(self):
        for rec in self:
            if rec.issue_date and rec.due_date and rec.due_date < rec.issue_date:
                raise ValidationError("Due Date cannot be earlier than Issue Date.")

    @api.constrains('amount_paid')
    def _check_amount_paid(self):
        for rec in self:
            if rec.amount_paid < 0:
                raise ValidationError("Paid Amount cannot be negative.")

    @api.constrains('sales_tax_percent')
    def _check_sales_tax_percent(self):
        for rec in self:
            if rec.sales_tax_percent < 0:
                raise ValidationError("Sales Tax cannot be negative.")

    @api.constrains(
        'apply_discount',
        'discount_mode',
        'discount_manual_amount',
        'discount_percentage',
    )
    def _check_discount_values(self):
        for rec in self:
            if not rec.apply_discount:
                continue

            if rec.discount_mode == 'manual' and rec.discount_manual_amount < 0:
                raise ValidationError("Discount amount cannot be negative.")

            if rec.discount_mode == 'percentage':
                if rec.discount_percentage < 0:
                    raise ValidationError("Discount percentage cannot be negative.")
                if rec.discount_percentage > 100:
                    raise ValidationError("Discount percentage cannot be greater than 100%.")

    @api.model
    def _get_next_unique_invoice_number(self):
        Invoice = self.sudo()
        max_number = 0

        existing_invoices = Invoice.search([
            ('invoice_number', 'like', 'INV%')
        ])

        for inv in existing_invoices:
            invoice_number = inv.invoice_number or ''

            if invoice_number.startswith('INV'):
                number_part = invoice_number.replace('INV', '').strip()

                if number_part.isdigit():
                    max_number = max(max_number, int(number_part))

        for next_number in range(max_number + 1, max_number + 1001):
            candidate = 'INV%04d' % next_number

            exists = Invoice.search_count([
                ('invoice_number', '=', candidate)
            ])

            if not exists:
                return candidate

        return 'INV%s' % fields.Datetime.now().strftime('%Y%m%d%H%M%S')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('invoice_number', 'New') == 'New':
                vals['invoice_number'] = self._get_next_unique_invoice_number()

            if vals.get('client_id') and not vals.get('client_name'):
                client = self.env['hr.invoice.client'].sudo().browse(vals.get('client_id'))
                if client.exists():
                    vals['client_name'] = client.name

            elif vals.get('client_employee_id') and not vals.get('client_name'):
                employee = self.env['hr.employee'].sudo().browse(vals.get('client_employee_id'))
                if employee.exists():
                    vals['client_name'] = employee.name

        records = super().create(vals_list)

        for rec in records:
            rec._add_history('created', 'Invoice created.')

        return records

    def write(self, vals):
        if vals.get('client_id') and not vals.get('client_name'):
            client = self.env['hr.invoice.client'].sudo().browse(vals.get('client_id'))
            if client.exists():
                vals['client_name'] = client.name

        elif vals.get('client_employee_id') and not vals.get('client_name'):
            employee = self.env['hr.employee'].sudo().browse(vals.get('client_employee_id'))
            if employee.exists():
                vals['client_name'] = employee.name

        result = super().write(vals)

        ignored_fields = {'message_follower_ids', 'message_ids', 'activity_ids'}

        if not self.env.context.get('skip_invoice_history'):
            if set(vals.keys()) - ignored_fields:
                for rec in self:
                    rec._add_history('updated', 'Invoice updated.')

        return result

    def action_mark_sent(self):
        for rec in self:
            rec.with_context(skip_invoice_history=True).write({'state': 'sent'})
            rec._add_history('sent', 'Invoice marked as sent.')

    def action_mark_paid(self):
        for rec in self:
            rec.with_context(skip_invoice_history=True).write({
                'state': 'paid',
                'amount_paid': rec.amount_total,
            })
            rec._add_history('paid', 'Invoice marked as paid.')

    def action_reset_draft(self):
        for rec in self:
            rec.with_context(skip_invoice_history=True).write({
                'state': 'draft',
                'amount_paid': 0.0,
            })
            rec._add_history('draft', 'Invoice reset to draft.')

    def action_cancel(self):
        for rec in self:
            rec.with_context(skip_invoice_history=True).write({'state': 'cancelled'})
            rec._add_history('cancelled', 'Invoice cancelled.')

    def _add_history(self, action_type, description):
        self.ensure_one()
        self.env['hr.invoice.management.history'].sudo().create({
            'invoice_id': self.id,
            'action_type': action_type,
            'description': description,
            'user_id': self.env.user.id,
            'action_date': fields.Datetime.now(),
        })


class HrInvoiceManagementLine(models.Model):
    _name = 'hr.invoice.management.line'
    _description = 'HR Invoice Management Line'
    _order = 'id asc'

    invoice_id = fields.Many2one(
        'hr.invoice.management',
        string='Invoice',
        required=True,
        ondelete='cascade',
    )

    item_type = fields.Selection(
        [
            ('service', 'Service'),
            ('product', 'Product'),
            ('other', 'Other'),
        ],
        string='Item Type',
        default='service',
        required=True,
    )

    description = fields.Text(
        string='Description',
        required=True,
    )

    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        required=True,
    )

    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        required=True,
    )

    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        related='invoice_id.currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = round((rec.quantity or 0.0) * (rec.unit_price or 0.0), 2)

    @api.constrains('quantity', 'unit_price')
    def _check_amount_values(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError("Quantity must be greater than zero.")
            if rec.unit_price < 0:
                raise ValidationError("Unit Price cannot be negative.")


class HrInvoiceManagementHistory(models.Model):
    _name = 'hr.invoice.management.history'
    _description = 'HR Invoice Management History'
    _order = 'action_date desc, id desc'

    invoice_id = fields.Many2one(
        'hr.invoice.management',
        string='Invoice',
        required=True,
        ondelete='cascade',
    )

    action_type = fields.Selection(
        [
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('sent', 'Sent'),
            ('paid', 'Paid'),
            ('draft', 'Draft'),
            ('cancelled', 'Cancelled'),
        ],
        string='Action',
        required=True,
    )

    description = fields.Char(
        string='Description',
        required=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        readonly=True,
    )

    action_date = fields.Datetime(
        string='Action Date',
        readonly=True,
        default=fields.Datetime.now,
    )


class HrInvoiceClient(models.Model):
    _name = 'hr.invoice.client'
    _description = 'HR Invoice Client'
    _order = 'name asc'
    _rec_name = 'name'

    name = fields.Char(
        string='Client Name',
        required=True,
    )

    email = fields.Char(
        string='Email',
    )

    phone = fields.Char(
        string='Phone',
    )

    address = fields.Text(
        string='Address',
    )

    ntn = fields.Char(
        string='NTN',
    )

    active = fields.Boolean(
        string='Active',
        default=True,
    )