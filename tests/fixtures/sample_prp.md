# Data Product Requirement Prompt

## 1. Product Type
Dashboard: A reusable, interactive tool for monitoring and analyzing betting model performance.

## 2. Business Objective
To continuously validate the live performance of a quantitative NFL betting model against its backtested expectations. This supports the core decisions of whether to continue trusting the model, adjust its parameters, or identify and diagnose performance degradation (model drift).

## 3. Product Functionality
This data product will provide a comprehensive performance overview of weekly NFL regression bets. Its capabilities include:
- Calculating and displaying overall cumulative and time-series (weekly) Profit & Loss (P&L) and Return on Investment (ROI).
- Plotting live cumulative ROI directly against the expected cumulative ROI from the corresponding backtest run in a side-by-side visualization.
- Allowing users to segment and filter performance by key bet characteristics, including `tier` (e.g., DIAMOND, GOLD) and the specific `model_name` used.
- Automatically generating alerts to highlight significant events, such as negative weekly ROI, underperformance of high-confidence bet segments, or a widening gap between live and backtested results.

## 4. Key Metrics
- **Profit & Loss (P&L):** The net monetary gain or loss from betting activities. Calculated on a per-bet, weekly, and cumulative basis.
- **Return on Investment (ROI):** The P&L expressed as a percentage of the total capital wagered. Calculated as `Total P&L / Total Amount Wagered`.
- **Cumulative ROI:** A running calculation of ROI over time, showing the growth or decline of the investment.
- **Weekly ROI:** The ROI calculated for a single week's betting activity.
- **Backtest Benchmark ROI:** The expected cumulative ROI for the same set of bets, as determined by the historical backtest data.
- **Performance Delta:** The difference between the Live Cumulative ROI and the Backtest Benchmark ROI, used to measure model drift.

## 5. Dimensions & Breakdowns  
- **Time Granularity:** The product must support both a cumulative (all-time) view and a weekly time-series view.
- **Performance Comparison:** A primary dimension is the comparison of `Live Performance` vs. `Backtest Performance`.
- **Bet Segmentation:** Performance metrics must be sliceable by:
    - `tier` (e.g., DIAMOND, GOLD)
    - `model_name` (e.g., `sniper_model_name`, `compromise_model_name`, `grinder_model_name`)
- **Benchmark Selection:** The user should be able to select the appropriate backtest run to use as a benchmark, likely based on the `model_name` or a `backtest_run_id`.

## 6. Success Criteria
- **Clarity:** The product provides an unambiguous, at-a-glance view of whether the live betting strategy is profitable and performing as expected.
- **Actionability:** It successfully highlights significant deviations between live and backtested performance, allowing the user to quickly diagnose issues.
- **Insight:** The segmentation capabilities enable the user to identify which parts of the betting strategy (e.g., specific tiers or models) are over- or under-performing.

## 7. Usage Pattern
- **Frequency**: Weekly, after the conclusion of each week's NFL games.
- **Audience**: Quantitative analysts, data scientists, or the individual managing the betting model and strategy.
- **Triggers**: Use is prompted by the need to review the previous week's results. An alert (e.g., email, notification) about poor performance or significant model drift would also trigger usage.

## 8. Example Usage Scenario
- **What inputs they provide**: The user navigates to the dashboard. The dashboard defaults to the most recent week's performance against the latest backtest. The user might use a filter to select a specific `model_name` to isolate its performance.
- **What outputs they get**: The user sees a primary line chart comparing cumulative live ROI vs. cumulative backtest ROI. They see KPI cards for total P&L and overall ROI. A table below details the performance for each week, highlighting a week where the `Performance Delta` exceeded a predefined threshold.
- **How they make decisions with it**: The user notices that the 'DIAMOND' tier bets had a -15% ROI last week, causing the overall performance to dip. This contradicts the backtest, which showed this tier as highly profitable. They decide to pause betting on the 'DIAMOND' tier and begin a deeper investigation into the model's features and predictions for that specific segment.

## 9. Data Requirements
### Table: `ensemble_predictions`
**Description:** Contains the model's weekly predictions for NFL games, including the recommended bet and associated probabilities.

**Schema:**
- `game_id` (STRING): A unique identifier for the game, combining teams, week, and year.
- `team` (STRING): The team the prediction is for.
- `opponent` (STRING): The opponent team.
- `week` (INTEGER): The week of the game.
- `year` (INTEGER): The year of the game.
- `start_time` (TIMESTAMP): The UTC timestamp for the start of the game.
- `spread` (FLOAT): The closing point spread for the team.
- `spread_price` (FLOAT): The American odds for the closing spread bet (e.g., -110).
- `tier` (STRING): The consensus tier of the pick based on model agreement.
- `win_prob` (FLOAT): The backtested win probability associated with the tier.
- `bet_amount` (FLOAT): The suggested bet amount based on the bankroll and Kelly percentage.
- `sniper_model_name` (STRING): The filename of the sniper model used for inference.
- `compromise_model_name` (STRING): The filename of the compromise model used for inference.
- `grinder_model_name` (STRING): The filename of the grinder model used for inference.
- `prediction_timestamp_utc` (TIMESTAMP): The UTC timestamp when the prediction was generated.

### Table: `game_results`
**Description:** Contains the final scores and outcomes for each NFL game. This table is required to determine the result of each bet.

**Schema:**
- `game_id` (STRING): A unique identifier for the game, used to join with `ensemble_predictions`.
- `home_team_score` (INTEGER): The final score of the home team.
- `away_team_score` (INTEGER): The final score of the away team.
- `game_status` (STRING): The final status of the game (e.g., 'Final').

### Table: `backtest_results`
**Description:** Contains the detailed, bet-by-bet historical simulation results. This is used as the benchmark for live performance.

**Schema:**
- `backtest_run_id` (STRING): A unique identifier for a specific backtest execution.
- `game_id` (STRING): A unique identifier for the game.
- `model_name` (STRING): The name of the model version used in the backtest.
- `backtest_bet_outcome` (STRING): The simulated outcome of the bet (e.g., 'WIN', 'LOSS', 'PUSH').
- `backtest_pnl` (FLOAT): The simulated P&L for this specific bet.

**Assessment:**
- **What data sources are being used?**
    - `ensemble_predictions`: This table is available.
    - `game_results`: A new data source is required to provide actual game outcomes. This could be sourced from a sports data API or a public dataset.
    - `backtest_results`: A new data source is required. This should be an output artifact from the model's backtesting process.
- **What gaps exist (if any)?**
    - The primary gaps are the lack of available `game_results` and `backtest_results` data. A process to ingest and store this information is necessary.
- **What assumptions are made?**
    - The `game_id` will be a consistent key across `ensemble_predictions`, `game_results`, and `backtest_results` to allow for accurate joins.
    - The `spread_price` field in `ensemble_predictions` will be used to calculate the payout for winning bets. A standard calculation for American odds will be applied.
    - A "push" (where the score difference exactly matches the spread) will result in a P&L of $0.
    - The `model_name` fields in `ensemble_predictions` can be used to link a live bet to its corresponding `backtest_results`.
- **What data quality considerations apply?**
    - Timeliness of `game_results` is critical; data must be available shortly after games conclude to enable weekly review.
    - The `backtest_results` must be comprehensive and map directly to the models being used for live predictions to ensure a valid comparison.

