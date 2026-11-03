# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


ACCOUNT_TYPES = [
    ('asset', 'Asset'),
    ('liability', 'Liability'),
    ('equity', 'Equity'),
    ('income', 'Income'),
    ('expense', 'Expense'),
]


class SimpleAccount(models.Model):
    _name = 'simple.account'
    _description = 'Simple Accounting: Account'
    _order = 'account_type, code'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    account_type = fields.Selection(ACCOUNT_TYPES, string='Type', required=True, default='expense')
    is_cash_bank = fields.Boolean(
        string='Cash / Bank Account',
        help="Only asset accounts flagged as cash/bank can be used as the money "
             "account on a ledger entry or payment.")
    opening_balance = fields.Monetary(default=0.0)
    active = fields.Boolean(default=True)
    note = fields.Char()
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    transaction_ids = fields.One2many('simple.transaction', 'cash_account_id')
    incoming_transfer_ids = fields.One2many('simple.transaction', 'destination_account_id')
    balance = fields.Monetary(compute='_compute_balance')

    _code_company_uniq = models.Constraint(
        'unique(code, company_id)',
        "An account with this code already exists.",
    )

    @api.depends(
        'opening_balance', 'is_cash_bank',
        'transaction_ids.state', 'transaction_ids.transaction_type', 'transaction_ids.amount_total',
        'incoming_transfer_ids.state', 'incoming_transfer_ids.transaction_type', 'incoming_transfer_ids.amount_total',
    )
    def _compute_balance(self):
        # Movements are only taken into account for cash/bank accounts; the
        # balance of income/expense/equity accounts is informational only
        # and is better read from the Profit & Loss / Balance Sheet reports,
        # which also take unposted documents and periods into account.
        for account in self:
            account.balance = account._get_balance_as_of(False)

    def _get_balance_as_of(self, date_to):
        """Balance of a cash/bank account for all posted movements up to
        (and including) `date_to`, or for all time if `date_to` is falsy."""
        self.ensure_one()
        balance = self.opening_balance
        if not self.is_cash_bank:
            return balance
        Transaction = self.env['simple.transaction']
        base_domain = [('state', '=', 'posted')]
        if date_to:
            base_domain.append(('date', '<=', date_to))
        incoming = Transaction.search(base_domain + [
            ('cash_account_id', '=', self.id), ('transaction_type', '=', 'income'),
        ])
        outgoing = Transaction.search(base_domain + [
            ('cash_account_id', '=', self.id), ('transaction_type', '=', 'expense'),
        ])
        transfers_out = Transaction.search(base_domain + [
            ('cash_account_id', '=', self.id), ('transaction_type', '=', 'transfer'),
        ])
        transfers_in = Transaction.search(base_domain + [
            ('destination_account_id', '=', self.id), ('transaction_type', '=', 'transfer'),
        ])
        balance += sum(incoming.mapped('amount_total'))
        balance -= sum(outgoing.mapped('amount_total'))
        balance -= sum(transfers_out.mapped('amount_total'))
        balance += sum(transfers_in.mapped('amount_total'))
        return balance

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for account in self:
            account.display_name = f"{account.code} {account.name}"
