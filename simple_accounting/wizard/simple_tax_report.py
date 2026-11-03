# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SimpleTaxReportWizard(models.TransientModel):
    _name = 'simple.tax.report.wizard'
    _description = "Simple Accounting: Tax Report"

    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    line_ids = fields.One2many('simple.tax.report.wizard.line', 'wizard_id', readonly=True)
    total_tax_collected = fields.Monetary(compute='_compute_totals')
    total_tax_paid = fields.Monetary(compute='_compute_totals')
    net_tax_due = fields.Monetary(compute='_compute_totals')

    @api.depends('line_ids.tax_amount', 'line_ids.type_tax_use')
    def _compute_totals(self):
        for wizard in self:
            collected = wizard.line_ids.filtered(lambda line: line.type_tax_use == 'sale')
            paid = wizard.line_ids.filtered(lambda line: line.type_tax_use == 'purchase')
            wizard.total_tax_collected = sum(collected.mapped('tax_amount'))
            wizard.total_tax_paid = sum(paid.mapped('tax_amount'))
            wizard.net_tax_due = wizard.total_tax_collected - wizard.total_tax_paid

    def action_generate(self):
        for wizard in self:
            wizard.line_ids.unlink()
            totals = {}  # tax -> [base, tax_amount]

            lines = self.env['simple.invoice.line'].search([
                ('invoice_id.company_id', '=', wizard.company_id.id),
                ('invoice_id.state', '=', 'posted'),
                ('invoice_id.date', '>=', wizard.date_from),
                ('invoice_id.date', '<=', wizard.date_to),
                ('tax_id', '!=', False),
            ])
            for line in lines:
                entry = totals.setdefault(line.tax_id, [0.0, 0.0])
                entry[0] += line.price_subtotal
                entry[1] += line.price_tax

            transactions = self.env['simple.transaction'].search([
                ('company_id', '=', wizard.company_id.id),
                ('state', '=', 'posted'),
                ('date', '>=', wizard.date_from),
                ('date', '<=', wizard.date_to),
                ('tax_id', '!=', False),
            ])
            for txn in transactions:
                entry = totals.setdefault(txn.tax_id, [0.0, 0.0])
                entry[0] += txn.amount
                entry[1] += txn.amount_tax

            vals_list = [{
                'wizard_id': wizard.id,
                'tax_id': tax.id,
                'type_tax_use': tax.type_tax_use,
                'base_amount': amounts[0],
                'tax_amount': amounts[1],
            } for tax, amounts in totals.items()]
            self.env['simple.tax.report.wizard.line'].create(vals_list)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'simple.tax.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class SimpleTaxReportWizardLine(models.TransientModel):
    _name = 'simple.tax.report.wizard.line'
    _description = "Simple Accounting: Tax Report Line"
    _order = 'type_tax_use, tax_amount desc'

    wizard_id = fields.Many2one('simple.tax.report.wizard', required=True, ondelete='cascade')
    tax_id = fields.Many2one('simple.tax', required=True)
    type_tax_use = fields.Selection([
        ('sale', 'Sales'), ('purchase', 'Purchases'), ('none', 'None'),
    ], required=True)
    base_amount = fields.Monetary(required=True)
    tax_amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
