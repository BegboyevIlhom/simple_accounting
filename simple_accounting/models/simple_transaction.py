# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SimpleTransaction(models.Model):
    _name = 'simple.transaction'
    _description = "Simple Accounting: Ledger Entry (income / expense / transfer)"
    _order = 'date desc, id desc'

    name = fields.Char(string='Description', required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    transaction_type = fields.Selection([
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('transfer', 'Transfer'),
    ], required=True, default='income')
    cash_account_id = fields.Many2one(
        'simple.account', string='Account', required=True,
        domain="[('is_cash_bank', '=', True), ('company_id', '=', company_id)]",
        help="The cash or bank account the money moves from/into.")
    destination_account_id = fields.Many2one(
        'simple.account', string='To Account',
        domain="[('is_cash_bank', '=', True), ('company_id', '=', company_id)]",
        help="Only used for transfers: the cash/bank account receiving the money.")
    category_id = fields.Many2one(
        'simple.account', string='Category',
        domain="[('account_type', '=', transaction_type), ('company_id', '=', company_id)]",
        help="Income or expense category used for the Profit & Loss report.")
    partner_id = fields.Many2one('res.partner', string='Contact')
    amount = fields.Monetary(required=True, default=0.0)
    tax_id = fields.Many2one('simple.tax', string='Tax')
    amount_tax = fields.Monetary(compute='_compute_amount_total', store=True)
    amount_total = fields.Monetary(compute='_compute_amount_total', store=True)
    invoice_id = fields.Many2one('simple.invoice', string='Invoice', readonly=True)
    payment_id = fields.Many2one('simple.payment', string='Payment', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], required=True, default='draft', copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)

    @api.depends('amount', 'tax_id')
    def _compute_amount_total(self):
        for txn in self:
            tax_amount = txn.tax_id._compute_amount(txn.amount) if txn.tax_id else 0.0
            txn.amount_tax = tax_amount
            txn.amount_total = txn.amount + tax_amount

    @api.constrains('transaction_type', 'cash_account_id', 'destination_account_id', 'category_id')
    def _check_accounts(self):
        for txn in self:
            if txn.transaction_type == 'transfer':
                if not txn.destination_account_id:
                    raise ValidationError(_("A transfer needs a destination account."))
                if txn.destination_account_id == txn.cash_account_id:
                    raise ValidationError(_("The source and destination account of a transfer must be different."))
            else:
                if not txn.category_id:
                    raise ValidationError(_("Please set an income/expense category for this entry."))
                if txn.category_id.account_type != txn.transaction_type:
                    raise ValidationError(_(
                        "The category of an %(type)s entry must be an %(type)s account.",
                        type=txn.transaction_type,
                    ))

    def action_post(self):
        for txn in self:
            if txn.state == 'posted':
                continue
            if txn.amount <= 0:
                raise UserError(_("The amount must be strictly positive."))
            txn.state = 'posted'

    def action_draft(self):
        self.write({'state': 'draft'})

    def unlink(self):
        if any(txn.state != 'draft' for txn in self):
            raise UserError(_("You can only delete draft entries. Reset to draft first."))
        return super().unlink()
