"""Simulateur au plus près des règles du jeu.

- décision à la clôture du dernier jour de la période, exécution à l'OUVERTURE suivante
- 0,20 % de frais sur chaque achat et chaque vente
- plafond de 25 000 € investis par action, nombre entier d'actions, pas de levier
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import GameRules, StratParams
from .signals import realized_vol, score


@dataclass
class Result:
    equity: pd.Series
    trades: pd.DataFrame
    holdings: pd.DataFrame      # nombre d'actions détenues par jour
    exposure: pd.Series         # exposition cible décidée à chaque rebalancement
    fees: float

    def stats(self) -> dict:
        eq = self.equity
        r = eq.pct_change().dropna()
        dd = eq / eq.cummax() - 1
        n_years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
        return {
            "rendement_total_%": round((eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
            "CAGR_%": round(((eq.iloc[-1] / eq.iloc[0]) ** (1 / n_years) - 1) * 100, 2),
            "vol_annuelle_%": round(r.std() * np.sqrt(252) * 100, 2),
            "sharpe": round(r.mean() / r.std() * np.sqrt(252), 2) if r.std() > 0 else np.nan,
            "drawdown_max_%": round(dd.min() * 100, 2),
            "frais_€": round(self.fees, 0),
            "nb_ordres": len(self.trades),
        }


def decision_days(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Derniers jours de bourse de chaque période : on décide ce jour-là, on exécute le lendemain."""
    s = pd.Series(index, index=index)
    if freq == "M":
        key = index.to_period("M")
    elif freq == "W":
        key = index.to_period("W")
    elif freq == "2W":
        key = (index.to_period("W").astype("int64") // 2)
    else:
        raise ValueError(freq)
    last = s.groupby(np.asarray(key)).max()
    return pd.DatetimeIndex(last.values)


def run(px: dict[str, pd.DataFrame], sectors: pd.Series, p: StratParams, g: GameRules,
        start: str, end: str, index_close: pd.Series | None = None,
        force_first_rebalance: bool = True) -> Result:
    close_all = px["close"].ffill(limit=5)
    open_all = px["open"]

    sc_all = score(close_all, sectors, p)
    vol_all = realized_vol(close_all, p.vol_lookback)
    rets_all = close_all.pct_change(fill_method=None)

    days = close_all.loc[start:end].index
    if len(days) < 2:
        raise ValueError("fenêtre trop courte")
    dec = set(decision_days(close_all.index, p.rebalance))
    # on décide aussi la veille du premier jour, pour s'investir dès le départ
    prev_day = close_all.index[close_all.index.get_loc(days[0]) - 1]
    if force_first_rebalance:
        dec.add(prev_day)

    regime_ok = None
    if p.regime_ma and index_close is not None:
        ic = index_close.reindex(close_all.index).ffill()
        regime_ok = ic > ic.rolling(p.regime_ma).mean()

    cash = g.capital
    shares: dict[str, int] = {}
    fees = 0.0
    trades, eq_hist, hold_hist, expo_hist = [], {}, {}, {}
    pending: dict[str, float] | None = None  # cibles en € à exécuter à l'ouverture

    all_days = [prev_day] + list(days)
    for i, d in enumerate(all_days):
        # 1) exécution à l'ouverture des ordres décidés la veille
        if pending is not None and d != prev_day:
            o = open_all.loc[d]
            c_prev = close_all.loc[all_days[i - 1]]
            # ventes d'abord
            for t in list(shares):
                tgt = pending.get(t, 0.0)
                price = o.get(t, np.nan)
                if not np.isfinite(price):
                    continue
                cur_val = shares[t] * price
                if tgt <= 0 or cur_val - tgt > p.min_trade_eur:
                    n_sell = shares[t] if tgt <= 0 else int((cur_val - tgt) // price)
                    if n_sell <= 0:
                        continue
                    amount = n_sell * price
                    fee = amount * g.fee_rate
                    cash += amount - fee
                    fees += fee
                    shares[t] -= n_sell
                    if shares[t] == 0:
                        del shares[t]
                    trades.append((d, t, "VENTE", n_sell, price, fee))
            # achats ensuite, du meilleur au moins bon (ordre du dict)
            for t, tgt in pending.items():
                price = o.get(t, np.nan)
                if not np.isfinite(price) or tgt <= 0:
                    continue
                cur_val = shares.get(t, 0) * price
                want = min(tgt, g.max_per_line) - cur_val
                if want < p.min_trade_eur:
                    continue
                budget = min(want, cash / (1 + g.fee_rate))
                n_buy = int(budget // price)
                if n_buy <= 0:
                    continue
                amount = n_buy * price
                fee = amount * g.fee_rate
                cash -= amount + fee
                fees += fee
                shares[t] = shares.get(t, 0) + n_buy
                trades.append((d, t, "ACHAT", n_buy, price, fee))
            pending = None

        # 2) valorisation à la clôture
        c = close_all.loc[d]
        equity = cash + sum(n * c.get(t, np.nan) for t, n in shares.items()
                            if np.isfinite(c.get(t, np.nan)))
        if d != prev_day:
            eq_hist[d] = equity
            hold_hist[d] = dict(shares)

        # 3) décision à la clôture
        if d in dec and d != all_days[-1]:
            s = sc_all.loc[d].dropna().sort_values(ascending=False)
            ranks = pd.Series(np.arange(1, len(s) + 1), index=s.index)
            keep = [t for t in shares if t in ranks and ranks[t] <= p.keep_rank]
            keep.sort(key=lambda t: ranks[t])
            new = [t for t in s.index if t not in keep][: max(p.n_positions - len(keep), 0)]
            selected = (keep + new)[: p.n_positions]

            expo = p.max_exposure
            if p.vol_target and selected:
                basket = rets_all.loc[:d, selected].tail(p.vol_lookback).mean(axis=1)
                bv = basket.std() * np.sqrt(252)
                if np.isfinite(bv) and bv > 0:
                    expo = min(expo, p.vol_target / bv)
            if regime_ok is not None and not bool(regime_ok.get(d, True)):
                expo = min(expo, p.regime_exposure)
            expo_hist[d] = expo

            per_line = min(g.max_per_line, expo * equity / max(len(selected), 1))
            pending = {t: per_line for t in selected}

    trades_df = pd.DataFrame(trades, columns=["date", "ticker", "sens", "quantite", "prix", "frais"])
    return Result(
        equity=pd.Series(eq_hist, name="equity"),
        trades=trades_df,
        holdings=pd.DataFrame(hold_hist).T.fillna(0),
        exposure=pd.Series(expo_hist, name="exposure"),
        fees=fees,
    )
