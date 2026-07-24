"""Tester for FIQ GUI CRM.

⚠️ HVA DENNE MODULEN ER: et tomt skall. Flaten viser «Kommer» og har ingen
   forretningslogikk. Testene kan derfor ikke teste beregninger — de tester
   det modulen FAKTISK lover: at handlingen og rettighetsgruppa lastes riktig,
   og at koblingen mellom dem holder.

   Det er ikke pynt. Nettopp denne klassen feil har felt oss to ganger:
   · en `ir.actions.client` med feil `tag` gir «under utvikling» i menyen —
     ingen feilmelding, bare en flate som ikke finnes
   · `res.groups` med `category_id` (Odoo 18) ga en gruppe som «virket», men
     var USYNLIG i Innstillinger → Brukere

🛑 `post_install` er påkrevd: `at_install` kjører midt i installasjonen, der
   registryet kun har modulens egne `depends`. Andre installerte moduler har
   NOT NULL-kolonner på de samme tabellene, og INSERT feiler.
🛑 Taggen `fiq` er påkrevd: CI kjører `--test-tags=fiq`. Uten den hoppes
   testene over, resultatet blir «0 of 0 tests», og gaten melder rødt.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq")
class TestFiqGuiCrm(TransactionCase):

    def test_klienthandling_finnes_og_peker_paa_flaten(self):
        """Handlingen må finnes OG ha riktig `tag`.

        `tag` er navnet JS-siden registrerer seg under
        (crm.js: registry.category("actions").add("fiq_gui_crm_dashboard")).
        Stemmer de ikke overens, åpner menypunktet ingenting — og Odoo sier
        ikke fra. Testen binder de to sammen så et navnebytte på én side
        fanges her og ikke av en bruker.
        """
        handling = self.env.ref("fiq_gui_crm.action_fiq_gui_crm")
        self.assertEqual(handling._name, "ir.actions.client")
        self.assertEqual(
            handling.tag, "fiq_gui_crm_dashboard",
            "tag må matche registreringen i crm.js — ellers åpner flaten ingenting.",
        )

    def test_gruppa_finnes_og_arver_intern_bruker(self):
        """Rettighetsgruppa må finnes og arve `base.group_user`.

        Uten arven ser en vanlig ansatt ikke flaten. Testen leser `implied_ids`
        framfor å stole på at XML-en ble lastet uten feil.
        """
        gruppe = self.env.ref("fiq_gui_crm.group_user")
        self.assertIn(
            self.env.ref("base.group_user"), gruppe.implied_ids,
            "Gruppa må arve base.group_user, ellers får ingen ansatt tilgang.",
        )

    def test_alle_interne_brukere_har_flaten(self):
        """Alle interne brukere skal ha flaten — det er modulens uttalte valg.

        Sikkerhets-XML-en legger `fiq_gui_crm.group_user` inn i
        `base.group_user.implied_ids`. Testen verifiserer at koblingen faktisk
        traff: en ekte bruker skal ha gruppa, ikke bare en record som finnes.
        """
        bruker = self.env["res.users"].create({
            "name": "Testbruker CRM-flate",
            "login": "test_fiq_gui_crm_bruker",
            "group_ids": [(4, self.env.ref("base.group_user").id)],
        })
        self.assertTrue(
            bruker.has_group("fiq_gui_crm.group_user"),
            "En intern bruker skal automatisk ha CRM-flatens gruppe.",
        )
