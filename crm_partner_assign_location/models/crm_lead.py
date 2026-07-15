from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_check_location(self):
        """ Check if another salesman has exclusive rights of the location of the contact. """
        self.ensure_one()
        partner = self.partner_id
        user = self.user_id
        if not partner or not user:
            return True
        
        if partner.state_id:
            self._check_exclusive("state_id")
        if partner.country_id:
            self._check_exclusive("country_id")
        return True

    def _check_exclusive(self, field_to_check):
        """ Ensure no conflicting assignments. """
        self.ensure_one()

        fields = ["state_id", "country_id"]
        i = fields.index(field_to_check)

        # The location_field will determine how specific the search is.
        # If the current record is assigned to a zip, search for conflicing zip/city/state/country.
        # If the current record is assigned to a country, search for conflicting country
        # (the location_field may be zip/city/state/country).
        search_fields = fields[i:]
        location_fields = fields[:i+1]

        # Build the domain dynamically
        domain = [("partner_id", "!=", self.user_id.partner_id.id)]
        domain += ["|"] * (len(search_fields) - 1)
        for search_field in search_fields:
            location_fields = location_fields or [search_field]
            domain += [
                "&",
                ("location_field", "in", location_fields),
                (search_field, "=", getattr(self.partner_id, search_field).id)
            ]
            location_fields = None

        existing = self.env["res.partner.assign.location"].search(domain)
        # If the current record is not exclusive, only conflict with exclusive assignments.
        # if not self.is_exclusive:
        existing = existing.filtered(lambda r: r.is_exclusive)
        if existing:
            names = ", ".join(existing.mapped("partner_id").mapped("name"))
            raise ValidationError(
                f"This location conflicts with exclusivity to {names}"
            )
    """
    Changes from res.partner.assign.location:
    field_to_check
    fields
    domain partner_id
    always filter on is_exclusive
    """