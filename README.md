# VietQR Tax Lookup

Odoo 19 module by Tricasia. On a company contact, the **Lấy thông tin MST** button (or typing the tax code on a new company) fetches the business from `api.vietqr.io` and fills the name, address, province, short name, international name and tax status.

Documentation: `docs/vn_accounting/VN_Accounting_Documentation.pdf` in [Tricasia/odoo-dev](https://github.com/Tricasia/odoo-dev), section 10.

Tests: `odoo -d <tmp_db> -i vietqr_tax_lookup --test-tags /vietqr_tax_lookup --stop-after-init`
