/* Page assistant : rendu des messages, streaming, sources, évaluations. */
(function () {
    "use strict";

    const FG = window.FG;
    if (!FG || !window.__CONVERSATION__) return;

    const state = {
        conversation: window.__CONVERSATION__,
        conversationId: Number(window.__CONVERSATION__.id),
        messages: (window.__CONVERSATION__.messages || []).slice(),
        sources: window.__SOURCES__ || [],
        domains: window.__DOMAINS__ || [],
        selectedSources: new Set(),
        busy: false,
        excerptCount: 2,
        lineCount: 4,
        streamParts: [],
    };

    const SUGGESTIONS = {
        general: [
            "Comment structurer une réponse claire et vérifiable ?",
            "Quels points vérifier avant de partager un document ?",
            "Aide-moi à préparer une synthèse de cette conversation.",
        ],
        informatique: [
            "Quelles sont les bonnes pratiques pour sécuriser une API Flask ?",
            "Comment organiser un déploiement avec retour arrière ?",
            "Explique les obligations RGPD pour une application web.",
        ],
        finance: [
            "Comment analyser la santé financière d'une entreprise ?",
            "Quels contrôles faire sur une facture et la TVA ?",
            "Aide-moi à construire un prévisionnel de trésorerie.",
        ],
        data: [
            "Comment évaluer la qualité d'un jeu de données ?",
            "Quelles dimensions de gouvernance présenter à un comité ?",
            "Comment distinguer une anomalie statistique d'une erreur métier ?",
        ],
        education: [
            "Quelles pièces sont nécessaires pour une inscription ?",
            "Comment obtenir une attestation de scolarité ?",
            "Explique la procédure de remboursement des frais.",
        ],
        sante: [
            "Quelles règles s'appliquent au partage de données de santé ?",
            "Comment fonctionne la prise de rendez-vous ?",
            "Que vérifier sur une facture de soins ?",
        ],
        droit: [
            "Comment analyser une clause contractuelle sensible ?",
            "Quels sont les principes de la protection des données ?",
            "Quelle méthode suivre pour qualifier juridiquement des faits ?",
        ],
        marketing: [
            "Comment construire une segmentation actionnable ?",
            "Quels indicateurs suivre pour une campagne ?",
            "Quelles règles de consentement respecter ?",
        ],
    };

    const $ = (selector, root = document) => root.querySelector(selector);

    function domainInfo(slug) {
        return state.domains.find((domain) => domain.slug === slug) || {
            slug: "general",
            label: "Général",
            icon: "✦",
            description: "",
        };
    }

    function currentDomain() {
        return state.conversation.domain || "general";
    }

    /* ------------------------------------------------------------------ */
    /* Sélection des sources                                              */
    /* ------------------------------------------------------------------ */

    function sourceStorageKey(domain = currentDomain()) {
        return `flaskgpt.sources.${domain}`;
    }

    function loadSourceSelection(domain, sources) {
        try {
            const raw = window.localStorage.getItem(sourceStorageKey(domain));
            if (raw === null) {
                return new Set(sources.map((source) => Number(source.id)));
            }
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return new Set(sources.map((source) => Number(source.id)));
            }
            const available = new Set(sources.map((source) => Number(source.id)));
            return new Set(parsed.map(Number).filter((id) => available.has(id)));
        } catch (error) {
            return new Set(sources.map((source) => Number(source.id)));
        }
    }

    function saveSourceSelection() {
        try {
            window.localStorage.setItem(
                sourceStorageKey(),
                JSON.stringify(Array.from(state.selectedSources))
            );
        } catch (error) {
            /* stockage local indisponible : la sélection reste en mémoire */
        }
    }

    function updateSourceCounters() {
        const count = state.selectedSources.size;
        const total = state.sources.length;
        const summary = $("#sources-summary");
        if (summary) {
            summary.textContent = `${total} source(s) disponible(s) · ${count} cochée(s)`;
        }
        const selected = $("#selected-source-count");
        if (selected) selected.textContent = String(count);
        const hint = $("#composer-source-hint");
        if (hint) {
            hint.textContent = count
                ? `${count} source(s) sélectionnée(s)`
                : "Aucune source sélectionnée";
            hint.classList.toggle("text-rose-500", count === 0);
            hint.classList.toggle("text-indigo-500", count > 0);
        }
    }

    function renderSources(sources) {
        state.sources = sources || [];
        state.selectedSources = loadSourceSelection(currentDomain(), state.sources);
        const list = $("#source-list");
        if (!list) return;
        if (!state.sources.length) {
            list.innerHTML = `<p class="px-1 py-2 text-[11px] text-slate-400">Aucune source pour ce domaine. Ajoutez un document pour permettre des réponses sourcées.</p>`;
            updateSourceCounters();
            return;
        }
        list.innerHTML = state.sources.map((source) => {
            const checked = state.selectedSources.has(Number(source.id));
            return `
                <div class="source-row group flex items-start gap-2 rounded-lg border border-transparent px-1.5 py-1.5 transition hover:border-slate-200 hover:bg-slate-50">
                    <input type="checkbox" class="source-checkbox mt-0.5 h-3.5 w-3.5 shrink-0 cursor-pointer rounded border-slate-300 text-indigo-600 accent-indigo-600"
                           value="${source.id}" ${checked ? "checked" : ""}>
                    <button type="button" data-preview-source="${source.id}" class="min-w-0 flex-1 text-left">
                        <span class="block truncate text-[11px] font-medium text-slate-600 group-hover:text-slate-900" title="${FG.escapeHtml(source.title)}">${FG.escapeHtml(source.title)}</span>
                        <span class="mt-0.5 flex items-center gap-1 text-[9px] uppercase tracking-wide text-slate-400">
                            <span class="inline-block h-1.5 w-1.5 rounded-full ${source.kind === "dataset" ? "bg-emerald-400" : "bg-indigo-300"}"></span>
                            ${source.kind === "dataset" ? "jeu de données" : "document"}
                        </span>
                    </button>
                </div>`;
        }).join("");

        FG.$$(".source-row", list).forEach((row) => {
            row.addEventListener("mouseenter", () => row.classList.add("bg-slate-50"));
            row.addEventListener("mouseleave", () => row.classList.remove("bg-slate-50"));
        });
        updateSourceCounters();
    }

    /* ------------------------------------------------------------------ */
    /* Rendu des messages                                                 */
    /* ------------------------------------------------------------------ */

    function ratingInfo(message) {
        let label = message.rating_label;
        if (!label && message.rating) {
            if (message.rating >= 4) label = "satisfaisante";
            else if (message.rating === 3) label = "moyenne";
            else label = "insuffisante";
        }
        return {
            label: label || "",
            className: label ? `rating-${label}` : "",
            color: label === "satisfaisante" ? "#10b981" : label === "moyenne" ? "#f59e0b" : label === "insuffisante" ? "#f43f5e" : "",
        };
    }

    function linkCitations(html, message) {
        const sources = message.sources || [];
        if (!sources.length) return html;
        return html.replace(/\[Source\s+(\d+)\]/g, (match, rank) => {
            const source = sources.find((item) => Number(item.rank) === Number(rank));
            if (!source || !source.source_id) return match;
            return `<button type="button" data-open-source="${source.source_id}" class="source-citation" title="Ouvrir le passage de la source ${source.rank}">${match}</button>`;
        });
    }

    function sourceSection(message) {        const sources = message.sources || [];
        if (!sources.length) {
            return `<p class="mt-3 text-[10px] text-slate-400">Aucune source n'a été transmise pour cette réponse.</p>`;
        }
        return `
            <details class="group/sources mt-3 rounded-xl border border-slate-100 bg-slate-50/70">
                <summary class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-[10px] font-semibold text-slate-500 [&::-webkit-details-marker]:hidden">
                    <svg class="h-3.5 w-3.5 text-indigo-400" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M7 4h7l4 4v12H7z"/><path stroke-linecap="round" d="M10 12h5M10 16h5"/></svg>
                    Sources utilisées (${sources.length})
                    <span class="ml-auto text-[9px] font-normal text-slate-400 group-open/sources:hidden">Voir les passages</span>
                    <svg class="h-3 w-3 text-slate-400 transition group-open/sources:rotate-180" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 9l6 6 6-6"/></svg>
                </summary>
                <div class="space-y-2 border-t border-slate-100 p-2.5">
                    ${sources.map((source) => `
                        <div class="rounded-lg border border-slate-100 bg-white p-2.5">
                            <div class="flex items-start justify-between gap-2">
                                <div class="flex min-w-0 items-start gap-1.5">
                                    <span class="mt-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-indigo-100 px-1 text-[8px] font-black text-indigo-600">S${source.rank}</span>
                                    <span class="min-w-0 text-[11px] font-semibold text-slate-700">${FG.escapeHtml(source.source_title)}</span>
                                </div>
                                ${source.source_id ? `<button type="button" data-open-source="${source.source_id}" class="shrink-0 text-[9px] font-semibold text-indigo-500 hover:text-indigo-700">Ouvrir</button>` : ""}
                            </div>
                            <div class="mt-1.5 flex items-center gap-2">
                                <div class="h-1 flex-1 overflow-hidden rounded-full bg-slate-100">
                                    <div class="h-full rounded-full bg-indigo-400" style="width:${Math.round(Number(source.score || 0) * 100)}%"></div>
                                </div>
                                <span class="text-[8px] font-semibold text-slate-400">${Math.round(Number(source.score || 0) * 100)} %</span>
                            </div>
                            <p class="mt-1.5 whitespace-pre-line text-[10.5px] leading-relaxed text-slate-500">${FG.escapeHtml(source.excerpt)}</p>
                        </div>`).join("")}
                </div>
            </details>`;
    }

    function ratingControls(message) {
        if (!message.id || message.error_code) return "";
        const info = ratingInfo(message);
        const labels = [
            ["satisfaisante", "Satisfaisante", "bg-emerald-500"],
            ["moyenne", "Moyenne", "bg-amber-400"],
            ["insuffisante", "Insuffisante", "bg-rose-500"],
        ];
        return `
            <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2.5" data-rating-message="${message.id}">
                <span class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Qualité</span>
                ${labels.map(([key, label, dot]) => `
                    <button type="button" class="quality-button" data-label="${key}" data-message-id="${message.id}" data-active="${info.label === key}">
                        <span class="h-1.5 w-1.5 rounded-full ${dot}"></span>${label}
                    </button>`).join("")}
                <span class="mx-1 h-3 w-px bg-slate-200"></span>
                <span class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Note</span>
                <span class="flex items-center gap-0.5">
                    ${[1, 2, 3, 4, 5].map((star) => `
                        <button type="button" class="star-button ${message.rating >= star ? "star-active" : ""}" data-star="${star}" data-message-id="${message.id}" title="${star}/5" aria-label="${star} sur 5">★</button>`).join("")}
                </span>
                ${message.rating ? `<span class="text-[9px] font-medium text-slate-400">${message.rating}/5</span>` : ""}
            </div>`;
    }

    function errorBlock(message) {
        if (!message.error_code) return "";
        return `
            <div class="rounded-xl border border-rose-200 bg-rose-50 p-3">
                <div class="flex items-start gap-2">
                    <div class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rose-100 text-[11px] font-black text-rose-600">!</div>
                    <div class="min-w-0">
                        <p class="text-xs font-bold text-rose-700">${FG.escapeHtml(message.error_message || "Une erreur est survenue.")}</p>
                        <p class="mt-1 text-[10px] text-rose-500">Code : ${FG.escapeHtml(message.error_code)}</p>
                        ${message.retryable !== false ? `<button type="button" data-retry-message class="mt-2 rounded-lg border border-rose-200 bg-white px-2.5 py-1 text-[10px] font-semibold text-rose-600 hover:bg-rose-100">Réessayer</button>` : ""}
                    </div>
                </div>
            </div>`;
    }

    function messageElement(message) {
        const isUser = message.role === "user";
        if (isUser) {
            return `
                <div class="fade-in flex justify-end" id="message-${message.id || "temp"}" data-message-id="${message.id || ""}">
                    <div class="max-w-[88%]">
                        <div class="mb-1 flex justify-end gap-2 text-[10px] text-slate-400">
                            <span>Vous</span><span>·</span><span>${FG.formatTime(message.created_at)}</span>
                        </div>
                        <div class="rounded-2xl rounded-br-md bg-indigo-600 px-4 py-3 shadow-sm shadow-indigo-200/50">
                            <div class="message-content message-user">${FG.markdownToHtml(message.content)}</div>
                        </div>
                    </div>
                </div>`;
        }

        const info = ratingInfo(message);
        const isFallback = message.provider === "local-fallback";
        const metrics = [];
        if (message.duration_ms) metrics.push(FG.formatDuration(message.duration_ms));
        if (message.total_tokens) metrics.push(`${FG.formatNumber(message.total_tokens)} tokens`);
        if (message.duration_ms && message.completion_tokens) {
            metrics.push(`${Math.round(message.completion_tokens / (message.duration_ms / 1000))} tok/s`);
        }
        return `
            <div class="fade-in flex gap-3" id="message-${message.id || "temp"}" data-message-id="${message.id || ""}">
                <div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-[10px] font-black text-white shadow-sm shadow-indigo-200">AI</div>
                <div class="min-w-0 flex-1">
                    <div class="mb-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
                        <span class="font-bold text-slate-600">Assistant</span>
                        <span class="rounded-full ${isFallback ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-500"} px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide">
                            ${isFallback ? "mode local" : FG.escapeHtml(message.provider || "modèle")}
                        </span>
                        ${message.model && !isFallback ? `<span class="hidden text-slate-300 sm:inline">${FG.escapeHtml(message.model)}</span>` : ""}
                        <span>${FG.formatTime(message.created_at)}</span>
                        ${metrics.length ? `<span class="ml-auto flex items-center gap-1.5 font-medium text-slate-400">
                            <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path stroke-linecap="round" d="M12 7v5l3 2"/></svg>
                            ${metrics.join(" · ")}
                        </span>` : ""}
                    </div>
                    <div class="assistant-card rounded-2xl rounded-tl-md border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/40 ${info.className}" data-card-message="${message.id || ""}">
                        ${isFallback ? `<div class="mb-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[10px] text-amber-800"><span class="mt-0.5 font-black">!</span><div><b>Réponse locale de secours.</b> Le service de génération est indisponible. La réponse est extraite des sources sélectionnées.</div></div>` : ""}
                        ${message.error_code ? errorBlock({ ...message, retryable: true }) : `<div class="message-content">${linkCitations(FG.markdownToHtml(message.content), message)}</div>`}
                        ${!message.error_code ? ratingControls(message) : ""}
                        ${!message.error_code ? sourceSection(message) : ""}
                    </div>
                </div>
            </div>`;
    }

    function renderMessages({ scroll = false } = {}) {
        const container = $("#messages");
        if (!container) return;
        container.innerHTML = state.messages.map(messageElement).join("");
        FG.highlightCode(container);
        const empty = $("#empty-state");
        if (empty) empty.classList.toggle("hidden", state.messages.length > 0);
        renderEmptySuggestions();
        if (scroll) scrollToBottom(true);
    }

    function renderEmptySuggestions() {
        const container = $("#empty-suggestions");
        if (!container) return;
        const domain = currentDomain();
        const items = SUGGESTIONS[domain] || SUGGESTIONS.general;
        container.innerHTML = items.map((item) => `
            <button type="button" data-suggestion="${FG.escapeHtml(item)}"
                    class="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-left text-[11px] font-medium text-slate-600 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700">
                ${FG.escapeHtml(item)}
            </button>`).join("");
        const description = $("#empty-domain-description");
        if (description) {
            description.textContent = `${domainInfo(domain).description || ""} Les réponses s'appuient sur les sources cochées.`;
        }
    }

    /* ------------------------------------------------------------------ */
    /* En-tête et indicateurs                                             */
    /* ------------------------------------------------------------------ */

    function computeStats() {
        const assistants = state.messages.filter(
            (message) => message.role === "assistant" && !message.error_code
        );
        const rated = assistants.filter((message) => message.rating > 0);
        const durations = assistants.filter((message) => message.duration_ms > 0);
        const totalTokens = assistants.reduce((sum, message) => sum + Number(message.total_tokens || 0), 0);
        return {
            message_count: state.messages.length,
            assistant_count: assistants.length,
            total_tokens: totalTokens,
            avg_duration_ms: durations.length
                ? Math.round(durations.reduce((sum, message) => sum + Number(message.duration_ms || 0), 0) / durations.length)
                : 0,
            avg_rating: rated.length
                ? (rated.reduce((sum, message) => sum + Number(message.rating || 0), 0) / rated.length).toFixed(2)
                : null,
            rated_count: rated.length,
        };
    }

    function renderHeader() {
        const domain = domainInfo(currentDomain());
        const title = $("#conversation-title");
        if (title) title.textContent = state.conversation.title;
        const badge = $("#domain-badge-label");
        if (badge) badge.textContent = domain.label;
        const badgeIcon = $("#domain-badge span");
        if (badgeIcon) badgeIcon.textContent = domain.icon;
        const description = $("#domain-description");
        if (description) description.textContent = domain.description;
        const stats = state.conversation.stats || computeStats();
        const duration = $("#metric-duration");
        if (duration) {
            duration.textContent = stats.avg_duration_ms ? FG.formatDuration(stats.avg_duration_ms) : "—";
        }
        const tokens = $("#metric-tokens");
        if (tokens) tokens.textContent = FG.formatNumber(stats.total_tokens || 0);
        const rating = $("#metric-rating");
        if (rating) rating.textContent = stats.avg_rating ? `${stats.avg_rating} / 5` : "—";
        const answers = $("#metric-answers");
        if (answers) answers.textContent = String(stats.assistant_count || 0);
        const subtitle = $("#conversation-subtitle");
        if (subtitle) {
            subtitle.textContent = `${stats.message_count || 0} message(s) · ${FG.formatNumber(stats.total_tokens || 0)} tokens · ${FG.formatDuration(stats.avg_duration_ms || 0)} en moyenne`;
        }
        const domainSelect = $("#domain-select");
        if (domainSelect) domainSelect.value = currentDomain();
        document.title = `${state.conversation.title} — FlaskGPT`;
        const base = `/api/conversations/${state.conversationId}/export`;
        FG.$$("#export-menu a").forEach((link, index) => {
            const formats = ["txt", "pdf", "json", "summary"];
            link.href = `${base}/${formats[index]}`;
        });
        const summaryButton = $("#summary-button");
        if (summaryButton) summaryButton.dataset.conversationId = String(state.conversationId);
        const clearButton = $("#clear-conversation");
        if (clearButton) clearButton.dataset.conversationId = String(state.conversationId);
        const messagesContainer = $("#messages");
        if (messagesContainer) messagesContainer.dataset.conversationId = String(state.conversationId);
    }

    /* ------------------------------------------------------------------ */
    /* Streaming                                                          */
    /* ------------------------------------------------------------------ */

    function isNearBottom() {
        const scroll = $("#chat-scroll");
        if (!scroll) return true;
        return scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 140;
    }

    function scrollToBottom(force = false) {
        const scroll = $("#chat-scroll");
        if (!scroll) return;
        if (!force && !isNearBottom()) return;
        requestAnimationFrame(() => {
            scroll.scrollTop = scroll.scrollHeight;
        });
    }

    function setBusy(busy) {
        state.busy = busy;
        const button = $("#send-button");
        const label = $("#send-label");
        if (button) button.disabled = busy;
        if (label) label.textContent = busy ? "Génération…" : "Envoyer";
        const icon = $("#send-icon");
        if (icon) icon.classList.toggle("animate-spin", busy);
        const status = $("#stream-status");
        if (status) status.classList.toggle("hidden", !busy);
    }

    function setStreamStatus(text) {
        const element = $("#stream-status-text");
        if (element) element.textContent = text;
    }

    function createStreamingMessage() {
        const container = $("#messages");
        const wrapper = document.createElement("div");
        wrapper.className = "fade-in flex gap-3";
        wrapper.dataset.streaming = "1";
        wrapper.innerHTML = `
            <div class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-[10px] font-black text-white shadow-sm shadow-indigo-200">AI</div>
            <div class="min-w-0 flex-1">
                <div class="mb-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
                    <span class="font-bold text-slate-600">Assistant</span>
                    <span class="rounded-full bg-indigo-50 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide text-indigo-600">en cours</span>
                </div>
                <div class="assistant-card rounded-2xl rounded-tl-md border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/40">
                    <div data-stream-warning></div>
                    <div class="message-content" data-stream-content></div>
                    <div data-stream-typing class="mt-1 flex items-center gap-1.5 text-[10px] text-indigo-400">
                        <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
                        <span class="ml-1 text-slate-400">Recherche des sources et préparation…</span>
                    </div>
                </div>
            </div>`;
        container.appendChild(wrapper);
        scrollToBottom(true);
        return {
            wrapper,
            content: wrapper.querySelector("[data-stream-content]"),
            typing: wrapper.querySelector("[data-stream-typing]"),
            warning: wrapper.querySelector("[data-stream-warning]"),
            parts: [],
            renderScheduled: false,
            render() {
                if (this.renderScheduled) return;
                this.renderScheduled = true;
                requestAnimationFrame(() => {
                    this.renderScheduled = false;
                    this.content.innerHTML = FG.markdownToHtml(this.parts.join(""));
                    FG.highlightCode(this.content);
                });
            },
            addWarning(payload) {
                this.warning.innerHTML = `
                    <div class="mb-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[10px] text-amber-800">
                        <span class="mt-0.5 font-black">!</span>
                        <div class="min-w-0">
                            <b>${FG.escapeHtml(payload.message || "Service de génération indisponible.")}</b>
                            ${payload.hint ? `<p class="mt-0.5 text-amber-700/80">${FG.escapeHtml(payload.hint)}</p>` : ""}
                            <p class="mt-0.5 text-amber-700/80">Une réponse locale construite à partir des sources est proposée.</p>
                        </div>
                    </div>`;
            },
        };
    }

    async function consumeNdjson(response, onEvent) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                let newline;
                while ((newline = buffer.indexOf("\n")) >= 0) {
                    const line = buffer.slice(0, newline).trim();
                    buffer = buffer.slice(newline + 1);
                    if (!line) continue;
                    try {
                        onEvent(JSON.parse(line));
                    } catch (error) {
                        console.error("Événement invalide", line, error);
                    }
                }
            }
            buffer += decoder.decode();
            if (buffer.trim()) {
                try {
                    onEvent(JSON.parse(buffer));
                } catch (error) {
                    console.error("Événement final invalide", error);
                }
            }
        } finally {
            reader.releaseLock();
        }
    }

    async function reloadConversation({ refreshList = false, scroll = true } = {}) {
        const data = await FG.apiFetch(`/api/conversations/${state.conversationId}`);
        state.conversation = data.conversation;
        state.messages = data.conversation.messages || [];
        renderHeader();
        renderMessages({ scroll });
        if (refreshList) FG.refreshConversationList();
    }

    function syntheticErrorMessage(payload) {
        return {
            id: payload.message_id || null,
            role: "assistant",
            content: "",
            created_at: new Date().toISOString(),
            provider: null,
            model: null,
            duration_ms: payload.duration_ms || 0,
            total_tokens: 0,
            error_code: payload.code || "error",
            error_message: [payload.message, payload.hint].filter(Boolean).join(" "),
            sources: [],
        };
    }

    async function sendMessage(rawText) {
        const text = String(rawText || "").trim();
        if (!text || state.busy) return;

        const userMessage = {
            id: null,
            role: "user",
            content: text,
            created_at: new Date().toISOString(),
            duration_ms: 0,
            total_tokens: 0,
            sources: [],
        };
        state.messages.push(userMessage);
        $("#messages").insertAdjacentHTML("beforeend", messageElement(userMessage));
        $("#empty-state").classList.add("hidden");
        FG.highlightCode($("#messages"));
        scrollToBottom(true);

        const input = $("#message-input");
        input.value = "";
        resizeInput();
        setBusy(true);
        setStreamStatus("Recherche des sources pertinentes…");
        const stream = createStreamingMessage();
        let done = false;

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    conversation_id: state.conversationId,
                    message: text,
                    source_ids: state.sources
                        .filter((source) => state.selectedSources.has(Number(source.id)))
                        .map((source) => Number(source.id)),
                    excerpts: state.excerptCount,
                    lines: state.lineCount,
                }),
            });

            if (!response.ok) {
                let payload = null;
                try {
                    payload = await response.json();
                } catch (error) {
                    payload = null;
                }
                const error = (payload && payload.error) || {};
                stream.wrapper.remove();
                const synthetic = syntheticErrorMessage({
                    code: error.code || `http_${response.status}`,
                    message: error.message || "La requête a échoué.",
                    hint: error.hint || "",
                });
                state.messages.push(synthetic);
                $("#messages").insertAdjacentHTML("beforeend", messageElement(synthetic));
                FG.toast(error.message || "La requête a échoué.", "error", { hint: error.hint });
                return;
            }

            await consumeNdjson(response, (event) => {
                if (event.type === "meta") {
                    setStreamStatus("Génération de la réponse…");
                    if (event.sources && event.sources.length) {
                        setStreamStatus(`${event.sources.length} source(s) mobilisée(s) · génération…`);
                    }
                } else if (event.type === "token") {
                    stream.parts.push(event.text || "");
                    stream.render();
                    if (stream.typing) stream.typing.remove();
                    setStreamStatus("Rédaction de la réponse…");
                    scrollToBottom();
                } else if (event.type === "warning") {
                    stream.addWarning(event);
                    FG.toast(event.message || "Service indisponible : réponse locale.", "warning", {
                        hint: event.fallback ? "La réponse sera construite à partir des sources." : event.hint,
                    });
                } else if (event.type === "error") {
                    done = true;
                    stream.wrapper.remove();
                    const synthetic = syntheticErrorMessage(event);
                    state.messages.push(synthetic);
                    $("#messages").insertAdjacentHTML("beforeend", messageElement(synthetic));
                    if (event.conversation) {
                        state.conversation = event.conversation;
                        renderHeader();
                    }
                    FG.toast(event.message || "Erreur de génération.", "error", { hint: event.hint });
                    scrollToBottom(true);
                } else if (event.type === "done") {
                    done = true;
                    if (event.conversation) {
                        state.conversation = event.conversation;
                        renderHeader();
                    }
                }
            });

            if (done) {
                await reloadConversation({ refreshList: true, scroll: true });
            } else {
                await reloadConversation({ refreshList: true, scroll: true });
                FG.toast("Le flux de réponse s'est interrompu.", "warning", {
                    hint: "La réponse partielle a été conservée si le serveur a pu l'enregistrer.",
                });
            }
        } catch (error) {
            console.error(error);
            if (!done) {
                stream.wrapper.remove();
                const synthetic = syntheticErrorMessage({
                    code: "network_error",
                    message: "Impossible de contacter le serveur.",
                    hint: "Vérifiez votre connexion puis réessayez.",
                });
                state.messages.push(synthetic);
                $("#messages").insertAdjacentHTML("beforeend", messageElement(synthetic));
                FG.toast("Impossible de contacter le serveur.", "error", { hint: "Vérifiez votre connexion." });
            }
        } finally {
            setBusy(false);
            scrollToBottom();
        }
    }

    /* ------------------------------------------------------------------ */
    /* Actions : évaluation, sources, résumé, exports, domaine             */
    /* ------------------------------------------------------------------ */

    async function rateMessage(messageId, rating, label, button) {
        const group = button.closest("[data-rating-message]");
        if (group) {
            FG.$$("button", group).forEach((item) => {
                item.disabled = true;
            });
        }
        try {
            await FG.apiFetch(`/api/messages/${messageId}/rating`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ rating, label }),
            });
            FG.toast("Évaluation enregistrée.", "success");
            await reloadConversation({ refreshList: true, scroll: false });
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        } finally {
            if (group) {
                FG.$$("button", group).forEach((item) => {
                    item.disabled = false;
                });
            }
        }
    }

    async function showSource(sourceId) {
        try {
            const data = await FG.apiFetch(`/api/sources/${sourceId}`);
            const source = data.source;
            FG.showModal({
                title: source.title,
                wide: true,
                body: `
                    <div class="mb-3 flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
                        <span class="rounded-full bg-slate-100 px-2 py-0.5 font-semibold uppercase tracking-wide">${source.kind === "dataset" ? "jeu de données" : "document"}</span>
                        <span>${FG.escapeHtml(source.origin || "source interne")}</span>
                        <span>·</span>
                        <span>${FG.formatDate(source.created_at)}</span>
                    </div>
                    <div class="max-h-[55vh] overflow-y-auto whitespace-pre-line rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-600">${FG.escapeHtml(source.content)}</div>
                    <p class="mt-3 text-[10px] text-slate-400">Ce document est une source de référence. Il est transmis au modèle uniquement si la case correspondante est cochée.</p>`,
                actions: [{ label: "Fermer" }],
            });
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        }
    }

    async function showSummary() {
        const button = $("#summary-button");
        const original = button ? button.innerHTML : "";
        if (button) {
            button.disabled = true;
            button.innerHTML = `<span class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600"></span><span class="hidden sm:inline">Génération…</span>`;
        }
        try {
            const data = await FG.apiFetch(`/api/conversations/${state.conversationId}/summary`);
            const summary = data.summary;
            const stats = summary.stats || {};
            const questions = (summary.questions || []).map((question) => `<li>${FG.escapeHtml(question)}</li>`).join("");
            const points = (summary.points || []).map((point) => `<li>${FG.escapeHtml(point)}</li>`).join("");
            FG.showModal({
                title: "Synthèse de la conversation",
                wide: true,
                body: `
                    <div class="mb-3 flex flex-wrap gap-2 text-[10px]">
                        <span class="rounded-full bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700">${stats.assistant_count || 0} réponse(s)</span>
                        <span class="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">${FG.formatNumber(stats.total_tokens || 0)} tokens</span>
                        <span class="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">Temps moyen ${FG.formatDuration(stats.avg_duration_ms || 0)}</span>
                        ${stats.avg_rating ? `<span class="rounded-full bg-amber-50 px-2.5 py-1 font-semibold text-amber-700">★ ${stats.avg_rating}/5</span>` : ""}
                    </div>
                    ${questions ? `<h4 class="mt-4 text-xs font-bold text-slate-800">Questions abordées</h4><ul class="mt-1.5 list-disc space-y-1 pl-4 text-xs text-slate-600">${questions}</ul>` : ""}
                    ${points ? `<h4 class="mt-4 text-xs font-bold text-slate-800">Points clés</h4><ul class="mt-1.5 list-disc space-y-1 pl-4 text-xs text-slate-600">${points}</ul>` : `<p class="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">Aucune réponse exploitable pour construire une synthèse.</p>`}
                    <p class="mt-4 rounded-lg border border-indigo-100 bg-indigo-50/70 p-3 text-[10px] text-indigo-900/70">
                        La synthèse est extractive : elle reprend des phrases des réponses. Le PDF ajoute les sources, les indicateurs et les questions.
                    </p>`,
                actions: [
                    {
                        label: "Télécharger le PDF",
                        variant: "primary",
                        onClick: () => {
                            window.location.href = `/api/conversations/${state.conversationId}/export/summary`;
                        },
                        close: false,
                    },
                    { label: "Fermer" },
                ],
            });
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = original;
            }
        }
    }

    function addSourceModal() {
        const domain = domainInfo(currentDomain());
        FG.showModal({
            title: "Ajouter une source documentaire",
            body: `
                <p class="mb-3 text-[11px] text-slate-500">La source sera disponible pour le domaine <b>${FG.escapeHtml(domain.label)}</b>. Elle sera transmise au modèle lorsqu'elle est cochée.</p>
                <form id="add-source-form" class="space-y-3">
                    <label class="block">
                        <span class="form-label">Titre</span>
                        <input name="title" class="form-input" maxlength="160" required placeholder="Ex. Procédure de remboursement 2026">
                    </label>
                    <label class="block">
                        <span class="form-label">Contenu</span>
                        <textarea name="content" rows="8" class="form-input" required minlength="40" maxlength="60000" placeholder="Collez ici le texte de la source (procédure, extrait de référentiel, notes…)."></textarea>
                    </label>
                </form>`,
            actions: [
                {
                    label: "Ajouter la source",
                    variant: "primary",
                    close: false,
                    onClick: async (button) => {
                        const form = $("#add-source-form");
                        const title = form.elements.title.value.trim();
                        const content = form.elements.content.value.trim();
                        if (title.length < 3 || content.length < 40) {
                            FG.toast("Le titre (3 caractères) et le contenu (40 caractères) sont requis.", "warning");
                            return;
                        }
                        button.disabled = true;
                        button.textContent = "Ajout…";
                        try {
                            const data = await FG.apiFetch("/api/sources", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ domain: currentDomain(), title, content }),
                            });
                            state.selectedSources.add(Number(data.source.id));
                            saveSourceSelection();
                            const refreshed = await FG.apiFetch(`/api/sources?domain=${currentDomain()}`);
                            renderSources(refreshed.sources);
                            updateSourceCounters();
                            FG.closeModal();
                            FG.toast("Source ajoutée et sélectionnée.", "success");
                        } catch (error) {
                            FG.toast(error.message, "error", { hint: error.hint });
                        } finally {
                            button.disabled = false;
                            button.textContent = "Ajouter la source";
                        }
                    },
                },
                { label: "Annuler" },
            ],
        });
    }

    async function changeDomain(domain) {
        const select = $("#domain-select");
        if (select) select.disabled = true;
        try {
            const data = await FG.apiFetch(`/api/conversations/${state.conversationId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ domain }),
            });
            state.conversation = { ...state.conversation, ...data.conversation };
            renderHeader();
            renderSources(data.sources || []);
            renderEmptySuggestions();
            FG.refreshConversationList();
            FG.toast(`Domaine : ${domainInfo(domain).label}.`, "success", {
                hint: "Les prochains échanges utiliseront les sources et les consignes de ce domaine.",
            });
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
            renderHeader();
        } finally {
            if (select) select.disabled = false;
        }
    }

    async function clearConversation() {
        if (!window.confirm("Effacer tous les messages de cette conversation ? Cette action est irréversible.")) return;
        try {
            await FG.apiFetch(`/api/conversations/${state.conversationId}/clear`, { method: "POST" });
            await reloadConversation({ refreshList: true, scroll: true });
            FG.toast("Conversation effacée.", "success");
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        }
    }

    /* ------------------------------------------------------------------ */
    /* Événements                                                         */
    /* ------------------------------------------------------------------ */

    function resizeInput() {
        const input = $("#message-input");
        if (!input) return;
        input.style.height = "auto";
        input.style.height = `${Math.min(input.scrollHeight, 192)}px`;
    }

    function bindEvents() {
        const form = $("#chat-form");
        const input = $("#message-input");

        form.addEventListener("submit", (event) => {
            event.preventDefault();
            sendMessage(input.value);
        });

        input.addEventListener("input", resizeInput);
        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
                event.preventDefault();
                sendMessage(input.value);
            }
        });

        $("#messages").addEventListener("click", (event) => {
            const quality = event.target.closest(".quality-button");
            if (quality) {
                const label = quality.dataset.label;
                const rating = label === "satisfaisante" ? 5 : label === "moyenne" ? 3 : 1;
                rateMessage(Number(quality.dataset.messageId), rating, label, quality);
                return;
            }
            const star = event.target.closest(".star-button");
            if (star) {
                const rating = Number(star.dataset.star);
                const label = rating >= 4 ? "satisfaisante" : rating === 3 ? "moyenne" : "insuffisante";
                rateMessage(Number(star.dataset.messageId), rating, label, star);
                return;
            }
            const source = event.target.closest("[data-open-source]");
            if (source) {
                showSource(Number(source.dataset.openSource));
                return;
            }
            const retry = event.target.closest("[data-retry-message]");
            if (retry) {
                const card = retry.closest("[data-message-id]");
                const errorId = card ? Number(card.dataset.messageId) : null;
                const index = errorId
                    ? state.messages.findIndex((message) => Number(message.id) === errorId)
                    : -1;
                let lastUser = null;
                if (index >= 0) {
                    lastUser = [...state.messages.slice(0, index)]
                        .reverse()
                        .find((message) => message.role === "user");
                }
                if (!lastUser) {
                    lastUser = [...state.messages].reverse().find((message) => message.role === "user");
                }
                if (lastUser) {
                    sendMessage(lastUser.content);
                }
            }
        });

        $("#empty-suggestions").addEventListener("click", (event) => {
            const suggestion = event.target.closest("[data-suggestion]");
            if (!suggestion) return;
            input.value = suggestion.dataset.suggestion;
            resizeInput();
            input.focus();
        });

        document.addEventListener("click", (event) => {
            const preview = event.target.closest("[data-preview-source]");
            if (preview) {
                showSource(Number(preview.dataset.previewSource));
            }
        });

        $("#source-list").addEventListener("change", (event) => {
            const checkbox = event.target.closest(".source-checkbox");
            if (!checkbox) return;
            const id = Number(checkbox.value);
            if (checkbox.checked) state.selectedSources.add(id);
            else state.selectedSources.delete(id);
            saveSourceSelection();
            updateSourceCounters();
        });

        const toggleSources = document.querySelector('[data-action="toggle-sources"]');
        if (toggleSources) {
            toggleSources.addEventListener("click", () => {
                const allSelected = state.selectedSources.size === state.sources.length;
                state.selectedSources = allSelected
                    ? new Set()
                    : new Set(state.sources.map((source) => Number(source.id)));
                saveSourceSelection();
                renderSources(state.sources);
            });
        }

        const addSource = document.querySelector('[data-action="add-source"]');
        if (addSource) addSource.addEventListener("click", addSourceModal);

        const domainSelect = $("#domain-select");
        if (domainSelect) {
            domainSelect.addEventListener("change", () => changeDomain(domainSelect.value));
        }

        $("#summary-button").addEventListener("click", showSummary);
        $("#clear-conversation").addEventListener("click", clearConversation);

        const exportToggle = $("#export-toggle");
        const exportMenu = $("#export-menu");
        if (exportToggle && exportMenu) {
            exportToggle.addEventListener("click", (event) => {
                event.stopPropagation();
                exportMenu.classList.toggle("hidden");
            });
        }

        const excerpts = $("#excerpts-per-source");
        const lines = $("#lines-per-excerpt");
        try {
            const savedExcerpts = window.localStorage.getItem("flaskgpt.excerpts");
            const savedLines = window.localStorage.getItem("flaskgpt.lines");
            if (savedExcerpts && excerpts) excerpts.value = savedExcerpts;
            if (savedLines && lines) lines.value = savedLines;
        } catch (error) {
            /* stockage local indisponible */
        }
        state.excerptCount = Number(excerpts ? excerpts.value : 2);
        state.lineCount = Number(lines ? lines.value : 4);
        if (excerpts) {
            excerpts.addEventListener("change", () => {
                state.excerptCount = Number(excerpts.value);
                try { window.localStorage.setItem("flaskgpt.excerpts", excerpts.value); } catch (error) { /* ignore */ }
            });
        }
        if (lines) {
            lines.addEventListener("change", () => {
                state.lineCount = Number(lines.value);
                try { window.localStorage.setItem("flaskgpt.lines", lines.value); } catch (error) { /* ignore */ }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderHeader();
        renderSources(state.sources);
        renderMessages({ scroll: true });
        bindEvents();
        setTimeout(() => scrollToBottom(true), 120);
    });
})();
