/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.mailChatState = useState({
            chats: [],
            activeChatId: false,
            draggingChatId: false,
            sourceModel: false,
            sourceId: false,
            loading: false,
        });

        onWillStart(async () => {
            await this.mailChatLoad(this.props);
        });

        onWillUpdateProps(async (nextProps) => {
            if (
                nextProps.threadModel !== this.mailChatState.sourceModel ||
                nextProps.threadId !== this.mailChatState.sourceId
            ) {
                await this.mailChatLoad(nextProps);
            }
        });
    },

    async mailChatLoad(props) {
        if (!props.threadId || props.threadModel === "mail.chat") {
            this.mailChatState.chats = [];
            this.mailChatState.activeChatId = false;
            this.mailChatState.sourceModel = props.threadModel;
            this.mailChatState.sourceId = props.threadId;
            return;
        }

        this.mailChatState.loading = true;
        this.mailChatState.sourceModel = props.threadModel;
        this.mailChatState.sourceId = props.threadId;

        const chats = await this.orm.call(props.threadModel, "mail_chat_get_chats", [[props.threadId]]);
        this.mailChatState.chats = chats || [];

        const active =
            this.mailChatState.chats.find((chat) => chat.id === this.mailChatState.activeChatId) ||
            this.mailChatState.chats.find((chat) => chat.is_default) ||
            this.mailChatState.chats[0];
        this.mailChatState.activeChatId = active ? active.id : false;

        if (this.mailChatState.activeChatId) {
            await super.changeThread("mail.chat", this.mailChatState.activeChatId);
            await this.load(this.state.thread, this.requestList);
            await this.state.thread.fetchNewMessages();
        }

        this.mailChatState.loading = false;
    },

    changeThread(threadModel, threadId) {
        if (
            threadModel !== "mail.chat" &&
            threadId &&
            this.mailChatState.activeChatId &&
            threadModel === this.mailChatState.sourceModel &&
            threadId === this.mailChatState.sourceId
        ) {
            return super.changeThread("mail.chat", this.mailChatState.activeChatId);
        }
        return super.changeThread(threadModel, threadId);
    },

    async mailChatSwitch(chatId) {
        if (!chatId || chatId === this.mailChatState.activeChatId) {
            return;
        }
        this.mailChatState.activeChatId = chatId;
        await super.changeThread("mail.chat", chatId);
        await this.load(this.state.thread, this.requestList);
        await this.state.thread.fetchNewMessages();
    },

    async mailChatCreate() {
        if (!this.mailChatState.sourceModel || !this.mailChatState.sourceId) {
            return;
        }
        const name = prompt("Chat name");
        if (!name || !name.trim()) {
            return;
        }
        const chatId = await this.orm.call(this.mailChatState.sourceModel, "action_create_chat", [
            [this.mailChatState.sourceId],
            name.trim(),
            [],
        ]);
        await this.mailChatLoad({
            threadModel: this.mailChatState.sourceModel,
            threadId: this.mailChatState.sourceId,
        });
        if (chatId) {
            await this.mailChatSwitch(chatId);
        }
    },

    async mailChatRename(chat) {
        if (!chat || !this.mailChatState.sourceModel || !this.mailChatState.sourceId) {
            return;
        }
        const name = prompt("Chat name", chat.name || "");
        if (name === null) {
            return;
        }
        if (!name.trim() || name.trim() === chat.name) {
            return;
        }
        await this.orm.call(this.mailChatState.sourceModel, "mail_chat_rename", [
            [this.mailChatState.sourceId],
            chat.id,
            name.trim(),
        ]);
        await this.mailChatLoad({
            threadModel: this.mailChatState.sourceModel,
            threadId: this.mailChatState.sourceId,
        });
        if (this.mailChatState.activeChatId) {
            await this.mailChatSwitch(this.mailChatState.activeChatId);
        }
    },

    mailChatDragStart(ev, chatId) {
        this.mailChatState.draggingChatId = chatId;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(chatId));
        }
    },

    mailChatDragOver(ev) {
        ev.preventDefault();
        if (ev.dataTransfer) {
            ev.dataTransfer.dropEffect = "move";
        }
    },

    async mailChatDrop(ev, targetChatId) {
        ev.preventDefault();
        const sourceChatId = this.mailChatState.draggingChatId;
        this.mailChatState.draggingChatId = false;
        if (!sourceChatId || sourceChatId === targetChatId) {
            return;
        }

        const chats = [...this.mailChatState.chats];
        const sourceIndex = chats.findIndex((chat) => chat.id === sourceChatId);
        const targetIndex = chats.findIndex((chat) => chat.id === targetChatId);
        if (sourceIndex < 0 || targetIndex < 0) {
            return;
        }

        const [moved] = chats.splice(sourceIndex, 1);
        chats.splice(targetIndex, 0, moved);
        this.mailChatState.chats = chats;

        await this.orm.call(this.mailChatState.sourceModel, "mail_chat_reorder", [
            [this.mailChatState.sourceId],
            chats.map((chat) => chat.id),
        ]);
    },

    mailChatDragEnd() {
        this.mailChatState.draggingChatId = false;
    },
});
