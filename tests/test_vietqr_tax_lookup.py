from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged

REQUESTS_GET = "odoo.addons.vietqr_tax_lookup.models.res_partner.requests.get"

DTECH = {
    "id": "0109153660",
    "name": "CÔNG TY TNHH CÔNG NGHỆ VÀ GIẢI PHÁP PHẦN MỀM DTECH",
    "internationalName": "DTECH SOFTWARE SOLUTION AND TECHNOLOGY COMPANY LIMITED",
    "shortName": "DTECH SST CO., LTD",
    "address": "Tầng 6, tòa nhà Việt Á, số 9 phố Duy Tân, Phường Cầu Giấy, TP Hà Nội",
    "status": "NNT đang hoạt động",
}


def _response(payload):
    response = MagicMock()
    response.json.return_value = payload
    return response


@tagged("post_install", "-at_install")
class TestVietqrTaxLookup(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.partner"].create(
            {"name": "Placeholder", "is_company": True, "vat": " 0109153660 "}
        )

    def test_fetch_fills_company(self):
        with patch(REQUESTS_GET, return_value=_response({"code": "00", "data": DTECH})):
            self.company.action_vietqr_fetch_tax_info()
        self.assertEqual(self.company.name, DTECH["name"])
        self.assertEqual(self.company.vat, "0109153660")
        self.assertEqual(self.company.vietqr_short_name, DTECH["shortName"])
        self.assertEqual(
            self.company.vietqr_international_name, DTECH["internationalName"]
        )
        self.assertEqual(self.company.vietqr_tax_status, DTECH["status"])
        self.assertEqual(
            self.company.street,
            "Tầng 6, tòa nhà Việt Á, số 9 phố Duy Tân, Phường Cầu Giấy",
        )
        self.assertEqual(self.company.state_id, self.env.ref("base.state_vn_VN-HN"))
        self.assertEqual(self.company.country_id, self.env.ref("base.vn"))

    def test_unknown_province_keeps_full_address(self):
        data = dict(DTECH, address="Số 1 Đường A, Quận B, Tỉnh Không Tồn Tại")
        with patch(REQUESTS_GET, return_value=_response({"code": "00", "data": data})):
            self.company.action_vietqr_fetch_tax_info()
        self.assertEqual(self.company.street, data["address"])
        self.assertFalse(self.company.state_id)

    def test_tax_code_not_found(self):
        payload = {"code": "51", "desc": "Tax not found", "data": None}
        with (
            patch(REQUESTS_GET, return_value=_response(payload)),
            self.assertRaisesRegex(UserError, "Tax not found"),
        ):
            self.company.action_vietqr_fetch_tax_info()

    def test_network_error(self):
        with (
            patch(REQUESTS_GET, side_effect=requests.ConnectionError),
            self.assertRaises(UserError),
        ):
            self.company.action_vietqr_fetch_tax_info()

    def test_invalid_tax_code_skips_request(self):
        self.company.vat = "12345"
        with patch(REQUESTS_GET) as get, self.assertRaises(UserError):
            self.company.action_vietqr_fetch_tax_info()
        get.assert_not_called()

    def test_individual_rejected(self):
        person = self.env["res.partner"].create(
            {"name": "Person", "is_company": False, "vat": "0109153660"}
        )
        with patch(REQUESTS_GET) as get, self.assertRaises(UserError):
            person.action_vietqr_fetch_tax_info()
        get.assert_not_called()

    def test_branch_tax_code(self):
        clean = self.env["res.partner"]._vietqr_clean_tax_code
        self.assertEqual(clean("VN 0109153660-001"), "0109153660-001")
        self.assertFalse(clean("0109153660-1"))

    def test_onchange_fills_new_company(self):
        with patch(REQUESTS_GET, return_value=_response({"code": "00", "data": DTECH})):
            form = Form(self.env["res.partner"])
            form.company_type = "company"
            form.vat = "0109153660"
        self.assertEqual(form.name, DTECH["name"])
        self.assertEqual(form.state_id, self.env.ref("base.state_vn_VN-HN"))
        partner = form.save()
        self.assertEqual(partner.vietqr_short_name, DTECH["shortName"])
