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
            grupper: { basis: [], tverrgaende: [], omraade: [] },   // fargeboksene (originalen)
            presence: [], visTomme: false,
            krMeny: [],                  // hovedmenyen fra KR — I TILLEGG til mappetreet
        });
        onWillStart(async () => {
            const cfg = await this.orm.call(DATA, "get_my_config", []);
            Object.assign(this.state, cfg, { loading: false });
            await this.lastOversikt();
        });
    }

    /** Forsiden: fargeboksene + Til stede + KR-menyen. Ett kall, ikke tre. */
    async lastOversikt() {
        const o = await this.orm.call(DATA, "get_oversikt", [this.state.current_firm || false]);
        this.state.grupper = o.grupper || { basis: [], tverrgaende: [], omraade: [] };
        this.state.presence = o.presence || [];
        this.state.krMeny = o.kr_meny || [];
    }

    /** Bokser som skal vises. Tomme skjules til brukeren ber om dem —
     *  Gjermund: «vær dynamisk, ikke vis bokser som er tomme». */
    bokser(gruppe) {
        const alle = (this.state.grupper && this.state.grupper[gruppe]) || [];
        return this.state.visTomme ? alle : alle.filter((b) => !b.tom);
    }

    harBokser() {
        return ["basis", "tverrgaende", "omraade"].some((g) => this.bokser(g).length);
    }

    /** Antall tomme bokser — så bryteren kan si hvor mange den skjuler. */
    antallTomme() {
        const g = this.state.grupper || {};
        return ["basis", "tverrgaende", "omraade"]
            .reduce((n, k) => n + ((g[k] || []).filter((b) => b.tom).length), 0);
    }

    vekslTomme() { this.state.visTomme = !this.state.visTomme; }

    /** Klikk en fargeboks → kanalens flate åpnes FILTRERT på boksen
     *  («Haster» → alle hastende meldinger). */
    async aapneBoks(b) {
        const act = await this.orm.call(DATA, "aapne_boks", [b.kode, b.kanal || "epost"]);
        if (act) this.action.doAction(act);
    }

    /** Menypunkt i KR-menyen: åpne flaten uten å gå veien om Kontrollrommet. */
    aapneKrFlate(f) {
        if (f.xmlid) this.action.doAction(f.xmlid);
    }

    boksCls(b) {
        return "boks c_" + (b.farge || "graa") + (b.tom ? " tom" : "");
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

// ---- Registrering i det delte skallet (V00.04) --------------------------------------
// KR meldte 22.07: røret for undermenyer er ferdig, men INGEN flate leverer punkter —
// derfor står venstremenyen tom. Kontrakten er lest i `shell.js:44-65`, ikke antatt:
//   key/label/color/sequence/Component + valgfri `meny: [{key, label, badge}]`
//
// 🛑 `label` MÅ være ren tekst. Et objekt {en_US, nb_NO} felte HELE grensesnittet 22.07
//    (`fiq_gui_relations` → «Invalid object: 'label' is not a string»). Samme feltnavn har
//    MOTSATT kontrakt i menypunkter, der oversettelsesobjekt er lov. Ikke bland dem.
//
// Menypunktene speiler flatens egne visninger — de samme brukeren allerede kjenner
// fra sidemenyen: oversikt, e-postkanalen og kalenderen. Ingen nye begreper.
//
// 🔑 NØKKELEN ER «komm» — og skal FORBLI det (avklart 23.07.2026).
// Menyen kaller «kommunikasjon», registeret her heter «komm». Det ser ut som en bom, og
// jeg registrerte en stund under BEGGE nøkler for å være sikker. Det var feil vei:
// KR løser oversettelsen SELV i `_slotKomponent()` via `NOKKEL_ALIAS`
// (`control_room.js:1811`, KR 19.0.7.4.0) — den prøver menyens nøkkel først, så flatens
// eget navn. Aliaset dekker alle åtte flatene.
// 🛑 Døper hver flate-eier om sin nøkkel på egen hånd, får vi fem uavhengige fikser på et
//    DELT register — og en glemt modul gir samme stille feil om igjen. Én oversettelse ett
//    sted er riktig; `fiq_gui_control` eier den.
// 📌 «komm» matcher dessuten selvregistreringen i `fiq_gui_comm_flate.xml` og modellnavnet
//    `fiq.gui.komm.data`. Å bytte her ville brutt de to.
registry.category("fiq_gui_flates").add("komm", {
    key: "komm",
    label: "Kommunikasjon",
    color: "#0078CC",          // 2 Admin-blå, kanonisk fargekart
    sequence: 40,              // samme plass som i KR-menyen (mellom 35 og 45)
    Component: FiqKommunikasjon,
    meny: [
        { key: "oversikt", label: "Oversikt" },
        { key: "epost", label: "E-post" },
        { key: "kalender", label: "Møter og kalender" },
    ],
});
