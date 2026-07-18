# -*- coding: utf-8 -*-
"""Datalag for Prosjektoversikt-flaten.

Hvorfor denne finnes (GUI Prosjekt V0.02, 2026-07-18):
Flaten var en STUBB — `prj.xml` viste bare teksten «Kommer». Modulen var installert,
grønn, med fungerende handling og riktig registrert i KR-menyen — men viste ingenting.
KR-sporet (01.01) målte hele kjeden og fant at feilen ikke lå i menyen: den lå her, i at
det ikke fantes innmat. Lærdom, kanonisert: «installert + grønt + handlingen resolver»
betyr IKKE «flaten viser noe».

KANON «Odoo-native først»: dette laget LESER bare. Det eier ingen forretningslogikk Odoo
alt har, og oppretter ingenting. Slås flaten av, står alle data uendret i Odoos egne visninger.

TENANT-ISOLASJON (kanon): company_id hentes ALDRI som parameter fra klienten. Vi leser
`self.env.companies` (sesjonens tillatte firmaer) og lar Odoos record rules gjøre resten.
Klienten kan SNEVRE INN med `firma_id`, aldri utvide.
"""

from odoo import api, fields, models


class FiqGuiPrjData(models.AbstractModel):
    _name = "fiq.gui.prj.data"
    _description = "FIQ Prosjektoversikt — datalag (kun lesing)"

    # ---------- intern hjelp ----------

    def _tillatte_firmaer(self):
        """Firmaer sesjonen faktisk har — aldri fra klient-parameter."""
        return self.env.companies.ids or [self.env.company.id]

    def _firma_domene(self, firma_id=None):
        """Domene begrenset til sesjonens firmaer. `firma_id` kan kun snevre inn."""
        tillatte = self._tillatte_firmaer()
        if firma_id and int(firma_id) in tillatte:
            return [("company_id", "=", int(firma_id))]
        return [("company_id", "in", tillatte)]

    # ---------- offentlig API for flaten ----------

    @api.model
    def get_prosjektoversikt(self, firma_id=None, grense=50):
        """Prosjekter med fremdrift, oppgavetelling og frister.

        Fremdrift = førte timer / estimerte timer (samme definisjon som AI KTRL-kontrakten),
        med andel ferdige oppgaver som fallback der `allocated_hours` ikke er satt.
        """
        Project = self.env["project.project"]
        domene = self._firma_domene(firma_id)
        prosjekter = Project.search(domene, limit=int(grense), order="name")

        rader = []
        for p in prosjekter:
            oppgaver = p.task_ids
            ferdige = oppgaver.filtered(lambda t: t.stage_id.fold or t.state in ("1_done", "1_canceled"))
            est = p.allocated_hours or 0.0
            ført = p.effective_hours if "effective_hours" in p._fields else 0.0

            if est:
                fremdrift = min(100.0, (ført / est) * 100.0)
                kilde = "timer"
            elif oppgaver:
                fremdrift = (len(ferdige) / len(oppgaver)) * 100.0
                kilde = "oppgaver"
            else:
                fremdrift = 0.0
                kilde = "ingen"

            rader.append({
                "id": p.id,
                "navn": p.display_name,
                # Navn, ikke ID — husets regel. Prosjektnummeret er STABILT (røres aldri).
                "nummer": p.sequence_code or "",
                "firma": p.company_id.display_name or "",
                "firma_id": p.company_id.id,
                "kunde": p.partner_id.display_name or "",
                "antall_oppgaver": len(oppgaver),
                "antall_ferdige": len(ferdige),
                "estimerte_timer": round(est, 1),
                "forte_timer": round(ført, 1),
                "fremdrift": round(fremdrift, 1),
                "fremdrift_kilde": kilde,
                "frist": fields.Date.to_string(p.date) if p.date else False,
            })
        return {
            "prosjekter": rader,
            "firmaer": [
                {"id": c.id, "navn": c.display_name}
                for c in self.env["res.company"].browse(self._tillatte_firmaer())
            ],
            "valgt_firma": int(firma_id) if firma_id else False,
        }

    @api.model
    def get_oppgaver(self, prosjekt_id, firma_id=None):
        """Oppgavene i ett prosjekt, sortert etter disposisjonsnummer (WBS).

        Sorteringen bruker `fiq_wbs_number` slik brukeren ser treet — ikke intern id.
        """
        domene = self._firma_domene(firma_id) + [("project_id", "=", int(prosjekt_id))]
        oppgaver = self.env["project.task"].search(domene, order="fiq_wbs_number, sequence, id")

        rader = []
        for t in oppgaver:
            sjekklister = t.fiq_sjekkliste_ids
            rader.append({
                "id": t.id,
                "navn": t.display_name,
                # Oppgavenummer (code) er STABILT; WBS er dynamisk. Aldri bland dem.
                "oppgavenr": t.code or "",
                "wbs": t.fiq_wbs_number or "",
                "ansvarlige": ", ".join(t.user_ids.mapped("name")),
                # 🤖 uten mennesker / 👤 med — samme merking som AI KTRL-kontrakten.
                "er_ai": not bool(t.user_ids),
                "stadium": t.stage_id.display_name or "",
                "ferdig": bool(t.stage_id.fold),
                "frist": fields.Date.to_string(t.date_deadline) if t.date_deadline else False,
                "prioritet": t.priority,
                "estimerte_timer": round(t.allocated_hours or 0.0, 1),
                "antall_sjekklister": len(sjekklister),
                "sjekkliste_fremdrift": round(t.fiq_sjekkliste_fremdrift or 0.0, 1),
            })
        prosjekt = self.env["project.project"].browse(int(prosjekt_id))
        return {
            "prosjekt": {"id": prosjekt.id, "navn": prosjekt.display_name},
            "oppgaver": rader,
        }
