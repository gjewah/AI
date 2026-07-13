/** @odoo-module **/

// FIQ AI Kontrollrom — native OWL-flate. Oppgave-oversikt (alle AI-økter: Claude Code +
// Cowork) + øktregister + org-kart. Prosjekt-filtre: skjul fullførte/kansellerte + kun kunde.
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.gui.ai.kr.data";

export class FiqAiKontrollrom extends Component {
    static template = "fiq_gui_ai_kr.AiKr";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true, view: "oppgaver",
            skjul_ferdig: true, skjul_kansellert: true, kun_kunde: false,
            oppg: { groups: [], tot: {}, krever: [], root: "" },
            okter: [], org: { roller: [], installert: false },
        });
        onWillStart(async () => {
            await this.lastOppgaver();
            this.state.loading = false;
        });
    }

    async lastOppgaver() {
        this.state.oppg = await this.orm.call(DATA, "get_ai_oppgaver", [], {
            skjul_ferdig: this.state.skjul_ferdig,
            skjul_kansellert: this.state.skjul_kansellert,
            kun_kunde: this.state.kun_kunde,
        });
    }

    async settFane(v) {
        this.state.view = v;
        if (v === "okter" && !this.state.okter.length) {
            this.state.okter = await this.orm.call(DATA, "get_okter", []);
        }
        if (v === "org" && !this.state.org.roller.length) {
            this.state.org = await this.orm.call(DATA, "get_org", []);
        }
    }

    async veksle(felt) {
        this.state[felt] = !this.state[felt];
        await this.lastOppgaver();
    }

    aapne(t) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "project.task",
            res_id: t.id, views: [[false, "form"]], target: "current",
        });
    }

    tilbakeKR() { this.action.doAction("fiq_gui_control.action_fiq_gui_control"); }
}

registry.category("actions").add("fiq_ai_kr_dashboard", FiqAiKontrollrom);
