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
// Farge #D80000 = 6 SALG i det kanoniske fargekartet (brand/fiq_fargekart_omrader.md).
//
// 🛑 NØKKELEN ER «salg» — OG DEN MÅ MATCHE DATAMODELLEN.
//
// Kontrollrommet bygger BÅDE rom-boksen OG datamodell-navnet fra nøkkelen
// (fiq_gui_control_config.py:1653):
//     model_name = "fiq.gui.%s.data" % flate["key"]
// Datamodellen vår heter fiq.gui.SALG.data (fiq_gui_salg_data.py:38). Nøkkelen
// og modellen må være samme ord, ellers finner get_kr_bokser ingen get_kr_boks
// → ingen rom-boks for Salg.
//
// Jeg bommet 23.07: byttet «salg» → «crm_leads» for å treffe NOKKEL_ALIAS
// (gui_leads → crm_leads). Men aliaset gjelder den GAMLE handlingsveien
// (get_actions), IKKE rom-boksene — de leser nøkkelen direkte. Med «crm_leads»
// ville kjernen lett etter fiq.gui.crm_leads.data, som ikke finnes.
// KR (01.03) målte det i koden og bekreftet: «salg» er kanonisk, ingen bro.
//
// 🔑 Lærdom: et navn kan matche ETT oppslag (aliaset) og bryte et ANNET
// (datamodellen). Jeg rettet symptomet jeg så og skapte ett jeg ikke så.
// «salg» er unik i registeret — to moduler med samme nøkkel gir
// DuplicatedKeyError og blank skjerm; ingen server-test fanger den.
registry.category("fiq_gui_flates").add("salg", {
    key: "salg",
    label: "Sales",
    color: "#D80000",
    sequence: 40,
    Component: FiqGuiCrmLeads,
});
