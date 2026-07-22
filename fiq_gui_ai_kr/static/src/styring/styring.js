/** @odoo-module **/

// STYRINGSFLATEN — «Alternativ Visning» i AI KR.
//
// Gjermund 22.07.2026: «nå har vi lagt ned så mye arbeid på denne at den bør bli
// en Alternativ Visning for FIQ GUI KR. Utvikles som et eget alternativ og
// innlemmes i menyen for GUI AI KR ASAP. Den fungerer til alt er oppe.»
//
// Fasit: artifact 72aae7c9, bygget av AI PK sammen med Gjermund gjennom ~30
// iterasjoner med hans direkte tilbakemelding. Alt her er hans bestilling.
//
// FASE 1 (denne): stadier · oppgaveliste · AI-spørsmål · kommentarlogg.
// Fase 2 (etter hans tilbakemelding): gruppering · filtre · bilder · tidslinje.
// Kunstpause: maks én versjon per tilbakemelding.

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.gui.ai.kr.data";

export class FiqAiStyring extends Component {
    static template = "fiq_gui_ai_kr.Styring";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            laster: true,
            stadier: [], spor: [], oppgaver: [], sporsmaal: [],
            valgt: null,          // oppgaven som er åpen i panelet
            logg: [],             // kommentarloggen for den oppgaven
            skjul_ferdig: false,
            stadiefilter: "",     // klikk på en stadie-pille filtrerer
            nyKommentar: "",
            svarUtkast: {},       // spørsmåls-id → påbegynt svar
        });

        onWillStart(async () => {
            // Stadiene må finnes FØR flaten tegner dem. Idempotent — kjøres
            // hver gang uten å lage duplikater, så en fersk base virker med én gang.
            await this.orm.call(DATA, "sikre_stadier", []);
            await this.last();
            this.state.laster = false;
        });
    }

    async last() {
        const d = await this.orm.call(DATA, "get_styring", [], {
            skjul_ferdig: this.state.skjul_ferdig,
        });
        Object.assign(this.state, d);
    }

    // ── STADIER ─────────────────────────────────────────────────────────────
    // Gjermund: «må flyttes fra et stadie til neste eller blir jo listen helt
    // statisk». Klikk på en pille i oppgavepanelet flytter oppgaven.
    async flytt(oppgave, kode) {
        if (oppgave.stadium === kode) { return; }
        const r = await this.orm.call(DATA, "flytt_stadium", [oppgave.id, kode]);
        if (r && r.ok) {
            oppgave.stadium = kode;
            oppgave.stadium_navn = r.stadium;
            await this.last();
        }
    }

    /** Klikk på en stadie-pille øverst filtrerer lista. Klikk igjen slår av. */
    filtrerStadium(kode) {
        this.state.stadiefilter = this.state.stadiefilter === kode ? "" : kode;
    }

    get synlige() {
        const f = this.state.stadiefilter;
        return f ? this.state.oppgaver.filter((o) => o.stadium === f) : this.state.oppgaver;
    }

    stadieFarge(kode) {
        const s = this.state.stadier.find((x) => x.kode === kode);
        return s ? s.farge : "#4a4560";
    }

    // ── OPPGAVEPANELET ──────────────────────────────────────────────────────
    async apne(oppgave) {
        this.state.valgt = oppgave;
        this.state.nyKommentar = "";
        const r = await this.orm.call(DATA, "get_kommentarlogg", [oppgave.id]);
        this.state.logg = r && r.finnes ? r.logg : [];
    }

    lukk() {
        this.state.valgt = null;
        this.state.logg = [];
    }

    async skrivKommentar() {
        const t = (this.state.nyKommentar || "").trim();
        if (!t || !this.state.valgt) { return; }
        const r = await this.orm.call(DATA, "skriv_kommentar", [this.state.valgt.id, t]);
        if (r && r.ok) {
            this.state.nyKommentar = "";
            await this.apne(this.state.valgt);   // hent loggen på nytt
            await this.last();                   // kommentartelleren i lista
        }
    }

    // ── AI-SPØRSMÅL ─────────────────────────────────────────────────────────
    // Fasitens gule felt ER godkjenningskøen (fiq.ai.godkjenning, 2.15.0).
    // Samme sak, andre ord — derfor ingen parallell mekanisme.
    // Svarer han → oppgaven flyttes til I Arbeid, svaret havner i chatteren.
    async svar(sporsmaal, valg) {
        const forbehold = this.state.svarUtkast[sporsmaal.id] || false;
        // «Ja, men…» UTEN tekst avvises server-side — et forbehold ingen kan
        // lese er intet forbehold. Vi stopper her så han slipper en feilmelding.
        if (valg === "ja_men" && !(forbehold || "").trim()) { return; }
        const r = await this.orm.call(DATA, "svar_godkjenning", [sporsmaal.id, valg, forbehold]);
        if (r && r.ok) {
            delete this.state.svarUtkast[sporsmaal.id];
            await this.last();
        }
    }

    async vekslFerdig() {
        this.state.skjul_ferdig = !this.state.skjul_ferdig;
        await this.last();
    }

    /** Åpne oppgaven i Odoos egen form — «Odoo uten KR skal virke». */
    aapneOdoo(id) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "project.task",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }

    tilbake() {
        this.action.doAction("fiq_gui_ai_kr.action_fiq_ai_kr");
    }
}

registry.category("actions").add("fiq_ai_styring", FiqAiStyring);
