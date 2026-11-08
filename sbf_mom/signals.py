"""Signaux de la stratégie A : momentum 12-1 + proximité du plus haut 52 semaines.

Tous les signaux à la date t n'utilisent que les clôtures jusqu'à t inclus.
L'exécution se fait à l'ouverture de t+1 (voir backtest.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import StratParams


def _zscore_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rang centré-réduit en coupe transversale (robuste aux valeurs extrêmes)."""
    r = df.rank(axis=1, pct=True)
    return (r - r.mean(axis=1).values[:, None]) / r.std(axis=1).values[:, None]


def momentum_12_1(close: pd.DataFrame, p: StratParams) -> pd.DataFrame:
    return close.shift(p.mom_skip) / close.shift(p.mom_lookback) - 1.0


def high_52w(close: pd.DataFrame, p: StratParams) -> pd.DataFrame:
    """Cours / plus haut sur 52 semaines (1 = au plus haut)."""
    hi = close.rolling(p.high_lookback, min_periods=p.high_lookback // 2).max()
    return close / hi


def sector_momentum(close: pd.DataFrame, sectors: pd.Series, p: StratParams) -> pd.DataFrame:
    """Rendement moyen équipondéré de chaque secteur sur sector_lookback, rediffusé par titre."""
    ret = close / close.shift(p.sector_lookback) - 1.0
    out = pd.DataFrame(index=close.index, columns=close.columns, dtype=float)
    for sec, cols in sectors.groupby(sectors).groups.items():
        cols = [c for c in cols if c in close.columns]
        if cols:
            m = ret[cols].mean(axis=1)
            for c in cols:
                out[c] = m
    return out


def score(close: pd.DataFrame, sectors: pd.Series, p: StratParams) -> pd.DataFrame:
    """Score composite ; NaN = titre non éligible."""
    mom = momentum_12_1(close, p)
    hi = high_52w(close, p)
    s = p.w_mom * _zscore_rows(mom) + p.w_high * _zscore_rows(hi)

    # éligibilité : historique suffisant et cours du jour disponible
    hist = close.notna().cumsum()
    s = s.where((hist >= p.min_history) & close.notna())

    if p.sector_filter > 0:
        sm = sector_momentum(close, sectors, p)
        # les titres d'un même secteur partagent la même valeur : le rang "dense"
        # donne donc directement le rang du secteur (1 = meilleur)
        best = sm.rank(axis=1, method="dense", ascending=False)
        s = s.where(best <= p.sector_filter)

    for t in p.tickers_excluded:
        if t in s.columns:
            s[t] = np.nan
    return s


def realized_vol(close: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return np.log(close).diff().rolling(lookback, min_periods=lookback // 2).std() * np.sqrt(252)
