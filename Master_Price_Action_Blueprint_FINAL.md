# Master Price Action Blueprint — FINAL Complete Specification

> **Author / Source**: Harale Datta (Phone: 8698105122) — `FINAL PDF 2026.pdf` (All 33 Pages Complete Blueprint)  
> **Master File Location**: `G:\Poovendan\AI\Trading\Share\ReadyToDeploy\Prod_code_01\Price_Action_Strategy\Master_Price_Action_Blueprint_FINAL.md`  
> **Status**: 100% Verified & Fully Implemented across Python Execution Suites (`Trade_Stock`, `Trade_Option`, and `common/trading_core.py`)

---

## Table of Contents
1. Document Cover & Dedication (Page 1)
2. 1-Candle Anatomy & Price Action Fundamentals (Page 2)
3. Candlestick Engulfing Formations (Page 3)
4. Bullish & Bearish Swing Mechanics & Rules (Pages 4 – 5)
5. A-B-C-D Reversal Confirmation Engine (Pages 6 – 7)
6. The 5 Master Bullish & Bearish Setups & Variations (Pages 8 – 17)
7. Trend Identification & Higher Timeframe Rules (Pages 18 – 20)
8. Bulls & Bears — Support & Resistance Identification (Pages 21 – 23)
9. Theory of Negation — Target Calculation Engine (Pages 24 – 26)
10. Option Trading Simplified — Mandatory Execution Rules (Page 27)
11. Real-World Trade Case Studies & Chart Annotations (Pages 28 – 33)
12. Core Engine Function Mapping & Code References

---

## 1. Document Cover & Dedication (Page 1)
* **Cover Page**: Dedicated with an auspicious image of Goddess Lakshmi for wealth, discipline, consistency, and trading excellence.

---

## 2. 1-Candle Anatomy & Price Action Fundamentals (Page 2)

```
       BULLISH CANDLE                        BEARISH CANDLE
     High of the Range                    High of the Range
            │                                    │
    ┌───────────────┐ Price Close        ┌───────────────┐ Price Open
    │               │                    │               │
    │   REAL BODY   │ (Price Rises)      │   REAL BODY   │ (Price Falls)
    │               │                    │               │
    └───────────────┘ Price Open         └───────────────┘ Price Close
            │                                    │
     Low of the Range                    Low of the Range
```

* **Bullish Green Candle**:
  * `Open`: Bottom of real body.
  * `Close`: Top of real body (`Close > Open`).
  * `Real Body`: Represents buying expansion / Demand taking control.
  * `Wicks (Tails)`: High and Low extremes of the timeframe range.
* **Bearish Red Candle**:
  * `Open`: Top of real body.
  * `Close`: Bottom of real body (`Close < Open`).
  * `Real Body`: Represents selling expansion / Supply taking control.
  * `Wicks (Tails)`: High and Low extremes of the timeframe range.

---

## 3. Candlestick Engulfing Formations (Page 3)

1. **1-Bullish Engulfing (At Bottom)**:
   * Formed at the end of a downtrend / floor of price drop.
   * A green real body completely wraps / engulfs the prior red body and wicks.
   * Signals institutional accumulation.

2. **2-Bearish Engulfing (At Top)**:
   * Formed at the peak of an uptrend / ceiling of rally.
   * A red real body completely wraps / engulfs the prior green body and wicks.
   * Signals institutional distribution.

---

## 4. Bullish & Bearish Swing Mechanics & Rules (Pages 4 – 5)

### Bullish Swings — Bearish Reversal / Higher-High (HH) Sweep (Page 4)
* **Rule 1 (Swing Distance)**: Must have **MORE THAN 2 CANDLES** (at least 3 candles gap) between High 1 and High 2.
* **Rule 2 (In-between Closing Guard)**: None of the in-between candles between High 1 and High 2 must **CLOSE ABOVE High 1** (wicks allowed).
* **Sequence**:
  1. Mark **High 1** (`HIGH-1`).
  2. Pullback swing ($> 2$ candles gap).
  3. Price rallies to form **High 2** (`HIGH-2 GREEN`) which breaks / sweeps above High 1.
  4. Next candle does **NOT break High 2** (liquidity rejection / stop run).
* **Verdict**: **PRICE WILL GO DOWN** (Triggers Bearish Reversal Trade).

### Bearish Swings — Bullish Reversal / Lower-Low (LL) Sweep (Page 5)
* **Rule 1 (Swing Distance)**: Must have **MORE THAN 2 CANDLES** (at least 3 candles gap) between Low 1 and Low 2.
* **Rule 2 (In-between Closing Guard)**: None of the in-between candles between Low 1 and Low 2 must **CLOSE BELOW Low 1** (wicks allowed).
* **Sequence**:
  1. Mark **Low 1** (`L-1`).
  2. Bounce swing ($> 2$ candles gap).
  3. Price falls to form **Low 2** (`L-2`) which breaks / sweeps below Low 1.
  4. Next candle does **NOT break Low 2** (reclaims floor line / buyer absorption).
* **Verdict**: **PRICE WILL GO UP** (Triggers Bullish Reversal Trade).

---

## 5. A-B-C-D Reversal Confirmation Engine (Pages 6 – 7)

```
================================================================================
          SETUP 1: BULLISH A-B-C-D REVERSAL (Page 6)
================================================================================
                     [D: Green Confirmation Close > BM]
                                   ####
                     [B: Breakout]  ####
                           ####    ####
             Benchmark ────┼───────┼────────────────────────────── (A.High Line)
                           │  [C]  │  (Red Retest Holds Above SL)
                           │ ####  │
            [A: Anchor]    │       │
               ####        │       │
              ######       │       │
  (NO PRICE AT LEFT >>>>>>)
  [SL Floor Line] ────────────────────────────────────────────────── (L2 - 2 Buffer)
================================================================================
```

### Setup 1 Bullish Sequence (Page 6)
1. **Anchor Candle A**: Bullish Engulfing formed at bottom.
   * **Left-Side Rule**: Must have **"NO PRICE AT LEFT >>>>>>"** (A.low is the absolute lowest low in lookback).
   * **Benchmark ($BM$)** = `A.high` (Wick Top of Candle A).
   * **Stop Loss ($SL$)** = `A.low - buffer` (`L2 - 2` buffer).
2. **Breakout Candle B**: Green candle closing above Benchmark line (`Close > A.high`).
3. **Retest Candle C**: Red pullback candle dipping into Benchmark zone (`Low <= BM`, `Close > SL`, `is_red = True`).
4. **Confirmation Candle D**: Green candle closing back above Benchmark line (`Close > A.high`, `Close > Open`).
5. **Trade Trigger**: Confirmed on Candle D bar completion!

### Setup 1 Bearish Sequence (Page 7)
1. **Anchor Candle A**: Bearish Engulfing formed at top with **"NO PRICE LEFT SIDE>>>"**.
   * **Benchmark ($BM$)** = `A.low` (Wick Bottom of Candle A).
   * **Stop Loss ($SL$)** = `A.high + buffer` (`H2 + 2` buffer).
2. **Breakout Candle B**: Red candle closing below Benchmark line (`Close < A.low`).
3. **Retest Candle C**: Green retest candle rallying into Benchmark zone (`High >= BM`, `Close < SL`, `is_red = False`).
4. **Confirmation Candle D**: Red candle closing back below Benchmark line (`Close < A.low`, `Close < Open`).
5. **Trade Trigger**: Bearish Short / Put trade confirmed on Candle D bar completion!

---

## 6. The 5 Master Bullish & Bearish Setups & Variations (Pages 8 – 17)

### Setup 2: Lower-Low Swing Pattern Variations (Pages 8 – 10)
* **Variation 1 (Pages 8 & 9 — Red Sweep)**:
  * Low 2 is a **RED candle** (`Close < Open`) that dips or closes below Low 1.
  * Recovered by a green bounce candle (`<<< LOW NOT BREAK`).
  * $B \rightarrow C \rightarrow D$ confirmation $\rightarrow$ Bullish rally!
* **Variation 2 (Page 10 — Green/Neutral Wick Sweep)**:
  * Low 2 is a **GREEN / Neutral candle** (`Close >= Open`).
  * Lower wick pierces below Low 1, but body closes **GREEN** above Low 1!
  * Immediate bullish expansion rally!

### Setup 3: Two Higher Highs / Two Lower Lows (Pages 12 & 13)
* **Bullish**: Successive higher high candles $A_1, A_2$ forming engulfing structure.
* **Bearish**: Successive lower low candles $A_1, A_2$ forming engulfing structure.

### Setup 4: Pin Bar / Hammer (Baby Candle CRC) (Pages 11 & 15)
* **Bullish Pin Bar (Page 11)**:
  * Title: **`PIN BAR / HAMER [GREEN AT BOTTOM]`**.
  * Small real body with long lower tail (`lower_wick > body`).
  * Primary: Green body (`Close >= Open`). Secondary: Red body (requires `lower_wick >= 1.8 * body`).
* **Bearish Shooting Star (Page 15 — Bajaj Auto 1D)**:
  * Title: **`PIN BAR / HAMER AT TOP`**.
  * Small real body with long upper tail (`upper_wick > body`).
  * Primary: Red body (`Close <= Open`). Secondary: Green body (requires `upper_wick >= 1.8 * body`).

### Setup 5: Bullish & Bearish Harami (Inside Bar) (Page 32)
* **Bullish Harami**: Small green inside bar enclosed within prior bearish mother candle (`high <= mother_open`, `low >= mother_close`).
* **Bearish Harami**: Small red inside bar enclosed within prior bullish mother candle (`high <= mother_close`, `low >= mother_open`).

### Trend Continuations & Re-Entries (Pages 16 & 17)
* **Bullish Trend Continuation (Page 16)**:
  * Context: Established Uptrend (Higher Highs & Higher Lows).
  * Price pulls back to prior swing support level.
  * When a Bullish Engulfing or Reclaim candle forms at support, **bypasses full B-C-D delay** and enters immediately on the **next candle close**!
* **Bearish Trend Continuation (Page 17)**:
  * Context: Established Downtrend (Lower Highs & Lower Lows).
  * Price pulls back to resistance, forms Bearish Engulfing $\rightarrow$ Immediate re-entry / short on next candle close.

---

## 7. Trend Identification & Higher Timeframe Rules (Pages 18 – 20)

1. **Highest Timeframe Principle**:
   * Always verify directional bias on the **Highest (Daily) Timeframe** (Weekly if needed).
2. **Uptrend Structure**: Sequence of **Higher Highs (HH) & Higher Lows (HL)**.
3. **Downtrend Structure**: Sequence of **Lower Highs (LH) & Lower Lows (LL)**.

---

## 8. Bulls & Bears — Support & Resistance Identification (Pages 21 – 23)

### Bullish Trend Support Levels (Page 22)
1. **Momentum High**: **HIGH Price** of Momentum High candle (retest ceiling-turned-floor).
2. **Higher-High**: **LOW Price** of Higher-High breakout candle.
3. **Bullish Engulfing**: **LOW Price** of Bullish Engulfing formation.

### Bearish Trend Resistance Levels (Page 23)
1. **Momentum Low**: **LOW Price** of Momentum Low candle.
2. **Lower-Low**: **HIGH Price** of Lower-Low breakout candle.
3. **Bearish Engulfing**: **HIGH Price** of Bearish Engulfing formation.

---

## 9. Theory of Negation — Target Calculation Engine (Pages 24 – 26)

### Negation Rules
* **Negation of Bearish Resistance Points (Bullish Targets)**:
  1. *Momentum Low (ML)*: Negated if price closes below & re-tests lowest price of ML.
  2. *Lower Low (LL)*: Negated if price closes / retests / closes above highest price of LL.
  3. *Bearish Engulfing (EC)*: Negated if price closes above highest price of EC.
* **Negation of Bullish Support Points (Bearish Targets)**:
  1. *Momentum High (MH)*: Negated if price closes above & re-tests highest price of MH.
  2. *Higher High (HH)*: Negated if price closes / retests / closes below lowest price of HH.
  3. *Bullish Engulfing (EC)*: Negated if price closes below lowest price of EC.

### Golden Rule of Negation
> [!IMPORTANT]
> **Once any Resistance or Support is NEGATED (closed past), it is completely discarded. The Price Target automatically moves to the NEXT NON-NEGATED level!**

### Target Timeframe Scaling Rule (+2 TF Rule)
$$\text{Target Timeframe} = \text{Trading Timeframe} + 2 \text{ Higher Timeframes}$$
* **Example**: 1-Hour Entry $\rightarrow$ Target from 4-Hour chart.
* **Example**: 3-Min / 15-Min Options Entry $\rightarrow$ Target from 15-Min / 60-Min charts.

### Negation Chart Proofs (Pages 25 & 26)
* **Bullish (Page 25)**: Reversal at ₹620 $\rightarrow$ Discards negated levels (₹770) $\rightarrow$ Targets **Non-Negated Bearish Engulfing at ₹799.80**!
* **Bearish (Page 26)**: Reversal at ₹1,080 $\rightarrow$ Discards negated levels (965, 940, 838.09) $\rightarrow$ Targets **Non-Negated Higher High Support at ₹726.22**!

---

## 10. Option Trading Simplified — Mandatory Execution Rules (Page 27)

```
================================================================================
                OPTION TRADING SIMPLIFIED — MANDATORY RULES (Page 27)
================================================================================
 1. INTRADAY INDEX OPTIONS TIMEFRAMES:
    - Primary Timeframes: 3 MIN and 15 MIN.
    - Mandatory Check: Check BOTH PE & CE once before trade.
    - Preference: Give preference to higher timeframe (15 MIN).

 2. STOCK OPTIONS TIMEFRAMES:
    - Primary Timeframes: 15 MIN, 1 HR, 4 HR candles.
    - Carryover: Positional carryover supported. Liquid stocks only.

 3. RISK & POSITION SIZING:
    - Lot Size: Practice with 1 LOT before scaling.
    - R:R Filter: Demand highest R:R (minimum R:R >= 1.88) before entering.
    - Stop Loss: ALL SL IS ON A CLOSING BASIS (wicks ignored).
    - Stop Loss Buffer: Options buffer = max(2.00, price * 0.015) [L2 - 2 / H2 + 2].

 4. TRADE DISCIPLINE & EXITS:
    - Single Execution: If SL or Target hit, CLOSE trade immediately.
    - Strictly Prohibited: NO AVERAGING, NO HEDGING, NO SHORT SELLING OF OPTIONS.
    - No Re-Entry: NO ENTRY on finished/stopped trades.
    - Target Achieved Filter: Discard trade if T1/T2 already touched prior to entry.

 5. THE 5 MOST WINNING PROBABILITY SETUPS:
    1. Bullish Engulf A-B-C-D
    2. Lower-Low Trend Reversal (Liquidity Sweeps Var 1 & Var 2)
    3. Baby Candle (Likely Pinbar / Hammer) after successive downtrend
    4. Bullish Harami Candle (Inside Bar)
    5. Sell Side Vice-Versa (Bearish Engulf, HH Sweep, Shooting Star, Bearish Harami)
================================================================================
```

---

## 11. Real-World Trade Case Studies & Chart Annotations (Pages 28 – 33)

1. **Case Study 1: EICHERMOT 7200 CE (15m Option Chart — Page 28)**:
   * Setup 1 A-B-C-D: Entry ₹180 $\rightarrow$ Target **₹326.96** (**+81.6% return**).
2. **Case Study 2: BANKNIFTY 34300 PE (3m Option Chart — Page 29)**:
   * Setup 2 LL Sweep: Entry ₹265.00, SL `STOP LOSS L2-2` (₹240.50) $\rightarrow$ `TARGET 420` hit at **₹430.15** (**+62.3% return**).
3. **Case Study 3: Negation Target Option Chart (Page 30)**:
   * Reversal D at ₹525 $\rightarrow$ `LAST BUYER SWING CHESS` Target hit at **₹750.55** (**+42.9% return**).
4. **Case Study 4: NIFTY 18650 CE (Index Option 3m/15m — Page 31)**:
   * Setup 4 Baby Candle CRC after 3/4 Swing Downtrend: Entry ₹90.00 $\rightarrow$ `PRICE CHESS LAST BUYER` Target hit at **₹158.80** (**+76.4% return**).
5. **Case Study 5: BANKNIFTY 54000 PE (15m Option Chart — Page 32)**:
   * Setup 5 Bullish Harami: Inside bar entry at ₹260.00 $\rightarrow$ Massive surge to **₹765.00** (**+194.2% return**).
6. **Case Study 6: BANKNIFTY 54000 PE Bearish Reversal (Page 33 — "ONLY FOR OPTION")**:
   * Special Option Rule: Reversal entry at ₹580.00 $\rightarrow$ `PRICE CHESS PREVIOUS REVERSAL SWINGS` Support Target hit at **₹363.32**.

---

## 12. Core Engine Function Mapping & Code References

| Blueprint Concept | Python Function | Source File |
| :--- | :--- | :--- |
| **Asset-Adaptive Buffer (`L2-2` / `H2+2`)** | [`calculate_sl_buffer()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L398) | `common/trading_core.py` |
| **Bullish Engulfing (Setup 1)** | [`find_anchor_bullish_engulfing()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L410) | `common/trading_core.py` |
| **LL Sweep Var 1 & Var 2 (Setup 2)** | [`find_anchor_ll_sweep()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L421) | `common/trading_core.py` |
| **Two Higher Highs (Setup 3)** | [`find_anchor_two_higher_highs()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L511) | `common/trading_core.py` |
| **Baby Candle / Pinbar (Setup 4)** | [`find_anchor_hammer_baby()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L469) | `common/trading_core.py` |
| **Bullish Harami (Setup 5)** | [`find_anchor_bullish_harami()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L495) | `common/trading_core.py` |
| **Bearish Anchors (Setups 1–5)** | `find_anchor_bearish_engulfing`, `find_anchor_hh_sweep`, etc. | `common/trading_core.py` |
| **A-B-C-D Breakout Engine** | [`scan_anchor_bcd_breakout()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L535) | `common/trading_core.py` |
| **Theory of Negation Engine** | [`find_profit_targets()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L275) & `find_profit_targets_bearish()` | `common/trading_core.py` |
| **Trend Continuation Re-Entry** | [`scan_trend_continuation_reentry()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L2032) | `common/trading_core.py` |
| **Unified Scanner Entry Point** | [`scan_anchor_bcd_breakout_generic()`](file:///G:/Poovendan/AI/Trading/Share/ReadyToDeploy/Prod_code_01/Price_Action_Strategy/common/trading_core.py#L2160) | `common/trading_core.py` |
