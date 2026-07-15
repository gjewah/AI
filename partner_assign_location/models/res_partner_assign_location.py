from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


class ResPartnerAssignLocation(models.Model):
    _name = "res.partner.assign.location"
    _description = "res.partner.assign.location"

    @api.depends("location_field", "zip_id", "city_id", "state_id", "country_id")
    def _compute_display_name(self):
        for record in self:
            if record.location_field == "zip_id" and record.zip_id:
                name = record.zip_id.display_name
            elif record.location_field == "city_id" and record.city_id:
                name = record.city_id.display_name
            elif record.location_field == "state_id" and record.state_id:
                name = record.state_id.display_name
            elif record.location_field == "country_id" and record.country_id:
                name = record.country_id.display_name
            else:
                name = "Undefined"
            record.display_name = name

    conflict_ids = fields.Many2many(
        comodel_name="res.partner.assign.location",
        relation="res_partner_assign_location_conflict",
        column1="assign_id",
        column2="conflicts_with",
        string="Conflicts",
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
        ],
        default="draft",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        required=True,
    )
    is_exclusive = fields.Boolean(
        string="Exclusive",
        help="If checked, this location will only be assigned to this contact.",
    )
    location_field = fields.Selection(
        [
            ("zip_id", "Zip"),
            ("city_id", "City"),
            ("state_id", "State"),
            ("country_id", "Country"),
        ],
        string="Location Field",
        required=True,
    )
    zip_id = fields.Many2one(
        "res.city.zip",
        string="Zip",
    )
    city_id = fields.Many2one(
        "res.city",
        string="City",
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """ Always draft state, check for conflicts """
        for vals in vals_list:
            vals["state"] = "draft"
        records = super().create(vals_list)
        records._set_location_fields()
        records._check_for_conflicts()
        return records

    def write(self, vals):
        """ Do not confirm if there are conflicts. Do not change confirmed records. """

        if "conflict_ids" in vals:
            assert len(vals) == 1
            return super().write(vals)

        if "state" in vals:
            if vals["state"] == "confirmed":
                assert len(vals) == 1
                self._check_for_conflicts()
                if self.mapped("conflict_ids"):
                    return # Rather update conflicts than notify user
            return super().write(vals)

        if "confirmed" in self.mapped("state"):
            raise ValidationError("Do not change confirmed records.")

        super().write(vals)
        if not self.env.context.get("_setting_location_fields"):
            self._set_location_fields()
            self._check_for_conflicts()
        return True

    def _set_location_fields(self):
        for record in self.with_context(_setting_location_fields=True):
            if record.location_field == "zip_id":
                record.city_id = record.zip_id.city_id
                record.state_id = record.zip_id.state_id
                record.country_id = record.zip_id.country_id
            elif record.location_field == "city_id":
                record.zip_id = False
                record.state_id = record.city_id.state_id
                record.country_id = record.city_id.country_id
            elif record.location_field == "state_id":
                record.zip_id = False
                record.city_id = False
                record.country_id = record.state_id.country_id
            elif record.location_field == "country_id":
                record.zip_id = False
                record.city_id = False
                record.state_id = False

    def _check_for_conflicts(self):
        """ List conflicting assignments. """

        fields = ["zip_id", "city_id", "state_id", "country_id"]
        for record in self:
            index = fields.index(record.location_field)

            # The location_field will determine how specific the search is.
            # If the current record is assigned to a zip, search for conflicing zip/city/state/country.
            # If the current record is assigned to a country, search for conflicting country.
            search_fields = fields[index:]

            # Build the domain dynamically
            domain = [("id", "!=", record.id)]
            domain += ["|"] * (len(search_fields) - 1)
            for search_field in search_fields:
                domain += [(search_field, "=", getattr(record, search_field).id)]

            # Save conflicts
            conflicts = record.search(domain)
            if not record.is_exclusive:
                conflicts = conflicts.filtered(lambda r: r.is_exclusive)
            record.conflict_ids = [Command.set(conflicts.ids)]
