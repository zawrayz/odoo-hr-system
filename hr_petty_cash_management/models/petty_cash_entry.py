from odoo import api, fields, models


class HrPettyCashEntry(models.Model):
    _name = 'hr.petty.cash.entry'
    _description = 'HR Petty Cash Entry'
    _order = 'transaction_date desc, id desc'
    _rec_name = 'description'

    transaction_date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )

    month_start = fields.Date(
        string='Month',
        compute='_compute_month_information',
        store=True,
        index=True,
    )

    month_label = fields.Char(
        string='Month Label',
        compute='_compute_month_information',
        store=True,
        index=True,
    )

    description = fields.Char(
        string='Description',
        required=True,
    )

    received = fields.Monetary(
        string='Received',
        currency_field='currency_id',
        default=0.0,
    )

    expense_paid = fields.Monetary(
        string='Expense / Paid',
        currency_field='currency_id',
        default=0.0,
    )

    net_amount = fields.Monetary(
        string='Net Amount',
        compute='_compute_net_amount',
        store=True,
        currency_field='currency_id',
    )

    remarks = fields.Text(
        string='Remarks',
    )

    invoice_shared = fields.Boolean(
        string='Invoice Shared',
        default=False,
    )

    invoice_url = fields.Char(
        string='Invoice URL',
        help='Google Drive link for the invoice document.',
    )

    cash_holder = fields.Selection(
        [
            ('irfan', 'Irfan Office'),
            ('hammad', 'Hammad'),
            ('irfan_personal', 'Irfan Personal'),
        ],
        string='Petty Cash Holder',
        required=True,
        default='irfan',
        index=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('transaction_date')
    def _compute_month_information(self):
        for record in self:
            if record.transaction_date:
                transaction_date = fields.Date.to_date(
                    record.transaction_date
                )

                record.month_start = transaction_date.replace(day=1)
                record.month_label = transaction_date.strftime('%b-%y')
            else:
                record.month_start = False
                record.month_label = False

    @api.depends('received', 'expense_paid')
    def _compute_net_amount(self):
        for record in self:
            record.net_amount = (
                (record.received or 0.0)
                - (record.expense_paid or 0.0)
            )