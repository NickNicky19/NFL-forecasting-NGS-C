---
license: cc-by-4.0
pretty_name: PropLine graded player props (14-day sample)
tags:
- sports
- sports-betting
- odds
- player-props
- mlb
- nfl
size_categories:
- 100K<n<1M
configs:
- config_name: mlb
  data_files: "mlb_graded_props_14d_part*.csv.gz"
- config_name: nfl
  data_files: "nfl_graded_props_14d.csv.gz"
---

# PropLine graded player props — free 14-day sample

Real player-prop prices from 25+ US sportsbooks, prediction markets and DFS apps,
each one **graded against the official box score**, with the **opening and closing
line** for every price. From [PropLine](https://prop-line.com/?ref=dataset).

## Files

| File | Sport | Markets |
|---|---|---|
| `mlb_graded_props_14d_part1/2.csv.gz` | MLB | pitcher strikeouts, batter hits, batter total bases |
| `nfl_graded_props_14d.csv.gz` | NFL | passing yards, rushing yards, receiving yards, receptions |

One row per priced outcome (one side of one line at one book).

## Columns

| Column | Meaning |
|---|---|
| `event_id`, `sport_key`, `commence_time`, `home_team`, `away_team` | The game |
| `home_score`, `away_score` | Final score |
| `market` | Market key, e.g. `pitcher_strikeouts` |
| `bookmaker` | Book key, e.g. `draftkings`, `pinnacle`, `kalshi` |
| `player_name` | Player |
| `outcome_name` | `Over` / `Under`, or a milestone like `6+ Strikeouts` |
| `line` | The line |
| `price_american`, `price_decimal` | Last price we saw |
| `resolution` | `won` / `lost` / `push` / `void`, graded by PropLine against the official stats |
| `actual_value` | The player's actual stat |
| `resolved_at` | When it was graded |
| `opening_price`, `opening_point`, `opening_at` | First price in the 14 days before the game |
| `closing_price`, `closing_point`, `closing_at` | Last price at or before kickoff |
| `dfs_odds_type` | PrizePicks tier: `standard` / `goblin` / `demon` (DFS only) |
| `payout_multiplier` | Underdog per-pick multiplier (DFS only) |
| `outcome_id`, `player_id` | Stable ids (`player_id` is the league id, e.g. `mlb:592450`) |

## Notes

- **Grading is PropLine's**, against the league's official box score — not each book's
  house rules. `void` usually means the player didn't play.
- DFS apps (PrizePicks, Underdog, Sleeper, Dabble, ParlayPlay) post pick'em prices, not
  bettable two-way odds. Filter them out for pricing work.
- `closing_point` can differ from `line`; use it for closing-line value (CLV).

## Get more

- The full archive (every sport, every market, since April 2026):
  [Historical Backfill](https://prop-line.com/historical-backfill?ref=dataset)
- Live odds and grading through the API, free tier: [prop-line.com](https://prop-line.com/?ref=dataset)
- Which books price props best: [Sportsbook accuracy report](https://prop-line.com/sportsbook-accuracy)

License: CC BY 4.0 — credit "PropLine (prop-line.com)".
