"""Couche SQLite : schéma, accès aux données et agrégats.

La base est créée automatiquement dans ``data/app.db`` au premier lancement.
Les requêtes sont paramétrées et les clés étrangères sont activées.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from seed_data import DOMAINS, SOURCES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"

ALLOWED_RATINGS = {1, 2, 3, 4, 5}
RATING_LABELS = {"satisfaisante", "moyenne", "insuffisante"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    slug TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '✦',
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Nouvelle conversation',
    domain TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_duration_ms INTEGER NOT NULL DEFAULT 0,
    message_count INTEGER NOT NULL DEFAULT 0,
    rating_sum INTEGER NOT NULL DEFAULT 0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (domain) REFERENCES domains(slug)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    rating INTEGER NOT NULL DEFAULT 0,
    rating_label TEXT,
    error_code TEXT,
    error_message TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'document',
    content TEXT NOT NULL,
    origin TEXT,
    created_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (domain) REFERENCES domains(slug)
);

CREATE TABLE IF NOT EXISTS message_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    source_id INTEGER,
    source_title TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'document',
    excerpt TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    rank INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    table_name TEXT,
    filename TEXT,
    file_type TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER NOT NULL DEFAULT 0,
    truncated_rows INTEGER NOT NULL DEFAULT 0,
    truncated_columns INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    quality_score REAL,
    report_json TEXT,
    source_id INTEGER,
    data_json TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS app_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_sources_domain
    ON sources(domain, is_active);
CREATE INDEX IF NOT EXISTS idx_message_sources_message
    ON message_sources(message_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated
    ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_datasets_imported
    ON datasets(imported_at DESC);
"""


def utc_now() -> str:
    """Horodatage ISO 8601 en UTC, comparable lexicographiquement."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as connection:
        connection.executescript(SCHEMA)
        _seed(connection)
        connection.commit()


def _seed(connection: sqlite3.Connection) -> None:
    for index, domain in enumerate(DOMAINS):
        connection.execute(
            """
            INSERT INTO domains(slug, label, icon, description, system_prompt, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                label = excluded.label,
                icon = excluded.icon,
                description = excluded.description,
                system_prompt = excluded.system_prompt,
                sort_order = excluded.sort_order
            """,
            (
                domain["slug"],
                domain["label"],
                domain["icon"],
                domain["description"],
                domain["system_prompt"],
                index,
            ),
        )

    existing = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    if existing == 0:
        now = utc_now()
        for source in SOURCES:
            connection.execute(
                """
                INSERT INTO sources(domain, title, kind, content, origin, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source["domain"],
                    source["title"],
                    source.get("kind", "document"),
                    source["content"],
                    source.get("origin"),
                    now,
                ),
            )


# --------------------------------------------------------------------------- #
# Domaines
# --------------------------------------------------------------------------- #


def list_domains(connection: sqlite3.Connection | None = None) -> list[dict]:
    own = connection is None
    connection = connection or connect()
    try:
        rows = connection.execute(
            "SELECT * FROM domains ORDER BY sort_order, label"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        if own:
            connection.close()


def get_domain(slug: str, connection: sqlite3.Connection | None = None) -> dict | None:
    own = connection is None
    connection = connection or connect()
    try:
        row = connection.execute(
            "SELECT * FROM domains WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own:
            connection.close()


# --------------------------------------------------------------------------- #
# Conversations
# --------------------------------------------------------------------------- #


def create_conversation(
    connection: sqlite3.Connection,
    domain: str = "general",
    title: str = "Nouvelle conversation",
) -> int:
    if not get_domain(domain, connection):
        domain = "general"
    now = utc_now()
    cursor = connection.execute(
        """
        INSERT INTO conversations(title, domain, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (title.strip() or "Nouvelle conversation", domain, now, now),
    )
    connection.commit()
    return int(cursor.lastrowid)


def get_conversation(connection: sqlite3.Connection, conversation_id: int) -> dict | None:
    row = connection.execute(
        """
        SELECT c.*, d.label AS domain_label, d.icon AS domain_icon,
               d.description AS domain_description
        FROM conversations c
        LEFT JOIN domains d ON d.slug = c.domain
        WHERE c.id = ?
        """,
        (conversation_id,),
    ).fetchone()
    return dict(row) if row else None


def list_conversations(
    connection: sqlite3.Connection, limit: int = 100
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT c.*, d.label AS domain_label, d.icon AS domain_icon,
               (SELECT substr(m.content, 1, 90)
                  FROM messages m
                 WHERE m.conversation_id = c.id
                 ORDER BY m.id DESC LIMIT 1) AS last_message,
               CASE WHEN c.rating_count > 0
                    THEN ROUND(1.0 * c.rating_sum / c.rating_count, 2)
                    ELSE NULL END AS rating_avg
        FROM conversations c
        LEFT JOIN domains d ON d.slug = c.domain
        ORDER BY c.updated_at DESC, c.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_conversation(
    connection: sqlite3.Connection, conversation_id: int, **fields: Any
) -> bool:
    allowed = {"title", "domain"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return False
    if "domain" in values and not get_domain(values["domain"], connection):
        values["domain"] = "general"
    if "title" in values:
        values["title"] = (str(values["title"]).strip() or "Nouvelle conversation")[:120]
    values["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in values)
    connection.execute(
        f"UPDATE conversations SET {assignments} WHERE id = ?",
        (*values.values(), conversation_id),
    )
    connection.commit()
    return True


def delete_conversation(connection: sqlite3.Connection, conversation_id: int) -> bool:
    cursor = connection.execute(
        "DELETE FROM conversations WHERE id = ?", (conversation_id,)
    )
    connection.commit()
    return cursor.rowcount > 0


def clear_conversation(connection: sqlite3.Connection, conversation_id: int) -> bool:
    connection.execute(
        "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
    )
    connection.execute(
        """
        UPDATE conversations
           SET total_tokens = 0, total_prompt_tokens = 0,
               total_completion_tokens = 0, total_duration_ms = 0,
               message_count = 0, rating_sum = 0, rating_count = 0,
               title = 'Nouvelle conversation',
               updated_at = ?
         WHERE id = ?
        """,
        (utc_now(), conversation_id),
    )
    connection.commit()
    return True


def recalc_conversation(connection: sqlite3.Connection, conversation_id: int) -> None:
    row = connection.execute(
        """
        SELECT COUNT(*) AS message_count,
               COALESCE(SUM(total_tokens), 0) AS total_tokens,
               COALESCE(SUM(prompt_tokens), 0) AS total_prompt_tokens,
               COALESCE(SUM(completion_tokens), 0) AS total_completion_tokens,
               COALESCE(SUM(duration_ms), 0) AS total_duration_ms,
               COALESCE(SUM(CASE WHEN rating > 0 THEN rating ELSE 0 END), 0) AS rating_sum,
               COALESCE(SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END), 0) AS rating_count
          FROM messages
         WHERE conversation_id = ?
        """,
        (conversation_id,),
    ).fetchone()
    connection.execute(
        """
        UPDATE conversations
           SET message_count = ?, total_tokens = ?, total_prompt_tokens = ?,
               total_completion_tokens = ?, total_duration_ms = ?,
               rating_sum = ?, rating_count = ?, updated_at = ?
         WHERE id = ?
        """,
        (
            row["message_count"],
            row["total_tokens"],
            row["total_prompt_tokens"],
            row["total_completion_tokens"],
            row["total_duration_ms"],
            row["rating_sum"],
            row["rating_count"],
            utc_now(),
            conversation_id,
        ),
    )
    connection.commit()


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #


def add_message(
    connection: sqlite3.Connection,
    conversation_id: int,
    role: str,
    content: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    duration_ms: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    error_code: str | None = None,
    error_message: str | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO messages(
            conversation_id, role, content, created_at, provider, model,
            duration_ms, prompt_tokens, completion_tokens, total_tokens,
            error_code, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            content,
            utc_now(),
            provider,
            model,
            int(duration_ms or 0),
            int(prompt_tokens or 0),
            int(completion_tokens or 0),
            int(total_tokens or 0),
            error_code,
            error_message,
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def get_message(connection: sqlite3.Connection, message_id: int) -> dict | None:
    row = connection.execute(
        "SELECT * FROM messages WHERE id = ?", (message_id,)
    ).fetchone()
    return dict(row) if row else None


def get_messages(
    connection: sqlite3.Connection,
    conversation_id: int,
    limit: int | None = None,
) -> list[dict]:
    sql = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id"
    params: tuple = (conversation_id,)
    if limit:
        sql = (
            "SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT ?) ORDER BY id"
        )
        params = (conversation_id, limit)
    rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def set_message_rating(
    connection: sqlite3.Connection,
    message_id: int,
    rating: int,
    label: str | None,
) -> dict | None:
    message = get_message(connection, message_id)
    if not message or message["role"] != "assistant":
        return None
    rating = int(rating) if int(rating) in ALLOWED_RATINGS else 0
    label = label if label in RATING_LABELS else None
    if rating == 0:
        label = None
    connection.execute(
        "UPDATE messages SET rating = ?, rating_label = ? WHERE id = ?",
        (rating, label, message_id),
    )
    connection.commit()
    recalc_conversation(connection, message["conversation_id"])
    return get_message(connection, message_id)


def set_message_error(
    connection: sqlite3.Connection,
    message_id: int,
    code: str,
    message: str,
) -> None:
    connection.execute(
        "UPDATE messages SET error_code = ?, error_message = ? WHERE id = ?",
        (code, message, message_id),
    )
    connection.commit()


def add_message_source(
    connection: sqlite3.Connection,
    message_id: int,
    *,
    source_id: int | None,
    title: str,
    kind: str,
    excerpt: str,
    score: float,
    rank: int,
) -> None:
    connection.execute(
        """
        INSERT INTO message_sources(
            message_id, source_id, source_title, source_kind, excerpt, score, rank
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, source_id, title, kind, excerpt, float(score), int(rank)),
    )
    connection.commit()


def get_message_sources(
    connection: sqlite3.Connection, message_id: int
) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM message_sources WHERE message_id = ? ORDER BY rank, id",
        (message_id,),
    ).fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# Sources documentaires
# --------------------------------------------------------------------------- #


def list_sources(
    connection: sqlite3.Connection,
    domain: str | None = None,
    active_only: bool = True,
    include_content: bool = False,
) -> list[dict]:
    clauses = []
    params: list[Any] = []
    if domain:
        clauses.append("domain = ?")
        params.append(domain)
    if active_only:
        clauses.append("is_active = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    columns = "*" if include_content else "id, domain, title, kind, origin, created_at, is_active"
    rows = connection.execute(
        f"SELECT {columns} FROM sources {where} ORDER BY kind, title",
        tuple(params),
    ).fetchall()
    return [dict(row) for row in rows]


def get_source(connection: sqlite3.Connection, source_id: int) -> dict | None:
    row = connection.execute(
        "SELECT * FROM sources WHERE id = ?", (source_id,)
    ).fetchone()
    return dict(row) if row else None


def add_source(
    connection: sqlite3.Connection,
    domain: str,
    title: str,
    content: str,
    *,
    kind: str = "document",
    origin: str | None = "Ajout manuel",
) -> int:
    if not get_domain(domain, connection):
        domain = "general"
    cursor = connection.execute(
        """
        INSERT INTO sources(domain, title, kind, content, origin, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (domain, title.strip()[:160], kind, content.strip(), origin, utc_now()),
    )
    connection.commit()
    return int(cursor.lastrowid)


def update_source(
    connection: sqlite3.Connection,
    source_id: int,
    *,
    title: str | None = None,
    content: str | None = None,
    is_active: bool | None = None,
) -> bool:
    fields: dict[str, Any] = {}
    if title is not None:
        fields["title"] = title.strip()[:160]
    if content is not None:
        fields["content"] = content.strip()
    if is_active is not None:
        fields["is_active"] = 1 if is_active else 0
    if not fields:
        return False
    assignments = ", ".join(f"{key} = ?" for key in fields)
    connection.execute(
        f"UPDATE sources SET {assignments} WHERE id = ?",
        (*fields.values(), source_id),
    )
    connection.commit()
    return True


def delete_source(connection: sqlite3.Connection, source_id: int) -> bool:
    cursor = connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    connection.commit()
    return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
# Conversation complète
# --------------------------------------------------------------------------- #


def get_conversation_bundle(
    connection: sqlite3.Connection, conversation_id: int
) -> dict | None:
    conversation = get_conversation(connection, conversation_id)
    if not conversation:
        return None
    messages = get_messages(connection, conversation_id)
    for message in messages:
        message["sources"] = (
            get_message_sources(connection, message["id"])
            if message["role"] == "assistant"
            else []
        )

    assistant_messages = [m for m in messages if m["role"] == "assistant"]
    rated = [m for m in assistant_messages if m["rating"] > 0]
    durations = [m["duration_ms"] for m in assistant_messages if m["duration_ms"] > 0]
    tokens = [m["total_tokens"] for m in assistant_messages if m["total_tokens"] > 0]

    stats = {
        "message_count": len(messages),
        "user_count": sum(1 for m in messages if m["role"] == "user"),
        "assistant_count": len(assistant_messages),
        "total_tokens": sum(m["total_tokens"] for m in assistant_messages),
        "prompt_tokens": sum(m["prompt_tokens"] for m in assistant_messages),
        "completion_tokens": sum(m["completion_tokens"] for m in assistant_messages),
        "avg_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
        "avg_tokens": round(sum(tokens) / len(tokens), 1) if tokens else 0,
        "avg_rating": round(sum(m["rating"] for m in rated) / len(rated), 2)
        if rated
        else None,
        "rated_count": len(rated),
        "errors": sum(1 for m in assistant_messages if m["error_code"]),
    }
    if stats["avg_duration_ms"]:
        stats["tokens_per_second"] = round(
            stats["completion_tokens"] / (stats["avg_duration_ms"] / 1000), 1
        ) if stats["completion_tokens"] else 0
    else:
        stats["tokens_per_second"] = 0
    conversation["messages"] = messages
    conversation["stats"] = stats
    return conversation


# --------------------------------------------------------------------------- #
# Jeux de données
# --------------------------------------------------------------------------- #


def add_dataset(
    connection: sqlite3.Connection,
    *,
    name: str,
    table_name: str | None,
    filename: str,
    file_type: str,
    row_count: int,
    column_count: int,
    data_json: str,
    truncated_rows: int = 0,
    truncated_columns: int = 0,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO datasets(
            name, table_name, filename, file_type, row_count, column_count,
            truncated_rows, truncated_columns, imported_at, data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            table_name,
            filename,
            file_type,
            row_count,
            column_count,
            truncated_rows,
            truncated_columns,
            utc_now(),
            data_json,
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_datasets(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT id, name, table_name, filename, file_type, row_count, column_count,
               truncated_rows, truncated_columns,
               imported_at, quality_score, source_id,
               CASE WHEN report_json IS NOT NULL THEN 1 ELSE 0 END AS has_report
        FROM datasets ORDER BY imported_at DESC, id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_dataset(
    connection: sqlite3.Connection, dataset_id: int, include_data: bool = False
) -> dict | None:
    row = connection.execute(
        "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
    ).fetchone()
    if not row:
        return None
    dataset = dict(row)
    if not include_data:
        dataset.pop("data_json", None)
    if dataset.get("report_json"):
        try:
            dataset["report"] = json.loads(dataset["report_json"])
        except (TypeError, ValueError):
            dataset["report"] = None
    else:
        dataset["report"] = None
    return dataset


def update_dataset_report(
    connection: sqlite3.Connection,
    dataset_id: int,
    report: dict,
    quality_score: float,
) -> None:
    connection.execute(
        "UPDATE datasets SET report_json = ?, quality_score = ? WHERE id = ?",
        (
            json.dumps(report, ensure_ascii=False),
            float(quality_score),
            dataset_id,
        ),
    )
    connection.commit()


def attach_dataset_source(
    connection: sqlite3.Connection, dataset_id: int, source_id: int
) -> None:
    connection.execute(
        "UPDATE datasets SET source_id = ? WHERE id = ?", (source_id, dataset_id)
    )
    connection.commit()


def delete_dataset(connection: sqlite3.Connection, dataset_id: int) -> bool:
    dataset = get_dataset(connection, dataset_id)
    if not dataset:
        return False
    if dataset.get("source_id"):
        connection.execute(
            "DELETE FROM sources WHERE id = ?", (dataset["source_id"],)
        )
    cursor = connection.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
    connection.commit()
    return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
# Statistiques
# --------------------------------------------------------------------------- #


def _percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def global_stats(connection: sqlite3.Connection) -> dict:
    conversations = connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0]
    messages = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    user_messages = connection.execute(
        "SELECT COUNT(*) FROM messages WHERE role = 'user'"
    ).fetchone()[0]
    assistant = connection.execute(
        "SELECT * FROM messages WHERE role = 'assistant'"
    ).fetchall()
    assistant_dicts = [dict(row) for row in assistant]

    durations = [m["duration_ms"] for m in assistant_dicts if m["duration_ms"] > 0]
    tokens = [m["total_tokens"] for m in assistant_dicts if m["total_tokens"] > 0]
    ratings = [m["rating"] for m in assistant_dicts if m["rating"] > 0]
    labels = {
        "satisfaisante": sum(
            1 for m in assistant_dicts if m["rating_label"] == "satisfaisante"
        ),
        "moyenne": sum(1 for m in assistant_dicts if m["rating_label"] == "moyenne"),
        "insuffisante": sum(
            1 for m in assistant_dicts if m["rating_label"] == "insuffisante"
        ),
    }
    errors = sum(1 for m in assistant_dicts if m["error_code"])
    rated = len(ratings)

    total_tokens = sum(tokens)
    total_duration = sum(durations)

    daily_rows = connection.execute(
        """
        SELECT substr(created_at, 1, 10) AS day,
               COUNT(*) AS messages,
               COALESCE(SUM(total_tokens), 0) AS tokens,
               COALESCE(AVG(CASE WHEN duration_ms > 0 THEN duration_ms END), 0) AS avg_ms
        FROM messages
        WHERE date(created_at) >= date('now', '-13 days')
        GROUP BY day ORDER BY day
        """
    ).fetchall()
    daily = [dict(row) for row in daily_rows]

    recent = connection.execute(
        """
        SELECT m.id, m.conversation_id, m.rating, m.rating_label, m.duration_ms,
               m.total_tokens, m.created_at, m.provider, m.error_code,
               substr(m.content, 1, 140) AS excerpt,
               c.title AS conversation_title, d.label AS domain_label
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN domains d ON d.slug = c.domain
        WHERE m.role = 'assistant'
        ORDER BY m.id DESC LIMIT 12
        """
    ).fetchall()

    top_conversations = connection.execute(
        """
        SELECT c.id, c.title, c.domain, d.label AS domain_label,
               c.total_tokens, c.total_duration_ms, c.rating_sum, c.rating_count,
               c.message_count,
               CASE WHEN c.rating_count > 0
                    THEN ROUND(1.0 * c.rating_sum / c.rating_count, 2) END AS rating_avg
        FROM conversations c
        LEFT JOIN domains d ON d.slug = c.domain
        WHERE c.message_count > 0
        ORDER BY c.total_tokens DESC, c.id DESC
        LIMIT 8
        """
    ).fetchall()

    return {
        "conversations": conversations,
        "messages": messages,
        "user_messages": user_messages,
        "assistant_messages": len(assistant_dicts),
        "avg_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
        "p50_duration_ms": _percentile(durations, 0.50),
        "p95_duration_ms": _percentile(durations, 0.95),
        "total_tokens": total_tokens,
        "avg_tokens": round(total_tokens / len(tokens), 1) if tokens else 0,
        "total_duration_ms": total_duration,
        "tokens_per_second": round(total_tokens / (total_duration / 1000), 1)
        if total_duration
        else 0,
        "rating_avg": round(sum(ratings) / rated, 2) if rated else None,
        "rated_count": rated,
        "rating_distribution": labels,
        "errors": errors,
        "success_rate": round(
            (len(assistant_dicts) - errors) / len(assistant_dicts) * 100, 1
        )
        if assistant_dicts
        else 100.0,
        "daily": daily,
        "recent_messages": [dict(row) for row in recent],
        "top_conversations": [dict(row) for row in top_conversations],
        "datasets": connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0],
        "sources": connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
    }


def log_event(
    connection: sqlite3.Connection, kind: str, detail: str = ""
) -> None:
    connection.execute(
        "INSERT INTO app_events(kind, detail, created_at) VALUES (?, ?, ?)",
        (kind, detail[:2000], utc_now()),
    )
    connection.commit()
