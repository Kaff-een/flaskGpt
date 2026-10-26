"""Sélection et extraction des passages utilisés comme sources.

La recherche est volontairement locale et déterministe : elle ne dépend
d'aucun service externe. Les paragraphes sont classés par recouvrement avec
les termes de la question, puis tronqués selon les préférences de l'utilisateur.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

STOPWORDS = {
    "a", "au", "aux", "avec", "ce", "ces", "cet", "cette", "dans", "de", "des",
    "du", "elle", "en", "est", "et", "eux", "il", "ils", "je", "la", "le",
    "les", "leur", "lui", "ma", "mais", "me", "meme", "mes", "moi", "mon",
    "ne", "nos", "notre", "nous", "on", "ou", "par", "pas", "pour", "qu",
    "que", "qui", "sa", "se", "ses", "son", "sur", "ta", "te", "tes", "toi",
    "ton", "tu", "un", "une", "vos", "votre", "vous", "y", "etre", "avoir",
    "faire", "plus", "moins", "comment", "pourquoi", "quel", "quelle", "quels",
    "quelles", "quoi", "dont", "si", "comme", "tout", "tous", "toute", "toutes",
    "sont", "sera", "seront", "ete", "peut", "peuvent", "doit", "doivent",
    "faut", "sans", "chez", "entre", "apres", "avant",
    "the", "and", "or", "of", "to", "in", "is", "are", "for", "with", "how",
}

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_'-]{1,}")

# Suffixes flexionnels français retirés pour rapprocher « structurer »,
# « structurée » ou « structuration ». On ne cherche pas une lemmatisation
# parfaite : l'objectif est que la question et les documents partagent le même
# radical de façon déterministe.
FLEXION_SUFFIXES = (
    "issements", "issement", "isations", "isation", "ements", "ement",
    "ations", "ation", "ateurs", "ateur", "euses", "euse", "ives", "ive",
    "eurs", "eur", "iser", "ités", "ité", "ites", "ite", "eux", "aux",
    "ées", "ée", "es", "er", "ez", "s", "e", "x",
)


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def stem(token: str) -> str:
    """Réduit un mot à un radical court, de façon conservative."""
    for _ in range(2):
        for suffix in FLEXION_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                token = token[: -len(suffix)]
                break
        else:
            break
    return token


def tokenize(text: str) -> list[str]:
    normalized = normalize(text)
    return [
        stem(token)
        for token in TOKEN_RE.findall(normalized)
        if token not in STOPWORDS and len(token) > 2
    ]


def _paragraphs(content: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    if len(blocks) > 1:
        return blocks
    # Un seul bloc : découper en groupes de phrases lisibles.
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(content.strip()) if s.strip()]
    chunks: list[str] = []
    for index in range(0, len(sentences), 3):
        chunks.append(" ".join(sentences[index:index + 3]))
    return chunks or [content.strip()]


def _truncate_lines(text: str, max_lines: int) -> str:
    if max_lines <= 0:
        return text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + " […]"
    if len(lines) <= 1:
        sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
        if len(sentences) > max_lines:
            return " ".join(sentences[:max_lines]) + " […]"
    return text


def _df_weights(query_terms: list[str], documents: list[tuple[set[str], Counter]]) -> dict[str, float]:
    """Pondère chaque terme par sa rareté dans le corpus (IDF adouci)."""
    total = max(1, len(documents))
    weights: dict[str, float] = {}
    for term in query_terms:
        df = sum(1 for title_terms, counts in documents if term in title_terms or term in counts)
        weights[term] = math.log(1.0 + (total + 1.0) / (df + 0.5))
    return weights


def _phrase_score(query_terms: list[str], paragraph_terms: list[str]) -> float:
    """Part des bigrammes de la question retrouvés dans un paragraphe."""
    if len(query_terms) < 2:
        return 0.0
    pairs = set(zip(query_terms, query_terms[1:]))
    paragraph_pairs = set(zip(paragraph_terms, paragraph_terms[1:]))
    return len(pairs & paragraph_pairs) / len(pairs)


def _score_paragraph(
    paragraph_terms: list[str],
    query_terms: list[str],
    weights: dict[str, float],
) -> float:
    if not paragraph_terms:
        return 0.0
    counts = Counter(paragraph_terms)
    score = 0.0
    for term in query_terms:
        frequency = counts.get(term, 0)
        if frequency:
            # La fréquence est saturée pour éviter qu'un mot répété domine.
            score += weights[term] * (1.0 + 0.25 * math.log1p(frequency))
    return score


def extract_excerpts(
    question: str,
    source: dict,
    max_excerpts: int = 2,
    max_lines: int = 4,
    *,
    weights: dict[str, float] | None = None,
) -> tuple[str, float, float]:
    """Retourne (extrait, score, couverture) pour une source.

    Le score combine la couverture pondérée des termes de la question, la
    concentration dans le meilleur paragraphe, la présence dans le titre et
    les bigrammes retrouvés. Il n'est donc plus relatif au seul document, ce
    qui évitait auparavant qu'un document ne contenant qu'un seul terme obtienne
    1,0 face à un document réellement plus pertinent.
    """
    query_terms = list(dict.fromkeys(tokenize(question)))
    title_terms = set(tokenize(source.get("title", "")))
    body_terms = tokenize(source.get("content", ""))
    body_counts = Counter(body_terms)
    paragraphs = _paragraphs(source.get("content", ""))
    if not paragraphs or not query_terms:
        return "", 0.0, 0.0

    if weights is None:
        weights = _df_weights(query_terms, [(title_terms, body_counts)])
    total_weight = sum(weights.get(term, 0.0) for term in query_terms) or 1.0

    ranked: list[tuple[int, float, str, list[str]]] = []
    for index, paragraph in enumerate(paragraphs):
        paragraph_terms = tokenize(paragraph)
        score = _score_paragraph(paragraph_terms, query_terms, weights)
        ranked.append((index, score, paragraph, paragraph_terms))

    positive = [item for item in ranked if item[1] > 0]
    if positive:
        positive.sort(key=lambda item: (-item[1], item[0]))
        selected = positive[:max_excerpts]
        selected.sort(key=lambda item: item[0])
    else:
        selected = ranked[:max_excerpts]

    matched = {term for term in query_terms if term in body_counts or term in title_terms}
    coverage = sum(weights.get(term, 0.0) for term in matched) / total_weight
    title_coverage = (
        sum(weights.get(term, 0.0) for term in matched if term in title_terms) / total_weight
    )
    focus = max((item[1] for item in ranked), default=0.0) / total_weight
    # Un paragraphe ne peut pas dépasser le poids total de la question.
    focus = min(1.0, focus)
    phrase = max((_phrase_score(query_terms, item[3]) for item in selected), default=0.0)

    score = 0.64 * coverage + 0.18 * focus + 0.12 * title_coverage + 0.06 * phrase
    score = min(1.0, max(0.0, score))

    pieces = []
    for _, _, paragraph, _ in selected:
        pieces.append(_truncate_lines(paragraph, max_lines))
    excerpt = "\n\n".join(pieces)
    return excerpt, round(score, 3), round(coverage, 3)


def retrieve_sources(
    connection,
    domain: str,
    question: str,
    source_ids: list[int] | None = None,
    *,
    excerpts_per_source: int = 2,
    lines_per_excerpt: int = 4,
    max_sources: int = 8,
    max_context_chars: int = 16000,
) -> list[dict]:
    """Sélectionne les sources et construit les extraits pertinents.

    ``source_ids=None`` signifie « toutes les sources actives du domaine ».
    Une liste vide signifie « aucune source ».
    """
    from db import list_sources  # import local pour éviter un cycle

    sources = list_sources(
        connection, domain=domain, active_only=True, include_content=True
    )
    if source_ids is not None:
        wanted = {int(source_id) for source_id in source_ids}
        sources = [source for source in sources if source["id"] in wanted]

    excerpts_per_source = max(1, min(int(excerpts_per_source), 5))
    lines_per_excerpt = max(1, min(int(lines_per_excerpt), 20))

    # Pondération IDF calculée sur l'ensemble des sources candidates : un terme
    # présent partout (ex. « réponse ») pèse moins qu'un terme spécifique.
    query_terms = list(dict.fromkeys(tokenize(question)))
    documents = [
        (
            set(tokenize(source.get("title", ""))),
            Counter(tokenize(source.get("content", ""))),
        )
        for source in sources
    ]
    weights = _df_weights(query_terms, documents)

    results: list[dict] = []
    for source in sources:
        excerpt, score, coverage = extract_excerpts(
            question, source, excerpts_per_source, lines_per_excerpt, weights=weights
        )
        if not excerpt:
            continue
        results.append(
            {
                "source_id": source["id"],
                "title": source["title"],
                "kind": source.get("kind", "document"),
                "origin": source.get("origin"),
                "excerpt": excerpt,
                "score": score,
                "coverage": coverage,
            }
        )

    # Si au moins une source est pertinente, ne pas encombrer le panneau avec
    # des documents sans aucun terme en commun. Une sélection explicite de
    # l'utilisateur est toujours conservée.
    if source_ids is None and any(item["score"] > 0 for item in results):
        results = [item for item in results if item["score"] > 0]

    results.sort(key=lambda item: (-item["score"], -item["coverage"], item["title"]))
    selected = results[:max_sources]

    # Respecter un budget de contexte tout en gardant au moins une source.
    total = 0
    trimmed: list[dict] = []
    for item in selected:
        length = len(item["excerpt"])
        if trimmed and total + length > max_context_chars:
            continue
        trimmed.append(item)
        total += length
    for rank, item in enumerate(trimmed, start=1):
        item["rank"] = rank
    return trimmed


def build_context(sources: list[dict]) -> str:
    if not sources:
        return ""
    blocks = []
    for source in sources:
        blocks.append(
            f"[Source {source['rank']} — {source['title']}]\n{source['excerpt']}"
        )
    return "\n\n".join(blocks)


def source_instruction(has_sources: bool) -> str:
    if has_sources:
        return (
            "Des sources numérotées sont fournies. Appuie chaque affirmation importante "
            "sur une source et cite-la entre crochets, par exemple [Source 1]. "
            "N'utilise que les informations réellement présentes dans les extraits. "
            "Si les sources ne permettent pas de répondre, dis-le explicitement. "
            "Ne fabrique jamais de citation ni de numéro de source."
        )
    return (
        "Aucune source documentaire n'est fournie. Réponds à partir de connaissances "
        "générales, en signalant clairement les limites et sans inventer de référence."
    )


def dataset_summary_source(report: dict, dataset: dict, sample_rows: list[dict]) -> str:
    """Transforme un rapport de qualité en source interrogeable dans le chat."""
    governance = report.get("governance", {})
    scores = report.get("scores", {})
    overview = report.get("overview", {})
    pii_columns = governance.get("pii_columns", [])
    pii_labels = [
        item.get("column", "") if isinstance(item, dict) else str(item)
        for item in pii_columns
    ]
    lines = [
        f"Jeu de données : {dataset['name']}"
        + (f" (table {dataset['table_name']})" if dataset.get("table_name") else ""),
        (
            f"{overview.get('rows', 0)} lignes, {overview.get('columns', 0)} colonnes. "
            f"Score global de qualité : {scores.get('global', 0)}/100. "
            f"Complétude : {scores.get('completude', 0)}/100. "
            f"Unicité : {scores.get('unicite', 0)}/100. "
            f"Cohérence : {scores.get('coherence', 0)}/100. "
            f"Validité : {scores.get('validite', 0)}/100."
        ),
        (
            f"Gouvernance : score {governance.get('score', 0)}/100. "
            f"Colonnes personnelles détectées : "
            f"{', '.join(label for label in pii_labels if label) or 'aucune'}."
        ),
    ]
    issues = report.get("issues", [])
    if issues:
        lines.append("Principaux problèmes :")
        for issue in issues[:8]:
            lines.append(
                f"- [{issue.get('severity', 'info')}] {issue.get('message', '')} "
                f"Recommandation : {issue.get('recommendation', '')}"
            )
    columns = report.get("columns", [])
    if columns:
        lines.append("Colonnes et complétude :")
        for column in columns[:20]:
            lines.append(
                f"- {column['name']} ({column.get('type', 'texte')}) : "
                f"{column.get('missing_pct', 0)} % de valeurs manquantes, "
                f"{column.get('unique', 0)} valeurs distinctes, "
                f"{column.get('outliers', 0)} valeurs atypiques."
            )
    if sample_rows:
        lines.append("Aperçu des premières lignes :")
        for row in sample_rows[:5]:
            lines.append(
                " | ".join(f"{key}={value}" for key, value in list(row.items())[:8])
            )
    return "\n\n".join(lines)


def ensure_dataset_source(
    connection,
    domain: str,
    dataset: dict,
    report: dict,
    sample_rows: list[dict],
):
    """Crée ou met à jour la source associée à un jeu de données."""
    from db import (
        add_source,
        attach_dataset_source,
        get_source,
        update_source,
    )

    title = f"Jeu de données — {dataset['name']}"[:160]
    content = dataset_summary_source(report, dataset, sample_rows)
    existing_id = dataset.get("source_id")
    if existing_id and get_source(connection, existing_id):
        update_source(connection, existing_id, title=title, content=content, is_active=True)
        return existing_id
    source_id = add_source(
        connection,
        domain=domain,
        title=title,
        content=content,
        kind="dataset",
        origin=dataset.get("filename") or "Import de données",
    )
    attach_dataset_source(connection, dataset["id"], source_id)
    return source_id
