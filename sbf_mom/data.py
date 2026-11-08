"""Téléchargement et cache des cours quotidiens (Yahoo Finance via yfinance).

ABC Bourse n'a pas d'API : on prend l'historique chez Yahoo, et on peut contrôler
les derniers cours avec un export manuel ABC Bourse (voir load_abc_export).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data"
INDEX_TICKER = "^SBF120"


def load_universe(path: Path | str = ROOT / "universe.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def download(tickers: list[str], start: str = "2004-01-01", end: str | None = None,
             refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Retourne {'open': df, 'close': df, 'volume': df} (index = dates, colonnes = tickers).

    Les cours sont ajustés des dividendes et opérations sur titres (auto_adjust=True).
    Résultat mis en cache dans data/*.parquet (ou .csv si pyarrow absent).
    """
    CACHE.mkdir(exist_ok=True)
    files = {k: CACHE / f"{k}.csv" for k in ("open", "close", "volume")}
    if not refresh and all(f.exists() for f in files.values()):
        out = {k: pd.read_csv(f, index_col=0, parse_dates=True) for k, f in files.items()}
        missing = [t for t in tickers if t not in out["close"].columns]
        if not missing:
            return out
        print(f"[data] {len(missing)} tickers absents du cache, nouveau téléchargement")

    import yfinance as yf  # import tardif : le reste du code tourne sans

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True,
                      group_by="column", progress=True, threads=True)
    out = {
        "open": raw["Open"].copy(),
        "close": raw["Close"].copy(),
        "volume": raw["Volume"].copy(),
    }
    for k, df in out.items():
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.sort_index(inplace=True)
        df.to_csv(files[k])
    report_missing(out["close"], tickers)
    return out


def report_missing(close: pd.DataFrame, tickers: list[str]) -> list[str]:
    bad = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
    if bad:
        print(f"[data] ATTENTION, aucun cours pour : {', '.join(bad)}"
              " -> corrige le ticker dans universe.csv")
    last = close.ffill().iloc[-1]
    stale = [t for t in close.columns if close[t].last_valid_index() is not None
             and close[t].last_valid_index() < close.index[-1] - pd.Timedelta(days=10)]
    if stale:
        print(f"[data] Cours arrêtés depuis plus de 10 jours : {', '.join(stale)}")
    return bad


def load_abc_export(path: Path | str) -> pd.DataFrame:
    """Lit un export ABC Bourse au format texte (ticker;date;open;high;low;close;volume).

    Sert à vérifier que les derniers cours Yahoo collent aux cours du jeu.
    """
    df = pd.read_csv(path, sep=";", header=None,
                     names=["code", "date", "open", "high", "low", "close", "volume"],
                     decimal=",")
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    return df
