"""
H-052: Premium Index Cross-Sectional Factor Research

Signal: Rank 14 crypto assets by average perpetual-to-spot premium/discount
over a lookback window. Contrarian: long most discounted (shorts aggressive),
short least discounted.

Results:
- IS: 100% params positive (30/30), best W5 R3 N4 Sharpe 2.25, +40.4%, DD -11.8%
- WF: 23/24 majority positive, mean OOS Sharpe 1.35. 3/24 ALL folds positive.
  - Best WF: W10 R3 N4 mean 2.01, W5 R5 N4 mean 1.86 (6/6 positive)
- Split-half: 2.18 / 2.95 (strong in both halves)
- Fee sensitivity: 1x fees Sharpe 1.88, 2x fees 1.50, 5x fees 0.39
- Correlations: -0.142 H-012 (XSMom), 0.097 H-021 (VolMom), 0.167 H-046 (Accel)
- Deployed params: W5 R5 N4 (best WF with all folds positive)

Data source: Bybit V5 /v5/market/premium-index-price-kline
"""

# Research code saved at /tmp/h052_premium_research.py and /tmp/h052_validation.py
# See runner at paper_trades/h052_premium/runner.py
