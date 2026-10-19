import logging
import re
import unicodedata

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

VIETQR_BUSINESS_URL = "https://api.vietqr.io/v2/business/{}"
VIETQR_TIMEOUT = 10
# 10 digits for a company, 10 digits + "-" + 3 digits for a branch
TAX_CODE_RE = re.compile(r"^\d{10}(-\d{3})?$")
PROVINCE_PREFIX_RE = re.compile(r"^(thanh pho|tp\.?|tinh)\s+")


def _normalize_place(name):
    """Lowercase, strip accents and administrative prefixes ("TP", "Tỉnh"...)."""
    name = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return PROVINCE_PREFIX_RE.sub("", name.lower().strip())


class ResPartner(models.Model):
    _inherit = "res.partner"

    vietqr_international_name = fields.Char(string="International Name")
    vietqr_short_name = fields.Char(string="Short Name")
    vietqr_tax_status = fields.Char(string="Tax Status")

    @api.model
    def _vietqr_clean_tax_code(self, vat):
        tax_code = re.sub(r"\s+", "", vat or "").upper().removeprefix("VN")
        return tax_code if TAX_CODE_RE.match(tax_code) else False

    @api.model
    def _vietqr_fetch_business(self, tax_code):
        """Return the VietQR business record for ``tax_code``, or raise UserError."""
        try:
            response = requests.get(
                VIETQR_BUSINESS_URL.format(tax_code), timeout=VIETQR_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as e:
            _logger.warning("VietQR lookup failed for %s: %s", tax_code, e)
            raise UserError(
                self.env._("Could not reach VietQR. Please try again later.")
            ) from e
        if payload.get("code") != "00" or not payload.get("data"):
            raise UserError(
                self.env._(
                    "VietQR: %(desc)s (tax ID %(tax_code)s)",
                    desc=payload.get("desc") or payload.get("code"),
                    tax_code=tax_code,
                )
            )
        return payload["data"]

    @api.model
    def _vietqr_split_address(self, address):
        """Split a VietQR address into (street, state) when the last part is a province."""
        vietnam = self.env.ref("base.vn", raise_if_not_found=False)
        parts = [part.strip() for part in (address or "").split(",")]
        if not vietnam or len(parts) < 2:
            return address, self.env["res.country.state"]
        province = _normalize_place(parts[-1])
        states = self.env["res.country.state"].search([("country_id", "=", vietnam.id)])
        for state in states:
            state_name = _normalize_place(state.name)
            # "Thừa Thiên - Huế" is printed as "TP Huế" on recent addresses
            if state_name == province or state_name.endswith(f" {province}"):
                return ", ".join(parts[:-1]), state
        return address, self.env["res.country.state"]

    def _vietqr_prepare_values(self, data):
        street, state = self._vietqr_split_address(data.get("address"))
        vietnam = self.env.ref("base.vn", raise_if_not_found=False)
        values = {
            "vat": data.get("id"),
            "vietqr_international_name": data.get("internationalName") or False,
            "vietqr_short_name": data.get("shortName") or False,
            "vietqr_tax_status": data.get("status") or False,
            "street": street or False,
            "street2": False,
            "city": False,
            "state_id": state.id,
            "country_id": vietnam.id if vietnam else False,
        }
        if data.get("name"):
            values["name"] = data["name"]
        return values

    def action_vietqr_fetch_tax_info(self):
        for partner in self:
            if not partner.is_company:
                raise UserError(
                    self.env._("Only companies can be looked up by tax ID.")
                )
            tax_code = self._vietqr_clean_tax_code(partner.vat)
            if not tax_code:
                raise UserError(
                    self.env._(
                        "Enter a valid tax ID (10 digits, or 10 digits-3 digits"
                        " for a branch) before fetching its information."
                    )
                )
            data = self._vietqr_fetch_business(tax_code)
            partner.write(partner._vietqr_prepare_values(data))
        return True

    @api.onchange("vat")
    def _onchange_vat_vietqr(self):
        # The button saves the record first, which a new company without a name
        # can't pass. Fill new companies straight from the tax code instead.
        if not self.is_company or self.name:
            return None
        tax_code = self._vietqr_clean_tax_code(self.vat)
        if not tax_code:
            return None
        try:
            data = self._vietqr_fetch_business(tax_code)
        except UserError as e:
            return {"warning": {"title": self.env._("VietQR"), "message": str(e)}}
        self.update(self._vietqr_prepare_values(data))
        return None
