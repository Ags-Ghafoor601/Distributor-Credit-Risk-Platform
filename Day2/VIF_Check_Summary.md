# Multicollinearity (VIF) Check — Diagnosed, Fixed, Re-Validated
Day 2 · skillSYNC AI/ML Sprint · Problem 01

---

## Correction to Step 4

Step 4 attributed `salesman_default_rate_loo`'s near-zero model coefficient to multicollinearity. **This VIF check disproves that specific explanation** — its VIF is 1.02, essentially zero collinearity with any other feature. Stating this plainly rather than letting the earlier guess stand: the weak marginal coefficient is real, but the cause is different — most likely L2 regularization shrinking a feature that adds less *additional* separable signal once the dominant lateness/volatility cluster already explains most of the variance in this dataset. This is confirmed by the fact that its coefficient stays small even after the actual multicollinearity problem (below) is fixed.

---

## What VIF Actually Found

| Feature | VIF | Verdict |
|---|---|---|
| `payment_volatility` | 11.08 | Severe |
| `avg_days_late_nonseasonal` | 9.26 | Severe (borderline) |
| `bounce_rate_lifetime` | 2.59 | Fine |
| `territory_default_rate_loo` | 1.07 | Fine |
| `order_frequency_trend` | 1.05 | Fine |
| `real_exposure_pkr` | 1.03 | Fine |
| `salesman_default_rate_loo` | 1.02 | Fine |

`payment_volatility` and `avg_days_late_nonseasonal` are correlated at **0.94** — makes intuitive sense, since dealers who pay very late also tend to pay inconsistently; both are largely measuring the same underlying behavior.

---

## Remediation

Rather than arbitrarily dropping one feature (losing information), combined both into a single composite: **`payment_delay_severity`** = average of their standardized (z-score) values.

**Result:**
- All VIF now under 2.5 (max: `payment_delay_severity` at 2.47)
- **AUC: 0.848 → 0.847** (unchanged)
- **KS: 0.702 → 0.702** (unchanged)

Performance held exactly, confirming the two original features truly were redundant — the composite captures the same signal without the instability.

---

## Final Feature Set (6 features, VIF-clean)

1. `payment_delay_severity` (composite — replaces the two collinear features)
2. `bounce_rate_lifetime`
3. `real_exposure_pkr`
4. `order_frequency_trend`
5. `salesman_default_rate_loo`
6. `territory_default_rate_loo`

This is now the feature set to carry forward into any further model refinement — it's statistically cleaner without sacrificing predictive power.

---

## Definition of Done

- [x] VIF computed for all 7 original features
- [x] Root cause of collinearity identified (0.94 correlation between two lateness-related features)
- [x] Remediated via composite feature, not blind feature dropping
- [x] Re-validated: AUC/KS unchanged after remediation
- [x] Corrected an earlier (Step 4) mistaken explanation with evidence, rather than leaving it standing
