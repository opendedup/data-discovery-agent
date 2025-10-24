✅ Data Product Requirement Prompt Generated!

📋 **Full Content:**

# Data Product Requirement Prompt

## 1. Product Type
A reusable, interactive dashboard designed for comparative analysis of different model backtest runs.

## 2. Business Objective
To validate the predictive power and practical betting utility of spread regression models by comparing their backtest performance against market benchmarks (Vegas) and actual game outcomes. This supports the decision-making process for model improvement, selection, and deployment.

## 3. Product Functionality
This data product allows a user to select one or more model backtest runs (`run_id`) and visually compare their performance. The dashboard will provide:
- **Correlation Analysis**: Visualizations (e.g., scatter plots) comparing the correlation of the model's predicted spread vs. the actual spread, and the Vegas spread vs. the actual spread.
- **Win Rate Calculation**: A metric showing the win/loss record of hypothetical bets placed using the model's prediction against the Vegas spread.
- **Comprehensive Segmentation**: The ability to filter and group all analyses by time (year, week), game characteristics (e.g., home/away, magnitude of spread), and model-generated confidence scores.
- **Flexible Confidence Metric**: Users can select which confidence metric (`win_prob`, `kelly_pct`, `is_sound_bet`) to use for segmentation.

## 4. Key Metrics
- **Correlation Coefficient**: A statistical measure of the linear relationship between two variables. This will be calculated for:
    1. `predicted_spread` vs. `actual_spread`
    2. `vegas_spread` vs. `actual_spread`
- **Hypothetical Bet Win Rate**: The percentage of games where a hypothetical bet based on the model's prediction against the Vegas spread would have won. A "win" is defined as when the `predicted_spread` is on the correct side of the `vegas_spread`, and the `actual_spread` covers the `vegas_spread` in that direction.
- **Model Prediction Error**: The difference between the `predicted_spread` and the `actual_spread`.
- **Vegas Prediction Error**: The difference between the `vegas_spread` and the `actual_spread`.

## 5. Dimensions & Breakdowns  
- **Backtest Run**: The primary unit of comparison, identified by `run_id`.
- **Time**: `year`, `week`.
- **Game Characteristics**: `home_team`, `away_team`, and buckets based on the magnitude of the `vegas_spread` (e.g., close games vs. blowouts).
- **Model Confidence**: User-selectable segmentation based on `win_prob`, `kelly_pct`, or `is_sound_bet`.

## 6. Success Criteria
This product is considered successful and useful if it enables an analyst to:
- **Quantify Model Lift**: Clearly determine if a model's predictions are more tightly correlated with actual outcomes than the Vegas spread.
- **Identify a Verifiable "Edge"**: Pinpoint specific, repeatable situations (e.g., games with a high `kelly_pct`, or games involving a specific team) where the model consistently provides more accurate predictions than the market.

## 7. Usage Pattern
- **Frequency**: On-demand.
- **Audience**: Data scientists, quantitative analysts, and model developers.
- **Triggers**: A new model backtest is completed and its `run_id` is available for analysis; a need arises to compare the performance of two or more existing models.

## 8. Example Usage Scenario
- **What inputs they provide**: A quantitative analyst selects two `run_id`s from a dropdown menu to compare Model A and Model B. They then apply a filter to only show games where the `vegas_spread` was between -3 and +3. Finally, they select `kelly_pct` as the confidence metric for segmentation.
- **What outputs they get**: The dashboard updates to show side-by-side scatter plots and win rate charts for the two models, filtered for these "close" games. The results are broken down into tiers based on the `kelly_pct` value for each prediction.
- **How they make decisions with it**: The analyst observes that for games in the top quintile of `kelly_pct`, Model A's win rate is 58% while Model B's is 51%. They conclude that Model A has a significant, identifiable edge in predicting the outcome of close games where it is most confident, and they recommend this model for further testing and potential live deployment.

## 9. Data Requirements

### Target Views/Tables
**View Name**: `backtest_evaluation_view`
- **Purpose**: To power an interactive dashboard for comparing spread model backtest performance against Vegas and actual outcomes, with segmentation capabilities.
- **Grain**: One row per game per backtest run (run_id, game_id).
- **Schema**:
  - `run_id` (string): Unique identifier for a specific backtest run of the model.
  - `game_id` (string): Unique identifier for a single game.
  - `game_date` (date): Date of the game, used for time-based segmentation.
  - `year` (integer): The year of the game.
  - `week` (integer): The week of the game.
  - `home_team` (string): Identifier for the home team.
  - `away_team` (string): Identifier for the away team.
  - `predicted_spread` (float): The model's predicted point spread for the game.
  - `vegas_spread` (float): The market's consensus point spread (Vegas spread) for the game.
  - `actual_spread` (float): The final score difference of the game (e.g., away_score - home_score).
  - `win_prob` (float): Model-generated win probability, used for confidence segmentation.
  - `kelly_pct` (float): Model-generated Kelly criterion percentage, used for confidence segmentation.
  - `is_sound_bet` (boolean): Model-generated flag indicating a sound bet, used for confidence segmentation.
- **Calculated Fields**:
  - `model_prediction_error` (float): `predicted_spread` - `actual_spread`
  - `vegas_prediction_error` (float): `vegas_spread` - `actual_spread`
  - `hypothetical_bet_outcome` (string): 'WIN', 'LOSS', or 'PUSH' based on the win rate definition.
  - `is_model_more_accurate` (boolean): TRUE if `abs(model_prediction_error)` < `abs(vegas_prediction_error)`.

### Data Gaps and Limitations
```json
{
  "data_gaps": [
    {
      "gap_id": "gap_01",
      "description": "Missing source for the model's `predicted_spread`. The conversation confirmed the existing 'spread' field is the `vegas_spread`.",
      "target_view": "backtest_evaluation_view",
      "required_information": "A source table or file containing the model's predictions, identifiable by `run_id` and `game_id`, which includes the `predicted_spread` value."
    },
    {
      "gap_id": "gap_02",
      "description": "Missing source for final game results needed to calculate the `actual_spread`.",
      "target_view": "backtest_evaluation_view",
      "required_information": "A source table or file containing final game scores (e.g., `home_score`, `away_score`) for each game, identifiable by a `game_id` that can be joined to the prediction data."
    }
  ]
}
```

### Available Source Data (For Reference)
The following existing tables could potentially be used as source data:

- **`backtest_regression_inferences`**
  - Metadata: 440.0 records, 14.0 columns
  - Key columns: `run_id`, `game_id`, `year`, `week`, `game_date` (and 9 more)

**Assessment:**
- **How well do the available source tables cover the target view requirements?**
  - The `backtest_regression_inferences` table provides the primary keys (`run_id`, `game_id`) and dimensional data (`year`, `week`, `game_date`), but it is missing the core measures required for the analysis: `predicted_spread`, `vegas_spread`, and `actual_spread`.
- **What transformations or joins are needed to build the target views?**
  - The target view will require a three-way join:
    1. The existing `backtest_regression_inferences` table (for run and game identifiers).
    2. A new source containing model predictions (`predicted_spread`, confidence metrics) joined on `run_id` and `game_id`.
    3. A new source containing game results (`home_score`, `away_score`) joined on `game_id`.
  - The `actual_spread` field will need to be calculated from the joined game result scores.
- **What data gaps or limitations exist?**
  - As detailed in the JSON object above, there are two critical data gaps: the source for model predictions (`predicted_spread`) and the source for actual game outcomes (`actual_spread`).
- **What assumptions are being made about data availability and quality?**
  - We assume that `game_id` is a consistent and reliable key for joining across all required data sources.
  - We assume that a data source for model predictions exists and can be mapped to a specific `run_id`.
  - We assume a complete and accurate source for historical game results is available.
- **Are there any data quality considerations (PII, PHI, freshness, completeness)?**
  - The data does not contain PII or PHI.
  - For backtesting, data completeness is critical. Every game within a `run_id` must have a corresponding actual game result to be included in the analysis. Missing results would skew performance metrics.