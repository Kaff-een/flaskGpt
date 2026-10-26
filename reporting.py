"""Génération des synthèses, exports texte/JSON et documents PDF."""

from __future__ import annotations

import html
import io
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from sources import STOPWORDS, tokenize

APP_NAME = "FlaskGPT · Assistant augmenté"
ACCENT = colors.HexColor("#4f46e5")
DARK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f1f5f9")
BORDER = colors.HexColor("#e2e8f0")
GREEN = colors.HexColor("#059669")
AMBER = colors.HexColor("#d97706")
RED = colors.HexColor("#dc2626")
SOFT_GREEN = colors.HexColor("#ecfdf5")
SOFT_AMBER = colors.HexColor("#fffbeb")
SOFT_RED = colors.HexColor("#fef2f2")

_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONT_ITALIC = "Helvetica-Oblique"


def _register_fonts() -> None:
    global _FONT_REGULAR, _FONT_BOLD, _FONT_ITALIC
    candidates = [
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/ariali.ttf"),
        ),
        (
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/segoeuii.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
        ),
    ]
    for regular, bold, italic in candidates:
        if regular.exists() and bold.exists():
            try:
                pdfmetrics.registerFont(TTFont("AppRegular", str(regular)))
                pdfmetrics.registerFont(TTFont("AppBold", str(bold)))
                if italic.exists():
                    pdfmetrics.registerFont(TTFont("AppItalic", str(italic)))
                    _FONT_ITALIC = "AppItalic"
                else:
                    _FONT_ITALIC = "AppRegular"
                _FONT_REGULAR = "AppRegular"
                _FONT_BOLD = "AppBold"
                return
            except Exception:  # noqa: BLE001 - on retombe sur Helvetica
                continue


_register_fonts()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AppTitle",
            parent=base["Title"],
            fontName=_FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=DARK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "AppSubtitle",
            fontName=_FONT_REGULAR,
            fontSize=9.5,
            leading=13,
            textColor=MUTED,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "AppH1",
            fontName=_FONT_BOLD,
            fontSize=13,
            leading=17,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "AppH2",
            fontName=_FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=DARK,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "AppBody",
            fontName=_FONT_REGULAR,
            fontSize=9.8,
            leading=14,
            textColor=DARK,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "AppSmall",
            fontName=_FONT_REGULAR,
            fontSize=8.2,
            leading=11,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "AppBullet",
            fontName=_FONT_REGULAR,
            fontSize=9.6,
            leading=13.5,
            textColor=DARK,
            leftIndent=10,
            bulletIndent=2,
            spaceAfter=3,
        ),
        "cell": ParagraphStyle(
            "AppCell",
            fontName=_FONT_REGULAR,
            fontSize=8,
            leading=10.5,
            textColor=DARK,
        ),
        "cell_bold": ParagraphStyle(
            "AppCellBold",
            fontName=_FONT_BOLD,
            fontSize=8,
            leading=10.5,
            textColor=DARK,
        ),
        "quote": ParagraphStyle(
            "AppQuote",
            fontName=_FONT_ITALIC,
            fontSize=9,
            leading=13,
            textColor=MUTED,
            leftIndent=10,
            spaceAfter=5,
        ),
    }


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _inline_markdown(text: str) -> str:
    text = _esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(
        r"\[(Source \d+)\]",
        r"<font color='#4f46e5'><b>[\1]</b></font>",
        text,
    )
    return text


def markdown_flowables(text: str, styles: dict, *, compact: bool = False) -> list:
    """Convertit un Markdown simple en paragraphes ReportLab."""
    flowables: list = []
    lines = (text or "").replace("\r\n", "\n").split("\n")
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph if part.strip())
            if joined:
                flowables.append(Paragraph(_inline_markdown(joined), styles["body"]))
            paragraph.clear()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("```"):
            flush()
            continue
        if stripped.startswith("#"):
            flush()
            level = len(stripped) - len(stripped.lstrip("#"))
            label = stripped.lstrip("#").strip()
            if label:
                flowables.append(
                    Paragraph(_esc(label), styles["h2" if level > 1 else "h1"])
                )
            continue
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        numbered = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if bullet or numbered:
            flush()
            label = bullet.group(1) if bullet else numbered.group(2)
            prefix = "•" if bullet else f"{numbered.group(1)}."
            flowables.append(
                Paragraph(
                    f"{prefix} {_inline_markdown(label)}",
                    styles["bullet"],
                )
            )
            continue
        if stripped.startswith(">"):
            flush()
            flowables.append(
                Paragraph(_inline_markdown(stripped.lstrip("> ").strip()), styles["quote"])
            )
            continue
        paragraph.append(stripped)
    flush()
    if compact:
        return flowables or [Paragraph("—", styles["small"])]
    return flowables


def clean_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " [code] ", text or "", flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"\[Source \d+\]", " ", text)
    text = re.sub(r"^[#>\-\*\d.\s]+", " ", text, flags=re.M)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _sentences(text: str) -> list[str]:
    cleaned = clean_markdown(text)
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if 12 <= len(part.strip()) <= 400]


def extractive_summary(messages: list[dict], max_points: int = 8) -> dict:
    questions: list[str] = []
    for message in messages:
        if message.get("role") != "user":
            continue
        question = clean_markdown(message.get("content", ""))
        if question and question not in questions:
            questions.append(question[:260])
    questions = questions[:8]

    sentences: list[str] = []
    for message in messages:
        if message.get("role") != "assistant" or message.get("error_code"):
            continue
        sentences.extend(_sentences(message.get("content", "")))

    frequencies: Counter = Counter()
    tokenized: list[list[str]] = []
    for sentence in sentences:
        tokens = tokenize(sentence)
        tokenized.append(tokens)
        frequencies.update(tokens)
    stop = set(STOPWORDS)
    for word in list(frequencies):
        if word in stop or len(word) < 4:
            frequencies.pop(word, None)

    scored: list[tuple[float, int, str]] = []
    seen: set[str] = set()
    for index, (sentence, tokens) in enumerate(zip(sentences, tokenized)):
        normalized = sentence.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if not tokens:
            score = 0.0
        else:
            score = sum(frequencies.get(token, 0) for token in set(tokens)) / (
                len(tokens) ** 0.6
            )
        scored.append((score, index, sentence))

    scored.sort(key=lambda item: (-item[0], item[1]))
    points = [sentence for _, _, sentence in scored[:max_points]]
    points.sort(key=lambda sentence: sentences.index(sentence) if sentence in sentences else 0)

    return {
        "questions": questions,
        "points": points,
        "main_question": questions[0] if questions else "",
        "answer_count": sum(
            1
            for message in messages
            if message.get("role") == "assistant" and not message.get("error_code")
        ),
    }


def safe_filename(value: str, fallback: str = "export") -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", normalized).strip("-._")
    return normalized[:80] or fallback


def conversation_to_json(bundle: dict) -> str:
    payload = {
        "application": APP_NAME,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "conversation": {
            key: value
            for key, value in bundle.items()
            if key != "messages"
        },
        "messages": bundle.get("messages", []),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def conversation_to_text(bundle: dict) -> str:
    conversation = bundle
    stats = conversation.get("stats", {})
    lines = [
        "=" * 78,
        f"{APP_NAME} — EXPORT DE CONVERSATION",
        "=" * 78,
        f"Titre        : {conversation.get('title', '')}",
        f"Domaine      : {conversation.get('domain_label', conversation.get('domain', ''))}",
        f"Créée le     : {conversation.get('created_at', '')}",
        f"Mise à jour  : {conversation.get('updated_at', '')}",
        f"Messages     : {stats.get('message_count', 0)}",
        f"Tokens       : {stats.get('total_tokens', 0)}",
        f"Temps moyen  : {stats.get('avg_duration_ms', 0)} ms",
        f"Note moyenne : {stats.get('avg_rating') if stats.get('avg_rating') is not None else 'non notée'} / 5",
        "=" * 78,
        "",
    ]
    for message in conversation.get("messages", []):
        role = "UTILISATEUR" if message["role"] == "user" else "ASSISTANT"
        lines.append("-" * 78)
        lines.append(f"[{role}] {message.get('created_at', '')}")
        if message["role"] == "assistant":
            lines.append(
                f"Modèle : {message.get('provider') or '—'} / {message.get('model') or '—'} · "
                f"{message.get('duration_ms', 0)} ms · {message.get('total_tokens', 0)} tokens"
            )
            if message.get("rating"):
                lines.append(
                    f"Évaluation : {message['rating']}/5 "
                    f"({message.get('rating_label') or 'sans libellé'})"
                )
            if message.get("error_code"):
                lines.append(
                    f"ERREUR [{message['error_code']}] : {message.get('error_message', '')}"
                )
        lines.append("")
        lines.append(message.get("content", ""))
        if message.get("sources"):
            lines.append("")
            lines.append("Sources :")
            for source in message["sources"]:
                lines.append(
                    f"  [Source {source['rank']}] {source['source_title']} "
                    f"(pertinence {round((source.get('score') or 0) * 100)} %)"
                )
                excerpt = " ".join(source.get("excerpt", "").split())
                lines.append(f"      {excerpt[:400]}")
        lines.append("")
    lines.append("=" * 78)
    lines.append(f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.")
    return "\n".join(lines)


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(_FONT_REGULAR, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, APP_NAME)
    canvas.drawRightString(
        A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}"
    )
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
    canvas.restoreState()


def _new_document(buffer: io.BytesIO, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title=title,
        author=APP_NAME,
    )


def _score_color(value: float) -> colors.Color:
    if value >= 80:
        return GREEN
    if value >= 60:
        return AMBER
    return RED


def _hex(color: colors.Color) -> str:
    raw = color.hexval()
    return "#" + raw[2:] if raw.startswith("0x") else raw


def _meta_table(rows: list[tuple[str, str]], styles: dict) -> Table:
    data = [
        [Paragraph(f"<b>{_esc(label)}</b>", styles["cell"]), Paragraph(_esc(value), styles["cell"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[42 * mm, 120 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _metric_band(bundle: dict, styles: dict) -> Table:
    stats = bundle.get("stats", {})
    rating = stats.get("avg_rating")
    values = [
        ("Messages", str(stats.get("message_count", 0))),
        ("Temps moyen", f"{stats.get('avg_duration_ms', 0)} ms"),
        ("Tokens", f"{stats.get('total_tokens', 0):,}".replace(",", " ")),
        ("Note", f"{rating}/5" if rating is not None else "—"),
    ]
    data = [
        [Paragraph(_esc(label), styles["small"]) for label, _ in values],
        [
            Paragraph(
                f"<b>{_esc(value)}</b>",
                ParagraphStyle(
                    "MetricValue",
                    fontName=_FONT_BOLD,
                    fontSize=13,
                    leading=16,
                    textColor=DARK,
                ),
            )
            for _, value in values
        ],
    ]
    table = Table(data, colWidths=[40.5 * mm] * 4)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def build_summary_pdf(bundle: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    styles = _styles()
    summary = extractive_summary(bundle.get("messages", []))
    doc = _new_document(buffer, f"Synthèse — {bundle.get('title', '')}")
    story = [
        Paragraph("Synthèse de conversation", styles["title"]),
        Paragraph(
            f"{_esc(bundle.get('domain_label', 'Général'))} · "
            f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            styles["subtitle"],
        ),
        _metric_band(bundle, styles),
        Spacer(1, 6 * mm),
        _meta_table(
            [
                ("Titre", bundle.get("title", "")),
                ("Domaine", bundle.get("domain_label", bundle.get("domain", ""))),
                ("Créée le", bundle.get("created_at", "")),
                ("Dernière activité", bundle.get("updated_at", "")),
                ("Sources consultées", str(
                    len({
                        source["source_title"]
                        for message in bundle.get("messages", [])
                        for source in message.get("sources", [])
                    })
                )),
            ],
            styles,
        ),
        Spacer(1, 4 * mm),
        Paragraph("Objet de la conversation", styles["h1"]),
        Paragraph(
            _esc(
                summary["main_question"]
                or "Conversation sans question enregistrée."
            ),
            styles["body"],
        ),
    ]

    if summary["questions"]:
        story.append(Paragraph("Questions abordées", styles["h1"]))
        for question in summary["questions"]:
            story.append(
                Paragraph(
                    f"• {_esc(question)}",
                    styles["bullet"],
                )
            )

    story.append(Paragraph("Points clés", styles["h1"]))
    if summary["points"]:
        for point in summary["points"]:
            story.append(Paragraph(f"• {_esc(point)}", styles["bullet"]))
    else:
        story.append(
            Paragraph(
                "Aucune réponse exploitable n'a encore été générée dans cette conversation.",
                styles["body"],
            )
        )

    sources: dict[str, dict] = {}
    for message in bundle.get("messages", []):
        for source in message.get("sources", []):
            sources.setdefault(source["source_title"], source)
    if sources:
        story.append(Paragraph("Sources mobilisées", styles["h1"]))
        for source in sources.values():
            story.append(
                Paragraph(
                    f"<b>{_esc(source['source_title'])}</b> — "
                    f"{_esc(source.get('source_kind', 'document'))}",
                    styles["body"],
                )
            )
            excerpt = " ".join((source.get("excerpt") or "").split())
            story.append(Paragraph(_esc(excerpt[:420]), styles["small"]))

    story.append(Paragraph("Indicateurs de qualité", styles["h1"]))
    stats = bundle.get("stats", {})
    story.append(
        _meta_table(
            [
                ("Réponses générées", str(stats.get("assistant_count", 0))),
                ("Temps de réponse moyen", f"{stats.get('avg_duration_ms', 0)} ms"),
                ("Tokens consommés", str(stats.get("total_tokens", 0))),
                ("Tokens par réponse", str(stats.get("avg_tokens", 0))),
                ("Note moyenne", f"{stats.get('avg_rating')}/5" if stats.get("avg_rating") is not None else "non notée"),
                ("Réponses évaluées", str(stats.get("rated_count", 0))),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(
        Paragraph(
            "Synthèse automatique par extraction de phrases. Elle ne remplace pas "
            "la lecture des réponses complètes et des documents sources.",
            styles["small"],
        )
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer


def build_export_pdf(bundle: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    styles = _styles()
    doc = _new_document(buffer, f"Conversation — {bundle.get('title', '')}")
    story = [
        Paragraph("Conversation complète", styles["title"]),
        Paragraph(
            f"{_esc(bundle.get('domain_label', 'Général'))} · "
            f"Export du {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            styles["subtitle"],
        ),
        _metric_band(bundle, styles),
        Spacer(1, 5 * mm),
    ]

    for message in bundle.get("messages", []):
        is_user = message.get("role") == "user"
        label = "Utilisateur" if is_user else "Assistant"
        color = ACCENT if is_user else GREEN
        story.append(
            Paragraph(
                f"<font color='{_hex(color)}'><b>{label}</b></font> "
                f"<font color='#94a3b8' size='7.5'>{_esc(message.get('created_at', ''))}</font>",
                styles["h2"],
            )
        )
        if not is_user:
            meta = (
                f"{message.get('provider') or '—'} · {message.get('model') or '—'} · "
                f"{message.get('duration_ms', 0)} ms · {message.get('total_tokens', 0)} tokens"
            )
            if message.get("rating"):
                meta += f" · note {message['rating']}/5 ({message.get('rating_label') or '—'})"
            story.append(Paragraph(_esc(meta), styles["small"]))
            story.append(Spacer(1, 1.5 * mm))
            if message.get("error_code"):
                story.append(
                    Paragraph(
                        f"<font color='#dc2626'><b>Erreur [{_esc(message['error_code'])}]</b> "
                        f"{_esc(message.get('error_message', ''))}</font>",
                        styles["body"],
                    )
                )
            else:
                story.extend(markdown_flowables(message.get("content", ""), styles))
            if message.get("sources"):
                story.append(Spacer(1, 1.5 * mm))
                story.append(Paragraph("Sources", styles["h2"]))
                for source in message["sources"]:
                    story.append(
                        Paragraph(
                            f"<b>[Source {source['rank']}] {_esc(source['source_title'])}</b> "
                            f"<font color='#64748b'>(pertinence {round((source.get('score') or 0) * 100)} %)</font>",
                            styles["body"],
                        )
                    )
                    excerpt = " ".join((source.get("excerpt") or "").split())
                    story.append(Paragraph(_esc(excerpt[:500]), styles["small"]))
        else:
            story.append(Paragraph(_esc(message.get("content", "")), styles["body"]))
        story.append(Spacer(1, 4 * mm))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer


def _score_table(report: dict, styles: dict) -> Table:
    scores = report.get("scores", {})
    rows = [
        [
            Paragraph("<b>Dimension</b>", styles["cell_bold"]),
            Paragraph("<b>Score</b>", styles["cell_bold"]),
            Paragraph("<b>Interprétation</b>", styles["cell_bold"]),
        ]
    ]
    labels = {
        "completude": "Complétude",
        "unicite": "Unicité",
        "coherence": "Cohérence",
        "validite": "Validité",
    }
    for key, label in labels.items():
        score = float(scores.get(key, 0))
        state = "Bon" if score >= 80 else "À améliorer" if score >= 60 else "Critique"
        rows.append(
            [
                Paragraph(_esc(label), styles["cell"]),
                Paragraph(
                    f"<font color='{_hex(_score_color(score))}'><b>{score}/100</b></font>",
                    styles["cell"],
                ),
                Paragraph(_esc(state), styles["cell"]),
            ]
        )
    global_score = float(scores.get("global", 0))
    rows.append(
        [
            Paragraph("<b>Score global</b>", styles["cell_bold"]),
            Paragraph(
                f"<font color='{_hex(_score_color(global_score))}'><b>{global_score}/100</b></font>",
                styles["cell_bold"],
            ),
            Paragraph(
                f"<b>{_esc(report.get('governance', {}).get('risk', ''))}</b>",
                styles["cell_bold"],
            ),
        ]
    )
    table = Table(rows, colWidths=[50 * mm, 35 * mm, 77 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_analysis_pdf(dataset: dict, report: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    styles = _styles()
    doc = _new_document(buffer, f"Qualité — {dataset.get('name', '')}")
    overview = report.get("overview", {})
    governance = report.get("governance", {})
    story = [
        Paragraph("Rapport de qualité et de gouvernance", styles["title"]),
        Paragraph(
            f"{_esc(dataset.get('name', ''))} · "
            f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            styles["subtitle"],
        ),
        Paragraph("Vue d'ensemble", styles["h1"]),
        _meta_table(
            [
                ("Fichier", dataset.get("filename", "")),
                ("Table", dataset.get("table_name") or "—"),
                ("Lignes", str(overview.get("rows", 0))),
                ("Colonnes", str(overview.get("columns", 0))),
                ("Valeurs manquantes", f"{overview.get('missing_pct', 0)} %"),
                ("Lignes dupliquées", f"{overview.get('duplicate_rows', 0)} ({overview.get('duplicate_pct', 0)} %)"),
                ("Risque de gouvernance", governance.get("risk", "—")),
            ],
            styles,
        ),
        Spacer(1, 4 * mm),
        Paragraph("Scores par dimension", styles["h1"]),
        _score_table(report, styles),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Score de gouvernance : <b>{governance.get('score', 0)}/100</b> · "
            f"colonnes personnelles : <b>{governance.get('pii_count', 0)}</b> · "
            f"documentation : <b>{governance.get('documentation_score', 0)}/100</b>.",
            styles["body"],
        ),
    ]

    issues = report.get("issues", [])
    story.append(Paragraph("Problèmes détectés", styles["h1"]))
    if issues:
        rows = [
            [
                Paragraph("<b>Gravité</b>", styles["cell_bold"]),
                Paragraph("<b>Catégorie</b>", styles["cell_bold"]),
                Paragraph("<b>Constat</b>", styles["cell_bold"]),
            ]
        ]
        for issue in issues[:40]:
            rows.append(
                [
                    Paragraph(_esc(issue.get("severity", "")), styles["cell"]),
                    Paragraph(_esc(issue.get("category", "")), styles["cell"]),
                    Paragraph(_esc(issue.get("message", "")), styles["cell"]),
                ]
            )
        table = Table(rows, colWidths=[22 * mm, 27 * mm, 113 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                    ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
        if len(issues) > 40:
            story.append(
                Paragraph(
                    f"{len(issues) - 40} problème(s) supplémentaire(s) dans le rapport JSON.",
                    styles["small"],
                )
            )
    else:
        story.append(Paragraph("Aucun problème détecté.", styles["body"]))

    columns = report.get("columns", [])
    if columns:
        story.append(Paragraph("Profil des colonnes", styles["h1"]))
        rows = [
            [
                Paragraph("<b>Colonne</b>", styles["cell_bold"]),
                Paragraph("<b>Type</b>", styles["cell_bold"]),
                Paragraph("<b>Manquants</b>", styles["cell_bold"]),
                Paragraph("<b>Uniques</b>", styles["cell_bold"]),
                Paragraph("<b>Atypiques</b>", styles["cell_bold"]),
                Paragraph("<b>Validité</b>", styles["cell_bold"]),
            ]
        ]
        for column in columns[:60]:
            rows.append(
                [
                    Paragraph(_esc(column.get("name", ""))[:40], styles["cell"]),
                    Paragraph(_esc(column.get("type", "")), styles["cell"]),
                    Paragraph(f"{column.get('missing_pct', 0)} %", styles["cell"]),
                    Paragraph(str(column.get("unique", 0)), styles["cell"]),
                    Paragraph(
                        f"{column.get('outliers', 0)} ({column.get('outlier_pct', 0)} %)",
                        styles["cell"],
                    ),
                    Paragraph(f"{column.get('valid_pct', 100)} %", styles["cell"]),
                ]
            )
        table = Table(
            rows,
            colWidths=[50 * mm, 22 * mm, 22 * mm, 20 * mm, 28 * mm, 26 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                    ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    pii = governance.get("pii_columns", [])
    if pii:
        story.append(Paragraph("Données personnelles détectées", styles["h1"]))
        for item in pii:
            story.append(
                Paragraph(
                    f"• <b>{_esc(item.get('column', ''))}</b> — "
                    f"{_esc(item.get('label', ''))} "
                    f"(sensibilité {_esc(item.get('sensitivity', ''))}, "
                    f"preuve : {_esc(item.get('evidence', ''))})",
                    styles["bullet"],
                )
            )
        story.append(
            Paragraph(
                "Ces détections sont heuristiques. Elles ne constituent pas une "
                "analyse de conformité juridique complète.",
                styles["small"],
            )
        )

    recommendations = report.get("recommendations", [])
    if recommendations:
        story.append(Paragraph("Recommandations", styles["h1"]))
        for recommendation in recommendations:
            story.append(Paragraph(f"• {_esc(recommendation)}", styles["bullet"]))

    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "Rapport généré automatiquement à partir du fichier importé. "
            "Les scores sont des indicateurs heuristiques à valider par les "
            "propriétaires métier.",
            styles["small"],
        )
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer
