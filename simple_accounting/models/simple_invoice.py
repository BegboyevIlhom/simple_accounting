# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SimpleInvoice(models.Model):
    _name = 'simple.invoice'
    _description = "Simple Accounting: Customer Invoice / Vendor Bill"
    _order = 'date desc, id desc'

    name = fields.Char(required=True, copy=False, default=lambda self: _('New'))
    move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
    ], required=True, default='out_invoice')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)
    date = fields.Date(string='Invoice Date', required=True, default=fields.Date.context_today)
    due_date = fields.Date()
    line_ids = fields.One2many('simple.invoice.line', 'invoice_id', string='Lines', copy=True)
    payment_ids = fields.One2many('simple.payment', 'invoice_id', string='Payments')
    amount_untaxed = fields.Monetary(compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(compute='_compute_amounts', store=True)
    amount_paid = fields.Monetary(compute='_compute_amounts', store=True)
    amount_residual = fields.Monetary(compute='_compute_amounts', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], required=True, default='draft', copy=False)
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], compute='_compute_amounts', store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)

    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'line_ids.price_total', 'payment_ids.amount')
    def _compute_amounts(self):
        for invoice in self:
            amount_untaxed = sum(invoice.line_ids.mapped('price_subtotal'))
            amount_tax = sum(invoice.line_ids.mapped('price_tax'))
            amount_total = amount_untaxed + amount_tax
            amount_paid = sum(invoice.payment_ids.mapped('amount'))
            invoice.amount_untaxed = amount_untaxed
            invoice.amount_tax = amount_tax
            invoice.amount_total = amount_total
            invoice.amount_paid = amount_paid
            invoice.amount_residual = amount_total - amount_paid
            if invoice.state != 'posted':
                invoice.payment_state = 'not_paid'
            elif amount_paid <= 0:
                invoice.payment_state = 'not_paid'
            elif invoice.amount_residual > 0.005:
                invoice.payment_state = 'partial'
            else:
                invoice.payment_state = 'paid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                sequence_code = 'simple.invoice.customer' if vals.get('move_type', 'out_invoice') == 'out_invoice' \
                    else 'simple.invoice.vendor'
                vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or _('New')
        return super().create(vals_list)

    def action_post(self):
        for invoice in self:
            if not invoice.line_ids:
                raise UserError(_("You cannot post an invoice without any line."))
            if invoice.amount_total <= 0:
                raise UserError(_("The total of the invoice must be strictly positive."))
            invoice.state = 'posted'

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        for invoice in self:
            if invoice.payment_ids:
                raise UserError(_("You cannot cancel an invoice that already has payments. Remove the payments first."))
            invoice.state = 'cancel'

    def unlink(self):
        if any(invoice.state == 'posted' for invoice in self):
            raise UserError(_("You cannot delete a posted invoice. Cancel it first."))
        return super().unlink()

    def _get_default_category(self):
        """Best-effort single category for a payment covering this invoice:
        the category of the line with the largest total, used as a simple
        heuristic when an invoice mixes several categories."""
        self.ensure_one()
        if not self.line_ids:
            return self.env['simple.account']
        return max(self.line_ids, key=lambda line: line.price_total).category_id


class SimpleInvoiceLine(models.Model):
    _name = 'simple.invoice.line'
    _description = "Simple Accounting: Invoice Line"

    invoice_id = fields.Many2one('simple.invoice', required=True, ondelete='cascade')
    move_type = fields.Selection(related='invoice_id.move_type')
    name = fields.Char(string='Description', required=True)
    category_id = fields.Many2one(
        'simple.account', string='Category', required=True,
        domain="[('account_type', '=', move_type == 'out_invoice' and 'income' or 'expense')]",
        help="Income or expense category used for the Profit & Loss report.")
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    tax_id = fields.Many2one('simple.tax', string='Tax')
    price_subtotal = fields.Monetary(compute='_compute_price', store=True)
    price_tax = fields.Monetary(compute='_compute_price', store=True)
    price_total = fields.Monetary(compute='_compute_price', store=True)
    currency_id = fields.Many2one(related='invoice_id.currency_id', readonly=True)

    @api.depends('quantity', 'price_unit', 'tax_id')
    def _compute_price(self):
        for line in self:
            subtotal = line.quantity * line.price_unit
            tax_amount = line.tax_id._compute_amount(subtotal) if line.tax_id else 0.0
            line.price_subtotal = subtotal
            line.price_tax = tax_amount
            line.price_total = subtotal + tax_amount
