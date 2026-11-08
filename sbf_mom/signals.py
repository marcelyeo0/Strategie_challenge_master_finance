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


def score(close: pd.DataFrame, sectors: pd.Series, p: StratParams, volume: pd.DataFrame | None = None) -> pd.DataFrame:
    """Score composite ; NaN = titre non éligible."""
    if p.signal == "fip":
        # Frog in the Pan : parmi les meilleurs rendements 6 mois, préférer ceux obtenus
        # par une suite de petites hausses (ID très négatif) plutôt que par quelques sauts
        lr = np.log(close).diff()
        pret = close.shift(p.mom_skip) / close.shift(p.mom_skip + p.fip_lookback) - 1
        up = (lr > 0).astype(float).rolling(p.fip_lookback).mean()
        down = (lr < 0).astype(float).rolling(p.fip_lookback).mean()
        info_disc = np.sign(pret) * (down - up)
        s = (-info_disc).where(pret.rank(axis=1, pct=True) >= p.fip_top_pct)
    else:
        mom = momentum_12_1(close, p)
        hi = high_52w(close, p)
        s = p.w_mom * _zscore_rows(mom) + p.w_high * _zscore_rows(hi)

    # éligibilité : historique suffisant et cours du jour disponible
    hist = close.notna().cumsum()
    s = s.where((hist >= p.min_history) & close.notna())

    # données douteuses : un saut de plus de max_daily_move en un jour fausse le momentum
    jump = close.pct_change(fill_method=None).abs().gt(p.max_daily_move)
    s = s.where(~jump.rolling(p.mom_lookback, min_periods=1).max().astype(bool))

    if getattr(p, "top_liquid", 0) and volume is not None:
        tv = (close * volume.reindex_like(close)).rolling(63, min_periods=40).median()
        s = s.where(tv.rank(axis=1, ascending=False) <= p.top_liquid)
    if getattr(p, "use_lowvol", 0):
        rv = np.log(close).diff().rolling(252, min_periods=120).std()
        s = s + p.use_lowvol * _zscore_rows(-rv)

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
