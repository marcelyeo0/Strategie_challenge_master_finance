"""Portefeuille cible et liste d'ordres à passer à la main sur ABC Bourse.

Usage : python -m sbf_mom.cli ordres --positions positions.csv --cash 12345.67
positions.csv : ticker,quantite   (une ligne par action détenue ; fichier vide si rien)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import GameRules, StratParams
from .signals import realized_vol, score


def target_orders(px, sectors, names: pd.Series, p: StratParams, g: GameRules,
                  positions: dict[str, int], cash: float,
                  index_close: pd.Series | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    close = px["close"].ffill(limit=5)
    d = close.index[-1]
    last = close.loc[d]
    sc = score(close, sectors, p).loc[d].dropna().sort_values(ascending=False)
    ranks = pd.Series(np.arange(1, len(sc) + 1), index=sc.index)

    keep = sorted([t for t in positions if t in ranks and ranks[t] <= p.keep_rank], key=lambda t: ranks[t])
    new = [t for t in sc.index if t not in keep][: max(p.n_positions - len(keep), 0)]
    selected = (keep + new)[: p.n_positions]

    equity = cash + sum(q * last.get(t, 0.0) for t, q in positions.items())
    expo = p.max_exposure
    rets = close.pct_change(fill_method=None)
    if p.vol_target and selected:
        bv = rets[selected].tail(p.vol_lookback).mean(axis=1).std() * np.sqrt(252)
        if np.isfinite(bv) and bv > 0:
            expo = min(expo, p.vol_target / bv)
    regime = "n/a"
    if p.regime_ma and index_close is not None:
        ic = index_close.dropna()
        above = ic.iloc[-1] > ic.tail(p.regime_ma).mean()
        regime = "haussier" if above else "baissier"
        if not above:
            expo = min(expo, p.regime_exposure)
    per_line = min(g.max_per_line, expo * equity / max(len(selected), 1))

    orders = []
    for t, q in positions.items():
        if t not in selected:
            orders.append((t, names.get(t, t), "VENDRE TOUT", q, last.get(t)))
    for t in selected:
        price = last[t]
        cur = positions.get(t, 0) * price
        diff = min(per_line, g.max_per_line) - cur
        if abs(diff) < p.min_trade_eur:
            continue
        q = int(abs(diff) // price)
        if q == 0 and t not in positions:
            print(f"  ! {names.get(t, t)} : cours ({price:,.0f} €) supérieur au montant par ligne, ignoré")
        if q > 0:
            orders.append((t, names.get(t, t), "ACHETER" if diff > 0 else "ALLÉGER", q, price))

    top = pd.DataFrame({
        "valeur": [names.get(t, t) for t in sc.index[:20]],
        "ticker": sc.index[:20],
        "rang": ranks.iloc[:20].values,
        "score": sc.iloc[:20].round(2).values,
        "sélectionné": [t in selected for t in sc.index[:20]],
    })
    ords = pd.DataFrame(orders, columns=["ticker", "valeur", "ordre", "quantite", "dernier_cours"])
    meta = {
        "date": d, "equity": equity, "regime": regime, "exposure": expo,
        "per_line": per_line, "selected": selected, "ranks": ranks, "last": last,
    }
    return top, ords, meta
