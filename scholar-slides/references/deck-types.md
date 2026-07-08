# Deck Types — time→budget, arc, density, archetypes

**Status: live for 组会 (Stages 1–4); conference & 答辩 are authoring guidance (Stage 5).** The
registered layouts already support all three — the deck *type* changes the **arc, density, slide
budget, and which archetypes you include**, which is how you author the `deck.json`, not new code.
Set `meta.deck_type` and follow the row below. Estimate talk length with `speaker_notes.mjs`.

| type | time → slides | arc | density | required / notable archetypes |
|---|---|---|---|---|
| **journal club / 组会** (default) | soft 30–60 min, interruption-driven | context → claims → method (deep) → results (dense, real tables) → **critique** → takeaway → discussion | **HIGH / reading-first** — dense tables, full equations, ablations, failure cases on-slide | `critique-concerns` + `discussion-questions` **required**; one-message-per-slide *relaxed* |
| **conference talk** | 12 min ≈ 10–14 slides; 20 min ≈ 16–22 (~45–60s/slide) | teaser, not survey: one problem → one idea → strongest result → "read the paper" | **SPARSE**, speaker-led: one claim/slide, big figures, minimal text | front-load motivation; push related work + most ablations to backup; no critique slide |
| **thesis defense / 答辩** | 40–60 min, 30–60 slides + deep appendix | roadmap → background/positioning → contribution 1…N (each its own mini problem→method→result) → synthesis → **limitations** → future work → contributions recap | **MIXED**; method/results denser than a conference talk; every number traceable | `section` dividers per contribution; future-work + timeline as `bullets` slides; **Backup/Appendix** (extra `results-table`/`assertion-evidence` slides after a `section` divider titled "Backup") |

Authoring deltas from the default 组会 deck:
- **Conference:** drop the `critique-concerns` slide; thin every `bullets` slide to one message;
  prefer `assertion-evidence` (figure-forward); fewer slides; move detail to a backup section.
- **答辩:** add `section` dividers and a future-work `bullets` slide; keep dense method/results;
  add an appendix of `results-table`/`assertion-evidence` slides for examiner questions; cite
  everything. (Only the 11 registered layouts exist — `scripts/lib/layouts.mjs` throws on any
  other name; archetypes above are *content roles* expressed through registered layouts.)

The same paper therefore yields visibly different decks: a sparse conference teaser vs a dense,
critique-bearing journal club vs a cumulative, appendix-backed defense.

The per-type audience/narrative analysis is summarized above; the density register (sparse
conference → dense journal club → cumulative defense) drives the slide-budget and archetype mix.
