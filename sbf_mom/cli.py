"""Point d'entrée.

  python -m sbf_mom.cli data                 # télécharge / met à jour les cours
  python -m sbf_mom.cli backtest             # backtest continu 2006 -> aujourd'hui
  python -m sbf_mom.cli concours             # P(top 3) sur chaque saison nov.-févr.
  python -m sbf_mom.cli grille               # compare quelques réglages sur le critère P(top 3)
  python -m sbf_mom.cli ordres --cash 100000 [--positions positions.csv]
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from . import data
from .backtest import run
from .config import GameRules, StratParams
from .live import target_orders
from .tournament import evaluate

OUT = data.ROOT / "resultats"


def _load(refresh=False):
    uni = data.load_universe()
    tickers = uni["ticker"].tolist() + [data.INDEX_TICKER]
    px = data.download(tickers, refresh=refresh)
    idx = px["close"].get(data.INDEX_TICKER)
    for k in px:
        px[k] = px[k].drop(columns=[data.INDEX_TICKER], errors="ignore")
    idx = data.index_or_proxy(px["close"], idx)
    sectors = uni.set_index("ticker")["sector"]
    names = uni.set_index("ticker")["name"]
    return px, idx, sectors, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["data", "backtest", "concours", "grille", "ordres"])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--positions", type=Path)
    ap.add_argument("--cash", type=float, default=100_000.0)
    ap.add_argument("--n", type=int, help="nombre de lignes")
    ap.add_argument("--rebal", choices=["M", "2W", "W"])
    a = ap.parse_args()

    p, g = StratParams(), GameRules()
    if a.n:
        p = replace(p, n_positions=a.n)
    if a.rebal:
        p = replace(p, rebalance=a.rebal)
    OUT.mkdir(exist_ok=True)

    px, idx, sectors, names = _load(refresh=a.refresh or a.cmd == "data")
    if a.cmd == "data":
        print(px["close"].shape, "->", px["close"].index[-1].date())
        return

    if a.cmd == "backtest":
        res = run(px, sectors, p, g, "2006-01-01", str(px["close"].index[-1].date()), index_close=idx)
        print(pd.Series(res.stats()).to_string())
        res.equity.to_csv(OUT / "equity.csv")
        res.trades.to_csv(OUT / "trades.csv", index=False)
        try:
            import matplotlib.pyplot as plt
            ax = (res.equity / res.equity.iloc[0]).plot(label="Stratégie A", logy=True, figsize=(10, 5))
            if idx is not None:
                i = idx.loc[res.equity.index[0]:].dropna()
                (i / i.iloc[0]).plot(ax=ax, label="SBF 120 (prix)")
            ax.legend(); ax.set_title("Stratégie A, frais 0,20 % inclus")
            plt.tight_layout(); plt.savefig(OUT / "equity.png", dpi=120)
            print(f"Graphique : {OUT / 'equity.png'}")
        except ImportError:
            pass

    elif a.cmd == "concours":
        last_year = px["close"].index[-1].year - 1
        df = evaluate(px, sectors, p, g, list(range(2006, last_year)), index_close=idx)
        print(df.to_string(index=False))
        df.to_csv(OUT / "concours.csv", index=False)

    elif a.cmd == "grille":
        last_year = px["close"].index[-1].year - 1
        years = list(range(2006, last_year))
        grid = []
        for n in (4, 5, 6, 8):
            for rebal in ("M", "2W"):
                for vt in (None, 0.30):
                    for reg in (None, 200):
                        q = replace(p, n_positions=n, rebalance=rebal, vol_target=vt, regime_ma=reg)
                        df = evaluate(px, sectors, q, g, years, index_close=idx, n_draws=10)
                        grid.append({"n": n, "rebal": rebal, "vol_target": vt, "regime": reg,
                                     "P(top3)": df["P(top3)"].mean(),
                                     "rang_moyen": df["rang_moyen_sur_50"].mean(),
                                     "rdt_moyen_%": df["strat_%"].mean(),
                                     "pire_saison_%": df["strat_%"].min()})
        gdf = pd.DataFrame(grid).sort_values("P(top3)", ascending=False)
        print(gdf.to_string(index=False))
        gdf.to_csv(OUT / "grille.csv", index=False)
        print("\nAttention : choisir le meilleur réglage sur ces mêmes saisons, c'est du surapprentissage."
              " Préfère un réglage bon partout plutôt que le premier de la liste.")

    elif a.cmd == "ordres":
        pos = {}
        if a.positions and a.positions.exists() and a.positions.stat().st_size > 0:
            dfp = pd.read_csv(a.positions)
            pos = dict(zip(dfp["ticker"], dfp["quantite"].astype(int)))
        top, ords, m = target_orders(px, sectors, names, p, g, pos, a.cash, index_close=idx)
        print(f"Date des données : {m['date'].date()} | valeur du portefeuille : {m['equity']:,.0f} € | "
              f"régime : {m['regime']} | exposition cible : {m['exposure']:.0%} | {m['per_line']:,.0f} € par ligne")
        print("\nTop 20 du score :\n" + top.to_string(index=False))
        print("\nOrdres à passer sur ABC Bourse (à l'ouverture, ordre à cours limité conseillé) :")
        print(ords.to_string(index=False) if not ords.empty else "  aucun")


if __name__ == "__main__":
    main()
