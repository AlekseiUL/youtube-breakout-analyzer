# Methodology

## 1. Research question

The analyzer asks:

> Which public videos are performing unusually well relative to their own channel's recent public baseline, and which recurring production features are worth testing?

It does not ask which videos have the largest absolute view count.

## 2. Evidence layers

### Metadata

Public title, URL, channel, publication time, duration, views, comment count, description snippet, tags when exposed, and thumbnail URL.

### Channel baseline

Recent public videos for the same channel. The default statistic is median views because it is less sensitive than the mean to one historic viral video.

Baseline sufficiency is based on usable public view samples. Missing view counts remain missing and do not inflate the usable sample count.

### Topic baseline

When enough comparable candidates exist, the analyzer estimates median views/day for a topic key and records a topic ratio. This is secondary to the channel baseline.

### Optional comments

Public comments can provide repeated audience language and implementation intent. They are incomplete and can be disabled or rate-limited. Comment text is evidence about the sampled comments, not the whole audience.

### Optional subtitles

Public creator captions or automatic captions when exposed. Absence is recorded as a gap.

### Optional thumbnails

Public image bytes and local pixel metrics. These are descriptive proxies, not semantic understanding.

Unavailable or degraded visual artifacts are recorded as coverage gaps and do not add visual evidence credit.

## 3. Core calculation

```text
channel_outlier_multiplier = current_public_views / recent_channel_median_views
```

The multiplier is accepted only when the channel baseline meets `min_channel_samples` using usable public view samples. Otherwise the status is `INSUFFICIENT_CHANNEL_BASELINE`.

The default thresholds are configurable:

```yaml
thresholds:
  strong: 5.0
  breakout: 10.0
  extreme: 20.0
```

## 4. Ranking

Qualified candidates are ordered by:

1. channel outlier multiplier;
2. evidence quality;
3. topic ratio;
4. views per day;
5. absolute views.

The order is explicit in the JSON output. It is not a learned black-box score.

## 5. Small and established channels

The niche config provides `small_channel.median_views_max`. This produces two lists:

- breakouts on channels with a smaller recent median;
- breakouts on established channels.

This split prevents large channels from hiding emerging formats on smaller channels.

## 6. Pattern generation

A pattern qualifies when it appears in breakout videos and has enough evidence according to the current deterministic rules. Each pattern includes examples and counterexamples.

Confidence considers:

- number of qualified examples;
- number of distinct channels;
- number of evidence types;
- presence of counterexamples.

Confidence is not causality.

## 7. Causality boundary

Every report and `PATTERN_BANK` carries:

```text
association, not proven cause
```

A title formula, duration, visual label, or comment theme can correlate with strong performance while the real cause is topic demand, recommendation distribution, creator reputation, timing, external traffic, or an unobserved factor.

The correct use of a pattern is a controlled production hypothesis:

1. change one feature;
2. hold topic intent and quality as stable as practical;
3. compare against the channel baseline;
4. repeat before adopting a rule.

## 8. Known and unknown

### Known from public evidence

- sampled public view and comment counts;
- sampled recent channel median;
- publication date when exposed;
- extracted deterministic feature matches;
- optional artifact coverage;
- observed associations and counterexamples.

### Unknown without private analytics or experiments

- impressions and click-through rate;
- average view duration and retention curve;
- traffic sources;
- subscriber/non-subscriber split;
- recommendation allocation;
- private A/B test results;
- causal contribution of any observed feature.

## 9. Reproducibility

Offline fixture runs pin `analysis_at` and use synthetic anonymous records. Live runs store timestamps, project-relative source labels, query provenance, coverage states, and immutable run artifacts.

Public platform results can change, so a live run is reproducible as an analysis of its saved input artifacts, not necessarily as a future network response.
