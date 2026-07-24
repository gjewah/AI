"""Oppgavens egen SharePoint-mappe — stabil referanse.

Krav 6 i dokument_sp_bro_spec (Gjermund 2026-07-05): oppgaven skal ha et
mappenavn-felt og en «Opprett mappe»-knapp. Knappen og Graph-kallet hører i
broen; her ligger BÆREREN — feltene som holder mappas identitet.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = "project.task"

    sp_mappe_drive_id = fields.Char(
        string="SP bibliotek-ID",
        index=True,
        copy=False,
        help="Dokumentbiblioteket oppgavens mappe ligger i.",
    )
    sp_mappe_item_id = fields.Char(
        string="SP mappe-ID",
        index=True,
        copy=False,
        help="SharePoint-ID for oppgavens mappe. Overlever omdøping og flytting.",
    )
    sp_mappe_url = fields.Char(
        string="SP mappe-lenke",
        copy=False,
        help="Nettadresse ved siste synk. Kun visning — ID-ene er fasit.",
    )
    sp_mappenavn = fields.Char(
        string="Mappenavn",
        copy=False,
        help="Navnet mappa skal ha i SharePoint. Foreslås fra oppgavenummer + navn, "
        "men kan overstyres. Tegn som ikke er tillatt i filnavn fjernes ved "
        "opprettelse (gjøres av broen).",
    )
    sp_har_mappe = fields.Boolean(
        string="Har SP-mappe",
        compute="_compute_sp_har_mappe",
        store=True,
    )

    def _compute_sp_har_mappe(self):
        for task in self:
            task.sp_har_mappe = bool(task.sp_mappe_drive_id and task.sp_mappe_item_id)

    def foreslatt_mappenavn(self):
        """Forslag til mappenavn: «<oppgavenr> <navn>», Excel- og filsystem-trygt.

        Setter ikke feltet — kalleren bestemmer. Broen bruker dette som default
        i «Opprett mappe»-knappen.
        """
        self.ensure_one()
        ugyldig = '\\/:*?"<>|'
        deler = []
        # project.task.code kommer fra loym project_sequence_number (T0001)
        kode = getattr(self, "code", False)
        if kode:
            deler.append(str(kode))
        if self.name:
            deler.append(self.name)
        navn = " ".join(deler).strip() or _("Oppgave %s") % self.id
        for tegn in ugyldig:
            navn = navn.replace(tegn, "-")
        # SharePoint tåler ikke navn som starter/slutter med punktum eller mellomrom
        return navn.strip(" .")[:120]

    def sett_sp_mappe(self, drive_id, item_id, web_url=None, mappenavn=None):
        """Lagrer mappereferansen. Ett inngangspunkt, som på dokumentet."""
        self.ensure_one()
        if not drive_id or not item_id:
            raise UserError(
                _("Både bibliotek-ID og mappe-ID må oppgis for en stabil referanse.")
            )
        vals = {"sp_mappe_drive_id": drive_id, "sp_mappe_item_id": item_id}
        if web_url:
            vals["sp_mappe_url"] = web_url
        if mappenavn:
            vals["sp_mappenavn"] = mappenavn
        self.write(vals)
        return True
