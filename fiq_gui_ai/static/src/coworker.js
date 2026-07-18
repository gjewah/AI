/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * FIQ AI co-worker – "Ask AI for help" chat (to Claude) + presence.
 * Registered as a client action ("fiq_gui_ai_coworker") so it opens standalone
 * AND can be embedded (e.g. in the Control room).
 */
export class FiqAiCoworker extends Component {
    static template = "fiq_gui_ai.Coworker";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.inputRef = useRef("input");
        this.listRef = useRef("list");

        this.state = useState({
            messages: [],        // {role: "user"|"ai", text}
            draft: "",
            busy: false,         // waiting for an answer
            presence: [],        // internal users + online status
            showPresence: true,
        });

        onWillStart(async () => {
            await this.loadPresence();
        });
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
    }

    async loadPresence() {
        try {
            this.state.presence = await this.orm.call(
                "fiq.gui.ai.assistent", "get_tilstedevaerelse", []
            );
        } catch (e) {
            this.state.presence = [];
        }
    }

    get onlineCount() {
        return this.state.presence.filter((p) => p.online).length;
    }

    // Enter sends; Shift+Enter makes a newline.
    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    async send() {
        const text = (this.state.draft || "").trim();
        if (!text || this.state.busy) {
            return;
        }
        this.state.messages.push({ role: "user", text });
        this.state.draft = "";
        this.state.busy = true;
        this._scrollSoon();

        let answer = "";
        try {
            answer = await this.orm.call("fiq.gui.ai.assistent", "spor", [text]);
        } catch (e) {
            // The server already degrades gracefully; this covers transport errors.
            answer = _t("AI is unavailable right now – please try again in a moment.");
        }
        this.state.messages.push({ role: "ai", text: answer || "" });
        this.state.busy = false;
        this._scrollSoon();
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    togglePresence() {
        this.state.showPresence = !this.state.showPresence;
    }

    _scrollSoon() {
        // Let OWL patch the DOM, then scroll the message list to the bottom.
        Promise.resolve().then(() => {
            if (this.listRef.el) {
                this.listRef.el.scrollTop = this.listRef.el.scrollHeight;
            }
        });
    }
}

registry.category("actions").add("fiq_gui_ai_coworker", FiqAiCoworker);
