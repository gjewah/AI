# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FiqGuiRelation(models.Model):
    """One row = one typed, directed, dated relation between two partners.

    Stored ONCE, read from both sides. Storing the mirror row as well would double the
    data and let the two copies drift apart; instead partner_a_id/partner_b_id keep the
    stored direction and the type supplies the label for whichever side is being viewed.

    parent_id on res.partner is never touched. This model sits beside it: the native
    address-book tree keeps working exactly as before, and no migration is required for
    this module to be useful.
    """

    _name = "fiq.gui.relation"
    _description = "FIQ Relations - relation between two contacts"
    _order = "date_start desc, id desc"
    _rec_name = "display_name"

    partner_a_id = fields.Many2one(
        "res.partner", string="From", required=True, index=True, ondelete="cascade")
    partner_b_id = fields.Many2one(
        "res.partner", string="To", required=True, index=True, ondelete="cascade")
    type_id = fields.Many2one(
        "fiq.gui.relation.type", string="Relation", required=True, ondelete="restrict")
    date_start = fields.Date("Valid from")
    date_end = fields.Date(
        "Valid to", help="Empty means ongoing. A relation that ends is dated, never "
                         "deleted - and the person is never archived because of it.")
    note = fields.Char(
        "Note", help="Free text, typically the job title held through this affiliation.")
    company_id = fields.Many2one(
        "res.company", string="Company", index=True,
        default=lambda self: self.env.company,
        help="Owning company. Empty = visible across the companies the user may see.")
    active = fields.Boolean(default=True)

    is_current = fields.Boolean(
        "Current", compute="_compute_is_current", store=True,
        help="Computed from the date window: no start date counts as always started, "
             "no end date as ongoing.")
    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("date_start", "date_end")
    def _compute_is_current(self):
        """Whether the relation is in force today. Stored so it can be searched and
        grouped; recomputed by the daily cron in a later version, since a stored compute
        does not refresh merely because the calendar advanced."""
        today = fields.Date.context_today(self)
        for rec in self:
            started = not rec.date_start or rec.date_start <= today
            ended = rec.date_end and rec.date_end < today
            rec.is_current = started and not ended

    @api.depends("partner_a_id", "partner_b_id", "type_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_a_id and rec.partner_b_id and rec.type_id:
                rec.display_name = "%s %s %s" % (
                    rec.partner_a_id.display_name,
                    rec.type_id.name,
                    rec.partner_b_id.display_name,
                )
            else:
                rec.display_name = _("New relation")

    @api.constrains("partner_a_id", "partner_b_id")
    def _check_not_self(self):
        for rec in self:
            if rec.partner_a_id == rec.partner_b_id:
                raise ValidationError(_("A contact cannot have a relation to itself."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    "The end date cannot be before the start date."))

    @api.constrains("partner_a_id", "partner_b_id", "type_id")
    def _check_partner_kind(self):
        """A type may restrict each side to a person or a company. Enforced on write so a
        catalogue mistake surfaces immediately rather than as odd data later."""
        for rec in self:
            checks = (
                (rec.type_id.partner_a_kind, rec.partner_a_id, _("From")),
                (rec.type_id.partner_b_kind, rec.partner_b_id, _("To")),
            )
            for expected, partner, label in checks:
                if expected == "person" and partner.is_company:
                    raise ValidationError(_(
                        '"%(type)s" expects a person on the %(side)s side, but '
                        "%(name)s is a company.",
                        type=rec.type_id.name, side=label, name=partner.display_name))
                if expected == "company" and not partner.is_company:
                    raise ValidationError(_(
                        '"%(type)s" expects a company on the %(side)s side, but '
                        "%(name)s is a person.",
                        type=rec.type_id.name, side=label, name=partner.display_name))

    @api.model
    def relations_for_partner(self, partner_id, only_current=False):
        """Every relation the partner takes part in, from either side, each already
        turned around so it reads correctly from that partner's point of view.

        This is the method the surfaces call. Returning plain dictionaries rather than
        recordsets keeps the caller free of assumptions about which side was stored.
        """
        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            return []
        domain = ["|", ("partner_a_id", "=", partner.id),
                  ("partner_b_id", "=", partner.id)]
        if only_current:
            domain.append(("is_current", "=", True))
        out = []
        for rel in self.search(domain):
            forward = rel.partner_a_id.id == partner.id
            other = rel.partner_b_id if forward else rel.partner_a_id
            out.append({
                "id": rel.id,
                "label": rel.type_id.label_for_direction(forward),
                "partner_id": other.id,
                "partner_name": other.display_name,
                "type_code": rel.type_id.code,
                "date_start": rel.date_start,
                "date_end": rel.date_end,
                "is_current": rel.is_current,
                "note": rel.note or "",
            })
        return out
