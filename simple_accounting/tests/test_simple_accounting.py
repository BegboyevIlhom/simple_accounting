# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError, ValidationError
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestSimpleAccounting(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['simple.account']
        cls.cash = Account.create({'code': 'T101', 'name': 'Test Cash', 'account_type': 'asset', 'is_cash_bank': True})
        cls.bank = Account.create({'code': 'T102', 'name': 'Test Bank', 'account_type': 'asset', 'is_cash_bank': True})
        cls.equity = Account.create({'code': 'T301', 'name': 'Test Equity', 'account_type': 'equity'})
        cls.income_cat = Account.create({'code': 'T401', 'name': 'Test Sales', 'account_type': 'income'})
        cls.expense_cat = Account.create({'code': 'T501', 'name': 'Test Expenses', 'account_type': 'expense'})
        cls.tax_12 = cls.env['simple.tax'].create({'name': 'Test VAT 12%', 'amount': 12.0, 'type_tax_use': 'sale'})
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})

    def test_transaction_updates_cash_balance(self):
        Transaction = self.env['simple.transaction']
        income = Transaction.create({
            'name': 'Cash sale', 'transaction_type': 'income',
            'cash_account_id': self.cash.id, 'category_id': self.income_cat.id, 'amount': 1000.0,
        })
        income.action_post()
        self.assertEqual(self.cash.balance, 1000.0)

        expense = Transaction.create({
            'name': 'Office supplies', 'transaction_type': 'expense',
            'cash_account_id': self.cash.id, 'category_id': self.expense_cat.id, 'amount': 400.0,
        })
        expense.action_post()
        self.assertEqual(self.cash.balance, 600.0)

        transfer = Transaction.create({
            'name': 'Deposit to bank', 'transaction_type': 'transfer',
            'cash_account_id': self.cash.id, 'destination_account_id': self.bank.id, 'amount': 200.0,
        })
        transfer.action_post()
        self.assertEqual(self.cash.balance, 400.0)
        self.assertEqual(self.bank.balance, 200.0)

    def test_transaction_requires_matching_category_type(self):
        Transaction = self.env['simple.transaction']
        with self.assertRaises(ValidationError):
            Transaction.create({
                'name': 'Wrong category', 'transaction_type': 'income',
                'cash_account_id': self.cash.id, 'category_id': self.expense_cat.id, 'amount': 100.0,
            })

    def test_draft_transaction_does_not_affect_balance(self):
        self.env['simple.transaction'].create({
            'name': 'Draft entry', 'transaction_type': 'income',
            'cash_account_id': self.cash.id, 'category_id': self.income_cat.id, 'amount': 1000.0,
        })
        self.assertEqual(self.cash.balance, 0.0)

    def test_invoice_totals_with_tax(self):
        invoice = self.env['simple.invoice'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'name': 'Consulting', 'category_id': self.income_cat.id,
                'quantity': 2, 'price_unit': 100.0, 'tax_id': self.tax_12.id,
            })],
        })
        self.assertEqual(invoice.amount_untaxed, 200.0)
        self.assertEqual(invoice.amount_tax, 24.0)
        self.assertEqual(invoice.amount_total, 224.0)
        self.assertTrue(invoice.name.startswith('INV/'))

        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.amount_residual, 224.0)
        self.assertEqual(invoice.payment_state, 'not_paid')

    def test_payment_flow_full_and_partial(self):
        invoice = self.env['simple.invoice'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'name': 'Consulting', 'category_id': self.income_cat.id,
                'quantity': 1, 'price_unit': 224.0,
            })],
        })
        invoice.action_post()

        partial_payment = self.env['simple.payment'].create({
            'invoice_id': invoice.id, 'cash_account_id': self.cash.id,
            'category_id': self.income_cat.id, 'amount': 100.0,
        })
        self.assertEqual(invoice.amount_residual, 124.0)
        self.assertEqual(invoice.payment_state, 'partial')
        self.assertEqual(self.cash.balance, 100.0)
        self.assertEqual(partial_payment.transaction_id.state, 'posted')
        self.assertEqual(partial_payment.transaction_id.transaction_type, 'income')

        self.env['simple.payment'].create({
            'invoice_id': invoice.id, 'cash_account_id': self.cash.id,
            'category_id': self.income_cat.id, 'amount': 124.0,
        })
        self.assertEqual(invoice.amount_residual, 0.0)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertEqual(self.cash.balance, 224.0)

    def test_payment_cannot_exceed_residual(self):
        invoice = self.env['simple.invoice'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'name': 'Consulting', 'category_id': self.income_cat.id,
                'quantity': 1, 'price_unit': 100.0,
            })],
        })
        invoice.action_post()
        with self.assertRaises(UserError):
            self.env['simple.payment'].create({
                'invoice_id': invoice.id, 'cash_account_id': self.cash.id,
                'category_id': self.income_cat.id, 'amount': 150.0,
            })

    def test_vendor_bill_payment_is_expense(self):
        bill = self.env['simple.invoice'].create({
            'move_type': 'in_invoice', 'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'name': 'Rent', 'category_id': self.expense_cat.id,
                'quantity': 1, 'price_unit': 500.0,
            })],
        })
        bill.action_post()
        self.env['simple.transaction'].create({
            'name': 'Seed cash', 'transaction_type': 'income',
            'cash_account_id': self.cash.id, 'category_id': self.income_cat.id, 'amount': 1000.0,
        }).action_post()

        payment = self.env['simple.payment'].create({
            'invoice_id': bill.id, 'cash_account_id': self.cash.id,
            'category_id': self.expense_cat.id, 'amount': 500.0,
        })
        self.assertEqual(payment.transaction_id.transaction_type, 'expense')
        self.assertEqual(self.cash.balance, 500.0)

    def test_profit_loss_wizard(self):
        Transaction = self.env['simple.transaction']
        Transaction.create({
            'name': 'Sale', 'transaction_type': 'income',
            'cash_account_id': self.cash.id, 'category_id': self.income_cat.id, 'amount': 1000.0,
        }).action_post()
        Transaction.create({
            'name': 'Expense', 'transaction_type': 'expense',
            'cash_account_id': self.cash.id, 'category_id': self.expense_cat.id, 'amount': 400.0,
        }).action_post()

        wizard = self.env['simple.profit.loss.wizard'].create({})
        wizard.action_generate()
        self.assertEqual(wizard.total_income, 1000.0)
        self.assertEqual(wizard.total_expense, 400.0)
        self.assertEqual(wizard.net_profit, 600.0)
        self.assertEqual(len(wizard.line_ids), 2)

    def test_balance_sheet_balances_with_no_outstanding_invoices(self):
        # Seed matching opening balances (initial capital): Debit Cash / Credit Equity.
        self.cash.opening_balance = 500.0
        self.equity.opening_balance = 500.0

        Transaction = self.env['simple.transaction']
        Transaction.create({
            'name': 'Sale', 'transaction_type': 'income',
            'cash_account_id': self.cash.id, 'category_id': self.income_cat.id, 'amount': 1000.0,
        }).action_post()
        Transaction.create({
            'name': 'Expense', 'transaction_type': 'expense',
            'cash_account_id': self.cash.id, 'category_id': self.expense_cat.id, 'amount': 400.0,
        }).action_post()

        wizard = self.env['simple.balance.sheet.wizard'].create({})
        wizard.action_generate()
        self.assertAlmostEqual(wizard.balance_check, 0.0, places=2)
        self.assertAlmostEqual(wizard.total_assets, 1100.0, places=2)  # 500 + 1000 - 400

    def test_balance_sheet_balances_with_outstanding_invoice(self):
        self.cash.opening_balance = 0.0
        self.equity.opening_balance = 0.0

        invoice = self.env['simple.invoice'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'name': 'Consulting', 'category_id': self.income_cat.id,
                'quantity': 1, 'price_unit': 300.0,
            })],
        })
        invoice.action_post()

        wizard = self.env['simple.balance.sheet.wizard'].create({})
        wizard.action_generate()
        # Unpaid invoice: Assets gain Accounts Receivable, Equity gains the
        # matching "accrued revenue pending" line, so the sheet still balances.
        self.assertAlmostEqual(wizard.balance_check, 0.0, places=2)
