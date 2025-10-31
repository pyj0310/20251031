"""Generate efficient frontier analytics and visualization for ``temp.csv``."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATA_PATH = Path('temp.csv')
OUTPUT_SVG = Path('efficient_frontier.svg')

ASSETS: Sequence[str] = ('005930.KS', 'AAPL', 'NVDA')
RISK_FREE_RATE = 0.0
TRADING_DAYS = 252


def load_prices() -> pd.DataFrame:
    raw = pd.read_csv(DATA_PATH, header=[0, 1])
    raw = raw[raw[('Price', 'Ticker')] != 'Date']
    raw.columns = pd.MultiIndex.from_tuples(
        [('Date', 'Date') if col == ('Price', 'Ticker') else col for col in raw.columns]
    )
    raw[('Date', 'Date')] = pd.to_datetime(raw[('Date', 'Date')])
    prices = raw.set_index(('Date', 'Date')).sort_index()
    close_prices = prices['Close'][list(ASSETS)].astype(float)
    return close_prices.dropna()


def annualized_statistics(returns: pd.DataFrame) -> pd.DataFrame:
    mean = returns.mean() * TRADING_DAYS
    vol = returns.std() * math.sqrt(TRADING_DAYS)
    return pd.DataFrame({'return': mean, 'volatility': vol})


def efficient_frontier(mean: pd.Series, cov: pd.DataFrame, points: int = 200) -> pd.DataFrame:
    ones = np.ones(len(mean))
    cov_inv = np.linalg.inv(cov.to_numpy())
    mu = mean.to_numpy()

    A = ones @ cov_inv @ ones
    B = ones @ cov_inv @ mu
    C = mu @ cov_inv @ mu
    D = A * C - B * B

    target_returns = np.linspace(mean.min(), mean.max(), points)
    vols = []
    for r in target_returns:
        lambda_ = (C - B * r) / D
        gamma = (A * r - B) / D
        w = lambda_ * (cov_inv @ ones) + gamma * (cov_inv @ mu)
        vol = math.sqrt(w @ cov.to_numpy() @ w)
        vols.append(vol)
    return pd.DataFrame({'return': target_returns, 'volatility': vols})


def solve_portfolio(mean: pd.Series, cov: pd.DataFrame, objective: str) -> pd.Series:
    ones = np.ones(len(mean))
    cov_inv = np.linalg.inv(cov.to_numpy())
    mu = mean.to_numpy()

    if objective == 'gmv':
        w = cov_inv @ ones
        w /= ones @ cov_inv @ ones
    elif objective == 'max_sharpe':
        excess = mu - RISK_FREE_RATE * ones
        w = cov_inv @ excess
        w /= ones @ cov_inv @ excess
    else:
        raise ValueError(f'Unknown objective: {objective}')

    return pd.Series(w, index=mean.index)


def annotate_portfolio(ax: plt.Axes, weights: pd.Series, mean: pd.Series, cov: pd.DataFrame,
                        label: str, color: str) -> None:
    ret = float(weights @ mean)
    vol = float(math.sqrt(weights.to_numpy() @ cov.to_numpy() @ weights.to_numpy()))
    ax.scatter(vol, ret, color=color, s=120, marker='D', label=label)
    text = '\n'.join([
        label,
        f"{ret * 100:.1f}% return",
        f"{vol * 100:.1f}% vol",
    ])
    ax.annotate(
        text,
        (vol, ret),
        textcoords='offset points',
        xytext=(6, -26),
        ha='left',
        va='top',
        fontsize=9,
        bbox=dict(boxstyle='round,pad=0.25', facecolor='white', alpha=0.8, edgecolor=color),
    )


def main() -> None:
    prices = load_prices()
    returns = prices.pct_change(fill_method=None).dropna()
    stats = annualized_statistics(returns)
    cov = returns.cov() * TRADING_DAYS
    mean = stats['return']

    frontier = efficient_frontier(mean, cov)
    gmv = solve_portfolio(mean, cov, 'gmv')
    max_sharpe = solve_portfolio(mean, cov, 'max_sharpe')

    plt.style.use('seaborn-v0_8')
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(frontier['volatility'], frontier['return'], color='#1f77b4', label='Efficient frontier')
    ax.scatter(stats['volatility'], stats['return'], s=60, color='#ff7f0e', label='Assets')
    for ticker, row in stats.iterrows():
        ax.annotate(ticker, (row['volatility'], row['return']), textcoords='offset points', xytext=(4, 4))

    annotate_portfolio(ax, gmv, mean, cov, 'GMV', '#2ca02c')
    annotate_portfolio(ax, max_sharpe, mean, cov, 'Max Sharpe', '#d62728')

    ax.set_xlabel('Annualized volatility')
    ax.set_ylabel('Annualized return')
    ax.set_title('Efficient Frontier (annualized)')
    ax.legend()
    ax.grid(True, which='both', ls='--', alpha=0.4)
    fig.tight_layout()
    fig.savefig(OUTPUT_SVG, format='svg')

    stats.to_csv('annualized_stats.csv', float_format='%.10f')
    gmv.to_csv('gmv_weights.csv', header=['weight'])
    max_sharpe.to_csv('max_sharpe_weights.csv', header=['weight'])


if __name__ == '__main__':
    main()
