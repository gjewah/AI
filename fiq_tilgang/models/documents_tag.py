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
        if user.has_group("fiq_tilgang.group_global_admin") or \
           user.has_group("fiq_tilgang.group_company_admin"):
            return NIVAA_RANG["administrere"]
        Regel = self.env["fiq.tilgang.regel"].sudo()
        beste = 0
        node = self
        while node:
            regler = Regel.search([("ressurs_id", "=", node.id)])
            egne = regler.filtered(lambda r: r._gjelder_bruker(user))
            for r in egne.filtered(lambda r: r.regel_type == "tildeling"):
                beste = max(beste, NIVAA_RANG[r.nivaa])
            if egne.filtered(lambda r: r.regel_type == "brudd"):
                break  # brudd stopper arv fra forelderen
            node = node.parent_id
        return beste

    def har_tilgang(self, nivaa, user=None):
        """Sant hvis brukeren har minst det gitte nivået (lese/skrive/administrere)."""
        self.ensure_one()
        return self.effektiv_nivaa(user) >= NIVAA_RANG.get(nivaa, 99)
