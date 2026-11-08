"""Construit les deux messages : rééquilibrage et check-up."""
from datetime import date

import numpy as np
import pandas as pd

from .telegram import esc


def _fmt_pct(x) -> str:
    return "n/d" if x is None or not np.isfinite(x) else f"{x:+.1%}"


def stock_card(t: str, names, sectors, close: pd.DataFrame) -> str:
    c = close[t].dropna()
    mom = c.iloc[-22] / c.iloc[-253] - 1 if len(c) > 253 else np.nan
    dist_hi = c.iloc[-1] / c.tail(252).max() - 1
    vol = np.log(c).diff().tail(126).std() * np.sqrt(252)
    return (f"<b>{esc(names.get(t, t))}</b> ({esc(t)}, {esc(sectors.get(t, '?'))})\n"
            f"   momentum 12-1 {_fmt_pct(mom)} · {_fmt_pct(dist_hi)} du plus haut 52 s · vol {vol:.0%}")


def rebalance_msg(meta, ords: pd.DataFrame, names, sectors, close, news: dict | None = None) -> str:
    lines = [f"🔁 <b>Rééquilibrage</b> (cours du {meta['date']:%d/%m})",
             f"Régime {esc(meta['regime'])} · exposition {meta['exposure']:.0%} · "
             f"{meta['per_line']:,.0f} € par ligne\n", "<b>Ordres à passer à l'ouverture</b>"]
    if ords.empty:
        lines.append("aucun : le portefeuille est déjà à la cible ✅")
    for _, o in ords.iterrows():
        buy = o["ordre"] == "ACHETER"
        limite = o["dernier_cours"] * (1.005 if buy else 0.995)
        lines.append(f"• {o['ordre']} {o['quantite']} {esc(o['valeur'])} — limite {limite:,.2f} €")
    lines.append("\n<b>Les valeurs retenues</b>")
    for t in meta["selected"]:
        lines.append(stock_card(t, names, sectors, close))
        if news and news.get(t):
            lines.append(f"   📰 {esc(news[t])}")
    lines.append("\nUne fois exécuté, réponds : <code>/fait ACHAT SAF 80 301.5</code> "
                 "(un message par ordre) puis <code>/cash 1234.56</code>")
    return "\n".join(lines)


def checkup_msg(meta, state, names, keep_rank: int, start_capital: float = 100_000.0) -> str:
    last, ranks = meta["last"], meta["ranks"]
    lines = [f"🩺 <b>Check-up</b> — rien à faire aujourd'hui (cours du {meta['date']:%d/%m})",
             f"Portefeuille ≈ {meta['equity']:,.0f} € ({meta['equity'] / start_capital - 1:+.2%} "
             f"depuis le départ) · cash {state['cash']:,.0f} €",
             f"Régime {esc(meta['regime'])} · exposition cible {meta['exposure']:.0%}\n"]
    if not state["positions"]:
        lines.append("Aucune position enregistrée.")
    for t, p in state["positions"].items():
        px = last.get(t, np.nan)
        rk = int(ranks[t]) if t in ranks else None
        flag = " ⚠️ sort du top" if rk is None or rk > keep_rank else ""
        lines.append(f"• {esc(names.get(t, t))} : {p['qty']} × {px:,.2f} € "
                     f"({px / p['price'] - 1:+.1%}) · rang {rk if rk else 'n/d'}{flag}")
    nxt = (pd.Timestamp(date.today()) + pd.offsets.BMonthBegin(1)).date()
    lines.append(f"\nProchain rééquilibrage : {nxt:%d/%m}")
    return "\n".join(lines)