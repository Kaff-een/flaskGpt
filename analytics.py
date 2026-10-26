"""Import de jeux de données et diagnostic de qualité / gouvernance.

Le module accepte CSV, TSV, Excel, JSON et bases SQLite. Il produit un rapport
JSON exploitable par l'interface : scores par dimension, problèmes classés par
gravité, anomalies, colonnes personnelles et recommandations.
"""

from __future__ import annotations

import io
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

MAX_ROWS = 50_000
MAX_COLUMNS = 200
MAX_SQLITE_TABLES = 10
ALLOWED_EXTENSIONS = {
    ".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".jsonl",
    ".db", ".sqlite", ".sqlite3",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{5,19}$")
IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$")
DATE_NAME_RE = re.compile(
    r"(date|dat|naissance|birth|echeance|échéance|created|updated|debut|début|fin|"
    r"expiration|validite|validité|mois|annee|année|jour)",
    re.IGNORECASE,
)
EMAIL_NAME_RE = re.compile(r"(email|mail|courriel)", re.IGNORECASE)
PHONE_NAME_RE = re.compile(r"(tel|phone|mobile|portable|fax)", re.IGNORECASE)
ID_NAME_RE = re.compile(
    r"(^id$|_id$|identifiant|code|reference|référence|numero|numéro|key|cle|clé)",
    re.IGNORECASE,
)
PII_NAME_PATTERNS: list[tuple[str, str, str, re.Pattern]] = [
    ("Coordonnées bancaires", "élevée", "bancaire", re.compile(r"(iban|bic|rib|compte|carte|card|cb|paiement|payment)", re.I)),
    ("Identifiant sensible", "élevée", "identifiant", re.compile(r"(ssn|social|secu|sécu|nir|passport|passeport|cin|nif|permis|license)", re.I)),
    ("Adresse électronique", "modérée", "email", re.compile(r"(email|mail|courriel)", re.I)),
    ("Numéro de téléphone", "modérée", "téléphone", re.compile(r"(tel|phone|mobile|portable|fax)", re.I)),
    ("Adresse postale", "modérée", "adresse", re.compile(r"(adresse|address|rue|street|ville|city|zip|postal)", re.I)),
    ("Nom ou prénom", "modérée", "nom", re.compile(r"(^nom$|nom_|_nom|prenom|prénom|lastname|firstname|fullname|surname)", re.I)),
    ("Date de naissance", "élevée", "date de naissance", re.compile(r"(naissance|birth)", re.I)),
    ("Donnée de santé", "élevée", "santé", re.compile(r"(sante|santé|maladie|diagnostic|patient|traitement|ordonnance)", re.I)),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, (int, bool, str)):
        return value
    return str(value)


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    names: list[str] = []
    seen: dict[str, int] = {}
    for index, raw in enumerate(df.columns):
        name = str(raw).replace("\ufeff", "").strip()
        if not name or name.lower().startswith("unnamed"):
            name = f"colonne_{index + 1}"
        base = name
        if base in seen:
            seen[base] += 1
            name = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
        names.append(name)
    df.columns = names
    return df


def _prepare_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    truncated_rows = max(0, len(df) - MAX_ROWS)
    truncated_columns = max(0, len(df.columns) - MAX_COLUMNS)
    df = df.iloc[:MAX_ROWS, :MAX_COLUMNS].copy()
    df = _clean_columns(df)
    df = df.replace([float("inf"), float("-inf")], pd.NA)
    return df, truncated_rows, truncated_columns


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        for separator in (None, ";", ",", "\t"):
            try:
                options: dict[str, Any] = {
                    "encoding": encoding,
                    "on_bad_lines": "skip",
                }
                if separator is None:
                    options.update(sep=None, engine="python")
                else:
                    options["sep"] = separator
                frame = pd.read_csv(path, **options)
                if frame.shape[1] >= 1:
                    return frame
            except Exception as exc:  # noqa: BLE001 - on essaie plusieurs formats
                last_error = exc
    raise ValueError(
        "Impossible de lire le fichier CSV. Vérifiez le séparateur et l'encodage."
    ) from last_error


def _read_json(path: Path) -> pd.DataFrame:
    try:
        return pd.read_json(path, lines=True)
    except ValueError:
        pass
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return pd.json_normalize(payload)
    if isinstance(payload, dict):
        for key in ("data", "rows", "records", "items", "results"):
            if isinstance(payload.get(key), list):
                return pd.json_normalize(payload[key])
        try:
            return pd.json_normalize(payload)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                "Le JSON doit contenir une liste d'objets ou un tableau de données."
            ) from exc
    raise ValueError("Format JSON non pris en charge.")


def _read_sqlite(path: Path) -> list[tuple[str, pd.DataFrame]]:
    tables: list[tuple[str, pd.DataFrame]] = []
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        for table in names[:MAX_SQLITE_TABLES]:
            try:
                frame = pd.read_sql_query(
                    f'SELECT * FROM "{table.replace(chr(34), chr(34) * 2)}" '
                    f"LIMIT {MAX_ROWS + 1}",
                    connection,
                )
                tables.append((table, frame))
            except Exception:  # noqa: BLE001 - table illisible, on continue
                continue
    finally:
        connection.close()
    if not tables:
        raise ValueError("Aucune table lisible trouvée dans cette base SQLite.")
    return tables


def parse_file(path: Path, filename: str) -> list[dict]:
    """Retourne une liste de jeux de données : nom, table, DataFrame, type."""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Format non pris en charge. Utilisez CSV, TSV, Excel, JSON ou SQLite."
        )
    base_name = Path(filename).stem or "jeu_de_donnees"
    file_type = extension.lstrip(".")
    datasets: list[dict] = []

    if extension in {".db", ".sqlite", ".sqlite3"}:
        for table, frame in _read_sqlite(path):
            datasets.append(
                {
                    "name": f"{base_name} · {table}",
                    "table_name": table,
                    "dataframe": frame,
                    "file_type": file_type,
                }
            )
    elif extension in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None)
        for sheet, frame in sheets.items():
            if frame is None or frame.empty:
                continue
            datasets.append(
                {
                    "name": f"{base_name} · {sheet}",
                    "table_name": str(sheet),
                    "dataframe": frame,
                    "file_type": file_type,
                }
            )
        if not datasets:
            raise ValueError("Le classeur ne contient aucune feuille exploitable.")
    elif extension in {".json", ".jsonl"}:
        frame = _read_json(path)
        datasets.append(
            {
                "name": base_name,
                "table_name": None,
                "dataframe": frame,
                "file_type": file_type,
            }
        )
    else:
        frame = _read_csv(path)
        datasets.append(
            {
                "name": base_name,
                "table_name": None,
                "dataframe": frame,
                "file_type": file_type,
            }
        )

    prepared = []
    for dataset in datasets:
        frame, truncated_rows, truncated_columns = _prepare_frame(
            dataset["dataframe"]
        )
        if frame.empty and len(frame.columns) == 0:
            continue
        dataset["dataframe"] = frame
        dataset["truncated_rows"] = truncated_rows
        dataset["truncated_columns"] = truncated_columns
        prepared.append(dataset)
    if not prepared:
        raise ValueError("Le fichier ne contient aucune donnée exploitable.")
    return prepared


def dataframe_to_json(df: pd.DataFrame) -> str:
    return df.to_json(
        orient="split",
        date_format="iso",
        force_ascii=False,
        default_handler=str,
    )


def json_to_dataframe(payload: str) -> pd.DataFrame:
    return pd.read_json(io.StringIO(payload), orient="split")


def _to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = (
        series.astype(str)
        .str.replace("\u202f", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _to_datetime(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed", dayfirst=True)
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce", dayfirst=True)


def _detect_type(series: pd.Series, name: str) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "booléen"
    if pd.api.types.is_numeric_dtype(series):
        return "numérique"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    non_null = series.dropna()
    if non_null.empty:
        return "vide"
    sample = non_null.astype(str).head(300)
    numeric_ratio = float(_to_numeric(sample).notna().mean())
    if numeric_ratio >= 0.9:
        return "numérique"
    if DATE_NAME_RE.search(name):
        date_ratio = float(_to_datetime(sample).notna().mean())
        if date_ratio >= 0.7:
            return "date"
    date_ratio = float(_to_datetime(sample).notna().mean())
    if date_ratio >= 0.9:
        # Éviter de classer des identifiants numériques comme des dates.
        if numeric_ratio < 0.8:
            return "date"
    return "texte"


def _luhn(number: str) -> bool:
    digits = [int(char) for char in number if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _pii_for_column(series: pd.Series, name: str) -> dict | None:
    for label, sensitivity, kind, pattern in PII_NAME_PATTERNS:
        if pattern.search(name):
            return {"type": kind, "label": label, "sensitivity": sensitivity, "evidence": "nom de colonne"}
    non_null = series.dropna().astype(str).head(500)
    if non_null.empty:
        return None
    email_ratio = float(non_null.str.match(EMAIL_RE).mean())
    if email_ratio >= 0.5:
        return {"type": "email", "label": "Adresse électronique", "sensitivity": "modérée", "evidence": "format des valeurs"}
    # Un montant ou un salaire peut ressembler à un numéro de téléphone : on
    # n'utilise ce contrôle que sur des valeurs non numériques.
    numeric_ratio = float(_to_numeric(non_null).notna().mean())
    phone_ratio = (
        0.0
        if numeric_ratio >= 0.9
        else float(non_null.map(lambda value: bool(PHONE_RE.match(value.strip()))).mean())
    )
    if phone_ratio >= 0.7:
        return {"type": "téléphone", "label": "Numéro de téléphone", "sensitivity": "modérée", "evidence": "format des valeurs"}
    iban_ratio = float(
        non_null.map(
            lambda value: bool(IBAN_RE.match(re.sub(r"\s+", "", value.upper())))
        ).mean()
    )
    if iban_ratio >= 0.5:
        return {"type": "bancaire", "label": "Coordonnées bancaires", "sensitivity": "élevée", "evidence": "format des valeurs"}
    card_ratio = float(
        non_null.map(lambda value: _luhn(re.sub(r"\D", "", value))).mean()
    )
    if card_ratio >= 0.5:
        return {"type": "bancaire", "label": "Numéro de carte bancaire", "sensitivity": "élevée", "evidence": "format des valeurs"}
    return None


SEVERITY_ORDER = {"élevée": 0, "moyenne": 1, "faible": 2, "info": 3}


def _add_issue(
    issues: list[dict],
    severity: str,
    category: str,
    message: str,
    recommendation: str,
    *,
    column: str | None = None,
    count: int | None = None,
) -> None:
    issues.append(
        {
            "severity": severity,
            "category": category,
            "column": column,
            "message": message,
            "recommendation": recommendation,
            "count": count,
        }
    )


def analyze_dataframe(df: pd.DataFrame, name: str) -> dict:
    rows = int(len(df))
    columns = [str(column) for column in df.columns]
    column_count = len(columns)
    total_cells = rows * column_count
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum()) if rows else 0
    duplicate_pct = round(duplicate_rows / rows * 100, 2) if rows else 0.0
    missing_pct = round(missing_cells / total_cells * 100, 2) if total_cells else 0.0

    issues: list[dict] = []
    anomalies: list[dict] = []
    column_reports: list[dict] = []
    pii_columns: list[dict] = []
    validation_checks: list[tuple[int, int]] = []  # (invalides, contrôlés)
    whitespace_total = 0
    case_total = 0
    non_null_total = 0
    constant_columns: list[str] = []
    date_columns: list[str] = []
    numeric_columns: list[str] = []
    text_columns: list[str] = []
    identifier_columns: list[str] = []

    if rows == 0:
        _add_issue(
            issues,
            "élevée",
            "complétude",
            "Le jeu de données ne contient aucune ligne.",
            "Vérifiez le fichier source et le filtre d'import.",
        )
    if duplicate_rows:
        severity = "élevée" if duplicate_pct >= 10 else "moyenne" if duplicate_pct >= 2 else "faible"
        _add_issue(
            issues,
            severity,
            "unicité",
            f"{duplicate_rows} ligne(s) entièrement dupliquée(s), soit {duplicate_pct} % du jeu.",
            "Définir une clé métier et supprimer les doublons après validation.",
            count=duplicate_rows,
        )

    for column in columns:
        series = df[column]
        non_null = series.dropna()
        missing = int(series.isna().sum())
        missing_percent = round(missing / rows * 100, 2) if rows else 0.0
        unique = int(non_null.nunique(dropna=True)) if len(non_null) else 0
        unique_pct = round(unique / max(1, len(non_null)) * 100, 2)
        inferred_type = _detect_type(series, column)
        values = non_null.astype(str)
        non_null_total += len(non_null)

        report: dict[str, Any] = {
            "name": column,
            "type": inferred_type,
            "missing": missing,
            "missing_pct": missing_percent,
            "unique": unique,
            "unique_pct": unique_pct,
            "top_values": [],
            "examples": [str(value)[:80] for value in non_null.head(3).tolist()],
            "outliers": 0,
            "outlier_pct": 0.0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
            "valid_pct": 100.0,
            "is_pii": False,
            "pii_type": None,
            "issues": [],
            "checks": [],
        }

        if inferred_type in {"numérique", "date"}:
            if inferred_type == "numérique":
                numeric_columns.append(column)
            else:
                date_columns.append(column)
        elif inferred_type == "texte":
            text_columns.append(column)

        if missing:
            severity = "élevée" if missing_percent >= 20 else "moyenne" if missing_percent >= 5 else "faible"
            _add_issue(
                issues,
                severity,
                "complétude",
                f"La colonne « {column} » contient {missing} valeur(s) manquante(s) ({missing_percent} %).",
                "Qualifier la cause des manquants puis compléter ou exclure la colonne des calculs sensibles.",
                column=column,
                count=missing,
            )
            report["issues"].append(
                f"{missing} valeur(s) manquante(s) ({missing_percent} %)"
            )

        if rows and unique <= 1 and inferred_type != "vide":
            constant_columns.append(column)
            _add_issue(
                issues,
                "faible",
                "cohérence",
                f"La colonne « {column} » est constante : aucune variabilité.",
                "Vérifier l'utilité de la colonne et son mode d'alimentation.",
                column=column,
            )
            report["issues"].append("colonne constante")

        # Statistiques numériques et valeurs atypiques.
        numeric_values = _to_numeric(non_null)
        numeric_ratio = float(numeric_values.notna().mean()) if len(non_null) else 0.0
        if inferred_type == "numérique" or (numeric_ratio >= 0.9 and len(non_null) >= 5):
            valid_numeric = numeric_values.dropna()
            if len(valid_numeric):
                q1 = float(valid_numeric.quantile(0.25))
                q3 = float(valid_numeric.quantile(0.75))
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = valid_numeric[(valid_numeric < lower) | (valid_numeric > upper)]
                report.update(
                    min=round(float(valid_numeric.min()), 4),
                    max=round(float(valid_numeric.max()), 4),
                    mean=round(float(valid_numeric.mean()), 4),
                    median=round(float(valid_numeric.median()), 4),
                    std=round(float(valid_numeric.std()), 4) if len(valid_numeric) > 1 else 0.0,
                    outliers=int(len(outliers)),
                    outlier_pct=round(len(outliers) / len(valid_numeric) * 100, 2),
                )
                if len(outliers):
                    examples = [round(float(value), 4) for value in outliers.head(5).tolist()]
                    report["checks"].append(
                        f"bornes IQR : [{round(lower, 4)} ; {round(upper, 4)}]"
                    )
                    anomalies.append(
                        {
                            "column": column,
                            "type": "valeur atypique",
                            "count": int(len(outliers)),
                            "pct": report["outlier_pct"],
                            "bounds": [round(lower, 4), round(upper, 4)],
                            "examples": examples,
                        }
                    )
                    severity = "élevée" if report["outlier_pct"] >= 10 else "moyenne" if report["outlier_pct"] >= 3 else "faible"
                    _add_issue(
                        issues,
                        severity,
                        "anomalie",
                        f"{len(outliers)} valeur(s) atypique(s) dans « {column} » "
                        f"({report['outlier_pct']} %), hors de l'intervalle IQR "
                        f"[{round(lower, 4)} ; {round(upper, 4)}].",
                        "Vérifier les valeurs extrêmes avec le métier avant de les corriger ou de les exclure.",
                        column=column,
                        count=int(len(outliers)),
                    )
                    report["issues"].append(
                        f"{len(outliers)} valeur(s) atypique(s) ({report['outlier_pct']} %)"
                    )
                if (valid_numeric < 0).any():
                    report["checks"].append(
                        f"{int((valid_numeric < 0).sum())} valeur(s) négative(s)"
                    )

        # Contrôles textuels.
        if inferred_type == "texte":
            stripped = values.str.strip()
            leading_trailing = int((values != stripped).sum())
            if leading_trailing:
                whitespace_total += leading_trailing
                _add_issue(
                    issues,
                    "faible",
                    "cohérence",
                    f"{leading_trailing} valeur(s) de « {column} » contiennent des espaces superflus.",
                    "Normaliser les espaces (trim) lors de l'import.",
                    column=column,
                    count=leading_trailing,
                )
                report["issues"].append(
                    f"{leading_trailing} valeur(s) avec espaces superflus"
                )
            lower = stripped.str.lower()
            grouped = stripped.groupby(lower).agg(
                variants="nunique", occurrences="size"
            )
            case_variants = (
                int(grouped.loc[grouped["variants"] > 1, "occurrences"].sum())
                if len(grouped)
                else 0
            )
            if case_variants > 0 and unique > 1:
                case_total += case_variants
                _add_issue(
                    issues,
                    "faible",
                    "cohérence",
                    f"« {column} » contient {case_variants} valeur(s) en variantes de casse.",
                    "Choisir une casse de référence et normaliser les libellés.",
                    column=column,
                    count=case_variants,
                )
                report["issues"].append(
                    f"{case_variants} variante(s) de casse"
                )
            empty_strings = int((stripped == "").sum())
            if empty_strings:
                report["issues"].append(
                    f"{empty_strings} chaîne(s) vide(s) non détectée(s) comme manquante(s)"
                )

        # Validations métier.
        if len(non_null):
            if EMAIL_NAME_RE.search(column) or values.str.contains("@", regex=False).mean() >= 0.5:
                checked = values.str.strip()
                invalid = int((~checked.str.match(EMAIL_RE)).sum())
                validation_checks.append((invalid, len(checked)))
                valid_pct = round((1 - invalid / len(checked)) * 100, 2)
                report["valid_pct"] = min(report["valid_pct"], valid_pct)
                report["checks"].append(f"{invalid} adresse(s) électronique(s) invalide(s)")
                if invalid:
                    _add_issue(
                        issues,
                        "moyenne" if invalid / len(checked) >= 0.05 else "faible",
                        "validité",
                        f"{invalid} adresse(s) électronique(s) invalide(s) dans « {column} ».",
                        "Corriger le format ou isoler les valeurs non conformes.",
                        column=column,
                        count=invalid,
                    )
            if PHONE_NAME_RE.search(column):
                checked = values.str.strip()
                invalid = int((~checked.map(lambda value: bool(PHONE_RE.match(value)))).sum())
                validation_checks.append((invalid, len(checked)))
                valid_pct = round((1 - invalid / len(checked)) * 100, 2)
                report["valid_pct"] = min(report["valid_pct"], valid_pct)
                report["checks"].append(f"{invalid} numéro(s) invalide(s)")
                if invalid:
                    _add_issue(
                        issues,
                        "moyenne" if invalid / len(checked) >= 0.05 else "faible",
                        "validité",
                        f"{invalid} numéro(s) de téléphone invalide(s) dans « {column} ».",
                        "Normaliser au format international et corriger les valeurs invalides.",
                        column=column,
                        count=invalid,
                    )
            if inferred_type == "date" or DATE_NAME_RE.search(column):
                parsed = _to_datetime(non_null)
                invalid = int(parsed.isna().sum())
                validation_checks.append((invalid, len(non_null)))
                valid_pct = round((1 - invalid / len(non_null)) * 100, 2)
                report["valid_pct"] = min(report["valid_pct"], valid_pct)
                if parsed.notna().any():
                    report["min"] = str(parsed.min())
                    report["max"] = str(parsed.max())
                    report["date_range"] = [str(parsed.min()), str(parsed.max())]
                report["checks"].append(f"{invalid} date(s) invalide(s)")
                if invalid:
                    _add_issue(
                        issues,
                        "moyenne" if invalid / len(non_null) >= 0.05 else "faible",
                        "validité",
                        f"{invalid} date(s) invalide(s) dans « {column} ».",
                        "Vérifier le format attendu (ISO 8601 recommandé) et corriger les valeurs.",
                        column=column,
                        count=invalid,
                    )

        # Clé métier et doublons fonctionnels.
        if ID_NAME_RE.search(column) and inferred_type != "vide":
            identifier_columns.append(column)
            duplicated = int(non_null.duplicated().sum())
            if duplicated:
                _add_issue(
                    issues,
                    "élevée" if duplicated / max(1, len(non_null)) >= 0.05 else "moyenne",
                    "unicité",
                    f"La colonne d'identification « {column} » contient {duplicated} doublon(s).",
                    "Vérifier la clé métier et dédupliquer avant les jointures.",
                    column=column,
                    count=duplicated,
                )
                report["issues"].append(f"{duplicated} doublon(s) de clé")
        elif unique == len(non_null) and len(non_null) >= 5 and inferred_type in {"texte", "numérique"}:
            identifier_columns.append(column)

        # Détection de données personnelles.
        pii = _pii_for_column(series, column)
        if pii:
            pii["column"] = column
            pii_columns.append(pii)
            report["is_pii"] = True
            report["pii_type"] = pii["type"]
            _add_issue(
                issues,
                "élevée" if pii["sensitivity"] == "élevée" else "moyenne",
                "gouvernance",
                f"La colonne « {column} » contient des données personnelles ({pii['label']}).",
                "Vérifier la base légale, minimiser la collecte, restreindre les accès et "
                "définir une durée de conservation.",
                column=column,
            )
            report["checks"].append(
                f"donnée personnelle détectée ({pii['label']}, preuve : {pii['evidence']})"
            )

        # Cardinalité et colonnes quasi uniques.
        if inferred_type == "texte" and unique_pct >= 95 and len(non_null) >= 20:
            report["checks"].append("cardinalité très élevée")
        if inferred_type == "texte" and unique == 1:
            pass

        # Valeurs les plus fréquentes.
        if len(non_null):
            top = non_null.astype(str).value_counts().head(5)
            report["top_values"] = [
                {"value": str(value)[:80], "count": int(count)}
                for value, count in top.items()
            ]

        column_reports.append(report)

    # Doublons fonctionnels : deux lignes identiques sur les attributs métier,
    # même si leur identifiant technique diffère.
    functional_duplicates = 0
    business_columns = [column for column in columns if column not in identifier_columns]
    if rows and duplicate_rows == 0 and len(business_columns) >= 2:
        functional_duplicates = int(df.duplicated(subset=business_columns).sum())
        if functional_duplicates:
            functional_pct = round(functional_duplicates / rows * 100, 2)
            _add_issue(
                issues,
                "élevée" if functional_pct >= 10 else "moyenne",
                "unicité",
                f"{functional_duplicates} ligne(s) en doublon fonctionnel "
                f"({functional_pct} %), identifiants techniques mis à part.",
                "Confirmer la clé métier puis fusionner ou supprimer les lignes redondantes.",
                count=functional_duplicates,
            )

    # Scores.
    completeness = round(100 - missing_pct, 2)
    effective_duplicate_rows = max(duplicate_rows, functional_duplicates)
    effective_duplicate_pct = (
        round(effective_duplicate_rows / rows * 100, 2) if rows else 0.0
    )
    uniqueness = round(100 - effective_duplicate_pct, 2)
    consistency_penalties = []
    if non_null_total:
        consistency_penalties.append(whitespace_total / non_null_total * 100)
        consistency_penalties.append(case_total / non_null_total * 100)
    if column_count:
        consistency_penalties.append(len(constant_columns) / column_count * 100)
    consistency = round(max(0.0, 100 - sum(consistency_penalties)), 2)
    if validation_checks:
        total_checked = sum(total for _, total in validation_checks)
        total_invalid = sum(invalid for invalid, _ in validation_checks)
        validity = round((1 - total_invalid / max(1, total_checked)) * 100, 2)
    else:
        validity = 100.0
    global_score = round(
        0.35 * completeness + 0.20 * uniqueness + 0.20 * consistency + 0.25 * validity,
        2,
    )

    # Gouvernance.
    documented = sum(
        1 for column in columns if not re.match(r"^(colonne|column|unnamed)\s*_?\d+$", column, re.I)
    )
    documentation_score = round(documented / max(1, column_count) * 100, 2)
    pii_penalty = 0
    if pii_columns:
        pii_penalty = 35 if any(item["sensitivity"] == "élevée" for item in pii_columns) else 20
    unique_key = False
    key_duplicates = 0
    for column_report in column_reports:
        if ID_NAME_RE.search(column_report["name"]) and column_report["type"] != "vide":
            unique_key = column_report["unique"] == rows
            key_duplicates += max(0, rows - column_report["unique"])
    if not any(ID_NAME_RE.search(column) for column in columns):
        key_quality = 45
        _add_issue(
            issues,
            "faible",
            "gouvernance",
            "Aucune colonne d'identification explicite n'a été détectée.",
            "Documenter une clé métier unique pour faciliter les rapprochements et les contrôles.",
        )
    elif unique_key:
        key_quality = 100
    else:
        key_quality = 70
    governance_score = round(
        0.45 * global_score
        + 0.25 * max(0, 100 - pii_penalty)
        + 0.15 * documentation_score
        + 0.15 * key_quality,
        2,
    )
    risk = "faible" if governance_score >= 80 else "modéré" if governance_score >= 60 else "élevé"

    if pii_columns:
        _add_issue(
            issues,
            "élevée" if any(item["sensitivity"] == "élevée" for item in pii_columns) else "moyenne",
            "conformité",
            f"{len(pii_columns)} colonne(s) de données personnelles détectée(s) : "
            + ", ".join(item["column"] for item in pii_columns[:8])
            + ".",
            "Réaliser une analyse d'impact si nécessaire, vérifier la base légale, "
            "limiter la conservation et journaliser les accès.",
            count=len(pii_columns),
        )
    if documentation_score < 100:
        _add_issue(
            issues,
            "moyenne" if documentation_score < 80 else "faible",
            "gouvernance",
            "Certaines colonnes n'ont pas de nom explicite.",
            "Renommer les colonnes et documenter leur définition dans un catalogue de données.",
        )

    # Fraîcheur.
    freshness = {"last_date": None, "days_old": None, "status": "non applicable"}
    date_values: list[pd.Timestamp] = []
    for column in date_columns:
        parsed = _to_datetime(df[column].dropna())
        if parsed.notna().any():
            date_values.append(parsed.max())
    if date_values:
        last = max(date_values)
        try:
            days_old = (pd.Timestamp.now() - last).days
        except (TypeError, ValueError):
            days_old = None
        freshness = {
            "last_date": last.isoformat(),
            "days_old": days_old,
            "status": "à jour" if days_old is not None and days_old <= 90 else "ancien",
        }

    # Échantillon.
    sample = []
    for _, row in df.head(10).iterrows():
        sample.append(
            {
                column: (str(_json_safe(row[column]))[:120] if _json_safe(row[column]) is not None else None)
                for column in columns
            }
        )

    # Dédoublonner et trier les problèmes.
    unique_issues: list[dict] = []
    seen_issues: set[tuple] = set()
    for issue in issues:
        key = (issue["severity"], issue["category"], issue["column"], issue["message"])
        if key in seen_issues:
            continue
        seen_issues.add(key)
        unique_issues.append(issue)
    unique_issues.sort(
        key=lambda issue: (
            SEVERITY_ORDER.get(issue["severity"], 9),
            issue["category"],
            issue["message"],
        )
    )

    recommendations: list[str] = []
    for issue in unique_issues:
        recommendation = issue.get("recommendation")
        if recommendation and recommendation not in recommendations:
            recommendations.append(recommendation)
    if not recommendations:
        recommendations.append(
            "Aucun problème majeur détecté. Mettre en place un contrôle périodique "
            "et documenter les règles de qualité dans le catalogue de données."
        )

    dimensions = [
        {"key": "completude", "label": "Complétude", "score": completeness, "description": "Valeurs renseignées"},
        {"key": "unicite", "label": "Unicité", "score": uniqueness, "description": "Absence de doublons"},
        {"key": "coherence", "label": "Cohérence", "score": consistency, "description": "Formats et règles internes"},
        {"key": "validite", "label": "Validité", "score": validity, "description": "Respect des formats autorisés"},
    ]

    return {
        "generated_at": utc_now(),
        "dataset": {"name": name},
        "overview": {
            "rows": rows,
            "columns": column_count,
            "cells": total_cells,
            "missing_cells": missing_cells,
            "missing_pct": missing_pct,
            "duplicate_rows": effective_duplicate_rows,
            "duplicate_pct": effective_duplicate_pct,
            "exact_duplicate_rows": duplicate_rows,
            "functional_duplicate_rows": functional_duplicates,
            "numeric_columns": len(numeric_columns),
            "text_columns": len(text_columns),
            "date_columns": len(date_columns),
            "identifier_columns": identifier_columns[:12],
        },
        "scores": {
            "global": global_score,
            "completude": completeness,
            "unicite": uniqueness,
            "coherence": consistency,
            "validite": validity,
        },
        "dimensions": dimensions,
        "governance": {
            "score": governance_score,
            "risk": risk,
            "pii_columns": pii_columns,
            "pii_count": len(pii_columns),
            "documentation_score": documentation_score,
            "documented_columns": documented,
            "key_quality": key_quality,
            "unique_key": unique_key,
            "freshness": freshness,
            "checks": [
                {
                    "label": "Données personnelles",
                    "status": "à vérifier" if pii_columns else "aucune détectée",
                    "detail": f"{len(pii_columns)} colonne(s) identifiée(s).",
                    "severity": "élevée" if pii_columns else "info",
                },
                {
                    "label": "Documentation des colonnes",
                    "status": f"{documented}/{column_count} colonnes nommées",
                    "detail": f"Score de documentation : {documentation_score}/100.",
                    "severity": "moyenne" if documentation_score < 80 else "info",
                },
                {
                    "label": "Clé d'identification",
                    "status": "présente" if unique_key else "à documenter",
                    "detail": "Une clé unique facilite les contrôles et les jointures."
                    if not unique_key else "Une colonne d'identification unique a été détectée.",
                    "severity": "info" if unique_key else "faible",
                },
                {
                    "label": "Fraîcheur",
                    "status": freshness["status"],
                    "detail": (
                        f"Dernière date observée : {freshness['last_date']}."
                        if freshness["last_date"]
                        else "Aucune colonne de date exploitable."
                    ),
                    "severity": "info",
                },
            ],
        },
        "columns": column_reports,
        "issues": unique_issues,
        "anomalies": anomalies,
        "recommendations": recommendations[:10],
        "sample": sample,
    }
