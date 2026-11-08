"""Test hors ligne : données synthétiques avec un vrai effet momentum injecté.

Si le code est juste, la stratégie doit battre des portefeuilles aléatoires.
Lance : python -m pytest -q tests  (ou python tests/test_synthetic.py)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sbf_mom.backtest import run
from sbf_mom.config import GameRules, StratParams
from sbf_mom.tournament import evaluate


def fake_market(n=60, start="2010-01-01", end="2020-03-31", seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end)
    T = len(idx)
    mkt = rng.normal(0.0003, 0.011, T)
    # drift persistant par titre, qui change lentement => momentum exploitable
    drift = np.zeros((T, n))
    d = rng.normal(0, 0.0008, n)
    for t in range(T):
        if t % 250 == 0:
            d = 0.7 * d + rng.normal(0, 0.0008, n)
        drift[t] = d
    r = mkt[:, None] + drift + rng.normal(0, 0.016, (T, n))
    close = 50 * np.exp(np.cumsum(r, axis=0))
    opn = close * np.exp(rng.normal(0, 0.004, (T, n)))
    cols = [f"T{i:02d}" for i in range(n)]
    close = pd.DataFrame(close, index=idx, columns=cols)
    opn = pd.DataFrame(opn, index=idx, columns=cols)
    vol = pd.DataFrame(1e5, index=idx, columns=cols)
    # un titre introduit en cours de route, un autre radié
    close.iloc[:800, 5] = np.nan; opn.iloc[:800, 5] = np.nan
    close.iloc[1500:, 7] = np.nan; opn.iloc[1500:, 7] = np.nan
    sectors = pd.Series([f"S{i % 8}" for i in range(n)], index=cols)
    index_close = pd.Series(100 * np.exp(np.cumsum(mkt)), index=idx)
    return {"open": opn, "close": close, "volume": vol}, sectors, index_close


def test_rules_and_edge():
    px, sec, ic = fake_market()
    g, p = GameRules(), StratParams()
    res = run(px, sec, p, g, "2012-01-01", "2020-03-31", index_close=ic)
    # jamais plus de 25 000 € investis par ligne au moment de l'achat
    buys = res.trades[res.trades.sens == "ACHAT"]
    held = res.holdings
    for d, row in buys.groupby("date"):
        for t in row.ticker:
            q = held.loc[d, t]
            assert q * px["open"].loc[d, t] <= g.max_per_line + 1e-6
    # au plus n lignes
    assert (held.gt(0).sum(axis=1) <= p.n_positions).all()
    # frais = 0,2 % du nominal
    assert np.isclose(res.trades.frais.sum(), (res.trades.quantite * res.trades.prix).sum() * g.fee_rate)
    # cash jamais négatif => équité cohérente
    assert (res.equity > 0).all()
    st = res.stats()
    print(st)
    assert st["sharpe"] > 0.3, "le momentum injecté devrait être capté"


def test_tournament():
    px, sec, ic = fake_market()
    df = evaluate(px, sec, StratParams(), GameRules(), list(range(2012, 2019)), index_close=ic, n_draws=5)
    print(df.to_string(index=False))
    assert df["rang_moyen_sur_50"].mean() < 25, "doit faire mieux que le hasard"


if __name__ == "__main__":
    test_rules_and_edge(); test_tournament(); print("OK")
