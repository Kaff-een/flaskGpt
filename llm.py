"""Fournisseurs de modèles et gestion normalisée des erreurs.

Trois modes sont supportés :
- ``ollama`` : API locale /api/chat (par défaut) ;
- ``openai`` : toute API compatible OpenAI (clé + URL de base) ;
- ``demo``   : réponses locales construites à partir des sources.

Les erreurs sont converties en :class:`LLMError` afin que l'interface puisse
afficher un message clair (clé invalide, quota, connexion, modèle absent).
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    timeout: int
    allow_fallback: bool
    max_tokens: int

    @property
    def label(self) -> str:
        if self.provider == "ollama":
            return f"Ollama · {self.model}"
        if self.provider == "openai":
            return f"API compatible OpenAI · {self.model}"
        return "Mode démonstration local"


def get_config() -> LLMConfig:
    provider = _env("LLM_PROVIDER", "ollama").lower()
    if provider not in {"ollama", "openai", "demo"}:
        provider = "ollama"
    if provider == "ollama":
        base_url = _env("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        model = _env("OLLAMA_MODEL", "llama3.2:3b")
        api_key = _env("OLLAMA_API_KEY")
    elif provider == "openai":
        base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = _env("OPENAI_MODEL", "gpt-4o-mini")
        api_key = _env("OPENAI_API_KEY")
    else:
        base_url = ""
        model = "demo-local"
        api_key = ""
    return LLMConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=int(_env("LLM_TIMEOUT", "300") or "300"),
        allow_fallback=_env("ALLOW_DEMO_FALLBACK", "true").lower()
        not in {"0", "false", "no"},
        max_tokens=max(128, int(_env("LLM_MAX_TOKENS", "1024") or "1024")),
    )


class LLMError(Exception):
    """Erreur lisible par l'utilisateur, avec un code stable."""

    def __init__(
        self,
        code: str,
        message: str,
        hint: str = "",
        *,
        retryable: bool = False,
        detail: str = "",
        status: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.retryable = retryable
        self.detail = detail
        self.status = status

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "retryable": self.retryable,
            "status": self.status,
        }


def estimate_tokens(text: str) -> int:
    """Estimation grossière pour les fournisseurs qui ne renvoient pas l'usage."""
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def _short_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error.get("code") or "")[:600]
            if isinstance(error, str):
                return error[:600]
            if payload.get("message"):
                return str(payload["message"])[:600]
    except ValueError:
        pass
    return (response.text or "")[:600]


def _http_error(response: requests.Response, provider: str) -> LLMError:
    status = response.status_code
    detail = _short_detail(response)
    if status in (401, 403):
        return LLMError(
            "invalid_api_key",
            "La clé API est invalide ou n'a pas les droits nécessaires.",
            "Vérifiez OPENAI_API_KEY (ou le jeton du fournisseur) dans le fichier .env, "
            "puis redémarrez l'application.",
            detail=detail,
            status=status,
        )
    if status == 402:
        return LLMError(
            "quota_exceeded",
            "Le crédit ou le quota du fournisseur est épuisé.",
            "Rechargez votre compte ou choisissez un autre fournisseur dans .env.",
            detail=detail,
            status=status,
        )
    if status == 404:
        if provider == "ollama":
            return LLMError(
                "model_not_found",
                "Le modèle demandé n'est pas installé sur le serveur Ollama.",
                "Installez-le avec « ollama pull <modele> », puis vérifiez OLLAMA_MODEL.",
                retryable=True,
                detail=detail,
                status=status,
            )
        return LLMError(
            "model_not_found",
            "Le modèle ou l'adresse de l'API est introuvable.",
            "Vérifiez OPENAI_MODEL et OPENAI_BASE_URL dans le fichier .env.",
            detail=detail,
            status=status,
        )
    if status == 429:
        retry_after = response.headers.get("Retry-After")
        suffix = f" Réessayez dans {retry_after} secondes." if retry_after else ""
        return LLMError(
            "quota_exceeded",
            "La limite de requêtes ou le quota du fournisseur est atteint." + suffix,
            "Attendez avant de réessayer, réduisez la fréquence des appels ou "
            "augmentez votre quota.",
            retryable=True,
            detail=detail,
            status=status,
        )
    if status >= 500:
        return LLMError(
            "provider_unavailable",
            "Le fournisseur du modèle est temporairement indisponible.",
            "Réessayez dans quelques instants. Si le problème persiste, consultez "
            "la page de statut du fournisseur.",
            retryable=True,
            detail=detail,
            status=status,
        )
    return LLMError(
        "provider_error",
        f"Le fournisseur a renvoyé une erreur ({status}).",
        "Vérifiez la configuration et réessayez.",
        retryable=status >= 500,
        detail=detail,
        status=status,
    )


def _connection_error(exc: Exception, provider: str) -> LLMError:
    if provider == "ollama":
        return LLMError(
            "connection_error",
            "Impossible de joindre Ollama. Le service local ne répond pas.",
            "Démarrez Ollama avec « ollama serve », vérifiez OLLAMA_HOST "
            "(par défaut http://localhost:11434), puis réessayez.",
            retryable=True,
            detail=str(exc)[:500],
        )
    return LLMError(
        "connection_error",
        "Impossible de joindre le fournisseur du modèle.",
        "Vérifiez votre connexion Internet, OPENAI_BASE_URL et votre pare-feu.",
        retryable=True,
        detail=str(exc)[:500],
    )


def _parse_usage(payload: dict) -> dict | None:
    usage = payload.get("usage")
    if isinstance(usage, dict):
        prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total = usage.get("total_tokens") or (prompt + completion)
        return {
            "prompt_tokens": int(prompt or 0),
            "completion_tokens": int(completion or 0),
            "total_tokens": int(total or 0),
        }
    if payload.get("prompt_eval_count") is not None or payload.get("eval_count") is not None:
        prompt = int(payload.get("prompt_eval_count") or 0)
        completion = int(payload.get("eval_count") or 0)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }
    return None


def _stream_ollama(
    messages: list[dict], config: LLMConfig
) -> Iterator[dict]:
    url = f"{config.base_url}/api/chat"
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.25,
            "top_p": 0.9,
            "num_predict": config.max_tokens,
        },
    }
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=(10, config.timeout),
        )
    except requests.exceptions.RequestException as exc:
        raise _connection_error(exc, "ollama") from exc

    if response.status_code >= 400:
        raise _http_error(response, "ollama")

    try:
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            try:
                chunk = json.loads(raw_line)
            except ValueError:
                continue
            if chunk.get("error"):
                raise LLMError(
                    "provider_error",
                    f"Ollama a signalé une erreur : {str(chunk['error'])[:300]}",
                    "Vérifiez que le modèle est installé et que le service fonctionne.",
                    retryable=True,
                )
            message = chunk.get("message") or {}
            text = message.get("content") or ""
            if text:
                yield {"type": "token", "text": text}
            if chunk.get("done"):
                usage = _parse_usage(chunk)
                if usage:
                    yield {"type": "usage", **usage}
                break
    except requests.exceptions.RequestException as exc:
        raise _connection_error(exc, "ollama") from exc
    finally:
        response.close()


def _stream_openai(
    messages: list[dict], config: LLMConfig
) -> Iterator[dict]:
    if not config.api_key:
        raise LLMError(
            "missing_api_key",
            "Aucune clé API n'est configurée pour ce fournisseur.",
            "Ajoutez OPENAI_API_KEY dans le fichier .env, puis redémarrez l'application.",
        )
    url = f"{config.base_url}/chat/completions"
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": True,
        "temperature": 0.25,
        "stream_options": {"include_usage": True},
        "max_tokens": config.max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=(10, config.timeout),
        )
    except requests.exceptions.RequestException as exc:
        raise _connection_error(exc, "openai") from exc

    if response.status_code >= 400:
        raise _http_error(response, "openai")

    try:
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            if chunk.get("error"):
                raise LLMError(
                    "provider_error",
                    f"Le fournisseur a signalé une erreur : {str(chunk['error'])[:300]}",
                    "Vérifiez la configuration du fournisseur.",
                    retryable=True,
                )
            usage = _parse_usage(chunk)
            if usage:
                yield {"type": "usage", **usage}
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            if content:
                yield {"type": "token", "text": content}
    except requests.exceptions.RequestException as exc:
        raise _connection_error(exc, "openai") from exc
    finally:
        response.close()


DEMO_WARNING = (
    "> **Mode local — service de génération indisponible.**  \n"
    "> Cette réponse est construite automatiquement à partir des sources "
    "sélectionnées, sans modèle génératif. Elle reste indicative et ne remplace "
    "pas une réponse du modèle."
)


def fallback_answer(
    question: str,
    sources: list[dict],
    domain_label: str = "Général",
    *,
    reason: str = "",
    with_warning: bool = True,
) -> str:
    """Réponse de secours extractive, explicitement signalée comme locale."""
    parts: list[str] = []
    if with_warning:
        parts.append(DEMO_WARNING)
        if reason:
            parts.append(f"> *Détail technique : {reason}*")
    parts.append(f"## Réponse locale — {domain_label}")
    if sources:
        parts.append(
            "Voici les éléments les plus pertinents extraits des sources que vous "
            "avez sélectionnées :"
        )
        for source in sources:
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", source["excerpt"])
                if sentence.strip()
            ]
            highlight = " ".join(sentences[:3]) if sentences else source["excerpt"]
            parts.append(
                f"**Source {source['rank']} — {source['title']}**  \n"
                f"{highlight}  \n"
                f"<span class=\"text-xs text-slate-500\">Pertinence : "
                f"{round(source['score'] * 100)} %</span>"
            )
        parts.append(
            "### Ce que vous pouvez faire ensuite\n"
            "- Vérifier les passages ci-dessus dans les documents d'origine.\n"
            "- Reformuler la question avec un contexte plus précis.\n"
            "- Réactiver le service de génération pour obtenir une synthèse rédigée."
        )
    else:
        parts.append(
            "Aucune source n'est sélectionnée et le service de génération est "
            "indisponible. Je ne peux donc pas produire une réponse fiable.\n\n"
            "Sélectionnez au moins une source dans le panneau de droite, puis "
            "réessayez. Vous pouvez aussi démarrer Ollama ou configurer une clé "
            "API dans le fichier `.env`."
        )
    if question:
        parts.append(f"*Question d'origine : {question.strip()[:500]}*")
    return "\n\n".join(parts)


def stream_completion(
    messages: list[dict],
    *,
    question: str = "",
    sources: list[dict] | None = None,
    domain_label: str = "Général",
) -> Iterator[dict]:
    config = get_config()
    if config.provider == "demo":
        answer = fallback_answer(
            question, sources or [], domain_label, with_warning=False
        )
        for chunk in re.split(r"(\s+)", answer):
            if chunk:
                yield {"type": "token", "text": chunk}
        yield {
            "type": "usage",
            "prompt_tokens": estimate_tokens(
                "\n".join(message.get("content", "") for message in messages)
            ),
            "completion_tokens": estimate_tokens(answer),
            "total_tokens": estimate_tokens(
                "\n".join(message.get("content", "") for message in messages)
            )
            + estimate_tokens(answer),
        }
        return
    if config.provider == "ollama":
        yield from _stream_ollama(messages, config)
        return
    yield from _stream_openai(messages, config)


def provider_status() -> dict:
    config = get_config()
    started = time.perf_counter()
    status: dict[str, Any] = {
        "provider": config.provider,
        "model": config.model,
        "label": config.label,
        "configured": True,
        "reachable": False,
        "model_available": None,
        "latency_ms": None,
        "message": "",
        "hint": "",
        "allow_fallback": config.allow_fallback,
    }
    if config.provider == "demo":
        status.update(
            reachable=True,
            model_available=True,
            latency_ms=0,
            message="Mode démonstration local activé.",
            hint="Les réponses sont construites à partir des sources.",
        )
        return status

    if config.provider == "openai":
        if not config.api_key:
            status.update(
                configured=False,
                message="Aucune clé API configurée.",
                hint="Ajoutez OPENAI_API_KEY dans le fichier .env.",
            )
            return status
        try:
            response = requests.get(
                f"{config.base_url}/models",
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=3,
            )
            status["latency_ms"] = round((time.perf_counter() - started) * 1000)
            if response.status_code >= 400:
                error = _http_error(response, "openai")
                status.update(
                    reachable=error.code != "connection_error",
                    message=error.message,
                    hint=error.hint,
                )
                return status
            status.update(
                reachable=True,
                model_available=True,
                message="Fournisseur joignable.",
                hint=f"Modèle configuré : {config.model}.",
            )
        except requests.exceptions.RequestException as exc:
            status.update(
                reachable=False,
                message="Fournisseur injoignable.",
                hint=str(exc)[:200],
            )
        return status

    # Ollama
    try:
        response = requests.get(f"{config.base_url}/api/tags", timeout=2.5)
        status["latency_ms"] = round((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            error = _http_error(response, "ollama")
            status.update(
                reachable=False,
                message=error.message,
                hint=error.hint,
            )
            return status
        payload = response.json()
        models = [item.get("name", "") for item in payload.get("models", [])]
        normalized = {name.split(":")[0] for name in models}
        available = config.model in models or config.model.split(":")[0] in normalized
        status.update(
            reachable=True,
            model_available=available,
            models=models[:20],
            message="Ollama est joignable." if available else "Ollama répond, mais le modèle est absent.",
            hint=(
                f"Modèle actif : {config.model}."
                if available
                else f"Installez le modèle avec « ollama pull {config.model} »."
            ),
        )
    except requests.exceptions.RequestException as exc:
        status.update(
            reachable=False,
            message="Ollama est injoignable.",
            hint="Démarrez Ollama avec « ollama serve », ou configurez un fournisseur API.",
            detail=str(exc)[:200],
        )
    return status
