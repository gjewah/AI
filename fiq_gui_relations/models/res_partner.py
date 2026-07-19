# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


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

    @api.depends("fiq_relation_a_ids", "fiq_relation_b_ids")
    def _compute_fiq_relation_count(self):
        """Counted per side and summed. A single search grouped by partner would miss the
        rows where this partner is on the B side, which is exactly the half that the
        native parent_id cannot express."""
        for partner in self:
            partner.fiq_relation_count = (
                len(partner.fiq_relation_a_ids) + len(partner.fiq_relation_b_ids))

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
