/** @odoo-module **/

// Kommunikasjon — paraply-flaten (V01, 17.07.2026).
// Gjermund: «Meldingssenteret og Kommunikasjonssenteret — det er det samme.»
// ETT navn utad: Kommunikasjon. E-post/WhatsApp/Teams/chat er KANALER inne i den.
// Paraplyen kjenner ingen kanal direkte — den leser kanal-registeret fra backend.
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.kommunikasjon.data";

export class FiqKommunikasjon extends Component {
    static template = "fiq_gui_comm.Kommunikasjon";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true, firms: [], current_firm: false, user: "",
            kryss_firma: false,          // 000-rettighet — fra sesjonen, aldri fra klienten
            kanaler: [], aktivKanal: "alle",
        });
        onWillStart(async () => {
            const cfg = await this.orm.call(DATA, "get_my_config", []);
            Object.assign(this.state, cfg, { loading: false });
        });
    }

    /** Klikk en kanal: har den egen flate, åpnes den; ellers vises den inne i paraplyen. */
    async velgKanal(kode) {
        this.state.aktivKanal = kode;
        if (kode === "alle") return;
        const act = await this.orm.call(DATA, "aapne_kanal", [kode]);
        if (act) this.action.doAction(act);
    }

    async byttFirma(id) {
        this.state.current_firm = id;
        const cfg = await this.orm.call(DATA, "get_my_config", []);
        this.state.kanaler = cfg.kanaler || [];
    }

    tilbakeKR() { this.action.doAction("fiq_gui_control.action_fiq_gui_control"); }

    kanalCls(k) {
        return "kanal c_" + (k.farge || "accent") + (this.state.aktivKanal === k.kode ? " on" : "");
    }
}

registry.category("actions").add("fiq_gui_comm_dashboard", FiqKommunikasjon);
