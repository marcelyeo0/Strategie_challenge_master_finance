"""À lancer une seule fois : crée la base « Runs agent SBF 120 » sous une page Notion.

python -m agent.setup_notion <id_de_la_page>
"""
import sys

import requests

from . import config
from .notion_log import HEADERS

page_id = sys.argv[1]
body = {
    "parent": {"type": "page_id", "page_id": page_id},
    "title": [{"text": {"content": "Runs agent SBF 120"}}],
    "properties": {
        "Run": {"title": {}},
        "Type": {"select": {"options": [{"name": "Rééquilibrage", "color": "blue"},
                                        {"name": "Check-up", "color": "green"},
                                        {"name": "Erreur", "color": "red"}]}},
        "Régime": {"select": {"options": [{"name": "haussier", "color": "green"},
                                          {"name": "baissier", "color": "red"}]}},
        "Exposition": {"number": {"format": "percent"}},
        "Valeur portefeuille": {"number": {"format": "euro"}},
        "Message": {"rich_text": {}},
    },
}
r = requests.post("https://api.notion.com/v1/databases", headers=HEADERS(), json=body, timeout=20)
if r.status_code != 200:
    sys.exit(f"Erreur {r.status_code} : {r.text}")
print("Base créée. Ajoute cette ligne à ton .env :")
print(f"NOTION_DB_ID={r.json()['id']}")