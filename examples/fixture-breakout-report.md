# YouTube Breakout Analyzer - Silent walking / city walks

## Verdict
Facts: 8 niche-matched public video record(s), 3 qualified breakout(s), 4 channel(s).
Computed signals: ranking uses visible channel multiplier, evidence quality, topic ratio, views/day, then raw views.
Interpretation / hypotheses: repeated patterns below are candidates for controlled production tests.
Warning: association, not proven cause. Public data does not include CTR, retention, traffic source, or YouTube Studio internals.

## Data coverage and access gaps
- Mode: full-public
- Latest pointer: result/breakout-latest.json
- Search bundle: data/search/2026-07-16/search-20260716-000000.json
- Excluded as outside niche: 3
- Gap: comments -> MISSING_COMMENTS_ARTIFACTS (5 video(s))
- Gap: visual -> MISSING_VISUAL_ARTIFACTS (5 video(s))
- Gap: transcripts -> MISSING_TRANSCRIPT_ARTIFACTS (8 video(s))
- Gap: audio -> NOT_AVAILABLE_WITHOUT_OPTIONAL_ANALYSIS (8 video(s))

## Top small-channel breakouts
- **Tokyo Rain Night Walk 4K - Shinjuku Backstreets - No Talking** | Rain Walks Micro | views: 12000 | median: 500.0 | channel multiplier: 24.0x (20x+ extreme) | views/day: 2000.0 | topic ratio: 20.0 | comments/1k views: 15.0 | status: EXTREME_BREAKOUT | https://www.youtube.com/watch?v=walk_tokyo_rain
- **Seoul Snow Morning Walk 4K - Silent Residential Streets** | Quiet Seoul Walks | views: 8000 | median: 800.0 | channel multiplier: 10.0x (10x+ breakout) | views/day: 1142.86 | topic ratio: 0.91 | comments/1k views: 11.25 | status: BREAKOUT | https://www.youtube.com/watch?v=walk_seoul_snow

## Top established-channel breakouts
- **Paris Night Walk 4K HDR - Rain Reflections, No Commentary** | City Lens | views: 650000 | median: 100000.0 | channel multiplier: 6.5x (5x+ strong) | views/day: 130000.0 | topic ratio: 113.75 | comments/1k views: 3.692 | status: STRONG_CHANNEL_OUTLIER | https://www.youtube.com/watch?v=walk_paris_night

## Repeated patterns

### Cross-channel patterns
- **weather: rain** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: comments, metadata, visual | confidence: HIGH | warning: association, not proven cause
- **title_promise: place_condition_moment_format** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **production_marker: resolution_4k** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **production_marker: no_talking** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: depth** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: reflections** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: neon** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: single_human** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: text_free** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **place_type: ordinary_neighborhood** | evidence: 2 | channels: 2 | median multiplier: 17.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause

## Niche-specific patterns
- **weather: rain** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: comments, metadata, visual | confidence: HIGH | warning: association, not proven cause
- **title_promise: place_condition_moment_format** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **production_marker: resolution_4k** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **production_marker: no_talking** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: depth** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: reflections** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: neon** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: single_human** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **thumbnail: text_free** | evidence: 3 | channels: 3 | median multiplier: 10.0x | sources: visual | confidence: MEDIUM | warning: association, not proven cause
- **place_type: ordinary_neighborhood** | evidence: 2 | channels: 2 | median multiplier: 17.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **event: ordinary** | evidence: 2 | channels: 2 | median multiplier: 17.0x | sources: metadata | confidence: MEDIUM | warning: association, not proven cause
- **audience_motivation: treadmill** | evidence: 2 | channels: 2 | median multiplier: 17.0x | sources: comments | confidence: MEDIUM | warning: association, not proven cause

## Counterexamples / killed hypotheses
- **weather: rain** has non-breakout examples:
  - Kyoto Day Walk 4K - No Talking | Rain Walks Micro | multiplier: 2.0 | status: BELOW_BREAKOUT_THRESHOLD
  - Seoul Clear Day Walking Tour 4K | Quiet Seoul Walks | multiplier: 1.5 | status: BELOW_BREAKOUT_THRESHOLD
  - Tokyo Rain Walking Tour 4K - Quiet Afternoon | Rain Walks Micro | multiplier: 1.2 | status: BELOW_BREAKOUT_THRESHOLD
- **title_promise: place_condition_moment_format** has non-breakout examples:
  - Kyoto Day Walk 4K - No Talking | Rain Walks Micro | multiplier: 2.0 | status: BELOW_BREAKOUT_THRESHOLD
  - Seoul Clear Day Walking Tour 4K | Quiet Seoul Walks | multiplier: 1.5 | status: BELOW_BREAKOUT_THRESHOLD
  - Tokyo Rain Walking Tour 4K - Quiet Afternoon | Rain Walks Micro | multiplier: 1.2 | status: BELOW_BREAKOUT_THRESHOLD
- **production_marker: resolution_4k** has non-breakout examples:
  - Kyoto Day Walk 4K - No Talking | Rain Walks Micro | multiplier: 2.0 | status: BELOW_BREAKOUT_THRESHOLD
  - Seoul Clear Day Walking Tour 4K | Quiet Seoul Walks | multiplier: 1.5 | status: BELOW_BREAKOUT_THRESHOLD
  - Tokyo Rain Walking Tour 4K - Quiet Afternoon | Rain Walks Micro | multiplier: 1.2 | status: BELOW_BREAKOUT_THRESHOLD
- **production_marker: no_talking** has non-breakout examples:
  - Kyoto Day Walk 4K - No Talking | Rain Walks Micro | multiplier: 2.0 | status: BELOW_BREAKOUT_THRESHOLD
  - Seoul Clear Day Walking Tour 4K | Quiet Seoul Walks | multiplier: 1.5 | status: BELOW_BREAKOUT_THRESHOLD
  - Tokyo Rain Walking Tour 4K - Quiet Afternoon | Rain Walks Micro | multiplier: 1.2 | status: BELOW_BREAKOUT_THRESHOLD

## PATTERN_BANK
- **title_formulas**: 1 qualified pattern(s).
- **thumbnail_formulas**: 5 qualified pattern(s).
- **content_formats**: 9 qualified pattern(s).
- **audience_promises**: 1 qualified pattern(s).
- **emotional_hooks**: 0 qualified pattern(s).
- **comment_motivations**: 7 qualified pattern(s).
- **saturation_signals**: 0 qualified pattern(s).
- **opportunity_gaps**: 0 qualified pattern(s).
- **counter_patterns**: 13 qualified pattern(s).
- **avoid_copying**: 3 guardrail(s); see `PATTERN_BANK.md`.

## Facts vs interpretation
- Facts: public titles, URLs, channels, view counts, comment counts, publish dates, local comments/artifacts when present.
- Computed signals: video age, views/day, channel multiplier, topic ratio, comment rate, evidence quality, pattern counts.
- Interpretation/hypotheses: any packaging, route, title, thumbnail, or audience-motivation pattern.
- Causality boundary: association, not proven cause.

## Main caveat
- This is public evidence only. It cannot verify impressions, CTR, retention, traffic sources, revenue, conversion, subscriber notifications, paid promotion, or creator-side edits.

## Limitations
- Public collection can be incomplete, rate-limited, region-dependent, or temporarily unavailable.
- Unknown values remain unknown; missing optional layers are never converted to zero.
- Statistical association does not prove why a video succeeded and does not guarantee virality.

## Recommended experiments
- Test `weather: rain` as one controlled variable. Keep topic/channel context stable and compare 7-day and 28-day metrics.
- Test `title_promise: place_condition_moment_format` as one controlled variable. Keep topic/channel context stable and compare 7-day and 28-day metrics.
- Test `production_marker: resolution_4k` as one controlled variable. Keep topic/channel context stable and compare 7-day and 28-day metrics.
- Test `production_marker: no_talking` as one controlled variable. Keep topic/channel context stable and compare 7-day and 28-day metrics.
- Test `thumbnail: depth` as one controlled variable. Keep topic/channel context stable and compare 7-day and 28-day metrics.

## Confidence
- HIGH patterns: 1
- MEDIUM patterns: 14
- LOW patterns: 15
- Confidence increases with repetition across channels, strong normalized outliers, adequate channel baselines, and agreement across metadata/comments/visual artifacts.
