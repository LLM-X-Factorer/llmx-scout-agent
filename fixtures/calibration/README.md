# Calibration Fixtures

Each `*.yaml` file in this directory is a **golden sample** — a real or synthetic
candidate paired with the score you (the human analyst) would give it.
`scout score-tune` runs the current prompt against every fixture and reports
where the model and you disagree.

## Why this exists

Prompt drift is invisible without a regression set. Every time you tweak
`prompts/scoring.md`, run `scout score-tune` to see what shifted. If the model
moves a known high-judgment topic from 8.0 to 5.0, the prompt change broke
something — even if everything else "feels" fine.

## Workflow

1. **Capture a fixture from a real run** when you see a result you want to lock in
   (good or bad). Copy the relevant fields into a new YAML file.
2. **Set `expected.final_score`** — your honest 0-10 verdict.
3. **Set `expected.layer`** if you have a strong opinion. Use `unsure` if you don't.
4. **Add `notes`** explaining *why* you scored it that way. This is the most
   valuable field: future-you will thank present-you for the rationale.
5. Commit the fixture. Run `scout score-tune` whenever you touch the prompt.

## Schema (v1)

```yaml
id: short-slug-matching-filename
description: one-line human summary of what this sample tests

# Everything inside `input` is the same shape as Candidate fields the
# scorer sees. Anything omitted defaults to "(unknown)".
input:
  platform: hacker_news | github | reddit | other
  title: "..."
  primary_url: "..."
  original_url: "..."          # optional; defaults to primary_url
  author: "..."                # optional
  metrics:                     # at least one non-null field required
    hn_score: 200
    hn_comments: 50
  matched_keywords: ["..."]    # what the keyword filter would have matched
  snippet: |                   # optional first paragraph / summary
    Multi-line OK.
  comments_preview: |          # optional; what the scorer was given (or would be)
    - @user1: ...
    - @user2: ...

# Your verdict
expected:
  final_score: 7.5             # required, [0, 10]
  layer: 留存层                 # required: 引流层 | 留存层 | 转化层 | unsure
  judgment_seed_keywords: []   # optional; if set, model's seed must contain
                               # at least one of these strings (case-insensitive)
                               # use this to lock in the conceptual axis,
                               # not exact wording

# How forgiving the regression should be
tolerance:
  score: 1.5                   # |actual - expected| <= this is "match"
  layer_strict: false          # if true, layer mismatch counts as failure

notes: |
  Why this sample matters and why you scored it this way.
  Future-you reads this when the model's verdict surprises you.
```

## Naming

`NNN-short-slug.yaml` — leading number gives stable ordering when you scan
the report. Slug should match `id` field.

## What NOT to put here

- **Cherry-picked easy wins.** Include the painful disagreements too.
- **Outdated examples.** If the world has moved on (model went GA, framework died),
  delete the fixture rather than letting it skew calibration.
- **Personal/sensitive content.** This directory is committed to git.
