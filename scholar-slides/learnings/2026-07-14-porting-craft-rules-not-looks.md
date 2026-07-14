# Borrowing from another design system: port the *lintable disciplines*, not the look

**Problem (one line):** asked whether `nexu-io/open-design` (77.9k★ AI-design app) had anything
worth borrowing for scholar-slides' aesthetics — most of its surface (150+ skills, 138 brand
DESIGN.md files) turned out to be stubs or generated boilerplate; the borrowable 20% had to be
identified, filtered against our register, and landed without churn.

## The approach

1. **Map the repo by asset class before reading content.** One tree fetch, grep for
   skill/deck/design paths → four candidate layers (craft rules, deck-framework prompt, token
   schema, skill catalog). Reading a *sample* of each layer first revealed that most "skills"
   were catalogue stubs pointing upstream — saved hours of reading thin files.
2. **Separate convergent validation from new information.** Their core architecture (fixed
   framework + content slots, locked layout pools, "no invented metrics") matched ours — that
   *validates* our decisions but changes nothing. The genuinely new material was the `craft/`
   layer: rules stated as **checkable thresholds** (caps tracking ≥ +0.06em, display ≥48px at
   −0.02–−0.03em, ≤2 accent uses/screen, value labels outside bars).
3. **Filter by register, not by quality.** Their visual language (Klein blue, manifesto slides,
   marketing soul) is good work for *their* register and wrong for Nature/Science. The test for
   porting: "is this a discipline (how to execute any look well) or a look (their taste)?"
   Disciplines port; looks don't.
4. **Scale-check heavy machinery before adopting it.** Their 4-layer token contract + guards
   exists because 138 brands drift; we have 2 theme flavors — the useful kernel is one small
   test (flavor only overrides declared tokens), not the schema. Adopting infrastructure built
   for someone else's scale problem is self-inflicted complexity.
5. **Land each borrowed rule at the strongest enforcement tier available:** token
   (`--track-display`) > deterministic check (`emojiAudit` P2, `tick_rotation`/`should_label_bars`
   in the renderer) > scoring anchor (scale-event, ≤3 sizes, pacing) > prose. A rule that could
   be a token should not be a rubric line.
6. **Prove the merge on a real deck.** Re-ran GLM-5 end-to-end: the chart top-defect (rotated
   tick labels) disappeared exactly as their craft rule predicted; scores under the *new*
   anchors confirmed no regressions; benchmark stayed 7/7 green.

## Gotcha logged on the way

`render_deck.mjs <deck.html> png slides` resolves the output dir against **CWD**, not against
the deck.html — screenshots landed in repo-root `./slides/` while `out/glm5/deck/slides/`
stayed stale, which silently produced "before" images in an "after" comparison. Caught by
md5-matching a source figure against the copy the slide *should* show. Pass explicit output
paths (same class of bug as the `export_pptx.mjs` default-path gotcha; both → M10 one-command
refresh).
