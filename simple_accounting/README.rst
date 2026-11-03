Simple Accounting
==================

A small, standalone bookkeeping app for businesses that find Odoo's full
Accounting app too complex. It does not depend on, read, or write anything
in the ``account`` module.

Features
--------

* A short chart of accounts (asset / liability / equity / income / expense)
* A cash book: income, expense and transfer entries
* Simple percentage-based taxes
* Customer invoices and vendor bills, with automatic tax computation and a
  live outstanding balance
* Payments against invoices that automatically post the matching cash-basis
  ledger entry
* Three reports: Profit & Loss, Balance Sheet (always balances, including
  an "accrued revenue pending" adjustment for unpaid invoices) and a Tax
  report

Installation
------------

No special requirements. Install like any other Odoo app:
``Apps > Update Apps List > search "Simple Accounting" > Install``.

Configuration
-------------

A default short chart of accounts and two VAT tax rates (0% / 12%) are
created on install, under
``Simple Accounting > Configuration``. Edit or extend them to match your
business before recording entries.

Usage
-----

1. **Ledger > Entries** — record income, expense or transfer entries
   directly (e.g. a cash sale, a rent payment), or
2. **Invoicing > Customer Invoices / Vendor Bills** — create a multi-line
   invoice, confirm it, then use **Register Payment** once it's paid. The
   matching ledger entry is created for you.
3. **Reporting** — generate Profit & Loss, Balance Sheet or Tax Report for
   any date range.

Support
-------

See the ``support`` field in the module manifest.
