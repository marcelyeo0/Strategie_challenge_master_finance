"""Paramètres de la stratégie A et règles du jeu ABC Bourse (AMF Clermont 2026-2027)."""
from dataclasses import dataclass, field


@dataclass
class GameRules:
    capital: float = 100_000.0       # capital de départ (non modifiable sur ABC Bourse)
    fee_rate: float = 0.002          # 0,20 % par opération (achat ET vente)
    max_per_line: float = 25_000.0   # plafond d'investissement par action (guide du membre)
    start: str = "2026-11-06"
    end: str = "2027-02-23"


@dataclass
class StratParams:
    # --- signal ---
    mom_lookback: int = 252          # 12 mois
    mom_skip: int = 21               # on saute le dernier mois (12-1)
    high_lookback: int = 252         # distance au plus haut 52 semaines
    w_mom: float = 0.5               # poids du momentum 12-1 dans le score
    w_high: float = 0.5              # poids de la proximité du plus haut 52 sem.
    sector_filter: int = 0           # 0 = off ; k > 0 = ne garder que les k meilleurs secteurs
    sector_lookback: int = 126       # momentum sectoriel sur 6 mois
    min_history: int = 260           # jours de cotation minimum pour être éligible
    # --- portefeuille ---
    n_positions: int = 5             # nombre de lignes
    keep_rank: int = 15              # bande de conservation : on garde une ligne tant qu'elle reste dans ce top
    rebalance: str = "M"             # "M" = mensuel (1re séance du mois), "2W" = toutes les 2 semaines, "W" = hebdo
    # --- gestion du risque ---
    vol_target: float | None = 0.30  # vol annualisée cible du panier (None = off). Élevée exprès : on joue un classement
    vol_lookback: int = 126          # 6 mois, comme Barroso & Santa-Clara
    max_exposure: float = 1.0        # pas de levier
    regime_ma: int | None = 200      # filtre de tendance sur l'indice (None = off)
    regime_exposure: float = 0.5     # exposition max quand l'indice est sous sa moyenne mobile
    min_trade_eur: float = 500.0     # on ignore les ajustements trop petits (frais pour rien)
    tickers_excluded: list = field(default_factory=list)
