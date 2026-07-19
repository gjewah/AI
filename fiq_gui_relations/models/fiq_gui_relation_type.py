# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FiqGuiRelationType(models.Model):
    """Catalogue of relation types. Each type carries a name in BOTH directions, which is
    what lets one stored row be read correctly from either side: the row
    "Gjermund -> general manager of -> FIQ as" must render as "has as general manager"
    when the same row is viewed from the FIQ as side.

    Configurable rather than a hardcoded Selection: a Selection cannot be extended per
    company without patching code, and the branch-specific types (property management,
    construction) must arrive as data, never as a customer fork.
    """

    _name = "fiq.gui.relation.type"
    _description = "FIQ Relations - relation type"
    _order = "sequence, name"

    name = fields.Char(
        "Forward name", required=True, translate=True,
        help='Read A -> B, e.g. "is general manager of".')
    name_inverse = fields.Char(
        "Reverse name", translate=True,
        help='Read B -> A, e.g. "has as general manager". '
             'Left empty on a symmetric type, where the forward name is used both ways.')
    code = fields.Char(
        "Code", required=True,
        help="Stable technical key. Referenced by data and integrations, so it should "
             "not change once the type is in use.")
    sequence = fields.Integer(default=10)
    symmetric = fields.Boolean(
        "Symmetric",
        help='Both directions read the same, e.g. "collaborates with". '
             "The reverse name is then not used.")
    partner_a_kind = fields.Selection(
        [("person", "Person"), ("company", "Company"), ("both", "Both")],
        string="A side", default="both", required=True)
    partner_b_kind = fields.Selection(
        [("person", "Person"), ("company", "Company"), ("both", "Both")],
        string="B side", default="both", required=True)
    active = fields.Boolean(default=True)
    company_ids = fields.Many2many(
        "res.company", string="Enabled for",
        help="Companies where this type is offered. Empty = available to all.")

    # Odoo 19: models.Constraint, not the deprecated _sql_constraints list. The old form
    # still creates the constraint, but warns on every registry load - which turns the
    # build orange and buries warnings that actually matter.
    # Core pattern: project/models/project_tags.py:25.
    _code_uniq = models.Constraint(
        "unique (code)",
        "The relation type code must be unique.",
    )

    @api.constrains("symmetric", "name_inverse")
    def _check_inverse(self):
        """A non-symmetric type without a reverse name would render as a blank label when
        the relation is viewed from the B side - the failure is silent and only visible in
        the UI, so it is blocked at write time instead."""
        for rec in self:
            if not rec.symmetric and not rec.name_inverse:
                raise ValidationError(_(
                    'The relation type "%s" needs a reverse name, or must be marked '
                    "symmetric. Without it the relation has no readable label when seen "
                    "from the other side.", rec.name))

    def label_for_direction(self, forward=True):
        """Return the label to display. Symmetric types read the same both ways."""
        self.ensure_one()
        if forward or self.symmetric:
            return self.name
        return self.name_inverse or self.name
