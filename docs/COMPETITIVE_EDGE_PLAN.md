# QuantSage Competitive Edge Plan

**Date:** January 13, 2026
**Goal:** Transform QuantSage from basic TA system to ML-powered competitive trading platform

---

## Current State vs Target State

| Aspect | Current | Target |
|--------|---------|--------|
| Strategy | 1 basic mean reversion | 3+ ML-enhanced strategies |
| ML/AI | Zero | XGBoost + LSTM + Sentiment |
| Data Sources | OHLCV only | OHLCV + News + On-chain + Social |
| Assets | Crypto only | Crypto + Stocks |
| Edge | None (retail-level) | Data + ML + Ensemble |
| Backtests | None run | Proven profitable in backtest |

---

## Phase 1: Foundation Fixes (Week 1-2)

### 1.1 Run Actual Backtests
**Priority: CRITICAL**

Before adding anything, we need to know if the current system even works.

```
Tasks:
- [ ] Collect 2+ years of historical BTC/ETH data
- [ ] Run mean reversion backtest with current parameters
- [ ] Document results (Sharpe, drawdown, win rate)
- [ ] Identify if strategy is profitable or not
- [ ] Make data-driven decision on strategy direction
```

**Files to create:**
- `scripts/run_full_backtest.py`
- `data/backtests/results/` directory with actual results

### 1.2 Add Stock Trading (Alpaca)
**Priority: HIGH**

```
Tasks:
- [ ] Create `src/data/collectors/stock_collector.py`
- [ ] Implement Alpaca API integration
- [ ] Add stock-specific commission/slippage models
- [ ] Enable stock symbols in config
- [ ] Test with paper trading
```

**Files to create:**
- `src/data/collectors/stock_collector.py`
- `config/strategies/mean_reversion_stocks.yaml`

---

## Phase 2: ML Foundation (Week 3-5)

### 2.1 Feature Engineering Enhancement
**Priority: HIGH**

Current features are basic TA. Need predictive features.

```
New Features to Add:
- [ ] Price momentum (multiple timeframes)
- [ ] Volatility regime indicators
- [ ] Volume profile analysis
- [ ] Cross-asset correlations (BTC vs ETH)
- [ ] Order flow imbalance (if available)
- [ ] Time-based patterns (hour, day, month effects)
- [ ] Lagged returns (1h, 4h, 24h, 7d)
```

**File to update:**
- `src/data/features.py`

### 2.2 XGBoost Classification Model
**Priority: HIGH**

First ML model - predict direction (up/down/flat).

```
Tasks:
- [ ] Create `src/ml/models/xgboost_classifier.py`
- [ ] Implement walk-forward validation
- [ ] Feature importance analysis
- [ ] Hyperparameter optimization
- [ ] Integration with strategy layer
```

**Target Metrics:**
- Accuracy > 52% (better than random)
- Precision > 55% for directional calls
- Feature importance documented

### 2.3 LSTM Price Prediction Model
**Priority: MEDIUM**

Deep learning for sequence prediction.

```
Tasks:
- [ ] Create `src/ml/models/lstm_predictor.py`
- [ ] Implement proper train/val/test split
- [ ] Sequence preparation pipeline
- [ ] Model training with early stopping
- [ ] Prediction confidence scoring
```

**Files to create:**
- `src/ml/models/lstm_predictor.py`
- `src/ml/training/train_lstm.py`

---

## Phase 3: Alternative Data (Week 6-8)

### 3.1 News Sentiment Integration
**Priority: HIGH**

Free/cheap APIs: NewsAPI, CryptoPanic, Alpha Vantage News

```
Tasks:
- [ ] Create `src/data/collectors/news_collector.py`
- [ ] Implement sentiment scoring (VADER or FinBERT)
- [ ] Aggregate sentiment by symbol
- [ ] Add sentiment features to ML models
- [ ] Backtest sentiment signal alone
```

**Files to create:**
- `src/data/collectors/news_collector.py`
- `src/ml/sentiment/sentiment_analyzer.py`

### 3.2 Social Media Sentiment
**Priority: MEDIUM**

Sources: Twitter API, Reddit API, LunarCrush

```
Tasks:
- [ ] Create `src/data/collectors/social_collector.py`
- [ ] Track mentions, sentiment, volume
- [ ] Create social momentum indicators
- [ ] Integrate with feature pipeline
```

### 3.3 On-Chain Metrics (Crypto)
**Priority: MEDIUM**

Sources: Glassnode, IntoTheBlock, CryptoQuant (some free tiers)

```
Tasks:
- [ ] Create `src/data/collectors/onchain_collector.py`
- [ ] Track whale movements, exchange flows
- [ ] MVRV, SOPR, NVT ratios
- [ ] Add as features to ML models
```

---

## Phase 4: Advanced Strategies (Week 9-11)

### 4.1 ML-Enhanced Mean Reversion
**Priority: HIGH**

Keep mean reversion but make it smarter.

```
Enhancements:
- [ ] ML model predicts if mean reversion will work
- [ ] Adaptive thresholds based on volatility
- [ ] Regime filter (don't trade in trends)
- [ ] Confidence-based position sizing
```

### 4.2 Momentum Strategy
**Priority: HIGH**

Complement mean reversion with trend-following.

```
Tasks:
- [ ] Create `src/strategies/momentum.py`
- [ ] Implement trend detection
- [ ] Breakout confirmation with ML
- [ ] Multiple timeframe analysis
```

### 4.3 Ensemble Strategy
**Priority: HIGH**

Combine multiple signals for robust decisions.

```
Tasks:
- [ ] Create `src/strategies/ensemble.py`
- [ ] Weight signals from different strategies
- [ ] ML meta-model for signal combination
- [ ] Adaptive weights based on regime
```

---

## Phase 5: Validation & Production (Week 12-16)

### 5.1 Comprehensive Backtesting
```
Tasks:
- [ ] Backtest all strategies individually
- [ ] Backtest ensemble approach
- [ ] Test across different market regimes
- [ ] Out-of-sample validation
- [ ] Document all results
```

**Success Criteria:**
- Sharpe Ratio > 1.0
- Max Drawdown < 20%
- Win Rate > 50%
- Profit Factor > 1.2

### 5.2 Paper Trading Validation
```
Tasks:
- [ ] Run paper trading for 4+ weeks
- [ ] Monitor daily performance
- [ ] Compare to backtest expectations
- [ ] Fix any live trading issues
```

### 5.3 Production Hardening
```
Tasks:
- [ ] Security audit
- [ ] Error recovery implementation
- [ ] Database upgrade (SQLite → PostgreSQL)
- [ ] Deployment documentation
- [ ] Monitoring and alerting
```

---

## Technology Stack

### ML/AI Stack
```
Current:
- scikit-learn (installed, unused)
- xgboost (installed, unused)

To Add:
- PyTorch or TensorFlow (for LSTM)
- transformers (for FinBERT sentiment)
- optuna (hyperparameter optimization)
- shap (model explainability)
```

### Data Stack
```
Current:
- CCXT (crypto exchanges)
- pandas (data manipulation)

To Add:
- NewsAPI or similar (news data)
- tweepy (Twitter API)
- praw (Reddit API)
- Glassnode API (on-chain)
```

---

## Success Metrics

### Phase Gates

| Phase | Success Criteria | Go/No-Go Decision |
|-------|------------------|-------------------|
| Phase 1 | Backtest complete, stocks working | Continue if backtest not catastrophic |
| Phase 2 | XGBoost accuracy > 52% | Continue if ML adds value |
| Phase 3 | Sentiment improves signals | Continue if data helps |
| Phase 4 | Ensemble Sharpe > 1.0 | Continue to production |
| Phase 5 | Paper trading matches backtest | Go live with small capital |

### Final Success Criteria
```
Minimum for Live Trading:
- Sharpe Ratio > 1.0
- Max Drawdown < 25%
- 4+ weeks profitable paper trading
- All strategies backtested
- Security audit passed
```

---

## Realistic Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 2 weeks | 2 weeks |
| Phase 2: ML Foundation | 3 weeks | 5 weeks |
| Phase 3: Alternative Data | 3 weeks | 8 weeks |
| Phase 4: Advanced Strategies | 3 weeks | 11 weeks |
| Phase 5: Validation | 4 weeks | 15 weeks |

**Total: ~15 weeks to competitive system**

---

## Risk Acknowledgment

### What This Plan Does NOT Guarantee:
1. **Profitability** - Even best quant funds lose money sometimes
2. **Beating the market** - Most traders underperform
3. **Quick returns** - This is a long-term project
4. **Zero losses** - Risk management limits losses, doesn't eliminate them

### What This Plan DOES Provide:
1. **Structured approach** - Clear phases with validation
2. **Modern techniques** - ML/AI that retail traders don't use
3. **Multiple edges** - Data + ML + Ensemble
4. **Risk management** - Built into the architecture
5. **Honest assessment** - Gate checks at each phase

---

## Next Immediate Steps

1. **Commit this plan** to git
2. **Run first backtest** to establish baseline
3. **Decide on Phase 1** start date
4. **Set up development environment** for ML (PyTorch/TensorFlow)

---

*This plan will be reviewed and updated after each phase completion.*
