{  # noqa: B018
    "name": "VietQR Tax Lookup",
    "version": "19.0.1.0.0",
    "summary": "Fill company contacts from their Vietnamese tax code via VietQR",
    "category": "Sales",
    "author": "Tricasia",
    "license": "LGPL-3",
    "depends": ["contacts"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
}
