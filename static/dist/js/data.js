/* Atelier données : import, rapport de qualité, gouvernance et exports. */
(function () {
    "use strict";

    const FG = window.FG;
    if (!FG) return;

    const state = {
        datasets: window.__DATA__ || [],
        selected: window.__DATASET__ || null,
        pendingFile: null,
        busy: false,
        issueFilter: "all",
        columnQuery: "",
    };

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    function scoreColor(score) {
        const value = Number(score || 0);
        if (value >= 80) return "#10b981";
        if (value >= 60) return "#f59e0b";
        return "#f43f5e";
    }

    function scoreTextClass(score) {
        const value = Number(score || 0);
        if (value >= 80) return "text-emerald-600";
        if (value >= 60) return "text-amber-600";
        return "text-rose-600";
    }

    function scoreBgClass(score) {
        const value = Number(score || 0);
        if (value >= 80) return "bg-emerald-500";
        if (value >= 60) return "bg-amber-400";
        return "bg-rose-500";
    }

    function scoreBadgeClass(score) {
        const value = Number(score || 0);
        if (value >= 80) return "bg-emerald-50 text-emerald-600";
        if (value >= 60) return "bg-amber-50 text-amber-600";
        if (value) return "bg-rose-50 text-rose-600";
        return "bg-slate-100 text-slate-500";
    }

    function severitySlug(severity) {
        return String(severity || "info")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "");
    }

    function severityLabel(severity) {
        const value = String(severity || "info").toLowerCase();
        if (value === "élevée" || value === "elevee") return "Élevée";
        if (value === "moyenne") return "Moyenne";
        if (value === "faible") return "Faible";
        return "Info";
    }

    function formatValue(value) {
        if (value === null || value === undefined || value === "") return "—";
        return String(value);
    }

    /* ------------------------------------------------------------------ */
    /* Liste des jeux de données                                          */
    /* ------------------------------------------------------------------ */

    function renderDatasetList() {
        const list = $("#dataset-list");
        const counter = $("#dataset-count");
        if (!list) return;
        if (counter) counter.textContent = String(state.datasets.length);
        if (!state.datasets.length) {
            list.innerHTML = `
                <div class="rounded-xl border border-dashed border-slate-200 p-4 text-center">
                    <p class="text-[11px] text-slate-400">Aucun jeu de données. Importez un CSV, Excel, JSON ou une base SQLite.</p>
                </div>`;
            return;
        }
        list.innerHTML = state.datasets.map((dataset) => {
            const score = Number(dataset.quality_score || 0);
            const active = state.selected && Number(state.selected.id) === Number(dataset.id);
            return `
                <button type="button" data-dataset-load="${dataset.id}" class="dataset-item w-full text-left ${active ? "dataset-item-active" : ""}">
                    <div class="flex items-start justify-between gap-2">
                        <div class="min-w-0">
                            <p class="truncate text-xs font-semibold text-slate-700">${FG.escapeHtml(dataset.name)}</p>
                            <p class="mt-0.5 text-[10px] text-slate-400">${FG.formatNumber(dataset.row_count)} lignes · ${dataset.column_count} colonnes</p>
                        </div>
                        <span class="shrink-0 rounded-lg px-1.5 py-0.5 text-[10px] font-bold ${scoreBadgeClass(score)}">${score ? Math.round(score) : "—"}</span>
                    </div>
                    <p class="mt-1 truncate text-[9px] uppercase tracking-wide text-slate-400">${FG.escapeHtml(dataset.file_type || "")} · ${FG.escapeHtml((dataset.imported_at || "").slice(0, 10))}</p>
                </button>`;
        }).join("");
    }

    function renderReport() {
        const root = $("#report-root");
        if (!root) return;
        if (!state.selected) {
            root.innerHTML = `
                <div class="panel flex min-h-[26rem] flex-col items-center justify-center text-center">
                    <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-500">
                        <svg class="h-7 w-7" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"/><path stroke-linecap="round" d="M4 7v5c0 1.7 3.6 3 8 3s8-1.3 8-3V7M4 12v5c0 1.7 3.6 3 8 3s8-1.3 8-3v-5"/></svg>
                    </div>
                    <h3 class="text-base font-bold text-slate-800">Aucun jeu de données sélectionné</h3>
                    <p class="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">Importez un fichier à gauche pour lancer le profilage : complétude, unicité, cohérence, validité, doublons, anomalies et données personnelles.</p>
                    <button type="button" id="empty-import" class="mt-4 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-indigo-700">Importer un fichier</button>
                </div>`;
            const button = $("#empty-import");
            if (button) button.addEventListener("click", () => $("#dataset-file").click());
            return;
        }

        const dataset = state.selected;
        const report = dataset.report;
        if (!report) {
            root.innerHTML = `
                <div class="panel">
                    <div class="panel-header">
                        <div>
                            <h3 class="panel-title">${FG.escapeHtml(dataset.name)}</h3>
                            <p class="panel-subtitle">${FG.formatNumber(dataset.row_count)} lignes · ${dataset.column_count} colonnes</p>
                        </div>
                    </div>
                    <div class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
                        <p class="text-xs font-semibold text-amber-800">Ce jeu de données n'a pas encore de rapport.</p>
                        <p class="mt-1 text-[11px] text-amber-700">Lancez l'analyse pour calculer les indicateurs de qualité et de gouvernance.</p>
                        <button type="button" data-dataset-action="analyze" class="mt-3 rounded-lg bg-amber-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-amber-700">Analyser maintenant</button>
                    </div>
                </div>`;
            bindReportActions();
            return;
        }

        const scores = report.scores || {};
        const overview = report.overview || {};
        const governance = report.governance || {};
        const globalScore = Number(scores.global || 0);
        const risk = governance.risk || "—";
        const riskClass = risk === "faible"
            ? "bg-emerald-50 text-emerald-700 ring-emerald-100"
            : risk === "modéré"
                ? "bg-amber-50 text-amber-700 ring-amber-100"
                : "bg-rose-50 text-rose-700 ring-rose-100";
        const pii = governance.pii_columns || [];
        const issues = report.issues || [];
        const columns = report.columns || [];
        const anomalies = report.anomalies || [];
        const dimensions = report.dimensions || [];
        const counts = {
            all: issues.length,
            elevee: issues.filter((issue) => severitySlug(issue.severity) === "elevee").length,
            moyenne: issues.filter((issue) => severitySlug(issue.severity) === "moyenne").length,
            faible: issues.filter((issue) => severitySlug(issue.severity) === "faible").length,
        };

        root.innerHTML = `
            <div class="space-y-4">
                <div class="panel">
                    <div class="flex flex-wrap items-start justify-between gap-3">
                        <div class="min-w-0">
                            <div class="flex flex-wrap items-center gap-2">
                                <h3 class="truncate text-base font-bold text-slate-900">${FG.escapeHtml(dataset.name)}</h3>
                                <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-slate-500">${FG.escapeHtml(dataset.file_type || "fichier")}</span>
                                ${dataset.table_name ? `<span class="rounded-full bg-indigo-50 px-2 py-0.5 text-[9px] font-semibold text-indigo-600">table ${FG.escapeHtml(dataset.table_name)}</span>` : ""}
                                <span class="rounded-full px-2 py-0.5 text-[9px] font-bold ring-1 ring-inset ${riskClass}">risque ${FG.escapeHtml(risk)}</span>
                            </div>
                            <p class="mt-1 text-[10px] text-slate-400">
                                ${FG.escapeHtml(dataset.filename || "")} · importé le ${FG.formatDate(dataset.imported_at)}
                                ${dataset.truncated_rows ? ` · ${dataset.truncated_rows} ligne(s) ignorée(s) (limite 50 000)` : ""}
                                ${dataset.truncated_columns ? ` · ${dataset.truncated_columns} colonne(s) ignorée(s) (limite 200)` : ""}
                            </p>
                        </div>
                        <div class="flex flex-wrap items-center gap-1.5">
                            <button type="button" data-dataset-action="analyze" class="rounded-lg border border-slate-200 px-2.5 py-1.5 text-[10px] font-semibold text-slate-600 hover:border-indigo-300 hover:text-indigo-700">Re-analyser</button>
                            <a href="/api/datasets/${dataset.id}/export/pdf" class="rounded-lg border border-slate-200 px-2.5 py-1.5 text-[10px] font-semibold text-slate-600 hover:border-indigo-300 hover:text-indigo-700">Rapport PDF</a>
                            <a href="/api/datasets/${dataset.id}/export/json" class="rounded-lg border border-slate-200 px-2.5 py-1.5 text-[10px] font-semibold text-slate-600 hover:border-indigo-300 hover:text-indigo-700">JSON</a>
                            <button type="button" data-dataset-action="use-in-chat" class="rounded-lg bg-indigo-600 px-2.5 py-1.5 text-[10px] font-semibold text-white hover:bg-indigo-700">Utiliser dans le chat</button>
                            <button type="button" data-dataset-action="delete" class="rounded-lg border border-rose-200 px-2.5 py-1.5 text-[10px] font-semibold text-rose-600 hover:bg-rose-50">Supprimer</button>
                        </div>
                    </div>

                    <div class="mt-5 grid gap-4 lg:grid-cols-[11rem_minmax(0,1fr)]">
                        <div class="flex flex-col items-center justify-center rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-5">
                            <div class="score-ring" style="--score:${globalScore};--ring-color:${scoreColor(globalScore)}">
                                <svg viewBox="0 0 110 110" aria-hidden="true">
                                    <circle class="ring-bg" cx="55" cy="55" r="46"></circle>
                                    <circle class="ring-value" cx="55" cy="55" r="46"></circle>
                                </svg>
                                <span class="score-ring-value">${Math.round(globalScore)}</span>
                            </div>
                            <p class="mt-2 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-400">Qualité globale</p>
                            <p class="mt-1 text-center text-[10px] leading-relaxed text-slate-500">Score pondéré : complétude, unicité, cohérence et validité.</p>
                        </div>
                        <div class="grid grid-cols-2 gap-2.5">
                            ${dimensions.map((dimension) => {
                                const score = Number(dimension.score || 0);
                                return `
                                    <div class="score-card">
                                        <div class="flex items-center justify-between gap-2">
                                            <p class="text-[10px] font-bold uppercase tracking-wide text-slate-500">${FG.escapeHtml(dimension.label)}</p>
                                            <span class="text-xs font-extrabold ${scoreTextClass(score)}">${Math.round(score)}</span>
                                        </div>
                                        <div class="progress-track mt-2"><div class="progress-bar ${scoreBgClass(score)}" style="width:${score}%"></div></div>
                                        <p class="mt-1.5 text-[9px] text-slate-400">${FG.escapeHtml(dimension.description || "")}</p>
                                    </div>`;
                            }).join("")}
                            <div class="score-card col-span-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                                <div><p class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Lignes</p><p class="mt-0.5 text-sm font-bold text-slate-800">${FG.formatNumber(overview.rows)}</p></div>
                                <div><p class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Colonnes</p><p class="mt-0.5 text-sm font-bold text-slate-800">${overview.columns || 0}</p></div>
                                <div><p class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Manquants</p><p class="mt-0.5 text-sm font-bold text-slate-800">${overview.missing_pct || 0} %</p></div>
                                <div><p class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Doublons</p><p class="mt-0.5 text-sm font-bold text-slate-800">${FG.formatNumber(overview.duplicate_rows)}</p></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="grid gap-4 lg:grid-cols-2">
                    <section class="panel">
                        <div class="panel-header">
                            <div>
                                <h3 class="panel-title">Gouvernance & conformité</h3>
                                <p class="panel-subtitle">Données personnelles, documentation et fraîcheur.</p>
                            </div>
                            <span class="rounded-full px-2.5 py-1 text-[10px] font-bold ring-1 ring-inset ${riskClass}">${Math.round(Number(governance.score || 0))}/100</span>
                        </div>
                        <div class="mt-3 grid grid-cols-2 gap-2">
                            <div class="rounded-xl border border-slate-100 bg-slate-50/70 p-2.5">
                                <p class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Données personnelles</p>
                                <p class="mt-0.5 text-sm font-bold ${pii.length ? "text-rose-600" : "text-emerald-600"}">${pii.length}</p>
                            </div>
                            <div class="rounded-xl border border-slate-100 bg-slate-50/70 p-2.5">
                                <p class="text-[9px] font-bold uppercase tracking-wide text-slate-400">Documentation</p>
                                <p class="mt-0.5 text-sm font-bold text-slate-800">${Math.round(Number(governance.documentation_score || 0))}/100</p>
                            </div>
                        </div>
                        ${pii.length ? `
                            <div class="mt-3 space-y-1.5">
                                ${pii.map((item) => `
                                    <div class="pii-card flex items-center justify-between gap-2">
                                        <div class="min-w-0">
                                            <p class="truncate text-[11px] font-semibold text-rose-800">${FG.escapeHtml(item.column)}</p>
                                            <p class="text-[9px] text-rose-600">${FG.escapeHtml(item.label)} · ${FG.escapeHtml(item.evidence)}</p>
                                        </div>
                                        <span class="shrink-0 rounded-full bg-rose-100 px-1.5 py-0.5 text-[8px] font-bold uppercase text-rose-600">${FG.escapeHtml(item.sensitivity)}</span>
                                    </div>`).join("")}
                            </div>` : `<p class="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-[10px] text-emerald-700">Aucune donnée personnelle évidente détectée par les heuristiques.</p>`}
                        <div class="mt-3 space-y-1.5">
                            ${(governance.checks || []).map((check) => `
                                <div class="flex items-start justify-between gap-2 rounded-lg border border-slate-100 px-2.5 py-1.5">
                                    <div class="min-w-0">
                                        <p class="text-[10px] font-semibold text-slate-600">${FG.escapeHtml(check.label)}</p>
                                        <p class="text-[9px] text-slate-400">${FG.escapeHtml(check.detail)}</p>
                                    </div>
                                    <span class="shrink-0 text-[9px] font-semibold text-slate-500">${FG.escapeHtml(check.status)}</span>
                                </div>`).join("")}
                        </div>
                        <p class="mt-3 text-[9px] leading-relaxed text-slate-400">Ces contrôles sont heuristiques. Une analyse de conformité juridique nécessite une revue humaine.</p>
                    </section>

                    <section class="panel">
                        <div class="panel-header">
                            <div>
                                <h3 class="panel-title">Anomalies & valeurs extrêmes</h3>
                                <p class="panel-subtitle">Méthode IQR (1,5 × écart interquartile).</p>
                            </div>
                            <span class="badge-soft">${anomalies.length} colonne(s)</span>
                        </div>
                        <div class="mt-3 space-y-2">
                            ${anomalies.length ? anomalies.map((anomaly) => `
                                <div class="rounded-xl border border-amber-100 bg-amber-50/60 p-2.5">
                                    <div class="flex items-center justify-between gap-2">
                                        <p class="text-[11px] font-bold text-amber-900">${FG.escapeHtml(anomaly.column)}</p>
                                        <span class="rounded-full bg-amber-100 px-1.5 py-0.5 text-[8px] font-bold text-amber-700">${anomaly.count} valeur(s)</span>
                                    </div>
                                    <p class="mt-1 text-[9px] text-amber-700">${anomaly.pct} % des valeurs · bornes [${anomaly.bounds[0]} ; ${anomaly.bounds[1]}]</p>
                                    <p class="mt-1 text-[9px] text-amber-600">Exemples : ${anomaly.examples.map((value) => FG.escapeHtml(value)).join(", ")}</p>
                                </div>`).join("") : `<div class="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-[10px] text-emerald-700">Aucune valeur atypique détectée avec les seuils appliqués.</div>`}
                        </div>
                        <div class="mt-4 border-t border-slate-100 pt-3">
                            <h4 class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Recommandations</h4>
                            <ul class="mt-2 space-y-1.5">
                                ${(report.recommendations || []).map((recommendation) => `<li class="flex gap-2 text-[10px] leading-relaxed text-slate-600"><span class="mt-0.5 text-indigo-400">→</span><span>${FG.escapeHtml(recommendation)}</span></li>`).join("")}
                            </ul>
                        </div>
                    </section>
                </div>

                <section class="panel">
                    <div class="panel-header">
                        <div>
                            <h3 class="panel-title">Problèmes détectés</h3>
                            <p class="panel-subtitle">${issues.length} constat(s), classés par gravité.</p>
                        </div>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-1.5">
                        ${[
                            ["all", `Toutes (${counts.all})`],
                            ["elevee", `Élevée (${counts.elevee})`],
                            ["moyenne", `Moyenne (${counts.moyenne})`],
                            ["faible", `Faible (${counts.faible})`],
                        ].map(([key, label]) => `
                            <button type="button" data-issue-filter="${key}" class="rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${state.issueFilter === key ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-500 hover:bg-slate-50"}">${label}</button>`).join("")}
                    </div>
                    <div class="mt-3 space-y-2">
                        ${issues.length ? issues.map((issue) => {
                            const slug = severitySlug(issue.severity);
                            return `
                                <div class="issue-card issue-${slug}" data-issue-severity="${slug}">
                                    <div class="flex flex-wrap items-center gap-2">
                                        <span class="severity-pill severity-${slug}">${FG.escapeHtml(severityLabel(issue.severity))}</span>
                                        <span class="rounded-full bg-white/80 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide text-slate-500">${FG.escapeHtml(issue.category)}</span>
                                        ${issue.column ? `<span class="text-[9px] font-semibold text-slate-500">colonne ${FG.escapeHtml(issue.column)}</span>` : ""}
                                        ${issue.count !== null && issue.count !== undefined ? `<span class="text-[9px] text-slate-400">${FG.formatNumber(issue.count)} occurrence(s)</span>` : ""}
                                    </div>
                                    <p class="mt-1.5 text-[11px] font-semibold text-slate-700">${FG.escapeHtml(issue.message)}</p>
                                    <p class="mt-1 text-[10px] leading-relaxed text-slate-500"><span class="font-semibold text-slate-600">Action :</span> ${FG.escapeHtml(issue.recommendation)}</p>
                                </div>`;
                        }).join("") : `<div class="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3 text-[10px] text-emerald-700">Aucun problème détecté.</div>`}
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-header">
                        <div>
                            <h3 class="panel-title">Profil des colonnes</h3>
                            <p class="panel-subtitle">${columns.length} colonne(s) analysée(s).</p>
                        </div>
                        <input id="column-search" type="search" placeholder="Filtrer une colonne…" class="w-44 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[10px] text-slate-600 outline-none focus:border-indigo-300 focus:bg-white">
                    </div>
                    <div class="mt-3 max-h-[30rem] overflow-auto rounded-xl border border-slate-100">
                        <table class="data-table">
                            <thead class="sticky top-0 z-10 bg-white">
                                <tr><th>Colonne</th><th>Type</th><th>Manquants</th><th>Uniques</th><th>Atypiques</th><th>Validité</th><th>Valeurs fréquentes</th></tr>
                            </thead>
                            <tbody>
                                ${columns.map((column) => `
                                    <tr data-column-name="${FG.escapeHtml(column.name).toLowerCase()}">
                                        <td>
                                            <span class="font-semibold text-slate-700">${FG.escapeHtml(column.name)}</span>
                                            ${column.is_pii ? `<span class="ml-1 rounded bg-rose-50 px-1 py-0.5 text-[7px] font-bold uppercase text-rose-500">PII</span>` : ""}
                                        </td>
                                        <td><span class="rounded bg-slate-100 px-1.5 py-0.5 text-[8px] font-semibold text-slate-500">${FG.escapeHtml(column.type)}</span></td>
                                        <td>
                                            <div class="flex items-center gap-1.5">
                                                <div class="h-1 w-12 overflow-hidden rounded-full bg-slate-100"><div class="h-full ${Number(column.missing_pct) >= 20 ? "bg-rose-500" : Number(column.missing_pct) >= 5 ? "bg-amber-400" : "bg-emerald-500"}" style="width:${Math.min(100, Number(column.missing_pct || 0))}%"></div></div>
                                                <span class="text-[9px] ${Number(column.missing_pct) >= 20 ? "font-bold text-rose-600" : "text-slate-500"}">${column.missing_pct} %</span>
                                            </div>
                                        </td>
                                        <td class="text-[9px]">${FG.formatNumber(column.unique)} <span class="text-slate-400">(${column.unique_pct} %)</span></td>
                                        <td class="text-[9px] ${column.outliers ? "font-semibold text-amber-600" : "text-slate-400"}">${column.outliers}</td>
                                        <td class="text-[9px] ${Number(column.valid_pct) < 95 ? "font-semibold text-rose-600" : "text-emerald-600"}">${column.valid_pct} %</td>
                                        <td class="max-w-[14rem] truncate text-[9px] text-slate-400">${(column.top_values || []).slice(0, 3).map((item) => `${FG.escapeHtml(item.value)} (${item.count})`).join(" · ") || "—"}</td>
                                    </tr>`).join("")}
                            </tbody>
                        </table>
                    </div>
                </section>

                <section class="panel">
                    <div class="panel-header">
                        <div>
                            <h3 class="panel-title">Aperçu des données</h3>
                            <p class="panel-subtitle">10 premières lignes · valeurs tronquées.</p>
                        </div>
                    </div>
                    <div class="mt-3 overflow-auto rounded-xl border border-slate-100">
                        <table class="preview-table">
                            <thead><tr>${columns.map((column) => `<th>${FG.escapeHtml(column.name)}</th>`).join("")}</tr></thead>
                            <tbody>
                                ${(report.sample || []).map((row) => `
                                    <tr>${columns.map((column) => `<td title="${FG.escapeHtml(formatValue(row[column.name]))}">${FG.escapeHtml(formatValue(row[column.name]))}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${Math.max(1, columns.length)}" class="py-5 text-center text-slate-400">Aucune ligne à afficher.</td></tr>`}
                            </tbody>
                        </table>
                    </div>
                </section>

                <p class="px-2 text-[9px] leading-relaxed text-slate-400">
                    Rapport généré le ${FG.formatDate(report.generated_at)}. Les scores sont des indicateurs heuristiques destinés à prioriser les contrôles. Ils ne constituent ni un audit ni un avis juridique.
                </p>
            </div>`;
        bindReportActions();
    }

    /* ------------------------------------------------------------------ */
    /* Actions du rapport                                                 */
    /* ------------------------------------------------------------------ */

    function bindReportActions() {
        $$("[data-dataset-action]").forEach((button) => {
            button.addEventListener("click", () => {
                const action = button.dataset.datasetAction;
                if (!state.selected) return;
                if (action === "analyze") analyzeDataset(button);
                if (action === "delete") deleteDataset(button);
                if (action === "use-in-chat") useInChat(button);
            });
        });
        $$("[data-issue-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                state.issueFilter = button.dataset.issueFilter;
                $$("[data-issue-filter]").forEach((item) => {
                    const active = item.dataset.issueFilter === state.issueFilter;
                    item.classList.toggle("border-indigo-200", active);
                    item.classList.toggle("bg-indigo-50", active);
                    item.classList.toggle("text-indigo-700", active);
                    item.classList.toggle("border-slate-200", !active);
                    item.classList.toggle("text-slate-500", !active);
                });
                $$("[data-issue-severity]").forEach((card) => {
                    card.classList.toggle("hidden", state.issueFilter !== "all" && card.dataset.issueSeverity !== state.issueFilter);
                });
            });
        });
        const search = $("#column-search");
        if (search) {
            search.value = state.columnQuery;
            search.addEventListener("input", () => {
                state.columnQuery = search.value.trim().toLowerCase();
                $$("[data-column-name]").forEach((row) => {
                    row.classList.toggle("hidden", state.columnQuery && !row.dataset.columnName.includes(state.columnQuery));
                });
            });
        }
    }

    async function refreshDatasetList() {
        try {
            const data = await FG.apiFetch("/api/datasets");
            state.datasets = data.datasets || [];
            renderDatasetList();
        } catch (error) {
            console.error(error);
        }
    }

    async function loadDataset(id, updateUrl = true) {
        try {
            const data = await FG.apiFetch(`/api/datasets/${id}`);
            state.selected = data.dataset;
            state.issueFilter = "all";
            state.columnQuery = "";
            renderDatasetList();
            renderReport();
            if (updateUrl) {
                const url = new URL(window.location.href);
                url.searchParams.set("d", id);
                window.history.replaceState({}, "", url);
            }
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        }
    }

    async function analyzeDataset(button) {
        if (!state.selected || state.busy) return;
        state.busy = true;
        if (button) {
            button.disabled = true;
            button.textContent = "Analyse…";
        }
        try {
            const data = await FG.apiFetch(`/api/datasets/${state.selected.id}/analyze`, {
                method: "POST",
            });
            state.selected = data.dataset;
            renderDatasetList();
            renderReport();
            await refreshDatasetList();
            FG.toast("Analyse terminée : rapport mis à jour.", "success", {
                hint: "Le résumé du jeu de données est disponible comme source dans le domaine Analyse de données.",
            });
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        } finally {
            state.busy = false;
            if (button && button.isConnected) {
                button.disabled = false;
                button.textContent = "Re-analyser";
            }
        }
    }

    async function deleteDataset(button) {
        if (!state.selected) return;
        if (!window.confirm(`Supprimer « ${state.selected.name} » et sa source associée ?`)) return;
        button.disabled = true;
        try {
            await FG.apiFetch(`/api/datasets/${state.selected.id}`, { method: "DELETE" });
            const deletedId = state.selected.id;
            state.selected = null;
            state.datasets = state.datasets.filter((dataset) => Number(dataset.id) !== Number(deletedId));
            if (state.datasets.length) {
                await loadDataset(state.datasets[0].id, false);
            } else {
                const url = new URL(window.location.href);
                url.searchParams.delete("d");
                window.history.replaceState({}, "", url);
                renderDatasetList();
                renderReport();
            }
            FG.toast("Jeu de données supprimé.", "success");
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        } finally {
            if (button && button.isConnected) button.disabled = false;
        }
    }

    async function useInChat(button) {
        if (!state.selected) return;
        button.disabled = true;
        try {
            const data = await FG.apiFetch(`/api/datasets/${state.selected.id}/use-in-chat`, {
                method: "POST",
            });
            window.location.href = `/?c=${data.conversation_id}`;
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
            button.disabled = false;
        }
    }

    /* ------------------------------------------------------------------ */
    /* Import                                                             */
    /* ------------------------------------------------------------------ */

    function setPendingFile(file) {
        state.pendingFile = file || null;
        const selected = $("#file-selected");
        const name = $("#file-selected-name");
        if (file) {
            if (selected) selected.classList.remove("hidden");
            if (selected) selected.classList.add("flex");
            if (name) name.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} Mo`;
        } else {
            if (selected) selected.classList.add("hidden");
            if (selected) selected.classList.remove("flex");
            if (name) name.textContent = "";
        }
    }

    async function importFile(event) {
        event.preventDefault();
        if (state.busy) return;
        const fileInput = $("#dataset-file");
        const file = state.pendingFile || (fileInput.files && fileInput.files[0]);
        if (!file) {
            FG.toast("Sélectionnez d'abord un fichier.", "warning");
            return;
        }
        const button = $("#import-submit");
        const label = $("#import-label");
        const progress = $("#import-progress");
        state.busy = true;
        button.disabled = true;
        if (label) label.textContent = "Import et analyse…";
        if (progress) progress.classList.remove("hidden");
        const formData = new FormData();
        formData.append("file", file);
        try {
            const data = await FG.apiFetch("/api/datasets/import", {
                method: "POST",
                body: formData,
            });
            const imported = data.datasets || [];
            await refreshDatasetList();
            if (imported.length) {
                state.selected = imported[0];
                state.issueFilter = "all";
                state.columnQuery = "";
                renderDatasetList();
                renderReport();
                const url = new URL(window.location.href);
                url.searchParams.set("d", imported[0].id);
                window.history.replaceState({}, "", url);
            }
            setPendingFile(null);
            if (fileInput) fileInput.value = "";
            FG.toast(
                imported.length > 1
                    ? `${imported.length} jeux de données importés et analysés.`
                    : "Fichier importé et analysé.",
                "success",
                { hint: "Le résumé du jeu de données est disponible comme source dans le chat." }
            );
        } catch (error) {
            FG.toast(error.message, "error", { hint: error.hint });
        } finally {
            state.busy = false;
            button.disabled = false;
            if (label) label.textContent = "Importer et analyser";
            if (progress) progress.classList.add("hidden");
        }
    }

    function bindImport() {
        const input = $("#dataset-file");
        const dropZone = $("#drop-zone");
        const form = $("#import-form");
        const openImport = $("#open-import");
        const clearFile = $("#clear-file");

        if (openImport && input) {
            openImport.addEventListener("click", () => input.click());
        }
        if (input) {
            input.addEventListener("change", () => {
                setPendingFile(input.files && input.files[0]);
            });
        }
        if (form) form.addEventListener("submit", importFile);
        if (clearFile) {
            clearFile.addEventListener("click", () => {
                setPendingFile(null);
                if (input) input.value = "";
            });
        }
        if (dropZone) {
            ["dragenter", "dragover"].forEach((eventName) => {
                dropZone.addEventListener(eventName, (event) => {
                    event.preventDefault();
                    dropZone.classList.add("border-indigo-400", "bg-indigo-50");
                });
            });
            ["dragleave", "drop"].forEach((eventName) => {
                dropZone.addEventListener(eventName, (event) => {
                    event.preventDefault();
                    dropZone.classList.remove("border-indigo-400", "bg-indigo-50");
                });
            });
            dropZone.addEventListener("drop", (event) => {
                const file = event.dataTransfer && event.dataTransfer.files[0];
                if (file) setPendingFile(file);
            });
        }

        document.addEventListener("click", (event) => {
            const load = event.target.closest("[data-dataset-load]");
            if (load) {
                event.preventDefault();
                loadDataset(Number(load.dataset.datasetLoad));
            }
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderDatasetList();
        renderReport();
        bindImport();
    });
})();
