# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """Relations exposed on the partner form itself.

    Odoo-native first: these are ordinary fields and an ordinary tab on the standard
    contact form. The relations are usable without any FIQ surface installed, and they
    survive if one is removed - relations are core partner data, not screen state.

    No field here replaces parent_id. It keeps driving the native address-book tree.
    """

    _inherit = "res.partner"

    fiq_relation_a_ids = fields.One2many(
        "fiq.gui.relation", "partner_a_id", string="Relations (from)")
    fiq_relation_b_ids = fields.One2many(
        "fiq.gui.relation", "partner_b_id", string="Relations (to)")
    fiq_relation_count = fields.Integer(
        compute="_compute_fiq_relation_count", string="Relations")

    # Absorbed from partner_short_name (Loym) 24.07.2026, per the consolidation map.
    # It belongs here rather than in a module of its own: a short name is what a
    # relation graph shows on a node. "SDV Prosjekt as" does not fit in a box; "SDVp"
    # does. Keeping an 18-line module alive for one field is upkeep without benefit.
    short_name = fields.Char(
        "Short name", index=True,
        help="Compact name used where the full one does not fit - graph nodes, cards, "
             "narrow columns. Falls back to the ordinary name when empty.")

    # Search-only fields: they hold nothing and display nothing. Their whole purpose is
    # to let a user filter contacts BY their relations - "everyone employed at Pecunia",
    # "everyone who had a relation to us in 2024". Without them the model can store
    # relations but not find anything through them, which for a relations surface is
    # half a feature.
    #
    # The pattern (compute that blanks the value + a search method returning a domain on
    # ids) is Odoo's standard way to expose a filter that has no stored counterpart. It
    # is borrowed from OCA partner_multi_relation 19.0.1.1.0, res_partner.py - the module
    # that solves this same problem, read for its design rather than installed.
    fiq_search_relation_type_id = fields.Many2one(
        "fiq.gui.relation.type",
        string="Has relation of type",
        compute=lambda self: self.update({"fiq_search_relation_type_id": False}),
        search="_search_fiq_relation_type_id",
    )
    fiq_search_relation_partner_id = fields.Many2one(
        "res.partner",
        string="Has relation with",
        compute=lambda self: self.update({"fiq_search_relation_partner_id": False}),
        search="_search_fiq_relation_partner_id",
    )
    fiq_search_relation_date = fields.Date(
        string="Had relation on",
        compute=lambda self: self.update({"fiq_search_relation_date": False}),
        search="_search_fiq_relation_date",
        help="Contacts holding a relation that was in force on this date. A relation "
             "with no start date counts as always started; no end date as ongoing.",
    )

    @api.depends("fiq_relation_a_ids", "fiq_relation_b_ids")
    def _compute_fiq_relation_count(self):
        """Counted per side and summed. A single search grouped by partner would miss the
        rows where this partner is on the B side, which is exactly the half that the
        native parent_id cannot express."""
        for partner in self:
            partner.fiq_relation_count = (
                len(partner.fiq_relation_a_ids) + len(partner.fiq_relation_b_ids))

    def _fiq_partners_from_relations(self, domain):
        """Partner ids taking part in any relation matching `domain`, from EITHER side.

        Both sides matter, and that is the whole point: searching only partner_a_id would
        find the employees but not the employers. The stored direction is an
        implementation detail of the row, never a property of the question being asked.
        """
        relations = self.env["fiq.gui.relation"].search(domain)
        return list({
            pid
            for rel in relations
            for pid in (rel.partner_a_id.id, rel.partner_b_id.id)
        })

    def _search_fiq_relation_type_id(self, operator, value):
        return [("id", "in", self._fiq_partners_from_relations(
            [("type_id", operator, value)]))]

    def _search_fiq_relation_partner_id(self, operator, value):
        """Contacts that have a relation TO the given partner.

        Note the asymmetry with the field above: here the searched-for partner must be
        excluded from the result. Asking "who has a relation with Pecunia" should not
        return Pecunia itself, even though it takes part in every one of those rows.
        """
        relations = self.env["fiq.gui.relation"].search([
            "|", ("partner_a_id", operator, value), ("partner_b_id", operator, value),
        ])
        wanted = set()
        for rel in relations:
            wanted.add(rel.partner_a_id.id)
            wanted.add(rel.partner_b_id.id)
        # Drop the partners that were themselves the target of the search.
        targets = set(self.env["res.partner"].search([("id", operator, value)]).ids)
        return [("id", "in", list(wanted - targets))]

    def _search_fiq_relation_date(self, operator, value):
        """Contacts holding a relation in force on the given date.

        Only equality is meaningful: "had a relation on 3 May" is a point-in-time
        question, and a date range would need two fields to be unambiguous. An
        unsupported operator raises rather than quietly returning everything - a filter
        that silently ignores its own operator is worse than one that refuses.
        """
        if operator not in ("=", "!="):
            raise UserError(_(
                'Search on "Had relation on" supports = and != only, not "%s".', operator))
        ids = self._fiq_partners_from_relations([
            "|", ("date_start", "=", False), ("date_start", "<=", value),
            "|", ("date_end", "=", False), ("date_end", ">=", value),
        ])
        return [("id", "in" if operator == "=" else "not in", ids)]

    def action_fiq_relations(self):
        """Open every relation this partner takes part in, from either side."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Relations - %s", self.display_name),
            "res_model": "fiq.gui.relation",
            "view_mode": "list,form",
            "domain": ["|", ("partner_a_id", "=", self.id),
                       ("partner_b_id", "=", self.id)],
            "context": {"default_partner_a_id": self.id},
        }
