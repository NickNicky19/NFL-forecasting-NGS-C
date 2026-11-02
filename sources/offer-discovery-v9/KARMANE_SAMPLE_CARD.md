---
language:
- en
license: cc-by-4.0
size_categories:
- n<1K
task_categories: []
tags:
- polymarket
- prediction-markets
- market-research
- sports-betting-research
- player-props
- spreads
- totals
- moneyline
- parquet
- public-data
pretty_name: "Polymarket Sports Lines and Player Props Research Data (Free Sample)"
configs:
- config_name: default
  data_files:
      - split: data
        path: "data/data.parquet"
---

# Polymarket Sports Lines and Player Props Research Data

Clean public Polymarket sports market data with player-prop, spread, total, moneyline, liquidity, and event-context fields for sports-betting research workflows.

**This is a free preview.** Load it instantly, inspect the schema, and validate quality before purchasing the full dataset.

---

## What This Preview Proves

- **Sample rows:** 575 (full dataset: 11,509 rows)
- **Columns:** 107 fields, fully described below
- **Format:** parquet (loads in pandas, HF datasets, or any parquet reader)
- **No authentication required** to load this sample
- **Schema and quality** are identical to the paid full dataset

---

## Upgrade to Full Dataset

The full production dataset contains **11,509 rows** across **107 columns**.

**Purchase here:** [https://thearticulated.gumroad.com/l/mcecom?utm_source=hf_sample_readme&utm_medium=referral&utm_campaign=polymarket-sports-lines-and-player-props](https://thearticulated.gumroad.com/l/mcecom?utm_source=hf_sample_readme&utm_medium=referral&utm_campaign=polymarket-sports-lines-and-player-props)

After purchase, provide your Hugging Face username and request access on the [full dataset page](https://huggingface.co/datasets/Karmane/polymarket-sports-lines-and-player-props).

---

## Quick Start

```python
from datasets import load_dataset

dataset = load_dataset("Karmane/polymarket-sports-lines-and-player-props-sample")
df = dataset["data"].to_pandas()
print(f"Rows: {len(df):,}, Columns: {len(df.columns)}")
print(df.head())
```

Or with pandas directly:

```python
import pandas as pd
df = pd.read_parquet("hf://datasets/Karmane/polymarket-sports-lines-and-player-props-sample/data/data.parquet")
print(df.head())
```

---

## Use Cases

- Filter public Polymarket sports contracts into player props, spreads, totals, and moneyline-style markets without flattening nested API responses yourself.
- Rank leagues, events, and contracts by volume or liquidity for dashboards, alerts, or manual market review queues.
- Compare active sports contracts with recently closed markets inside one parquet dataset for notebook analysis, BI, or newsletter research.

---

## Column Descriptions

- `record_id`: Stable unique identifier for the dataset row derived from the Polymarket market id.
- `market_id`: Polymarket market identifier from the public Gamma API.
- `condition_id`: On-chain condition identifier associated with the binary market.
- `market_slug`: Public slug string for the market in the Gamma API.
- `question`: Primary market question text shown to traders.
- `question_word_count`: Word-count length of the market question after normalization.
- `outcomes`: JSON-array string containing the ordered list of outcome labels returned by the market payload.
- `outcome_count`: Number of outcome labels available for the market.
- `yes_price`: Implied Yes-side price when the market exposes Yes and No outcomes.
- `no_price`: Implied No-side price when the market exposes Yes and No outcomes.
- `favorite_outcome`: Outcome label with the highest exposed price at collection time when prices were available.
- `favorite_price`: Highest exposed outcome price at collection time when prices were available.
- `price_sum`: Sum of all parsed outcome prices for the market snapshot.
- `market_spread`: Difference between best ask and best bid when those values were available.
- `last_trade_price`: Last trade price reported by the public market payload.
- `best_bid`: Current best bid from the public market payload.
- `best_ask`: Current best ask from the public market payload.
- `one_day_price_change`: One-day price change reported by the market payload.
- `one_week_price_change`: One-week price change reported by the market payload.
- `one_month_price_change`: One-month price change reported by the market payload.
- `one_year_price_change`: One-year price change reported by the market payload.
- `volume_usd`: Cumulative market volume reported in dollar terms by the public payload.
- `liquidity_usd`: Current market liquidity reported in dollar terms by the public payload.
- `volume_24h_usd`: Trailing 24-hour market volume in dollars when available.
- `volume_1wk_usd`: Trailing 1-week market volume in dollars when available.
- `volume_1mo_usd`: Trailing 1-month market volume in dollars when available.
- `volume_1yr_usd`: Trailing 1-year market volume in dollars when available.
- `order_min_size`: Minimum order size reported by the market payload when available.
- `order_price_min_tick_size`: Minimum tick size for the order book when available.
- `market_status`: Normalized market-status label derived from archived, closed, active, and accepting-orders flags.
- `market_active`: Boolean flag indicating the market payload marked the market as active.
- `market_closed`: Boolean flag indicating the market payload marked the market as closed.
- `market_archived`: Boolean flag indicating the market payload marked the market as archived.
- `market_restricted`: Boolean flag indicating the payload marked the market as restricted.
- `market_featured`: Boolean flag indicating the market payload marked the market as featured.
- `accepting_orders`: Boolean flag indicating whether the market was accepting orders at collection time.
- `enable_order_book`: Boolean flag indicating whether the market exposed order-book support.
- `fees_enabled`: Boolean flag indicating whether fees were enabled on the market.
- `neg_risk`: Boolean flag indicating whether the market payload flagged negative-risk support.
- `competitive_score`: Competitive score value reported by the market payload when available.
- `created_at`: Timestamp when the market was created according to the market payload.
- `updated_at`: Timestamp when the market was last updated according to the market payload.
- `start_date`: Market start timestamp when available.
- `end_date`: Market end timestamp when available.
- `closed_time`: Timestamp when the market closed when exposed by the payload.
- `days_since_creation`: Number of days between market creation and collection time.
- `days_since_update`: Number of days between market last update and collection time.
- `days_until_end`: Number of days between collection time and the scheduled market end timestamp.
- `event_id`: Parent Polymarket event identifier.
- `event_ticker`: Parent Polymarket event ticker when available.
- `event_slug`: Parent Polymarket event slug.
- `event_title`: Parent Polymarket event title.
- `event_category`: Event-level category string from Polymarket when available.
- `event_active`: Boolean flag indicating the parent event was marked active.
- `event_closed`: Boolean flag indicating the parent event was marked closed.
- `event_archived`: Boolean flag indicating the parent event was marked archived.
- `event_restricted`: Boolean flag indicating the parent event was marked restricted.
- `event_comment_count`: Comment count reported on the parent event when available.
- `event_market_count`: Number of market rows attached to the parent event payload.
- `event_volume_usd`: Cumulative event volume reported in dollars.
- `event_liquidity_usd`: Current event liquidity reported in dollars.
- `event_open_interest_usd`: Open interest reported on the event when available.
- `event_created_at`: Timestamp when the event record was created on Polymarket.
- `event_updated_at`: Timestamp when the event record was last updated on Polymarket.
- `event_start_date`: Parent event start timestamp when available.
- `event_end_date`: Parent event end timestamp when available.
- `series_titles`: JSON-array string containing the list of series titles attached to the parent event.
- `series_slugs`: JSON-array string containing the list of series slugs attached to the parent event.
- `primary_series_title`: First attached series title when available.
- `primary_series_slug`: First attached series slug when available.
- `tag_labels`: JSON-array string containing the list of event tag labels attached to the parent event.
- `tag_slugs`: JSON-array string containing the list of event tag slugs attached to the parent event.
- `tag_count`: Number of event tags attached to the parent event.
- `is_multi_market_event`: Boolean flag indicating the parent event contains more than one market.
- `is_binary_market`: Boolean flag indicating the market exposed exactly two outcomes.
- `is_sports_market`: Boolean flag indicating sports-oriented event, series, or title language.
- `sports_league`: Normalized sports league label derived from series, tags, category, and title heuristics when detected.
- `is_crypto_market`: Boolean flag indicating crypto-related market language or category.
- `is_politics_market`: Boolean flag indicating politics or election language or category.
- `is_current_affairs_market`: Boolean flag indicating current-affairs style categorization.
- `is_pop_culture_market`: Boolean flag indicating entertainment or pop-culture language.
- `has_player_prop_signal`: Boolean flag indicating a player-prop style betting market.
- `has_spread_signal`: Boolean flag indicating spread-style language.
- `has_total_signal`: Boolean flag indicating totals or over-under language.
- `has_moneyline_signal`: Boolean flag indicating moneyline-style win or beat language.
- `has_price_target_signal`: Boolean flag indicating price-target or threshold-style language.
- `has_election_signal`: Boolean flag indicating election-oriented language.
- `has_award_signal`: Boolean flag indicating award-oriented language.
- `has_culture_signal`: Boolean flag indicating entertainment, music, movie, or release-oriented language.
- `resolution_source_domain`: Domain extracted from the market resolution source URL when available.
- `source_api_events_url`: Base events endpoint used to collect the source data.
- `source_api_event_url`: Event-specific public API URL for the parent event.
- `source_api_market_url`: Market-specific public API URL for the market.
- `source_directory_url`: Top-level Polymarket website URL for the source platform.
- `source_domain`: Source platform domain for the dataset row.
- `last_collected_at`: UTC timestamp when the row was collected for this dataset build.
- `sports_market_type`: Normalized sports-betting market archetype derived from player-prop, spread, total, and moneyline heuristics.
- `sports_subvertical`: Higher-level sports segment such as team sports, combat sports, racket sports, esports, or other sports.
- `liquidity_tier`: Bucketed liquidity label derived from current market liquidity in USD for quick filtering.
- `volume_tier`: Bucketed cumulative volume label derived from market volume in USD for quick filtering.
- `implied_edge_from_even`: Absolute distance between the favorite-side price and the even-money midpoint of 0.50.
- `time_bucket_to_event_end`: Time-to-close bucket derived from days_until_end and market status.
- `league_volume_rank`: Descending rank of the market by cumulative volume within its normalized sports league.
- `event_volume_rank`: Descending rank of the market by cumulative volume within its parent event.
- `is_active_tradable_market`: Boolean flag indicating the sports market is active and accepting orders at collection time.
- `is_featured_research_market`: Boolean helper flag for markets that are active or structurally important enough to merit first-pass analyst review.
- `sports_context_key`: Readable grouping key combining the normalized sports league and event title for dashboard pivots.

---

## Dataset Structure

- **Rows:** 575
- **Columns:** 107
- **Split:** `data`
- **File:** `data/data.parquet`

---

## Full Dataset Access

| | Sample (this repo) | Full Dataset |
|---|---|---|
| Rows | 575 | 11,509 |
| Columns | 107 | 107 |
| Auth required | No | Yes (after purchase) |
| Price | Free | [See pricing](https://thearticulated.gumroad.com/l/mcecom?utm_source=hf_sample_readme&utm_medium=referral&utm_campaign=polymarket-sports-lines-and-player-props) |


## Related Datasets

- [Polymarket Prediction Markets Enriched](https://huggingface.co/datasets/Karmane/polymarket-prediction-markets-enriched)
- [Kalshi Prediction Market Candlestick Features](https://huggingface.co/datasets/Karmane/kalshi-prediction-market-candlestick-features)
- [Memecoins Chart Data Low Mc](https://huggingface.co/datasets/Karmane/memecoins-chart-data-low-mc)


## Final CTA

**Get the full dataset:** [https://thearticulated.gumroad.com/l/mcecom?utm_source=hf_sample_readme&utm_medium=referral&utm_campaign=polymarket-sports-lines-and-player-props](https://thearticulated.gumroad.com/l/mcecom?utm_source=hf_sample_readme&utm_medium=referral&utm_campaign=polymarket-sports-lines-and-player-props)

---

Karmane. (2025). _Polymarket Sports Lines and Player Props Research Data (Free Sample)_. Hugging Face. [https://huggingface.co/datasets/Karmane/polymarket-sports-lines-and-player-props-sample](https://huggingface.co/datasets/Karmane/polymarket-sports-lines-and-player-props-sample)
