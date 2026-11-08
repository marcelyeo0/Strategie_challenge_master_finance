# Stratégie A — momentum concentré sur le SBF 120 (jeu AMF Clermont, ABC Bourse)

Momentum 12-1 + proximité du plus haut 52 semaines, 5 lignes, rééquilibrage mensuel avec
bande de conservation, exposition pilotée par la volatilité du panier et la tendance du SBF 120.
Le simulateur applique les règles du jeu : 0,20 % de frais par ordre, 25 000 € max par action,
nombre entier d'actions, décision à la clôture, exécution à l'ouverture suivante.

ABC Bourse n'a pas d'API : les cours viennent de Yahoo Finance (`yfinance`), et les ordres
se passent à la main sur le site.

## Installation (PowerShell)

```powershell
cd strat_a
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Utilisation

```powershell
python -m sbf_mom.cli data        # 1. télécharge 2004 -> aujourd'hui (vérifie les tickers signalés en erreur)
python -m sbf_mom.cli backtest    # 2. backtest continu 2006 -> aujourd'hui + resultats/equity.png
python -m sbf_mom.cli concours    # 3. LE test qui compte : P(top 3 sur 50) sur chaque saison 6 nov. -> 23 févr.
python -m sbf_mom.cli grille      # 4. compare 32 réglages (n lignes, fréquence, vol target, filtre de tendance)
python -m sbf_mom.cli ordres --cash 100000                              # 5. ordres du jour, portefeuille vide
python -m sbf_mom.cli ordres --cash 2350 --positions positions.csv      #    ensuite, avec tes lignes
```

`positions.csv` :
```
ticker,quantite
SAF.PA,80
NEX.PA,190
```

Lance `ordres` le **dernier jour de bourse du mois après la clôture** (ou le dimanche soir
avant le 1er), puis passe les ordres le lendemain à l'ouverture, à cours limité.
Options : `--n 4` (nombre de lignes), `--rebal 2W` (toutes les 2 semaines).
`--refresh` force le re-téléchargement.

## Réglages

Tout est dans `sbf_mom/config.py` (`StratParams`). Les plus importants :
`n_positions`, `keep_rank`, `rebalance`, `vol_target`, `regime_ma`, `sector_filter`.

## Limites à garder en tête

- **Biais du survivant** : l'univers est la composition d'octobre 2026, appliquée au passé.
  Les valeurs sorties (Casino, Orpea…) manquent, ce qui embellit tous les backtests.
  Les adversaires simulés tirent dans le même univers, donc le classement est moins biaisé
  que le rendement brut.
- **Adversaires simulés** : 49 portefeuilles aléatoires de 4 à 8 actions, achetés et conservés.
  Les vrais participants feront peut-être mieux ou pire ; c'est un repère, pas une prédiction.
- **Cours ajustés** des dividendes chez Yahoo ; vérifie que le jeu crédite les dividendes.
- **Tickers** : `Aperam` (APAM.AS), `ArcelorMittal` (MT.AS) et `Solvay` (SOLB.BR) sont pris sur
  leur place principale chez Yahoo. Les tickers sans données sont listés par `data`.
- Ne choisis pas le réglage n°1 de `grille` aveuglément : 20 saisons, c'est peu, et on
  sur-apprend vite. Préfère un réglage stable sur toutes les saisons.

## Tests

`python tests/test_synthetic.py` : données synthétiques avec un momentum injecté ;
vérifie le plafond de 25 000 €, le nombre de lignes, les frais, et que la stratégie bat
des portefeuilles aléatoires.
