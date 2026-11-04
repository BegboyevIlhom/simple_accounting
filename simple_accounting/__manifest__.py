# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Simple Accounting',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Accounting',
    'sequence': 30,
    'summary': "Lightweight cash-basis bookkeeping: accounts, income/expense entries, invoices, payments and basic reports",
    'description': """
Simple Accounting
==================
A deliberately small, standalone bookkeeping app for businesses that find
the full Accounting app too complex. It does not depend on and does not
touch the `account` module at all.

Features
--------
* A short chart of accounts (asset / liability / equity / income / expense)
* A cash book: record income, expense and transfer entries (kirim / chiqim / o'tkazma)
* Simple percentage-based taxes
* Customer and vendor invoices with automatic tax computation and an
  outstanding (residual) balance
* Payments against invoices that automatically post the matching cash
  entry (cash-basis accounting)
* Three basic reports: Profit & Loss, Balance Sheet and a Tax report
""",
    'website': 'https://your-domain.example',
    'author': 'YOUR COMPANY NAME HERE',
    'support': 'support@your-domain.example',
    'depends': ['base'],
    'data': [
        'security/simple_accounting_security.xml',
        'data/simple_accounting_data.xml',
        'views/simple_account_views.xml',
        'views/simple_tax_views.xml',
        'views/simple_transaction_views.xml',
        'views/simple_payment_views.xml',
        'views/simple_invoice_views.xml',
        'wizard/simple_profit_loss_views.xml',
        'wizard/simple_balance_sheet_views.xml',
        'wizard/simple_tax_report_views.xml',
        'views/simple_accounting_menus.xml',
        'security/ir.access.csv',
    ],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
