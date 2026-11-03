# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SimpleProfitLossWizard(models.TransientModel):
    _name = 'simple.profit.loss.wizard'
    _description = "Simple Accounting: Profit & Loss Report"

    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    line_ids = fields.One2many('simple.profit.loss.wizard.line', 'wizard_id', readonly=True)
    total_income = fields.Monetary(compute='_compute_totals')
    total_expense = fields.Monetary(compute='_compute_totals')
    net_profit = fields.Monetary(compute='_compute_totals')

    @api.depends('line_ids.amount', 'line_ids.account_type')
    def _compute_totals(self):
        for wizard in self:
            income_lines = wizard.line_ids.filtered(lambda line: line.account_type == 'income')
            expense_lines = wizard.line_ids.filtered(lambda line: line.account_type == 'expense')
            wizard.total_income = sum(income_lines.mapped('amount'))
            wizard.total_expense = sum(expense_lines.mapped('amount'))
            wizard.net_profit = wizard.total_income - wizard.total_expense

    def action_generate(self):
        for wizard in self:
            wizard.line_ids.unlink()
            transactions = self.env['simple.transaction'].search([
                ('company_id', '=', wizard.company_id.id),
                ('state', '=', 'posted'),
                ('transaction_type', 'in', ('income', 'expense')),
                ('date', '>=', wizard.date_from),
                ('date', '<=', wizard.date_to),
            ])
            totals = {}
            for txn in transactions:
                key = txn.category_id
                totals.setdefault(key, 0.0)
                totals[key] += txn.amount
            lines = [{
                'wizard_id': wizard.id,
                'category_id': category.id,
                'account_type': category.account_type,
                'amount': amount,
            } for category, amount in totals.items()]
            self.env['simple.profit.loss.wizard.line'].create(lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'simple.profit.loss.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class SimpleProfitLossWizardLine(models.TransientModel):
    _name = 'simple.profit.loss.wizard.line'
    _description = "Simple Accounting: Profit & Loss Report Line"
    _order = 'account_type, amount desc'

    wizard_id = fields.Many2one('simple.profit.loss.wizard', required=True, ondelete='cascade')
    category_id = fields.Many2one('simple.account', string='Category', required=True)
    account_type = fields.Selection([('income', 'Income'), ('expense', 'Expense')], required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
