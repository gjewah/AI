from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # res_company_search_view / base_address_extended make the address searchable
    # by storing the address fields on res.company. Odoo 19 requires every field
    # sharing the same compute method (_compute_address) to be consistent in both
    # 'store' and 'compute_sudo', otherwise the registry emits a UserWarning.
    #
    # _compute_address reads partner_id.sudo() (see base/models/res_company.py),
    # so the whole group is stored AND compute_sudo=True to stay consistent.

    street = fields.Char(store=True, compute_sudo=True)
    street2 = fields.Char(store=True, compute_sudo=True)
    zip = fields.Char(store=True, compute_sudo=True)
    city = fields.Char(store=True, compute_sudo=True)
    state_id = fields.Many2one(store=True, compute_sudo=True)
    country_id = fields.Many2one(store=True, compute_sudo=True)
    city_id = fields.Many2one(store=True, compute_sudo=True)
    zip_id = fields.Many2one(store=True, compute_sudo=True)
