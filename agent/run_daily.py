"""Le job quotidien de l'agent. Lancé chaque matin de semaine par le Planificateur de tâches.

python run_daily.py            # run normal : Telegram + Notion
python run_daily.py --dry-run  # affiche le message, n'envoie rien, ne modifie pas state.json
"""
import argparse
import logging
import os
import sys
import traceback
from datetime import date, datetime

import pandas as pd

from agent import config, notion_log, report, state as st, telegram
from sbf_mom import data
from sbf_mom.config import GameRules, StratParams
from sbf_mom.live import target_orders

# Lancé par pythonw.exe (sans fenêtre), il n'y a pas de console : on écrit dans le vide
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
# Windows : la console n'est pas en UTF-8 par défaut -> les emojis plantent sans ça
sys.stdout.reconfigure(encoding="utf-8")
config.LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(config.LOG_DIR / f"run_{date.today()}.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("agent")


def main(dry_run: bool, with_news: bool) -> None:
    p, g = StratParams(), GameRules()
    state = st.load()
    uni = data.load_universe()
    tickers = uni["ticker"].tolist()
    names = uni.set_index("ticker")["name"]
    sectors = uni.set_index("ticker")["sector"]

    # 1) commandes reçues sur Telegram depuis le dernier run
    receipts = []
    if not dry_run:
        texts, state["tg_offset"] = telegram.get_commands(state["tg_offset"])
        for txt in texts:
            try:
                receipts.append(st.apply_command(state, txt, tickers))
            except Exception as e:  # une commande mal tapée ne doit pas bloquer le run
                receipts.append(f"❌ {telegram.esc(txt)} : {telegram.esc(e)}")
        log.info("%d commande(s) traitée(s)", len(texts))

    # 2) données à jour (téléchargement complet : simple et robuste)
    px = data.download(tickers + [data.INDEX_TICKER], refresh=True)
    idx = px["close"].get(data.INDEX_TICKER)
    for k in px:
        px[k] = px[k].drop(columns=[data.INDEX_TICKER], errors="ignore")
    idx = data.index_or_proxy(px["close"], idx)  # Yahoo n'a plus ^SBF120 depuis 2015
    last_date = px["close"].index[-1].date()
    prev_bday = (pd.Timestamp(date.today()) - pd.offsets.BDay(1)).date()
    stale = last_date < prev_bday

    # 3) stratégie
    positions = {t: v["qty"] for t, v in state["positions"].items()}
    top, ords, meta = target_orders(px, sectors, names, p, g, positions, state["cash"], index_close=idx)

    month = date.today().strftime("%Y-%m")
    rebalance = state["last_rebalance"] != month  # 1er run du mois (ou /rebal)

    # 4) message
    if rebalance:
        news = {}
        if with_news:
            from agent import news as nw
            for t in meta["selected"]:
                try:
                    news[t] = nw.summarize(names.get(t, t), nw.headlines(t))
                except Exception as e:
                    log.warning("news %s : %s", t, e)
        msg = report.rebalance_msg(meta, ords, names, sectors, px["close"], news)
        kind = "Rééquilibrage"
    else:
        msg = report.checkup_msg(meta, state, names, p.keep_rank, g.capital)
        kind = "Check-up"
    if stale:
        msg = f"⚠️ Données du {last_date:%d/%m} : Yahoo n'a pas encore le dernier cours.\n\n" + msg
    if receipts:
        msg = "\n".join(receipts) + "\n\n" + msg

    if dry_run:
        print(msg)
        return

    telegram.send(msg)
    if rebalance:
        state["last_rebalance"] = month
    st.save(state)
    try:
        notion_log.log_run(kind, meta["regime"], meta["exposure"], meta["equity"], msg,
                           title=f"{datetime.now():%Y-%m-%d %H:%M} · {kind}")
    except Exception as e:  # Notion en panne ne doit pas faire échouer le run
        log.warning("Notion : %s", e)
    log.info("run terminé (%s)", kind)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--news", action="store_true", help="résumé d'actualité par le LLM")
    a = ap.parse_args()
    try:
        main(a.dry_run, a.news)
    except Exception:
        tb = traceback.format_exc()
        log.error(tb)
        if not a.dry_run:
            try:
                telegram.send("❌ <b>Le run a planté</b>\n<pre>" + telegram.esc(tb[-3000:]) + "</pre>")
            except Exception:
                log.error("impossible de prévenir sur Telegram")
        sys.exit(1)