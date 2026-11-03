# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SimpleTax(models.Model):
    _name = 'simple.tax'
    _description = 'Simple Accounting: Tax'
    _order = 'type_tax_use, amount'

    name = fields.Char(required=True)
    amount = fields.Float(string='Percentage', required=True, default=0.0,
        help="Tax rate in percent, e.g. 12 for 12%.")
    type_tax_use = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchases'),
        ('none', 'None'),
    ], string='Used on', required=True, default='sale')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    def _compute_amount(self, base_amount):
        self.ensure_one()
        return base_amount * self.amount / 100.0

    @api.depends('name', 'amount')
    def _compute_display_name(self):
        for tax in self:
            tax.display_name = f"{tax.name} ({tax.amount:g}%)"
