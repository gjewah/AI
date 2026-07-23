# -*- coding: utf-8 -*-
"""Tester for FIQ GUI Salgsordre.

⚠️ HVA DENNE MODULEN ER: et tomt skall. Flaten viser «Kommer» og har ingen
   forretningslogikk ennå. Testene tester derfor det modulen FAKTISK lover:
   at handlingen og rettighetsgruppa lastes riktig, og at koblingen holder.

   Det er ikke pynt. Denne klassen feil har felt oss to ganger:
   · en `ir.actions.client` med feil `tag` gir «under utvikling» i menyen —
     ingen feilmelding, bare en flate som ikke finnes
   · `res.groups` med `category_id` (Odoo 18) ga en gruppe som «virket», men
     var USYNLIG i Innstillinger → Brukere

📌 Når salgsordre-innmaten bygges (oppgave «15 Antall leads + salgsordrer»),
   skal testene her utvides med ekte tall-tester som OPPRETTER sine egne
   salgsordrer — ikke leser basens. En test som bare leser eksisterende data
   beviser ingenting.

🛑 `post_install` er påkrevd: `at_install` kjører midt i installasjonen, der
   registryet kun har modulens egne `depends`. Andre installerte moduler har
   NOT NULL-kolonner på de samme tabellene, og INSERT feiler.
🛑 Taggen `fiq` er påkrevd: CI kjører `--test-tags=fiq`. Uten den hoppes
   testene over, resultatet blir «0 of 0 tests», og gaten melder rødt.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq")
class TestFiqGuiCrmSo(TransactionCase):

    def test_klienthandling_finnes_og_peker_paa_flaten(self):
        """Handlingen må finnes OG ha riktig `tag`.

        `tag` er navnet JS-siden registrerer seg under (crm_so.js:16:
        registry.category("actions").add("fiq_gui_crm_so_dashboard")).
        Stemmer de ikke overens, åpner menypunktet ingenting — og Odoo sier
        ikke fra.
        """
        handling = self.env.ref("fiq_gui_crm_so.action_fiq_gui_crm_so")
        self.assertEqual(handling._name, "ir.actions.client")
        self.assertEqual(
            handling.tag, "fiq_gui_crm_so_dashboard",
            "tag må matche registreringen i crm_so.js — ellers åpner flaten ingenting.",
        )

    def test_gruppa_finnes_og_arver_intern_bruker(self):
        """Rettighetsgruppa må finnes og arve `base.group_user`."""
        gruppe = self.env.ref("fiq_gui_crm_so.group_user")
        self.assertIn(
            self.env.ref("base.group_user"), gruppe.implied_ids,
            "Gruppa må arve base.group_user, ellers får ingen ansatt tilgang.",
        )

    def test_alle_interne_brukere_har_flaten(self):
        """Alle interne brukere skal ha flaten — modulens uttalte valg.

        Testen oppretter en ekte bruker framfor å lese en record: poenget er
        at koblingen faktisk TREFFER, ikke at XML-en ble lastet.
        """
        bruker = self.env["res.users"].create({
            "name": "Testbruker Salgsordre-flate",
            "login": "test_fiq_gui_crm_so_bruker",
            "group_ids": [(4, self.env.ref("base.group_user").id)],
        })
        self.assertTrue(
            bruker.has_group("fiq_gui_crm_so.group_user"),
            "En intern bruker skal automatisk ha salgsordre-flatens gruppe.",
        )

    def test_modulen_avhenger_av_sale(self):
        """Salgsordre-flaten må ha `sale` installert for å kunne lese ordrer.

        Skallet er tomt i dag, men avhengigheten er hele forutsetningen for
        innmaten som kommer. Er den borte, feiler flaten først når noen prøver
        å hente tall — altså langt fra der feilen ble laget.
        """
        modul = self.env["ir.module.module"].search(
            [("name", "=", "sale")], limit=1,
        )
        self.assertEqual(
            modul.state, "installed",
            "fiq_gui_crm_so depends på sale — den må være installert.",
        )
