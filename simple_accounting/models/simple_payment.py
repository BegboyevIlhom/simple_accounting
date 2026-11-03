# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SimplePayment(models.Model):
    _name = 'simple.payment'
    _description = "Simple Accounting: Payment"
    _order = 'date desc, id desc'

    invoice_id = fields.Many2one(
        'simple.invoice', string='Invoice', required=True,
        domain="[('state', '=', 'posted')]")
    move_type = fields.Selection(related='invoice_id.move_type', readonly=True)
    partner_id = fields.Many2one(related='invoice_id.partner_id', readonly=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    amount = fields.Monetary(required=True, default=0.0)
    cash_account_id = fields.Many2one(
        'simple.account', string='Paid Through', required=True,
        domain="[('is_cash_bank', '=', True), ('company_id', '=', company_id)]")
    category_id = fields.Many2one(
        'simple.account', string='Category', required=True,
        domain="[('account_type', '=', move_type == 'out_invoice' and 'income' or 'expense'), "
                "('company_id', '=', company_id)]",
        help="Income/expense category this payment is reported under in the Profit & Loss report. "
             "Defaults to the category of the invoice's largest line.")
    memo = fields.Char()
    transaction_id = fields.Many2one('simple.transaction', string='Ledger Entry', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        for payment in self:
            if payment.invoice_id:
                payment.amount = payment.invoice_id.amount_residual
                payment.category_id = payment.invoice_id._get_default_category()

    @api.constrains('amount')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise UserError(_("The payment amount must be strictly positive."))
            if payment.invoice_id:
                other_paid = sum((payment.invoice_id.payment_ids - payment).mapped('amount'))
                residual_before = payment.invoice_id.amount_total - other_paid
                if payment.amount - residual_before > 0.005:
                    raise UserError(_(
                        "The payment amount (%(amount)s) cannot exceed the outstanding amount (%(residual)s) of the invoice.",
                        amount=payment.amount, residual=residual_before,
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('invoice_id') and not vals.get('category_id'):
                invoice = self.env['simple.invoice'].browse(vals['invoice_id'])
                category = invoice._get_default_category()
                if category:
                    vals['category_id'] = category.id
            if vals.get('invoice_id') and not vals.get('amount'):
                invoice = self.env['simple.invoice'].browse(vals['invoice_id'])
                vals['amount'] = invoice.amount_residual
        payments = super().create(vals_list)
        for payment in payments:
            payment._create_transaction()
        return payments

    def _create_transaction(self):
        self.ensure_one()
        invoice = self.invoice_id
        if invoice.state != 'posted':
            raise UserError(_("You can only register a payment on a posted invoice."))
        transaction_type = 'income' if invoice.move_type == 'out_invoice' else 'expense'
        txn = self.env['simple.transaction'].create({
            'name': self.memo or _("Payment for %s", invoice.name),
            'date': self.date,
            'transaction_type': transaction_type,
            'cash_account_id': self.cash_account_id.id,
            'category_id': self.category_id.id,
            'partner_id': invoice.partner_id.id,
            'amount': self.amount,
            'invoice_id': invoice.id,
            'payment_id': self.id,
            'company_id': self.company_id.id,
        })
        txn.action_post()
        self.transaction_id = txn.id

    def unlink(self):
        transactions = self.mapped('transaction_id')
        res = super().unlink()
        if transactions:
            transactions.action_draft()
            transactions.unlink()
        return res
