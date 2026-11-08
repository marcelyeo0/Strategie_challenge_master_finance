"""Envoyer des messages et lire les commandes reçues par le bot."""
import html

import requests

from . import config

API = "https://api.telegram.org/bot{token}/{method}"


def _call(method: str, **params) -> dict:
    url = API.format(token=config.TG_TOKEN, method=method)
    r = requests.post(url, json=params, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} : {data.get('description')}")
    return data["result"]


def esc(text) -> str:
    """Échappe < > & pour le mode HTML de Telegram."""
    return html.escape(str(text), quote=False)


def send(text: str) -> None:
    """Envoie un message (découpé si > 4000 caractères, la limite est 4096)."""
    while text:
        chunk, text = text[:4000], text[4000:]
        _call("sendMessage", chat_id=config.TG_CHAT_ID, text=chunk,
              parse_mode="HTML", disable_web_page_preview=True)


def get_commands(offset: int) -> tuple[list[str], int]:
    """Retourne les textes reçus depuis `offset` et le nouvel offset.

    Telegram garde les messages non lus 24 h : pas besoin d'un bot allumé en continu.
    """
    updates = _call("getUpdates", offset=offset, timeout=0)
    texts = []
    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) == str(config.TG_CHAT_ID) and "text" in msg:
            texts.append(msg["text"].strip())
    return texts, offset