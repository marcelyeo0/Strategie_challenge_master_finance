"""Le bon critère pour un concours : la probabilité de finir dans le top 3.

Pour chaque fenêtre historique 6 nov. -> 23 févr., on simule 49 adversaires
(portefeuilles de 4 à 8 actions tirées au hasard dans l'univers, achetés au départ
et conservés, frais compris), et on regarde le classement de la stratégie.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import run
from .config import GameRules, StratParams


def window_bounds(index: pd.DatetimeIndex, year: int, g: GameRules) -> tuple[str, str]:
    s_md, e_md = g.start[5:], g.end[5:]
    return f"{year}-{s_md}", f"{year + 1}-{e_md}"


def random_competitors(close: pd.DataFrame, start: str, end: str, g: GameRules,
                       n: int = 49, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    w = close.loc[start:end]
    first, last = w.iloc[0], w.ffill().iloc[-1]
    ok = first.notna() & last.notna()
    names = first.index[ok]
    out = []
    for _ in range(n):
        k = int(rng.integers(4, 9))
        pick = rng.choice(names, size=min(k, len(names)), replace=False)
        alloc = min(g.max_per_line, g.capital / k)
        cash = g.capital
        val_end = 0.0
        for t in pick:
            q = int(alloc / (first[t] * (1 + g.fee_rate)))
            cash -= q * first[t] * (1 + g.fee_rate)
            val_end += q * last[t] * (1 - g.fee_rate)  # on liquide à la fin pour comparer net
        out.append((cash + val_end) / g.capital - 1)
    return np.array(out)


def evaluate(px, sectors, p: StratParams, g: GameRules, years: list[int],
             index_close: pd.Series | None = None, n_comp: int = 49, n_draws: int = 20,
             seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = px["close"]
    rows = []
    for y in years:
        start, end = window_bounds(close.index, y, g)
        if close.loc[start:end].shape[0] < 40:
            continue
        res = run(px, sectors, p, g, start, end, index_close=index_close)
        r = res.equity.iloc[-1] / g.capital - 1
        # plusieurs tirages d'adversaires pour lisser le hasard
        ranks = []
        for _ in range(n_draws):
            comp = random_competitors(close, start, end, g, n_comp, rng)
            ranks.append(1 + int((comp > r).sum()))
        idx_r = np.nan
        if index_close is not None:
            ic = index_close.loc[start:end].dropna()
            if len(ic) > 1:
                idx_r = ic.iloc[-1] / ic.iloc[0] - 1
        rows.append({
            "saison": f"{y}-{y + 1}",
            "strat_%": round(r * 100, 2),
            "indice_%": round(idx_r * 100, 2) if np.isfinite(idx_r) else np.nan,
            "rang_moyen_sur_50": round(float(np.mean(ranks)), 1),
            "P(top3)": round(float(np.mean([k <= 3 for k in ranks])), 2),
            "drawdown_max_%": round(float((res.equity / res.equity.cummax() - 1).min() * 100), 2),
            "frais_€": round(res.fees),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        print(f"\nP(top 3) moyenne : {df['P(top3)'].mean():.2f}  |  "
              f"rang moyen : {df['rang_moyen_sur_50'].mean():.1f} / 50  |  "
              f"saisons gagnantes vs indice : {(df['strat_%'] > df['indice_%']).mean():.0%}")
    return df
