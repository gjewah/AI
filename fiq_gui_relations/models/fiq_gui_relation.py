from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date


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
        "res.partner", string="From", required=True, index=True, ondelete="cascade"
    )
    partner_b_id = fields.Many2one(
        "res.partner", string="To", required=True, index=True, ondelete="cascade"
    )
    type_id = fields.Many2one(
        "fiq.gui.relation.type", string="Relation", required=True, ondelete="restrict"
    )
    date_start = fields.Date("Valid from")
    date_end = fields.Date(
        "Valid to",
        help="Empty means ongoing. A relation that ends is dated, never "
        "deleted - and the person is never archived because of it.",
    )
    note = fields.Char(
        "Note", help="Free text, typically the job title held through this affiliation."
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        default=lambda self: self.env.company,
        help="Owning company. Empty = visible across the companies the user may see.",
    )
    active = fields.Boolean(default=True)

    is_current = fields.Boolean(
        "Current",
        compute="_compute_is_current",
        store=True,
        help="Computed from the date window: no start date counts as always started, "
        "no end date as ongoing.",
    )
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
                rec.display_name = f"{rec.partner_a_id.display_name} {rec.type_id.name} {rec.partner_b_id.display_name}"
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
                raise ValidationError(
                    _("The end date cannot be before the start date.")
                )

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
                    raise ValidationError(
                        _(
                            '"%(type)s" expects a person on the %(side)s side, but '
                            "%(name)s is a company.",
                            type=rec.type_id.name,
                            side=label,
                            name=partner.display_name,
                        )
                    )
                if expected == "company" and not partner.is_company:
                    raise ValidationError(
                        _(
                            '"%(type)s" expects a company on the %(side)s side, but '
                            "%(name)s is a person.",
                            type=rec.type_id.name,
                            side=label,
                            name=partner.display_name,
                        )
                    )

    @api.model
    def get_graf(self, firma_id=False):
        """The graph for the relations surface, scoped server-side.

        Returns {noder, kanter, utenfor}. `utenfor` is the count of relations this user
        may NOT see in full, and it is the reason this method exists rather than letting
        the client read the model directly.

        A relation joins two parties. If one of them sits outside the user's companies,
        the relation does not vanish — it becomes half. And half a graph looks complete:
        no empty rows, no error, just fewer nodes than reality has. So the omission is
        counted and handed to the surface, which says it in plain words.

        Scope comes from the session via the control room's helpers, never from the
        client: a company id sent in can only narrow what the user was already allowed
        to see. Falls back to the active company if the core is unavailable, which fails
        closed — one company, never all.
        """
        try:
            config = self.env["fiq.gui.control.config"]
            lovlige = config.tillatte_firmaer().ids
        except Exception:  # noqa: BLE001 - deliberate: see below
            # Broad on purpose, and narrow in effect. Whatever goes wrong reaching the
            # control room - module absent, model renamed, access denied - the answer
            # must be ONE company, never all of them. A narrower except would let an
            # unforeseen error escape and, worse, could leave scope undefined.
            lovlige = self.env.company.ids
        if firma_id and int(firma_id) in lovlige:
            lovlige = [int(firma_id)]

        alle = self.search([("is_current", "=", True)])
        synlige = alle.filtered(
            lambda r: not r.company_id or r.company_id.id in lovlige
        )

        noder, kanter = {}, []
        for rel in synlige:
            for partner, motpart, forward in (
                (rel.partner_a_id, rel.partner_b_id, True),
                (rel.partner_b_id, rel.partner_a_id, False),
            ):
                node = noder.setdefault(
                    partner.id,
                    {
                        "id": partner.id,
                        # short_name where it exists: a graph node is a small box, and
                        # "SDV Prosjekt as" does not fit where "SDVp" does. The full name
                        # stays available for the detail panel.
                        "navn": partner.short_name or partner.display_name or "",
                        "fullt_navn": partner.display_name or "",
                        "kind": "company" if partner.is_company else "person",
                        "kind_navn": _("Companies")
                        if partner.is_company
                        else _("People"),
                        "antall": 0,
                        "relasjoner": [],
                    },
                )
                node["antall"] += 1
                node["relasjoner"].append(
                    {
                        "id": rel.id,
                        "label": rel.type_id.label_for_direction(forward),
                        "partner_name": motpart.display_name or "",
                        "periode": self._periode_tekst(rel),
                        "is_current": rel.is_current,
                    }
                )
            kanter.append(
                {
                    "id": rel.id,
                    "a": rel.partner_a_id.id,
                    "b": rel.partner_b_id.id,
                    "type": rel.type_id.code,
                }
            )

        return {
            "noder": sorted(noder.values(), key=lambda n: n["navn"]),
            "kanter": kanter,
            "utenfor": len(alle) - len(synlige),
        }

    @api.model
    def get_kort(self, firma_id=False):
        """The card view: managers, each with the properties they look after.

        Structure taken from the fasit (docs/mockups/0.00 IQ demo_samlet_pc_mobil.html,
        renderRelasjoner + FORVR): manager -> property -> projects, with "owned by" and
        the responsible person on each property. The point it makes is in the banner
        text: the manager is rarely the owner. Invoices and contact go through the
        manager, while the building belongs to someone else - and that distinction is
        exactly what a flat contact list loses.

        Built from relations, not from a table of its own: a property is a partner, the
        manager link is a relation of type property_manager, ownership a relation of
        type owner. Same scope rules as get_graf - what the user may not see is counted,
        never silently dropped.
        """
        try:
            config = self.env["fiq.gui.control.config"]
            lovlige = config.tillatte_firmaer().ids
        except Exception:  # noqa: BLE001 - deliberate: see below
            # Broad on purpose, and narrow in effect. Whatever goes wrong reaching the
            # control room - module absent, model renamed, access denied - the answer
            # must be ONE company, never all of them. A narrower except would let an
            # unforeseen error escape and, worse, could leave scope undefined.
            lovlige = self.env.company.ids
        if firma_id and int(firma_id) in lovlige:
            lovlige = [int(firma_id)]

        def i_scope(rel):
            return not rel.company_id or rel.company_id.id in lovlige

        forvalter_alle = self.search(
            [("type_id.code", "=", "property_manager"), ("is_current", "=", True)]
        )
        forvalter_rel = forvalter_alle.filtered(i_scope)

        # Ownership and contact persons, looked up once and indexed by property/manager
        # rather than queried per row - a card view over a few hundred properties would
        # otherwise issue a query per property.
        eier_rel = self.search(
            [("type_id.code", "=", "owner"), ("is_current", "=", True)]
        ).filtered(i_scope)
        eier_av = {r.partner_b_id.id: r.partner_a_id for r in eier_rel}

        kontakt_rel = self.search(
            [("type_id.code", "=", "contact_person"), ("is_current", "=", True)]
        ).filtered(i_scope)
        kontakt_hos = {}
        for r in kontakt_rel:
            kontakt_hos.setdefault(r.partner_b_id.id, r.partner_a_id)

        forvaltere = {}
        for rel in forvalter_rel:
            forvalter, eiendom = rel.partner_a_id, rel.partner_b_id
            f = forvaltere.setdefault(
                forvalter.id,
                {
                    "id": forvalter.id,
                    "navn": forvalter.display_name or "",
                    "kontakt": "",
                    "kontakt_id": False,
                    "telefon": "",
                    "eiendommer": [],
                },
            )
            if not f["kontakt"] and forvalter.id in kontakt_hos:
                k = kontakt_hos[forvalter.id]
                f["kontakt"], f["kontakt_id"] = k.display_name or "", k.id
                f["telefon"] = k.mobile or k.phone or ""

            eier = eier_av.get(eiendom.id)
            f["eiendommer"].append(
                {
                    "id": eiendom.id,
                    "adresse": eiendom.display_name or "",
                    "eier": eier.display_name if eier else "",
                    "eier_id": eier.id if eier else False,
                    "prosjekter": self._prosjekter_for(eiendom),
                }
            )

        for f in forvaltere.values():
            f["eiendommer"].sort(key=lambda e: e["adresse"])

        return {
            "forvaltere": sorted(forvaltere.values(), key=lambda f: f["navn"]),
            "utenfor": len(forvalter_alle) - len(forvalter_rel),
        }

    def _prosjekter_for(self, eiendom):
        """Projects running on a property, newest first.

        Read defensively: project may not be installed, and a card view must not fail
        because an optional module is absent. No projects is a valid answer.
        """
        Project = self.env.get("project.project")
        if Project is None:
            return []
        try:
            projects = Project.search(
                [("partner_id", "=", eiendom.id)], order="id desc", limit=10
            )
        except Exception:  # noqa: BLE001 - an optional module must not break the view
            # project may be absent, or its fields may differ between editions. No
            # projects is a valid answer for a card view; a traceback is not.
            return []
        return [
            {
                "id": p.id,
                "nr": (p.sequence_code if "sequence_code" in p._fields else "") or "",
                "navn": p.name or "",
            }
            for p in projects
        ]

    def _periode_tekst(self, rel):
        """Human-readable validity, or empty when the relation has no dates at all."""
        if not rel.date_start and not rel.date_end:
            return ""
        start = format_date(self.env, rel.date_start) if rel.date_start else ""
        if not rel.date_end:
            return _("%s →", start) if start else ""
        slutt = format_date(self.env, rel.date_end)
        return _("%(fra)s – %(til)s", fra=start or "…", til=slutt)

    @api.model
    def _cron_recompute_is_current(self):
        """Refresh is_current daily.

        is_current is stored so it can be searched and grouped, but a stored compute only
        recalculates when a DEPENDENCY changes - and time passing is not a dependency. A
        relation that ended last night would keep reading as current until something
        happened to touch the row.

        Only rows whose stored value actually disagrees with today are recomputed, so the
        job stays cheap on a table that mostly holds settled history.
        """
        today = fields.Date.context_today(self)
        stale = self.search(
            [
                "|",
                # Marked current, but the end date has passed.
                "&",
                ("is_current", "=", True),
                ("date_end", "<", today),
                # Marked not current, but the window now includes today.
                "&",
                "&",
                ("is_current", "=", False),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", today),
                "|",
                ("date_start", "=", False),
                ("date_start", "<=", today),
            ]
        )
        if stale:
            stale._compute_is_current()
        return len(stale)

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
        domain = [
            "|",
            ("partner_a_id", "=", partner.id),
            ("partner_b_id", "=", partner.id),
        ]
        if only_current:
            domain.append(("is_current", "=", True))
        out = []
        for rel in self.search(domain):
            forward = rel.partner_a_id.id == partner.id
            other = rel.partner_b_id if forward else rel.partner_a_id
            out.append(
                {
                    "id": rel.id,
                    "label": rel.type_id.label_for_direction(forward),
                    "partner_id": other.id,
                    "partner_name": other.display_name,
                    "type_code": rel.type_id.code,
                    "date_start": rel.date_start,
                    "date_end": rel.date_end,
                    "is_current": rel.is_current,
                    "note": rel.note or "",
                }
            )
        return out
