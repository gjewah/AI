/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// FIQ GUI Salg — flate 6 SALG. VISNINGEN av rolla «0.00 6 AI Salg-Rådgiver».
// Rolle bak, flate foran: ingen salgslogikk bygges her som Odoo alt eier
// (native-først). Tallene leses fra crm.lead gjennom fiq.gui.salg.data.
//
// UTKAST 01 = pipeline-oversikten. Livsløps-drillen (forespørsel → kontakt →
// befaring → tilbud → beslutning → prosjekt) kommer som egen versjon; den
// krever befarings- og tilbudsdelene som ennå ikke er koblet.
export class FiqGuiCrmLeads extends Component {
    static template = "fiq_gui_crm_leads.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ stadier: [], laster: true });

        onWillStart(async () => {
            // Firma kommer fra skallet (sloten sender {firm, har000, label}).
            // Flaten eier ALDRI firma-valget selv — serveren avgjør hva
            // brukeren får se, uansett hva klienten sender.
            const firma = this.props.firm || false;
            this.state.stadier = await this.orm.call(
                "fiq.gui.salg.data", "get_pipeline", [], { company_id: firma },
            );
            this.state.laster = false;
        });
    }

    // Åpen pipeline = kun AKTIVE stadier. Vunnet og tapt holdes utenfor.
    //
    // 🛑 Det holder ikke å filtrere på `vunnet`: tapte saker er ikke
    //    nødvendigvis arkivert (fiqas har 25 aktive i «9.99 Tapt»), og Odoo
    //    har ingen `is_lost` på stadiet. Serveren avgjør hva som er avsluttet
    //    og sender `avsluttet` — flaten gjentar ikke den vurderingen selv.
    get aktiveStadier() {
        return this.state.stadier.filter((s) => !s.avsluttet);
    }

    get apneAntall() {
        return this.aktiveStadier.reduce((sum, s) => sum + s.antall, 0);
    }

    get apenVerdi() {
        return this.aktiveStadier.reduce((sum, s) => sum + s.verdi, 0);
    }

    // Beløp uten desimaler: en pipeline leses i størrelsesorden, ikke i kroner
    // og øre. Locale fra nettleseren, så tusenskillet blir riktig per språk.
    formatKr(verdi) {
        return Math.round(verdi || 0).toLocaleString();
    }

    // Bredden på stolpen. Relativ til største AKTIVE stadium — ikke til
    // totalen, og ikke til vunnet/tapt. På fiqas ligger 25 saker i «Tapt»
    // mot 1–2 i de aktive: målte vi mot dem, ble hele den levende pipelinen
    // en tynn strek, og flaten ville sett tom ut mens det faktisk var arbeid.
    stolpeBredde(stadium) {
        const storst = Math.max(...this.aktiveStadier.map((s) => s.antall), 1);
        return `${Math.round((stadium.antall / storst) * 100)}%`;
    }

    // Klikk på et stadium åpner Odoos egen liste, filtrert på det stadiet.
    // Native-først: vi bygger ikke vår egen redigering av noe Odoo alt gjør.
    apneStadium(stadium) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead",
            name: stadium.navn,
            views: [[false, "list"], [false, "form"]],
            domain: [["stage_id", "=", stadium.id], ["type", "=", "opportunity"]],
        });
    }
}

registry.category("actions").add("fiq_gui_crm_leads_dashboard", FiqGuiCrmLeads);

// Registrering i det delte skallet, slik at flaten åpner INNI Kontrollrommet
// (sloten, KR v6.95) og rammen står. Kontrakt: shell.js + fiq_gui_fin/fin.js.
// Nøkkelen «salg» er unik — to moduler med samme nøkkel gir DuplicatedKeyError
// og blank skjerm for hele grensesnittet, og ingen server-test fanger den.
// Farge #D80000 = 6 SALG i det kanoniske fargekartet (brand/fiq_fargekart_omrader.md).
// 🛑 NØKKELEN MÅ VÆRE «crm_leads» — IKKE «salg».
//
// Kontrollrommet slår opp flaten via NOKKEL_ALIAS (control_room.js): menyens nøkkel
// «gui_leads» oversettes til «crm_leads». Jeg registrerte «salg» fordi det er navnet
// på området (6 SALG). Da fant oppslaget INGENTING, og KR falt tilbake på doAction —
// som bytter HELE siden. Resultatet: salgsflaten åpnet UTENFOR rammen, uten
// venstremeny, firmavelger eller vei tilbake. Gjermund 23.07: «bortsett fra salg har
// de klart å innarbeide KR shell.» Fire av fem flater sto riktig; denne var den siste.
//
// 🔑 Feilen ga INGEN feilmelding. Oppslaget returnerer null, fallback overtar, og alt
// «virker» — bare i feil ramme. Samme klasse som resten av uka: ingen krasj, bare et
// stille galt svar. Et navn som betyr noe for mennesker er ikke nødvendigvis nøkkelen
// maskinen leter etter.
registry.category("fiq_gui_flates").add("crm_leads", {
    key: "crm_leads",
    label: "Sales",
    color: "#D80000",
    sequence: 40,
    Component: FiqGuiCrmLeads,
});
