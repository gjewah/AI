# -*- coding: utf-8 -*-
from odoo import models
from .fiq_tilgang_regel import NIVAA_RANG


class DocumentsTag(models.Model):
    """Utvider dokument-etiketten (området) med arvet effektiv tilgang."""
    _inherit = "documents.tag"

    def effektiv_nivaa(self, user=None):
        """Effektivt tilgangsnivå for brukeren på dette området (0 = ingen tilgang).

        Novell-arv («Inherited Rights Filter»): gå oppover forelder-kjeden og akkumuler
        tildelinger. Et BRUDD på en node stopper videre arv oppover (forelderen arves ikke).
        Global admin (topp/selskap) overstyrer alt."""
        self.ensure_one()
        user = user or self.env.user

        # 🔴 TENANT-LEKKASJE RETTET 23.07.2026 (funnet av enhetstest, verifisert av AI PK):
        # her sto bare `has_group(group_company_admin)` → administrere. En bruker med
        # «Global admin (selskap)» i FIRMA B fikk dermed full tilgang til FIRMA A sitt
        # område. «Per selskap» var bare et NAVN på gruppa — ingen kode så på hvilket
        # selskap området tilhørte. Feilen ga feil svar STILLE; ingen feilmelding.
        # Global admin (topp) er tenant-uavhengig og overstyrer fortsatt alt.
        if user.has_group("fiq_tilgang.group_global_admin"):
            return NIVAA_RANG["administrere"]
        if user.has_group("fiq_tilgang.group_company_admin") and self._samme_selskap(user):
            return NIVAA_RANG["administrere"]

        Regel = self.env["fiq.tilgang.regel"].sudo()
        beste = 0
        node = self
        while node:
            # Regelsøket filtreres nå på selskap: en regel som tilhører et annet
            # selskap skal aldri gi tilgang her. `company_id = False` = generisk regel
            # (deles på tvers), jf. samme mønster som malene i fiq_mgmtsystem.
            regler = Regel.search([
                ("ressurs_id", "=", node.id),
                ("company_id", "in", [False] + user.company_ids.ids),
            ])
            egne = regler.filtered(lambda r: r._gjelder_bruker(user))
            for r in egne.filtered(lambda r: r.regel_type == "tildeling"):
                beste = max(beste, NIVAA_RANG[r.nivaa])
            if egne.filtered(lambda r: r.regel_type == "brudd"):
                break  # brudd stopper arv fra forelderen
            node = node._forelder()
        return beste

    def _samme_selskap(self, user):
        """Sant hvis området hører til et selskap brukeren har tilgang til.

        Et område uten selskap (`company_id = False`) er generisk og deles av alle —
        samme regel som for maler ellers i huset."""
        self.ensure_one()
        eier = getattr(self, "company_id", False)
        return (not eier) or eier.id in user.company_ids.ids

    def _forelder(self):
        """Forelderen i områdehierarkiet, eller tomt recordset.

        🔴 RETTET 23.07.2026: her sto `node.parent_id` direkte. Feltet finnes IKKE på
        `documents.tag` i Odoo 19 — det kommer fra modulen `documents_tag`, som ikke
        står i `depends`. Målt: 0 treff i `ir_model_fields`, modulen `uninstalled`.
        Følgen var at HELE `effektiv_nivaa()` krasjet med AttributeError ved hvert kall
        (18 av 33 tester feilet på den). Nå degraderes arven til «ingen forelder» når
        feltet mangler, i stedet for å ta ned tilgangskontrollen."""
        self.ensure_one()
        return self.parent_id if "parent_id" in self._fields else self.browse()

    def har_tilgang(self, nivaa, user=None):
        """Sant hvis brukeren har minst det gitte nivået (lese/skrive/administrere)."""
        self.ensure_one()
        return self.effektiv_nivaa(user) >= NIVAA_RANG.get(nivaa, 99)
