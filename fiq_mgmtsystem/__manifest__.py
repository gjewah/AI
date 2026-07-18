# -*- coding: utf-8 -*-
{
    "name": "FIQ Styringssystem — ISO 9001 (krav/kontroll/sjekkliste/avvik)",
    "version": "19.0.1.0.1",
    "summary": "ISO-styringssystem: krav (klausuler), kontroller, sjekklister og avvik "
               "med taksonomi-kobling (code.list / documents.tag, feature-detektert). "
               "Multi-selskap, tenant-isolert, config-drevet — generisk for alle FIQ-kunder.",
    "description": """
FIQ Styringssystem — ISO 9001
===============================
Add-only styringssystem-modul forankret i ISO 9001 (dokumentert informasjon §7.5),
utvidbar til ISO 14001/14064/14067 (miljø/bærekraft) og ISO 27001 (informasjonssikkerhet).

Modeller:
 * fiq.mgmtsystem.krav          — krav/klausul (standard + klausulnummer + taksonomi-kode)
 * fiq.mgmtsystem.kontroll      — kontroll som dekker ett eller flere krav (frekvens/ansvarlig)
 * fiq.mgmtsystem.sjekkliste    — sjekkliste (mal eller instans) knyttet til krav
 * fiq.mgmtsystem.sjekkliste.punkt — sjekklistepunkt (utført, ansvarlig, oppgave-referanse/URL)
 * fiq.mgmtsystem.avvik         — avvik (rotårsak, tiltak, alvorlighet, status) med sporing (mail.thread)

Taksonomi-kobling:
 Hvert krav bærer en taksonomi-KODE (code.list.item.code, f.eks. «2.40.01») + valgfritt
 dokumentetikett-navn. Modulen slår opp code.list.item / documents.tag ved KJØRETID
 (feature-detektert via env-registry) — så modulen er installerbar uten hard-avhengighet
 til Documents (Enterprise) eller base_code_list. Se referanse_metadata_iso9001.md.

Multi-selskap:
 Hver modell har company_id (default env.company) + globale record rules per firma
 (['|',('company_id','=',False),('company_id','in',company_ids)]). Tenant-isolert,
 generisk for ALLE FIQ AS-kunder — aldri kunde-fork.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/fiq_mgmtsystem_rules.xml",
        "views/fiq_mgmtsystem_krav_views.xml",
        "views/fiq_mgmtsystem_kontroll_views.xml",
        "views/fiq_mgmtsystem_sjekkliste_views.xml",
        "views/fiq_mgmtsystem_avvik_views.xml",
        "views/fiq_mgmtsystem_menus.xml",
    ],
    "application": False,
    "installable": True,
}
