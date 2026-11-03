# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SimpleBalanceSheetWizard(models.TransientModel):
    _name = 'simple.balance.sheet.wizard'
    _description = "Simple Accounting: Balance Sheet Report"

    date = fields.Date(string='As of', required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    line_ids = fields.One2many('simple.balance.sheet.wizard.line', 'wizard_id', readonly=True)
    total_assets = fields.Monetary(compute='_compute_totals')
    total_liabilities = fields.Monetary(compute='_compute_totals')
    total_equity = fields.Monetary(compute='_compute_totals')
    balance_check = fields.Monetary(
        compute='_compute_totals',
        help="Total Assets minus (Total Liabilities + Total Equity). Should always be 0 "
             "if opening balances were entered correctly (matching debit/credit on setup).")

    @api.depends('line_ids.amount', 'line_ids.section')
    def _compute_totals(self):
        for wizard in self:
            assets = wizard.line_ids.filtered(lambda line: line.section == 'asset')
            liabilities = wizard.line_ids.filtered(lambda line: line.section == 'liability')
            equity = wizard.line_ids.filtered(lambda line: line.section == 'equity')
            wizard.total_assets = sum(assets.mapped('amount'))
            wizard.total_liabilities = sum(liabilities.mapped('amount'))
            wizard.total_equity = sum(equity.mapped('amount'))
            wizard.balance_check = wizard.total_assets - wizard.total_liabilities - wizard.total_equity

    def action_generate(self):
        Account = self.env['simple.account']
        Transaction = self.env['simple.transaction']
        Invoice = self.env['simple.invoice']
        for wizard in self:
            wizard.line_ids.unlink()
            lines = []

            cash_accounts = Account.search([
                ('company_id', '=', wizard.company_id.id), ('is_cash_bank', '=', True),
            ])
            for account in cash_accounts:
                lines.append(wizard._make_line('asset', account.display_name, account._get_balance_as_of(wizard.date)))

            receivable = sum(Invoice.search([
                ('company_id', '=', wizard.company_id.id),
                ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('date', '<=', wizard.date),
            ]).mapped('amount_residual'))
            lines.append(wizard._make_line('asset', "Accounts Receivable", receivable))

            payable = sum(Invoice.search([
                ('company_id', '=', wizard.company_id.id),
                ('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), ('date', '<=', wizard.date),
            ]).mapped('amount_residual'))
            lines.append(wizard._make_line('liability', "Accounts Payable", payable))

            other_liabilities = Account.search([
                ('company_id', '=', wizard.company_id.id), ('account_type', '=', 'liability'),
            ])
            for account in other_liabilities:
                lines.append(wizard._make_line('liability', account.display_name, account.opening_balance))

            owner_equity = Account.search([
                ('company_id', '=', wizard.company_id.id), ('account_type', '=', 'equity'),
            ])
            for account in owner_equity:
                lines.append(wizard._make_line('equity', account.display_name, account.opening_balance))

            income_total = sum(Transaction.search([
                ('company_id', '=', wizard.company_id.id), ('state', '=', 'posted'),
                ('transaction_type', '=', 'income'), ('date', '<=', wizard.date),
            ]).mapped('amount'))
            expense_total = sum(Transaction.search([
                ('company_id', '=', wizard.company_id.id), ('state', '=', 'posted'),
                ('transaction_type', '=', 'expense'), ('date', '<=', wizard.date),
            ]).mapped('amount'))
            lines.append(wizard._make_line('equity', "Retained Earnings (cash-basis net result)", income_total - expense_total))

            pending = receivable - payable
            lines.append(wizard._make_line(
                'equity', "Accrued revenue pending (unpaid invoices, not yet recognized)", pending))

            self.env['simple.balance.sheet.wizard.line'].create(lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'simple.balance.sheet.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _make_line(self, section, name, amount):
        self.ensure_one()
        return {'wizard_id': self.id, 'section': section, 'name': name, 'amount': amount}


class SimpleBalanceSheetWizardLine(models.TransientModel):
    _name = 'simple.balance.sheet.wizard.line'
    _description = "Simple Accounting: Balance Sheet Report Line"
    _order = 'section, amount desc'

    wizard_id = fields.Many2one('simple.balance.sheet.wizard', required=True, ondelete='cascade')
    section = fields.Selection([
        ('asset', 'Asset'), ('liability', 'Liability'), ('equity', 'Equity'),
    ], required=True)
    name = fields.Char(required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
