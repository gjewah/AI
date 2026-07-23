# -*- coding: utf-8 -*-
{
    "name": "FIQ Lønn Norge",
    "version": "19.0.1.1.0",
    "summary": "Norsk lønnslokalisering (2.20) — lønnsarter, satser og AA-register. "
               "Regnskapsfunksjon som LESER HR-data.",
    "description": """
FIQ Lønn Norge — norsk lønnslokalisering
========================================
Norsk lønn finnes IKKE i Odoo: 26 land har payroll-lokalisering, Norge er ikke ett av dem,
og hele Norden mangler. `l10n_no*` dekker kun regnskap og SAF-T. OCA/l10n-norway er tom.
Denne modulen fyller det hullet — bygget PÅ Enterprise `hr_payroll`, ikke ved siden av.

To spor side om side (Gjermund 22.07.2026):
 * Kunder med POG/Tripletex-integrasjon: DE kjører lønn der. Modulen er ikke for dem.
 * Kunder på FIQ-plattformen: denne modulen fører lønnen i Odoo.

Innhold (UTKAST — rammeverk, ingen lønnsarter lagt inn ennå):
 * Lønnsarter og regelkategorier for norsk lønn
 * Satser med datoversjonering (`hr.rule.parameter`) — endres hvert statsbudsjett
 * Arbeidsgiveravgift med sonesats (varierer per kommune)
 * Feriepenger etter ferieloven (10,2 % / 12 % — avhenger av alder og avtale)
 * AA-registeret — arbeidsforhold: start, slutt, stillingsprosent, permisjon
 * Aggregater til cashflow (2.80 RGS) — KUN summer, aldri individdata

Harde regler innebygd:
 * ALDRI gjett — lønn er juridisk bindende mot Skatteetaten. Feil i trekk eller avgift er
   ikke en programfeil man retter neste sprint; det er avviksmelding med frist og gebyr.
 * Personvern-veggen er en TILGANGSGRENSE, ikke lenger en systemgrense: ansattdata ligger
   i samme base som regnskapet. Håndheves av rettigheter — svakere enn avstand, derfor
   bygget inn fra dag én.
 * Til 2.80/2.70 leveres KUN summer. Aldri en linje som representerer færre enn 3 ansatte
   (én ansatt er re-identifiserbar selv uten navn).
 * Innsending til Altinn/Skatteetaten = MENNESKE. Modulen sender aldri selv.

Tilgang (Gjermund 23.07.2026): 2.20 HRi · lønningsansvarlig · daglig leder — alle LESING.
Modulen er en regnskapsfunksjon som leser HR-data; den flytter ikke lønn ut av HR.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Human Resources/Payroll",
    "license": "OPL-1",
    # hr_payroll = Enterprise-motoren (12 230 linjer) vi bygger PÅ, ikke ved siden av.
    # Gjermunds valg 23.07: en lokalisering er ~1 000 linjer og overveiende DATA —
    # fritt-fra-bunnen ville krevd motoren først, og desember 2026 ville falt.
    # OPL-1 forutsetter uansett Enterprise, så de to valgene peker samme vei.
    # MERK: hr_contract er IKKE en egen modul i Odoo 19 — den er slått sammen
    # inn i `hr` (verifisert på Dev 35275074, ikke antatt fra Odoo 18-kunnskap).
    # Kontrakter ligger på hr.employee/hr.version. Jf. kanon_ingen_odoo18_kode.
    "depends": ["hr_payroll", "fiq_tilgang"],
    "data": [
        "security/fiq_rgs_lonn_groups.xml",
        "security/ir.model.access.csv",
        # Satser med gyldighetsdato. Kilde: Stortingsvedtak FOR-2025-12-18-2748 § 3.
        # Ved nytt statsbudsjett legges ÉN ny record til her — historikken består.
        "data/hr_rule_parameters_data.xml",
        # Lønnsartene MÅ lastes ETTER parameterne — reglene slår opp satser.
        "data/hr_salary_rule_data.xml",
        "views/fiq_rgs_lonn_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
