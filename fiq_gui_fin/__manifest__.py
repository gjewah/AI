{
    "name": "FIQ Finans",
    "version": "19.0.1.8.2",
    "summary": "AI GUI Finans (2.70) — visningen av AI Finans-Rådgiveren: analyse, "
    "framskrivning, simulator (fortid/nåtid/fremtid), KPI og POG.",
    "description": """
FIQ GUI Finans — flate 2.70
=============================
Flaten er VISNINGEN av rolla «0.00 2.70 AI Finans-Rådgiver» (rolle bak, flate foran).
Ingen parallell logikk: KPI/rapporter gjenbrukes fra Odoo (native-først).

Innhold (UTKAST 01 — rammeverk, ikke ferdig funksjonalitet):
 * Analyse + framskrivning — hvordan går firmaet (styrker/svakheter/forbedring)
 * Simulator i tre tidsakser: 01 Fortid · 02 Nåtid · 03 Fremtid (3/6/12 mnd, A/B-scenario)
 * KPI-rapporter — brukeren velger hvilke (config-drevet)
 * POG-dashbord + URL (fase 7, etter POG-implementering)

Harde regler innebygd i flaten:
 * FAKTA (bokført) skilles SKARPT fra SCENARIO — et scenario presenteres aldri som regnskapstall.
 * Rådgiver, ikke beslutter — ingen automatiske finansielle handlinger.
 * «Hva gjør andre» = bransje-/markedsdata, ALDRI en annen FIQ-kundes tall (tenant-isolasjon).
 * Lønn = egen gate (lønningsansvarlig ≠ regnskap; sensitiv PII).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    # 🛑 `account_reports` (Enterprise) står BEVISST IKKE her, selv om KPI-velgeren
    # peker på åtte av dens rapporter. Beslutning 24.07 etter AI IQs gate-kjøring:
    #   · Kredittrisiko-delen (samleboks, faresignaler) bruker kun `account.move`
    #     og virker uten Enterprise. Det er kjernen i 2.70-flaten.
    #   · KPI-velgeren er et TILLEGG. `hent_kpi_valg()` hopper over rapporter som
    #     ikke finnes, så flaten viser færre kort i stedet for å krasje.
    #   · Legges `account_reports` i depends, kan modulen IKKE installeres på en
    #     Community-base i det hele tatt — hele flaten faller for et tillegg.
    # `depends` beskytter installasjon, koden beskytter kjøretid. Ulike problemer.
    "depends": ["fiq_gui_control", "fiq_gui_shell", "web", "account"],
    "data": [
        "security/fiq_gui_fin_groups.xml",
        "views/fiq_gui_fin_action.xml",
        # Selvregistrering i KR-menyen — MÅ lastes ETTER action-fila (viser til den).
        "data/fiq_gui_fin_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_fin/static/src/fin.scss",
            "fiq_gui_fin/static/src/fin.js",
            "fiq_gui_fin/static/src/fin.xml",
        ],
    },
    "application": True,
    "installable": True,
}
