# 2025 rolling validation and earlier-trained calibration

All twelve categories use the fixed P2_LEAF/E0_OP/H-MULTI procedure. The new216raw origins cover all18regular-season2025weeks and272games. The2026base fits/predictions are reused unchanged. One predeclared monotone sigmoid percategory learns only from2025out-of-sample probabilities and labels. These exposed periods are not fresh holdouts.

The probability change below is calibrated minus identical saved raw2026probabilities. Most thresholds are synthetic; anytime is an actual rushing-or-receiving TD event. No offered-pick or price/value result follows. Point products remain in the raw model; the calibrated threshold/event product does not claim a mean, median or complete law.

|Category / primary panel|2025 raw median MAE|2025 raw Brier / earlier prevalence|2025 outcomes/queries|2026 raw → calibrated Brier|Paired change [95% week CI]|2026 outcomes/queries|
|---|---:|---:|---:|---:|---|---:|
|pass_yd / ALL|68.6867|0.132887 / 0.161701|664/664|0.137976 → 0.140009|+0.002033 [+0.001262,+0.002900]|242/242|
|pass_td / ALL|0.8253|0.139840 / 0.157106|664/664|0.146272 → 0.146585|+0.000313 [+0.000108,+0.000510]|242/242|
|pass_cmp / ALL|5.8102|0.137540 / 0.164347|664/664|0.135293 → 0.137479|+0.002186 [+0.001063,+0.003331]|242/242|
|pass_att / ALL|8.5512|0.155123 / 0.188268|664/664|0.146835 → 0.148056|+0.001220 [+0.000205,+0.002625]|242/242|
|pass_int / ALL|0.5663|0.122713 / 0.124958|664/664|0.121892 → 0.122158|+0.000265 [-0.000366,+0.000935]|242/242|
|rush_yd / RB|19.9051|0.104466 / 0.144511|1475/1575|0.103175 → 0.103205|+0.000031 [-0.000235,+0.000249]|572/605|
|rush_att / RB|3.5003|0.089295 / 0.137682|1475/1575|0.095600 → 0.095804|+0.000205 [-0.000166,+0.000522]|572/605|
|rec / ALL|1.2034|0.112138 / 0.149521|4994/5373|0.117268 → 0.117575|+0.000308 [+0.000127,+0.000498]|1986/2152|
|rec_yd / ALL|15.7407|0.090220 / 0.113115|4994/5373|0.094941 → 0.095045|+0.000104 [-0.000034,+0.000242]|1986/2152|
|rush_rec_yd / PRIMARY|20.3260|0.090565 / 0.117967|4994/5373|0.092368 → 0.092307|-0.000061 [-0.000140,+0.000028]|1986/2152|
|anytime_td / ALL|N/A event|0.143249 / 0.154999|5658/6037|0.143665 → 0.143573|-0.000092 [-0.000352,+0.000176]|2228/2394|
|fpts / ALL|4.4619|0.094121 / 0.118648|5637/6037|0.096511 → 0.096690|+0.000178 [+0.000083,+0.000255]|2227/2394|

All query masks/unknowns remain. Rushing RB and QB and receiving RB/WR/TE panels are reported separately in [SCORES.csv](SCORES.csv). Full, weekly, startup, learned-only, strict/inclusive1native-unit and tail views are retained. Do not rank categories using native-unit errors. Seven2026week clusters and exposed design/multiple tests limit uncertainty interpretation. [Paired records](PAIRED.json) retain every interval, gain and reversal. [Reliability](RELIABILITY.csv) describes actual raw and transformed probabilities, not guaranteed calibration improvement.

Raw2025performance is a genuine chronological reconstruction. No calibrated2025performance is claimed: the2025OOFrecords train the sigmoid. The actual final2026probabilities are also reconstructions generated after those games, not original issued forecasts. Source revisions, retrospective participant-only population, partial chart rare-component labels, and the assumed7day availability rule remain unchanged.

The separate [frozen C0 benchmark](C0_2025_MATCHES.json) matches all five original categories to new2025rows, verifying exact labels/gamekickoffs/fitcutoffs without refitting C0. This compares whole procedures: both learner and added ordinary opportunity change. It is not an isolated information ablation or exact A/Breproduction. Full new populations remain separate from the reduced oldC0 rushing panel.

Real Over/Under W/L/decided/rates, A/C and B/C exact matching, six-leg success, payouts/profit and price-aware value remain N/A pending the exact previously listed exports/contracts. No anytimeNO/Under offer or chart market is created. NGSintake is a repeatedbyteidentical packet and adds no modelinput; the original failed/inconclusive NGSrecipe remains frozen.

The fixed sigmoid worsens Brier in 10 of 12 primary panels. The tiny Rush+Rec and Anytime TD improvements have game/week intervals that include zero. Log loss improves in four categories and worsens in eight, so proper-score conclusions remain separate. QB rushing improves where the RB headline worsens; WR Rush+Rec and TE Anytime TD worsen despite tiny combined gains. No sigmoid package is promoted.

Raw 2025 forecasts beat the earlier-only role prevalence Brier reference in all twelve primary panels. That supports further testing of the fixed raw procedure; it does not establish better offered selections or isolate an NGS effect. New point forecasts have lower observed MAE than frozen C0 on all five original same-row category benchmarks, with learner and ordinary opportunity both changing. Native-unit scores cannot rank categories.

[Fresh GitHub restoration](GITHUB_RESTORE.json) downloads all twelve archives, checks every saved slot hash, recomputes aggregate scores, reproduces representative W18 raw inference and every calibrated 2026 row without fitting. [Dataset versions](DATASET_VERSIONS.json) keep source outcomes, original forecasts, transformed probabilities and unavailable offers/selections/entries distinct. [Selection status](SELECTION_STATUS.csv) and [external matching](ABC_COMPARABILITY.csv) retain precise N/A states. [Independent audit](INDEPENDENT.json) checks actual rows and code. [Local website acceptance](SITE_LOCAL_QA_V3.json) is not a served-site receipt.
