/* Fonctions partagées : navigation, modales, toasts, Markdown et API. */
(function () {
    "use strict";

    const FG = (window.FG = window.FG || {});

    FG.$ = (selector, root = document) => root.querySelector(selector);
    FG.$$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    FG.escapeHtml = function (value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    };

    FG.formatNumber = function (value) {
        const number = Number(value || 0);
        return new Intl.NumberFormat("fr-FR").format(Number.isFinite(number) ? number : 0);
    };

    FG.formatDuration = function (ms) {
        const value = Number(ms || 0);
        if (!value) return "—";
        if (value < 1000) return `${Math.round(value)} ms`;
        if (value < 10000) return `${(value / 1000).toFixed(1)} s`;
        return `${Math.round(value / 1000)} s`;
    };

    FG.formatDate = function (iso, options) {
        if (!iso) return "—";
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) return String(iso).slice(0, 16).replace("T", " ");
        return new Intl.DateTimeFormat("fr-FR", options || {
            dateStyle: "medium",
            timeStyle: "short",
        }).format(date);
    };

    FG.formatTime = function (iso) {
        if (!iso) return "";
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) return String(iso).slice(11, 16);
        return new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(date);
    };

    FG.debounce = function (fn, delay = 120) {
        let timer = null;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    };

    /* ------------------------------------------------------------------ */
    /* API                                                                 */
    /* ------------------------------------------------------------------ */

    class ApiError extends Error {
        constructor(message, options = {}) {
            super(message);
            this.name = "ApiError";
            this.code = options.code || "error";
            this.hint = options.hint || "";
            this.status = options.status || 0;
            this.retryable = Boolean(options.retryable);
        }
    }
    FG.ApiError = ApiError;

    FG.apiFetch = async function (url, options = {}) {
        const response = await fetch(url, options);
        const contentType = response.headers.get("content-type") || "";
        let payload = null;
        if (contentType.includes("application/json")) {
            try {
                payload = await response.json();
            } catch (error) {
                payload = null;
            }
        }
        if (!response.ok) {
            const error = payload && payload.error ? payload.error : {};
            throw new ApiError(
                error.message || `La requête a échoué (${response.status}).`,
                {
                    code: error.code || `http_${response.status}`,
                    hint: error.hint || "",
                    status: response.status,
                    retryable: response.status >= 500 || response.status === 429,
                }
            );
        }
        return payload;
    };

    /* ------------------------------------------------------------------ */
    /* Markdown                                                            */
    /* ------------------------------------------------------------------ */

    let converter = null;

    function getConverter() {
        if (converter) return converter;
        if (typeof showdown === "undefined") return null;
        converter = new showdown.Converter({
            tables: true,
            tasklists: true,
            simplifiedAutoLink: true,
            strikethrough: true,
            ghCompatibleHeaderId: true,
            literalMidWordUnderscores: true,
            emoji: false,
        });
        converter.setOption("noHeaderId", false);
        return converter;
    }

    FG.markdownToHtml = function (text) {
        const source = String(text || "");
        const localConverter = getConverter();
        let html;
        if (localConverter) {
            html = localConverter.makeHtml(source);
        } else {
            html = `<p>${FG.escapeHtml(source).replace(/\n/g, "<br>")}</p>`;
        }
        if (typeof DOMPurify !== "undefined") {
            html = DOMPurify.sanitize(html, {
                ADD_ATTR: ["target", "rel"],
                FORBID_TAGS: ["style", "iframe", "form", "input", "button"],
            });
        }
        return html;
    };

    FG.highlightCode = function (root = document) {
        if (typeof hljs === "undefined") return;
        FG.$$("pre code", root).forEach((block) => {
            try {
                if (!block.dataset.highlighted) {
                    hljs.highlightElement(block);
                    block.dataset.highlighted = "1";
                }
            } catch (error) {
                /* le bloc reste affiché en texte brut */
            }
        });
    };

    FG.plainText = function (text) {
        const element = document.createElement("div");
        element.innerHTML = FG.markdownToHtml(text);
        return element.textContent || "";
    };

    /* ------------------------------------------------------------------ */
    /* Toasts                                                              */
    /* ------------------------------------------------------------------ */

    const TOAST_ICONS = {
        success: "✓",
        error: "!",
        warning: "⚠",
        info: "i",
    };

    FG.toast = function (message, type = "info", options = {}) {
        const container = FG.$("#toast-container");
        if (!container) return;
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-black
                ${type === "success" ? "bg-emerald-100 text-emerald-600" : ""}
                ${type === "error" ? "bg-rose-100 text-rose-600" : ""}
                ${type === "warning" ? "bg-amber-100 text-amber-600" : ""}
                ${type === "info" ? "bg-indigo-100 text-indigo-600" : ""}">
                ${TOAST_ICONS[type] || "i"}
            </div>
            <div class="min-w-0 flex-1">
                <p class="text-xs font-semibold text-slate-800">${FG.escapeHtml(message)}</p>
                ${options.hint ? `<p class="mt-0.5 text-[10px] leading-relaxed text-slate-500">${FG.escapeHtml(options.hint)}</p>` : ""}
            </div>
            <button type="button" class="shrink-0 self-start rounded p-0.5 text-slate-300 hover:text-slate-600" aria-label="Fermer">×</button>
        `;
        container.appendChild(toast);
        const remove = () => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(6px)";
            setTimeout(() => toast.remove(), 160);
        };
        toast.querySelector("button").addEventListener("click", remove);
        setTimeout(remove, options.duration || (type === "error" ? 7500 : 4500));
    };

    /* ------------------------------------------------------------------ */
    /* Modales                                                             */
    /* ------------------------------------------------------------------ */

    let activeModal = null;

    FG.closeModal = function () {
        const root = FG.$("#modal-root");
        if (root) root.innerHTML = "";
        activeModal = null;
    };

    FG.showModal = function ({ title, body = "", actions = [], wide = false, onMount }) {
        const root = FG.$("#modal-root");
        if (!root) return null;
        FG.closeModal();
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";
        backdrop.dataset.modalBackdrop = "1";
        backdrop.innerHTML = `
            <div class="modal-card ${wide ? "max-w-4xl" : "max-w-xl"}" role="dialog" aria-modal="true">
                <div class="flex items-start justify-between gap-4">
                    <h3 class="modal-title">${FG.escapeHtml(title || "")}</h3>
                    <button type="button" data-modal-close class="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Fermer">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"/></svg>
                    </button>
                </div>
                <div class="modal-body">${body}</div>
                ${actions.length ? `<div class="mt-5 flex flex-wrap justify-end gap-2">${actions.map((action, index) => {
                    const variant = action.variant || "secondary";
                    const classes = variant === "primary"
                        ? "bg-indigo-600 text-white hover:bg-indigo-700"
                        : variant === "danger"
                            ? "bg-rose-600 text-white hover:bg-rose-700"
                            : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50";
                    return `<button type="button" data-modal-action="${index}" class="rounded-xl px-3.5 py-2 text-xs font-semibold transition ${classes}">${FG.escapeHtml(action.label)}</button>`;
                }).join("")}</div>` : ""}
            </div>
        `;
        root.appendChild(backdrop);
        activeModal = backdrop;
        backdrop.addEventListener("click", (event) => {
            if (event.target === backdrop || event.target.closest("[data-modal-close]")) {
                FG.closeModal();
            }
        });
        FG.$$("[data-modal-action]", backdrop).forEach((button) => {
            button.addEventListener("click", async () => {
                const action = actions[Number(button.dataset.modalAction)];
                if (!action) return;
                if (action.onClick) {
                    await action.onClick(button);
                }
                if (action.close !== false) FG.closeModal();
            });
        });
        if (typeof onMount === "function") onMount(backdrop);
        return backdrop;
    };

    /* ------------------------------------------------------------------ */
    /* Liste des conversations                                             */
    /* ------------------------------------------------------------------ */

    FG.refreshConversationList = async function () {
        try {
            const data = await FG.apiFetch("/api/conversations");
            const list = FG.$("#conversation-list");
            const counter = FG.$("#conversation-count");
            if (!list) return;
            const activeId = Number(
                (FG.$("#messages") && FG.$("#messages").dataset.conversationId) ||
                new URLSearchParams(window.location.search).get("c") ||
                0
            );
            list.innerHTML = data.conversations.map((item) => {
                const active = Number(item.id) === activeId;
                return `
                    <div class="group relative flex items-stretch">
                        <a href="/?c=${item.id}" class="conversation-item ${active ? "conversation-item-active" : ""}" data-conversation-link="${item.id}">
                            <div class="flex items-center gap-1.5">
                                <span class="text-[11px]">${FG.escapeHtml(item.domain_icon || "✦")}</span>
                                <span class="truncate text-[13px] font-medium">${FG.escapeHtml(item.title)}</span>
                            </div>
                            <div class="mt-1 flex items-center gap-2 text-[10px] text-slate-400">
                                <span>${item.message_count} msg</span><span>·</span>
                                <span>${FG.formatNumber(item.total_tokens)} tok</span>
                                ${item.rating_avg ? `<span>·</span><span class="text-amber-500">★ ${item.rating_avg}</span>` : ""}
                            </div>
                        </a>
                        <button type="button" data-delete-conversation="${item.id}"
                                class="absolute right-1 top-1.5 rounded-md p-1 text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100"
                                title="Supprimer la conversation" aria-label="Supprimer la conversation">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 7h12M9 7V4h6v3m-8 0l1 13h8l1-13"/></svg>
                        </button>
                    </div>`;
            }).join("") || `<p class="px-2 py-3 text-xs text-slate-400">Aucune conversation pour l'instant.</p>`;
            if (counter) counter.textContent = String(data.conversations.length);
        } catch (error) {
            console.error(error);
        }
    };

    /* ------------------------------------------------------------------ */
    /* Santé du fournisseur                                                */
    /* ------------------------------------------------------------------ */

    FG.health = null;

    FG.refreshProviderStatus = async function () {
        const dot = FG.$("#provider-dot");
        const label = FG.$("#provider-status");
        if (!dot || !label) return;
        try {
            const health = await FG.apiFetch("/api/health");
            FG.health = health;
            if (!health.configured) {
                dot.className = "h-2 w-2 shrink-0 rounded-full bg-amber-400";
                label.textContent = "Configuration requise";
            } else if (health.reachable && health.model_available !== false) {
                dot.className = "h-2 w-2 shrink-0 rounded-full bg-emerald-500";
                label.textContent = "Service opérationnel";
            } else if (health.reachable) {
                dot.className = "h-2 w-2 shrink-0 rounded-full bg-amber-400";
                label.textContent = "Modèle indisponible";
            } else {
                dot.className = "h-2 w-2 shrink-0 rounded-full bg-rose-500";
                label.textContent = health.provider === "ollama" ? "Ollama hors ligne" : "Service hors ligne";
            }
            const button = label.closest("button");
            if (button) button.title = health.hint || health.message || "";
        } catch (error) {
            dot.className = "h-2 w-2 shrink-0 rounded-full bg-rose-500";
            label.textContent = "État inconnu";
        }
    };

    FG.showHealth = function () {
        const health = FG.health;
        if (!health) {
            FG.toast("Vérification du service en cours…", "info");
            FG.refreshProviderStatus().then(() => FG.showHealth());
            return;
        }
        const fallback = health.allow_fallback
            ? `<p class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">En cas d'indisponibilité de la connexion, une réponse locale construite à partir des sources peut être proposée.</p>`
            : "";
        FG.showModal({
            title: "État du service de génération",
            body: `
                <div class="space-y-3">
                    <div class="rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Fournisseur</p>
                        <p class="mt-0.5 text-sm font-semibold text-slate-800">${FG.escapeHtml(health.label || health.provider)}</p>
                        <p class="mt-0.5 text-[11px] text-slate-500">${FG.escapeHtml(health.message || "")}</p>
                        ${health.hint ? `<p class="mt-1 text-[11px] text-slate-500">${FG.escapeHtml(health.hint)}</p>` : ""}
                        ${health.latency_ms !== null && health.latency_ms !== undefined ? `<p class="mt-1 text-[10px] text-slate-400">Latence de vérification : ${health.latency_ms} ms</p>` : ""}
                    </div>
                    ${fallback}
                    <div class="rounded-xl border border-indigo-100 bg-indigo-50/70 p-3">
                        <p class="text-[10px] font-bold uppercase tracking-wide text-indigo-500">Configuration</p>
                        <p class="mt-1 text-[11px] leading-relaxed text-indigo-900/70">
                            Modifiez le fichier <code class="rounded bg-white px-1 py-0.5">.env</code> à la racine du projet :
                            <br><code class="mt-1 block whitespace-pre-wrap rounded bg-white px-2 py-1.5 text-[10px]">LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
# ou
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini</code>
                        </p>
                    </div>
                </div>`,
            actions: [
                {
                    label: "Réessayer",
                    variant: "primary",
                    onClick: async () => {
                        await FG.refreshProviderStatus();
                        FG.closeModal();
                        FG.showHealth();
                        FG.toast("État du service actualisé.", "info");
                    },
                    close: false,
                },
                { label: "Fermer" },
            ],
        });
    };

    /* ------------------------------------------------------------------ */
    /* Initialisation globale                                             */
    /* ------------------------------------------------------------------ */

    function openSidebar() {
        const sidebar = FG.$("#sidebar");
        const backdrop = FG.$("#mobile-backdrop");
        if (sidebar) sidebar.classList.remove("-translate-x-full");
        if (backdrop) backdrop.classList.remove("hidden");
    }

    function closeSidebar() {
        const sidebar = FG.$("#sidebar");
        const backdrop = FG.$("#mobile-backdrop");
        if (sidebar) sidebar.classList.add("-translate-x-full");
        if (backdrop) backdrop.classList.add("hidden");
    }

    function bindGlobalActions() {
        document.addEventListener("click", async (event) => {
            const menu = FG.$("#export-menu");
            if (menu && !event.target.closest("#export-toggle") && !event.target.closest("#export-menu")) {
                menu.classList.add("hidden");
            }

            const open = event.target.closest('[data-action="open-sidebar"]');
            if (open) {
                event.preventDefault();
                openSidebar();
                return;
            }
            if (event.target.closest('[data-action="close-sidebar"]') || event.target === FG.$("#mobile-backdrop")) {
                closeSidebar();
                return;
            }
            if (event.target.closest('[data-action="show-health"]')) {
                event.preventDefault();
                FG.showHealth();
                return;
            }
            if (event.target.closest('[data-action="new-conversation"]')) {
                event.preventDefault();
                const button = event.target.closest('[data-action="new-conversation"]');
                button.disabled = true;
                const domainSelect = FG.$("#domain-select");
                const domain = domainSelect ? domainSelect.value : (document.body.dataset.domain || "general");
                try {
                    const data = await FG.apiFetch("/api/conversations", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ domain, title: "Nouvelle conversation" }),
                    });
                    window.location.href = `/?c=${data.id}`;
                } catch (error) {
                    FG.toast(error.message, "error", { hint: error.hint });
                } finally {
                    button.disabled = false;
                }
                return;
            }
            const deleteButton = event.target.closest("[data-delete-conversation]");
            if (deleteButton) {
                event.preventDefault();
                event.stopPropagation();
                const id = Number(deleteButton.dataset.deleteConversation);
                if (!window.confirm("Supprimer définitivement cette conversation et ses messages ?")) return;
                try {
                    await FG.apiFetch(`/api/conversations/${id}`, { method: "DELETE" });
                    const activeId = Number(
                        (FG.$("#messages") && FG.$("#messages").dataset.conversationId) ||
                        new URLSearchParams(window.location.search).get("c") ||
                        0
                    );
                    FG.toast("Conversation supprimée.", "success");
                    if (activeId === id) {
                        window.location.href = "/";
                    } else {
                        await FG.refreshConversationList();
                    }
                } catch (error) {
                    FG.toast(error.message, "error", { hint: error.hint });
                }
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                FG.closeModal();
                closeSidebar();
                const menu = FG.$("#export-menu");
                if (menu) menu.classList.add("hidden");
            }
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        bindGlobalActions();
        FG.refreshProviderStatus();
        setTimeout(() => {
            if (!FG.health) FG.refreshProviderStatus();
        }, 4000);
    });
})();
