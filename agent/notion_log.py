"""Journal des runs dans une base Notion."""
import requests

from . import config

HEADERS = lambda: {
    "Authorization": f"Bearer {config.NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _text(s: str) -> list:
    # une propriété texte Notion accepte au plus 2000 caractères par bloc
    return [{"text": {"content": s[i:i + 2000]}} for i in range(0, min(len(s), 6000), 2000)]


def log_run(kind: str, regime: str, exposure: float, equity: float, message: str, title: str) -> None:
    body = {
        "parent": {"database_id": config.NOTION_DB_ID},
        "properties": {
            "Run": {"title": [{"text": {"content": title}}]},
            "Type": {"select": {"name": kind}},
            "Régime": {"select": {"name": regime}},
            "Exposition": {"number": round(exposure, 3)},
            "Valeur portefeuille": {"number": round(equity, 2)},
            "Message": {"rich_text": _text(message)},
        },
    }
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS(), json=body, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Notion {r.status_code} : {r.text[:300]}")