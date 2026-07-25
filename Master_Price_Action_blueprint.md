# Master Price Action Blueprint — Exhaustive Reference & Strategy Specification

> **Source**: `FINAL PDF 2026.pdf` (33 Pages Master Blueprint by Harale Datta — Phone: 8698105122)  
> **Purpose**: Complete, exhaustive technical blueprint covering 1-candle anatomy, 5 Bullish setups, 5 Bearish setups, A-B-C-D confirmation engine, Theory of Negation target finder, and intraday option trading rules.

---

## Table of Contents
1. Document Information & Sacred Cover (Page 1)
2. 1-Candle Anatomy & Price Action Fundamentals (Page 2)
3. Candlestick Engulfing Formations (Page 3)
4. Bullish & Bearish Swings Mechanics (Pages 4 – 5)
5. A-B-C-D Reversal Confirmation Engine (Pages 6 – 7)
6. Lower-Low & Higher-High Sweep Variations (Pages 8 – 17)
7. Trend Identification Rules & Structural Swings (Pages 18 – 20)
8. Bulls & Bears — Support & Resistance Identification (Pages 21 – 23)
9. Theory of Negation — Target Calculation Engine (Pages 24 – 26)
10. Option Trading Simplified — Core Process & Execution Rules (Page 27)
11. Real-World Option Trade Case Studies & Chart Annotations (Pages 28 – 33)

---

## 1. Document Information & Sacred Cover (Page 1)
* **Cover Page**: Dedicated with an auspicious image of Goddess Lakshmi for prosperity, discipline, and success in trading.

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

### Key Elements
* **Bullish Green Candle**:
  * `Price at Open`: Bottom of real body.
  * `Price at Close`: Top of real body (`Close > Open`).
  * `Real Body`: Represents buying expansion / Price Rises.
  * `Wicks (Tails)`: High and Low extremes of the time period range.
* **Bearish Red Candle**:
  * `Price at Open`: Top of real body.
  * `Price at Close`: Bottom of real body (`Close < Open`).
  * `Real Body`: Represents selling expansion / Price Falls.
  * `Wicks (Tails)`: High and Low extremes of the time period range.

---

## 3. Candlestick Engulfing Formations (Page 3)

1. **1-Bullish Engulfing (At Bottom)**:
   * Occurs at the end of a downtrend / bottom of price move.
   * A large green candle body completely wraps / engulfs the prior red candle body and wicks.
   * Indicates buyers taking complete control from sellers.

2. **2-Bearish Engulfing (At Top)**:
   * Occurs at the top of an uptrend / peak of price move.
   * A large red candle body completely wraps / engulfs the prior green candle body and wicks.
   * Indicates institutional supply overwhelming demand.

---

## 4. Bullish & Bearish Swings Mechanics (Pages 4 – 5)

### Bullish Swings — Bearish Reversal / Higher-High (HH) Sweep (Page 4)
* **Structural Requirement**: Need **more than 2 candles** in between swings.
* **Sequence**:
  1. Mark **High 1** (`HIGH-1`).
  2. Price must pull down below High 1.
  3. Need $> 2$ candles in the pullback swing.
  4. Price rallies to form **High 2** (`HIGH-2 GREEN`) which breaks / pierces above High 1.
  5. After High 2, the **next candle does NOT break High 2** (liquidity rejection / stop run).
* **Trade Suggestion**: **PRICE WILL GO DOWN** (Triggers Bearish Reversal Trade).

### Bearish Swings — Bullish Reversal / Lower-Low (LL) Sweep (Page 5)
* **Structural Requirement**: Need **more than 2 candles** in between swings.
* **Sequence**:
  1. After fall, mark **Low 1** (`L-1`).
  2. Price must bounce above Low 1.
  3. Price falls to form **Low 2** (`L-2`) which breaks / sweeps below Low 1.
  4. Next candle does **NOT break Low 2** (reclaims floor line / buyer absorption).
* **Trade Suggestion**: **PRICE WILL GO UP** (Triggers Bullish Reversal Trade).

---

## 5. A-B-C-D Reversal Confirmation Engine (Pages 6 – 7)

### Setup 1: Bearish to Bullish Reversal (Page 6)

```
                     [D: Green Confirmation Close > BM]
                                   ####
                     [B: Breakout]  ####
                           ####    ####
             Benchmark ────┼───────┼────────────────────────────── (A.High Line)
                           │  [C]  │  (Red Retest Holds Above A.Low)
                           │ ####  │
            [A: Anchor]    │       │
               ####        │       │
              ######       │       │
  (NO PRICE AT LEFT >>>>>>)
  [A.Low Floor Line] ─────────────────────────────────────────────── (Stop Loss)
```

1. **A (Anchor Candle)**: Bullish Engulfing candle formed at bottom.
   * **Left-Side Rule**: Must have **"NO PRICE AT LEFT >>>>>>"** (A.low is the absolute lowest low in historical window).
   * Benchmark Line ($BM$) = `A.high`.
   * Stop Loss Line ($SL$) = `A.low - buffer`.
2. **B (Breakout Candle)**: Green candle closing above Benchmark line (`Close > A.high`).
3. **C (Retest Candle)**: Pullback candle (must be red to Benchmark zone) holding above `A.low`.
4. **D (Confirmation Candle)**: Green candle closing back above Benchmark line (`Close > A.high`).
5. **Confirmation**: Trade confirmed upon completion of Candle D bar close!

---

### Setup 1: Bullish to Bearish Reversal (Page 7)

```
  [A.High Ceiling Line] ─────────────────────────────────────────── (Stop Loss)
            [A: Anchor Top]
               ######
                ####
  (NO PRICE LEFT SIDE>>>)
             Benchmark ────┼───────┼────────────────────────────── (A.Low Line)
                           │  [C]  │  (Green Retest Holds Below A.High)
                           │ ####  │
                     [B: Breakout]  ####
                           ####    ####
                     [D: Red Confirmation Close < BM] -> BEARISH ENTRY SELL SIDE
```

1. **A (Anchor Candle)**: Bearish Engulfing candle formed at top.
   * **Left-Side Rule**: Must have **"NO PRICE LEFT SIDE>>>"** (A.high is the absolute highest high in historical window).
   * Benchmark Line ($BM$) = `A.low`.
   * Stop Loss Line ($SL$) = `A.high + buffer`.
2. **B (Breakout Candle)**: Red candle closing below Benchmark line (`Close < A.low`).
3. **C (Retest Candle)**: Retest candle (must be green back to Benchmark zone) holding below `A.high`.
4. **D (Confirmation Candle)**: Red candle closing back below Benchmark line (`Close < A.low`).
5. **Confirmation**: Bearish Entry confirmed upon completion of Candle D bar close!

---

## 6. Lower-Low & Higher-High Sweep Variations (Pages 8 – 17)

### Setup 2: Lower-Low Swing Pattern (Page 8 – 10)
* **Downtrend Context**: Price falling along downtrend line.
* **Low 1**: Initial swing low (any color).
* **Low 2**: Red candle dips below Low 1.
* **Sweep Reclaim**: Immediate green candle recovers back above Low 1 with annotation **`<< LOW NOT BREAK`**.
* **Variations**:
  * **Variation 1 (Page 9)**: Low 2 breaks Low 1 but closes above Low 2. Candle B closes above Benchmark $\rightarrow$ C retest holding above Low 2 $\rightarrow$ D green confirmation close $\rightarrow$ Massive rally from 720 to 935!
  * **Variation 2 (Page 10)**: Low 2 Neutral Green candle (lower wick pierces Low 1, body closes green above Low 1). Immediate bullish expansion from 145 to 195!

### Setup 4: Pin Bar / Hammer — Baby Candle CRC (Page 11)
* **Context**: After successive downtrend.
* **Anchor A**: Small body candle with long lower tail (Hammer / Pinbar) at bottom.
* **B**: Green close above Benchmark line.
* **C**: Retest with red candle holding above tail low.
* **D**: Green close above Benchmark line (`MUST`).
* **Result**: Bullish expansion rally!

### Bearish 2-Swing Reversal & HH Sweep Variations (Pages 12 – 14)
* **High 1 & High 2**: High 1 formed $\rightarrow$ High 2 green candle sweeps above High 1 $\rightarrow$ Next candle does NOT break High 2.
* **Stop Loss**: Placed at `Top High + 2` buffer.
* **Variation 1 (Page 12)**: B closes below Benchmark $\rightarrow$ C retest $\rightarrow$ D red confirmation close $\rightarrow$ Fall from 256 to 215.
* **Variation 2 (Page 13)**: High 2 sweep $\rightarrow$ Benchmark line $\rightarrow$ B closes below $\rightarrow$ C green retest $\rightarrow$ D red confirmation close $\rightarrow$ Sharp crash!
* **Page 14 Expansion**: Breakdown from Benchmark line at 950 $\rightarrow$ Continuous crash down to 600.

### Setup 4 Bearish: Pin Bar / Shooting Star at Top (Page 15 — Bajaj Auto 1D)
* **Context**: No price at left.
* **Anchor A**: Pin Bar / Hammer at top.
* **B**: Red close below Benchmark line.
* **C**: Retest with green candle holding below pinbar high.
* **D**: Red close below Benchmark line (`MUST`).
* **Result**: Bearish crash from 4,250 down to 3,600!

### Trend Continuations (Pages 16 – 17)
* **Bullish Re-entry (Page 16)**: Up trend $\rightarrow$ Swing 1 $\rightarrow$ Swing 2 red retest holding above 660 $\rightarrow$ Reclaims Benchmark line at 680 $\rightarrow$ Rally to 743.
* **Bearish Re-entry (Page 17)**: Downtrend $\rightarrow$ Swing 1 $\rightarrow$ Swing 2 rejection $\rightarrow$ Closes below Benchmark line at 1,680 $\rightarrow$ Plunge to 1,139.

---

## 7. Trend Identification Rules & Structural Swings (Pages 18 – 20)

### How to Identify the Trend
1. **Higher Timeframe First**: Always check the **Highest (Daily) timeframe** for overall directional bias (weekly if needed).
2. **Uptrend Definition**: Series of **Higher Highs (HH) & Higher Lows (HL)**.
3. **Downtrend Definition**: Series of **Lower Highs (LH) & Lower Lows (LL)**. Confirm on higher timeframes.

### Structural Swing Terminology
* **Momentum High (MH)**: Candle with the highest price of a swing high.
* **Higher High (HH)**: 1st candle that breaks momentum high.
* **Momentum Low (ML)**: Candle with the lowest price of a swing low.
* **Lower Low (LL)**: 1st candle that breaks momentum low.

---

## 8. Bulls & Bears — Support & Resistance Identification (Pages 21 – 23)

### Bullish Trend Support Levels (Page 22)
1. **Momentum High**: High price level acting as retest support.
2. **Higher-High**: Low price level of HH candle.
3. **Bullish Engulfing**: Low price level of bullish engulfing candle.

### Bearish Trend Resistance Levels (Page 23)
1. **Momentum Low**: Low price level acting as retest resistance.
2. **Lower-Low**: High price level of LL candle.
3. **Bearish Engulfing**: High price level of bearish engulfing candle.

---

## 9. Theory of Negation — Target Calculation Engine (Pages 24 – 26)

```
        THEORY OF NEGATION — TARGET SELECTION PIPELINE
        
  Historical Price Pivots (Prior to Entry)
        │
        ├── Is Level Breached / Closed Past?
        │     ├── YES ──► LEVEL IS NEGATED (Discarded from targets)
        │     └── NO  ──► LEVEL IS NON-NEGATED (Valid Target)
        │
        ▼
  Sort Non-Negated Levels:
    - Bullish: Ascending Order  (T1 < T2 < T3)  [Overhead Resistance]
    - Bearish: Descending Order (T1 > T2 > T3)  [Underfoot Support]
```

### Negation Rules for Bearish Pressure Points (Bullish Targets)
1. **Momentum Low (ML)**: Negated if a candle closes BELOW and re-tests the lowest price of ML.
2. **Lower Low (LL)**: Negated if a candle CLOSES / RETESTS / CLOSES ABOVE the highest price of LL.
3. **Bearish Engulfing Candle (EC)**: Negated if a candle Closes ABOVE the highest price of EC.

### Negation Rules for Bullish Pressure Points (Bearish Targets)
1. **Momentum High (MH)**: Negated if a candle closes ABOVE & a candle re-tests highest price of MH.
2. **Higher High (HH)**: Negated if a candle CLOSES / RETESTS / CLOSES BELOW lowest price of HH.
3. **Bullish Engulfing Candle (EC)**: Negated if a candle Closes BELOW lowest price of EC.

### Golden Rules of Negation
> [!IMPORTANT]
> **Once any Resistance or Support is NEGATED, the Price (Target) automatically moves to the NEXT Level of Support or Resistance!**

### Target Timeframe Rule (+2 TF Rule)
$$\text{Target Timeframe} = \text{Trading Timeframe} + 2 \text{ Higher Timeframes}$$
* **Example**: 1-Hour Trading Timeframe $\rightarrow$ Target from 4-Hour Timeframe.
* **Example**: 3-Min / 15-Min Options Timeframe $\rightarrow$ Targets derived from 15-Min / 60-Min charts.

### Negation Chart Proofs (Pages 25 – 26)
* **Bullish Example (Page 25)**: Low 1, Low 2 $\rightarrow$ Entry at D (620) $\rightarrow$ ML negated, Bearish Engulf 1 negated $\rightarrow$ Target achieved at **NON-NEGATED Bearish Engulfing level (799.80)**!
* **Bearish Example (Page 26)**: Reversal at top 1,080 $\rightarrow$ MH negated, HH negated $\rightarrow$ Support Target achieved at **NON-NEGATED Higher High level (726.22)**!

---

## 10. Option Trading Simplified — Core Process & Execution Rules (Page 27)

```
================================================================================
                    OPTION TRADING SIMPLIFIED — MANDATORY RULES
================================================================================
 1. INTRADAY INDEX OPTIONS TIMEFRAMES:
    - Primary Timeframes: 3 MIN and 15 MIN.
    - Mandatory Check: Check BOTH PE & CE once before trade.
    - Preference: Give preference to higher timeframe (15 MIN).

 2. STOCK OPTIONS TIMEFRAMES:
    - Primary Timeframes: 15 MIN, 1 HR, 4 HR candles.
    - Carryover: Carry over trades mostly. Liquid stocks only (Less jobbing).

 3. RISK & POSITION SIZING:
    - Lot Size: Practice with 1 LOT before scaling.
    - R:R Filter: Demand highest R:R before entering trade.
    - Stop Loss: ALL SL IS ON A CLOSING BASIS (wicks ignored).

 4. TRADE DISCIPLINE & EXITS:
    - Single Execution: If SL or Target hit, CLOSE trade immediately.
    - Strictly Prohibited: NO AVERAGING, NO HEDGING, NO SHORT SELLING.
    - No Re-Entry: NO ENTRY in older trades if SL or Target achieved.

 5. THE 5 MOST WINNING PROBABILITY SETUPS:
    1. Bullish Engulf A-B-C-D
    2. Lower-Low Trend Reversal (Liquidity Sweeps)
    3. Baby Candle (Likely Pinbar / Hammer) after successive downtrend
    4. Bullish Harami Candle (Inside Bar)
    5. Sell Side Vice-Versa (Bearish Engulf, HH Sweep, Shooting Star, Bearish Harami)
================================================================================
```

---

## 11. Real-World Option Trade Case Studies & Chart Annotations (Pages 28 – 33)

### Case Study 1: EICHERMOT 7200 CE (15m Option Chart — Page 28)
* **Pattern**: Setup 1 Bullish Engulfing A-B-C-D.
* **Anchor A**: Bottom Anchor Low at ₹168.
* **Breakout B**: Rally to ₹205.
* **Retest C**: Red pullback holding at ₹170.
* **Confirmation D**: Green confirmation close at ₹180.
* **Target Exit**: Target hit at **₹326.96**!
* **P&L Return**: **+81.6% option premium gain** (from ₹180 to ₹326.96).

### Case Study 2: BANKNIFTY 34300 PE (3m Option Chart — Page 29)
* **Pattern**: Setup 2 Lower-Low Sweep.
* **Low 1 & Low 2**: Low 1 at ₹250 $\rightarrow$ Low 2 sweep $\rightarrow$ Reclaims with `<<< L2 NOT BREAK`.
* **Stop Loss**: `STOP LOSS L2-2` set at ₹240.50.
* **Entry**: Entry arrow at ₹265.
* **Target Exit**: `TARGET 420` hit (printed **₹430.15**)!
* **P&L Return**: **+62.3% option premium gain** (from ₹265 to ₹430).

### Case Study 3: Negation Target Option Chart (Page 30)
* **Pattern**: Trend Reversal Variation.
* **Setup**: ML Negated, LL Negated $\rightarrow$ B $\rightarrow$ C retest at ₹486.65 $\rightarrow$ D entry at ₹525.
* **Target Exit**: `LAST BUYER SWING CHESS` Target hit at **₹750.55**!
* **P&L Return**: **+42.9% option premium gain**.

### Case Study 4: NIFTY 18650 CE (Index Option 3m/15m Intraday — Page 31)
* **Pattern**: Setup 4 Baby Candle CRC (3 MIN - 15 MIN).
* **Context**: After 3/4 Swing Downtrend.
* **Proper Baby Candle A**: Small body at ₹85.
* **Confirmation B-C-D**: Entry arrow at ₹90.
* **Target Exit**: `PRICE CHESS LAST BUYER` Target hit at **₹158.80**!
* **P&L Return**: **+76.4% option premium gain**.

### Case Study 5: BANKNIFTY 54000 PE (15m Option Chart — Page 32)
* **Pattern**: Setup 5 Bullish Harami (Inside Bar).
* **Anchor A**: Small inside bar inside prior bear body at ₹230.
* **Benchmark Line**: ₹250.
* **Entry**: Entry arrow at ₹260.
* **Target Exit**: Massive expansion to **₹765.00**!
* **P&L Return**: **+194.2% option premium gain** (from ₹260 to ₹765).

### Case Study 6: BANKNIFTY 54000 PE Bearish Reversal Chart (Page 33 — "ONLY FOR OPTION")
* **Pattern**: Bearish Option Reversal.
* **Context**: High 1, High 2 sweep $\rightarrow$ Reversal entry at ₹580.
* **Target Exit**: `PRICE CHESS PREVIOUS REVERSAL SWINGS` Support Target hit at **₹363.32**!
