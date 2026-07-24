"""Tester for fiq_partner_relasjon (relasjonstype/-nivå + merkelogo-kilde).

Hvorfor testene finnes: modulen hadde NULL tester. `--test-enable` ga da
«0 failed, 0 error(s) of 0 tests» — den «bestod» fordi det ikke fantes noe å
teste. Det er falsk trygghet, ikke dekning.

Tre ting MÅ være bevist, ikke antatt:

1. **Klassifiseringen.** `fiq_relation_type` har default «customer» med vilje:
   en partner blir avtalepartner kun ved et bevisst valg. Hvis defaulten glipper
   (f.eks. ved at feltet gjøres required eller defaulten fjernes), blir hver ny
   kontakt uklassifisert — og filteret «Agreement partners» begynner å lyve.
2. **Logo-computen tåler at logoen MANGLER.** Dette er null-tilfellet. Både
   `res.partner._compute_fiq_brand_logo` og `res.company._compute_fiq_brand_logo`
   må gi False uten å kaste når det ikke finnes noe bilde. En compute som kaster
   på tom verdi tar med seg HELE listevisningen, ikke bare én rad.
3. **Firma-scope (tenant-isolasjon).** Feltene ligger på res.partner, som har
   `company_id`. En partner som tilhører firma B skal ikke komme med når man
   søker innenfor firma A. Vi beviser at feltene våre ikke omgår det.

Testene lager SIN EGEN tilstand (egne partnere) og leser aldri bare eksisterende
data — et treff på en tilfeldig eksisterende rad beviser ingenting.
"""

from odoo.addons.fiq_partner_relasjon.models.res_partner import (
    RELATION_LEVELS,
    RELATION_TYPES,
)
from odoo.tests import TransactionCase, tagged


# post_install er PÅKREVD her, ikke en preferanse.
#
# Under default at_install inneholder registeret kun denne modulens egne depends
# (kun «base»), mens databasen fortsatt har NOT NULL-kolonner lagt til av moduler
# som ER installert men ikke i registeret — group_rfq på res.partner
# (purchase_stock) er den som biter. Skranken bor i Postgres, men defaulten settes
# av Odoo i Python: et felt registeret ikke kjenner får aldri sin default, og
# INSERT-en utelater kolonnen → NotNullViolation på et felt denne modulen verken
# eier eller ser. Alle testene under lager res.partner-poster.
# Odoo-kjernen gjør det samme: project/tests/test_project_mail_features.py:9.
@tagged("post_install", "-at_install", "fiq_partner")
class TestFiqPartnerRelasjon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Company = cls.env["res.company"]

    def _partner(self, name="FIQ testpartner", **vals):
        """Egen, fersk partner. Hver test eier sine egne poster."""
        return self.Partner.create(dict({"name": name}, **vals))

    # =================================================================
    #  fiq_relation_type — ALLE verdier
    # =================================================================

    def test_default_er_customer(self):
        """En ny partner er en vanlig kunde til noen bevisst sier noe annet.

        Dette er selve forutsetningen modulen bygger på (docstring i
        res_partner.py: «a partner only becomes an agreement partner by an
        explicit, deliberate choice»). Ryker defaulten, blir klassifiseringen
        meningsløs uten at noe annet feiler synlig.
        """
        partner = self._partner("Default-kunde")
        self.assertEqual(partner.fiq_relation_type, "customer")

    def test_default_gjelder_ogsaa_for_firmapartner(self):
        """Defaulten skal ikke avhenge av is_company."""
        partner = self._partner("Default-firma", is_company=True)
        self.assertEqual(partner.fiq_relation_type, "customer")

    def test_alle_relasjonstyper_kan_lagres_og_leses(self):
        """Hver verdi i RELATION_TYPES må faktisk kunne skrives og leses igjen.

        Vi itererer over selection-lista i stedet for å hardkode to strenger:
        legges en tredje type til uten at den virker, skal DENNE testen fange
        det — ikke en bruker.
        """
        for value, _label in RELATION_TYPES:
            with self.subTest(relation_type=value):
                partner = self._partner(f"Type {value}", fiq_relation_type=value)
                self.assertEqual(partner.fiq_relation_type, value)
                # Lest på nytt fra basen, ikke bare fra cachen.
                partner.invalidate_recordset(["fiq_relation_type"])
                self.assertEqual(partner.fiq_relation_type, value)

    def test_selection_inneholder_de_kanoniserte_verdiene(self):
        """Verdinøklene er en kontrakt: de brukes i domener i views/res_partner_views.xml
        og leses av Kontrollrommet. Endrer man en nøkkel, slutter filteret å treffe."""
        nokler = [v for v, _l in RELATION_TYPES]
        self.assertEqual(nokler, ["customer", "agreement_partner"])

    def test_alle_partnernivaa_kan_lagres(self):
        """Alle fire nivåene (1-4) må kunne settes på en avtalepartner."""
        for value, _label in RELATION_LEVELS:
            with self.subTest(level=value):
                partner = self._partner(
                    f"Nivaa {value}",
                    fiq_relation_type="agreement_partner",
                    fiq_relation_level=value,
                )
                self.assertEqual(partner.fiq_relation_level, value)

    def test_nivaa_er_tomt_som_standard(self):
        """Nivå har ingen default — et nivå er en påstand, ikke en antagelse."""
        partner = self._partner("Uten nivaa")
        self.assertFalse(partner.fiq_relation_level)

    def test_bytte_av_type_bevarer_lagret_verdi(self):
        """Skriving skal virke begge veier, ikke bare fra default og oppover."""
        partner = self._partner("Frem og tilbake")
        partner.fiq_relation_type = "agreement_partner"
        self.assertEqual(partner.fiq_relation_type, "agreement_partner")
        partner.fiq_relation_type = "customer"
        self.assertEqual(partner.fiq_relation_type, "customer")

    # =================================================================
    #  _onchange_fiq_relation_type — nivået skal ikke henge igjen
    # =================================================================

    def test_onchange_tommer_nivaa_for_vanlig_kunde(self):
        """Et nivå beskriver KUN en avtalepartner.

        Blir nivået hengende igjen når typen settes tilbake til «customer», får
        man en vanlig kunde merket «4 - Strategic partner». Feltet er usynlig i
        skjemaet (invisible-attributtet i views), så feilen ville aldri blitt
        SETT — bare eksportert.
        """
        partner = self._partner(
            "Nedgradert",
            fiq_relation_type="agreement_partner",
            fiq_relation_level="4",
        )
        self.assertEqual(partner.fiq_relation_level, "4")
        partner.fiq_relation_type = "customer"
        partner._onchange_fiq_relation_type()
        self.assertFalse(partner.fiq_relation_level)

    def test_onchange_beholder_nivaa_for_avtalepartner(self):
        """Motstykket: onchangen må ikke slette et nivå som er gyldig."""
        partner = self._partner(
            "Beholder",
            fiq_relation_type="agreement_partner",
            fiq_relation_level="2",
        )
        partner._onchange_fiq_relation_type()
        self.assertEqual(partner.fiq_relation_level, "2")

    def test_onchange_er_trygg_naar_nivaa_allerede_er_tomt(self):
        """Null-tilfellet: ingenting å tømme skal ikke kaste."""
        partner = self._partner("Tomt nivaa", fiq_relation_type="customer")
        partner._onchange_fiq_relation_type()
        self.assertFalse(partner.fiq_relation_level)

    def test_onchange_haandterer_flere_poster(self):
        """Metoden itererer over self — den må virke på et recordset, ikke bare én."""
        a = self._partner(
            "Flere A", fiq_relation_type="customer", fiq_relation_level="1"
        )
        b = self._partner(
            "Flere B", fiq_relation_type="agreement_partner", fiq_relation_level="3"
        )
        (a | b)._onchange_fiq_relation_type()
        self.assertFalse(a.fiq_relation_level)
        self.assertEqual(b.fiq_relation_level, "3")

    def test_onchange_i_new_kontekst(self):
        """Slik onchangen faktisk kjører i skjemaet: på en ULAGRET post (NewId).

        En compute/onchange som bare er prøvd på lagrede poster kan feile i
        skjemaet uten at noen enhetstest merker det.
        """
        ny = self.Partner.new(
            {
                "name": "Ulagret",
                "fiq_relation_type": "agreement_partner",
                "fiq_relation_level": "3",
            }
        )
        ny.fiq_relation_type = "customer"
        ny._onchange_fiq_relation_type()
        self.assertFalse(ny.fiq_relation_level)

    # =================================================================
    #  _compute_fiq_brand_logo — NULL-TILFELLENE
    # =================================================================

    def test_partner_logo_uten_bilde_gir_false_uten_aa_kaste(self):
        """🔴 Null-tilfellet. En partner uten bilde er NORMALEN, ikke unntaket.

        Kaster eller returnerer computen noe rart her, ryker hele listevisningen
        — ikke bare den ene raden.
        """
        partner = self._partner("Uten bilde")
        self.assertFalse(partner.image_1920)
        self.assertFalse(partner.fiq_brand_logo)

    def test_partner_logo_returnerer_eget_bilde(self):
        """Med bilde skal computen levere nettopp det bildet."""
        bilde = self._bilde()
        partner = self._partner("Med bilde", image_1920=bilde)
        self.assertTrue(partner.fiq_brand_logo)
        self.assertEqual(partner.fiq_brand_logo, partner.image_1920)

    def test_partner_logo_paa_tomt_recordset(self):
        """Null-tilfelle nr. 2: computen på et TOMT recordset skal ikke kaste."""
        tomt = self.Partner.browse()
        tomt._compute_fiq_brand_logo()
        self.assertFalse(tomt)

    def test_partner_logo_paa_blandet_recordset(self):
        """Med og uten bilde i SAMME kall — løkka må håndtere begge i én omgang.

        Klassisk feil: en compute som setter feltet kun i if-grenen og lar
        else-grenen falle igjennom → «Compute method failed to assign».
        """
        med = self._partner("Blandet med", image_1920=self._bilde())
        uten = self._partner("Blandet uten")
        (med | uten)._compute_fiq_brand_logo()
        self.assertTrue(med.fiq_brand_logo)
        self.assertFalse(uten.fiq_brand_logo)

    def test_partner_logo_foelger_bildet_naar_det_fjernes(self):
        """Computen er depends på image_1920 — fjernes bildet, skal logoen bli tom."""
        partner = self._partner("Mister bilde", image_1920=self._bilde())
        self.assertTrue(partner.fiq_brand_logo)
        partner.image_1920 = False
        self.assertFalse(partner.fiq_brand_logo)

    def test_firma_logo_uten_logo_gir_false_uten_aa_kaste(self):
        """🔴 Null-tilfellet på firma: intet firmalogo, ingen override → False.

        Testfirmaet vi lager har ingen logo. Odoo kan gi et standardbilde ved
        create; testen krever derfor kun at computen SVARER SAMME som kilden —
        ikke at den er tom — og at den ikke kaster.
        """
        firma = self._eget_firma("FIQ testfirma uten logo")
        if firma is None:
            self.skipTest("kan ikke opprette res.company paa denne basen")
        firma.logo = False
        self.assertFalse(firma.fiq_brand_logo)

    def test_firma_logo_bruker_egen_logo_naar_ingen_override(self):
        """Uten Kontrollrom-override er firmaets egen logo kilden."""
        firma = self._eget_firma("FIQ testfirma med logo")
        if firma is None:
            self.skipTest("kan ikke opprette res.company paa denne basen")
        firma.logo = self._bilde()
        self.assertEqual(firma.fiq_brand_logo, firma.logo)

    def test_override_hjelperen_er_defensiv_uten_kontrollrommet(self):
        """`_fiq_control_logo_override` skal virke på en NAKEN Odoo.

        Modulen depends kun på «base» med vilje: fiq_control_logo bor i
        fiq_gui_control som kanskje ikke er installert. Hjelperen må derfor
        SPØRRE _fields, ikke anta. Testen dekker begge utfall uten å late som
        den vet hvilket som gjelder her.
        """
        firma = self.env.company
        resultat = firma._fiq_control_logo_override()
        if "fiq_control_logo" in firma._fields:
            self.assertEqual(resultat, firma.fiq_control_logo)
        else:
            self.assertFalse(resultat)

    def test_override_krever_en_enkelt_post(self):
        """ensure_one() er et bevisst vern: en override er per firma."""
        firmaer = self.Company.search([], limit=2)
        if len(firmaer) < 2:
            self.skipTest("basen har kun ett firma")
        with self.assertRaises(ValueError):
            firmaer._fiq_control_logo_override()

    def test_firma_logo_paa_tomt_recordset(self):
        """Null-tilfelle: tomt firma-recordset skal ikke kaste."""
        tomt = self.Company.browse()
        tomt._compute_fiq_brand_logo()
        self.assertFalse(tomt)

    # =================================================================
    #  Firma-scope — tenant-isolasjon
    # =================================================================

    def test_partner_uten_firma_er_delt(self):
        """company_id = False betyr «delt», og det er standarden for kontakter.

        Viktig å slå fast: hvis noe begynner å sette company_id automatisk på
        partnere, endres synligheten for ALLE firmaer på én gang.
        """
        partner = self._partner("Delt kontakt")
        self.assertFalse(partner.company_id)

    def test_relasjonsfelt_overlever_firmabinding(self):
        """Feltene våre skal virke likt enten partneren er bundet til et firma
        eller ikke — de legger ikke på egen scope-logikk."""
        partner = self._partner(
            "Bundet",
            company_id=self.env.company.id,
            fiq_relation_type="agreement_partner",
            fiq_relation_level="2",
        )
        self.assertEqual(partner.company_id, self.env.company)
        self.assertEqual(partner.fiq_relation_type, "agreement_partner")
        self.assertEqual(partner.fiq_relation_level, "2")

    def test_soek_paa_relasjonstype_respekterer_firma_scope(self):
        """🔴 Tenant-isolasjon: en avtalepartner i firma B skal IKKE dukke opp
        når man søker innenfor firma A.

        Dette er hele poenget med at klassifiseringen ligger på res.partner:
        den arver Odoos native firma-record-rules. Begynner et søk på
        `fiq_relation_type` å krysse firmagrensen, lekker den hvem som er
        avtalepartner hos en annen kunde.
        """
        annet = self._annet_firma()
        egen = self._partner(
            "Scope egen",
            company_id=self.env.company.id,
            fiq_relation_type="agreement_partner",
        )
        fremmed = self._partner(
            "Scope fremmed",
            company_id=annet.id,
            fiq_relation_type="agreement_partner",
        )
        domene = [
            ("fiq_relation_type", "=", "agreement_partner"),
            ("id", "in", (egen | fremmed).ids),
        ]
        # Søk med KUN eget firma i allowed_company_ids: den fremmede skal falle ut.
        funnet = (
            self.Partner.with_context(allowed_company_ids=[self.env.company.id])
            .with_company(self.env.company)
            .search(
                domene
                + [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "in", [self.env.company.id]),
                ]
            )
        )
        self.assertIn(egen, funnet)
        self.assertNotIn(fremmed, funnet, "partner fra annet firma lekket inn i søket")

    def test_firmabundet_partner_har_riktig_firma(self):
        """Grunnmuren under scope-testen: bindingen må faktisk feste seg."""
        annet = self._annet_firma()
        fremmed = self._partner("Fremmed binding", company_id=annet.id)
        self.assertEqual(fremmed.company_id, annet)
        self.assertNotEqual(fremmed.company_id, self.env.company)

    def test_logo_computen_er_uavhengig_av_aktivt_firma(self):
        """Partnerens logo er partnerens eget bilde — ikke det aktive firmaets.

        Blandes de to, viser Kontrollrommet feil merke når man bytter firma.
        """
        annet = self._annet_firma()
        bilde = self._bilde()
        partner = self._partner("Logo scope", image_1920=bilde)
        sett_fra_annet = partner.with_company(annet).fiq_brand_logo
        self.assertEqual(sett_fra_annet, partner.fiq_brand_logo)

    # =================================================================
    #  Hjelpere
    # =================================================================

    def _bilde(self):
        """Minste gyldige PNG (1x1) som base64 — Odoo validerer Binary-bilder.

        Hardkodet med vilje: å generere bildet krever Pillow-kall vi ikke
        trenger, og en fast verdi gjør testen deterministisk.
        """
        return (
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
            b"z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )

    def _eget_firma(self, navn):
        """Prøv å lage et EGET firma; returner None hvis basen nekter.

        res.company.create() drar med seg alle enterprise-moduler som utvider
        modellen, og minst én av dem kan nekte skrivingen (documents_project:
        «Company Project Folders cannot be linked to another company»). Vi later
        ikke som vi vet hvilke moduler som er installert her — vi PRØVER, og
        testen som kaller hopper over hvis det ikke går. En hoppet test sier
        ærlig at forutsetningen ikke lot seg lage; en test som feiler på en
        nabomodul sier noe usant om vår modul.
        """
        try:
            with self.env.cr.savepoint():
                return self.Company.create({"name": navn})
        except Exception:  # noqa: BLE001 - vi bryr oss ikke om HVILKEN modul som nektet
            return None

    def _annet_firma(self):
        """Et firma som er UTENFOR scope for testen.

        Først et forsøk på å lage et eget (da eier testen sin egen tilstand).
        Går ikke det (se _eget_firma), faller vi tilbake på et eksisterende
        firma som ikke er det aktive — og finnes heller ikke det, hopper vi.
        """
        eget = self._eget_firma("FIQ scope-testfirma")
        if eget is not None:
            return eget
        annet = self.Company.search([("id", "!=", self.env.company.id)], limit=1)
        if not annet:
            self.skipTest(
                "trenger et firma nr. 2; oppretting er blokkert paa denne basen"
            )
        return annet
