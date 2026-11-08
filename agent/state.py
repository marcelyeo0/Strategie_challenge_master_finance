"""État local : positions réelles, cash, dernier rééquilibrage. Source de vérité = ce que TU as saisi."""
import copy
import json
from datetime import date

from . import config

FEE = 0.002
DEFAULT = {"cash": 100_000.0, "positions": {}, "last_rebalance": "", "tg_offset": 0}


def load() -> dict:
    if config.STATE_FILE.exists():
        return {**copy.deepcopy(DEFAULT), **json.loads(config.STATE_FILE.read_text(encoding="utf-8"))}
    return copy.deepcopy(DEFAULT)  # copie profonde : sinon on modifierait DEFAULT lui-même


def save(state: dict) -> None:
    config.STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_ticker(code: str, tickers: list[str]) -> str:
    """'saf' -> 'SAF.PA' ; accepte aussi le ticker complet."""
    code = code.upper()
    if code in tickers:
        return code
    hits = [t for t in tickers if t.split(".")[0] == code]
    if len(hits) != 1:
        raise ValueError(f"ticker inconnu ou ambigu : {code}")
    return hits[0]


def apply_command(state: dict, text: str, tickers: list[str]) -> str:
    """Applique une commande Telegram et retourne un compte rendu d'une ligne.

    /fait ACHAT SAF 80 301.5   /fait VENTE SAF 80 310   /cash 2350.12   /rebal
    """
    parts = text.replace(",", ".").split()
    cmd = parts[0].lower()
    if cmd == "/fait" and len(parts) == 5:
        sens, code, qty, price = parts[1].upper(), parts[2], int(parts[3]), float(parts[4])
        t = resolve_ticker(code, tickers)
        pos = state["positions"].get(t, {"qty": 0, "price": 0.0, "date": ""})
        if sens == "ACHAT":
            new_qty = pos["qty"] + qty
            pos["price"] = (pos["qty"] * pos["price"] + qty * price) / new_qty  # prix de revient moyen
            pos["qty"], pos["date"] = new_qty, pos["date"] or date.today().isoformat()
            state["cash"] -= qty * price * (1 + FEE)
            state["positions"][t] = pos
        elif sens == "VENTE":
            if qty > pos["qty"]:
                raise ValueError(f"tu ne détiens que {pos['qty']} {t}")
            pos["qty"] -= qty
            state["cash"] += qty * price * (1 - FEE)
            if pos["qty"] == 0:
                state["positions"].pop(t, None)
            else:
                state["positions"][t] = pos
        else:
            raise ValueError("sens attendu : ACHAT ou VENTE")
        return f"✅ {sens} {qty} {t} à {price} € enregistré"
    if cmd == "/cash" and len(parts) == 2:
        state["cash"] = float(parts[1])
        return f"✅ cash fixé à {state['cash']:,.2f} €"
    if cmd == "/rebal":
        state["last_rebalance"] = ""
        return "✅ rééquilibrage forcé à ce run"
    if cmd in ("/positions", "/start", "/aide"):
        return "ℹ️ positions détaillées dans le check-up ci-dessous"
    raise ValueError(f"commande non comprise : {text}")