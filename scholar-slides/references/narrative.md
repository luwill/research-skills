# Narrative — paper-section→slide-role, action titles, arc-tension (Stage 3, CKPT-2)

**Status: live.** This is the authoring discipline for Stage 3 (outline). It consumes the
**confirmed digest** from Stage 1 and produces the slide-by-slide outline the user approves at
**CKPT-2**. The outline then becomes per-slide specs (`references/slide-spec.md`).

## Re-sequence the paper into talk order

A paper is written IMRaD for a *reader*; a talk is built for a *listener*. Do not walk the
paper's section order — walk the **argument**:

| paper section | slide role (组会 default) | registered layout |
|---|---|---|
| Title/authors/venue | cover | `paper-title` |
| — | agenda (7±2 items) | `outline-agenda` |
| Abstract + Intro gap | motivation: the problem, why now | `bullets` (thin) or `assertion-evidence` |
| Contributions | claims — enumerated, falsifiable | `bullets` |
| Method | method deep-dive: architecture figure, then THE equation | `assertion-evidence`, `equation`, `two-column` |
| Experiments setup | only what results need (datasets, baselines) | `bullets` / `two-column` |
| Results | headline result first, then dense evidence | `assertion-evidence` (figure/chart), `results-table` |
| Ablations | what actually carries the win | `results-table` / `assertion-evidence` |
| Limitations (+ yours) | **critique — required in 组会** | `critique-concerns` |
| Conclusion | takeaway in one assertion | `bullets` (1–3 points) or `section` |
| — | **discussion questions — required in 组会** | `discussion-questions` |
| References | every citation shown in the deck | `references` |

Deck-type deltas (budget, density, which roles to drop): `references/deck-types.md`.

## Action titles (the non-negotiable)

Every content slide's `action_title` is a **full-sentence assertion stating the slide's
conclusion** — what the audience should believe after 10 seconds — never a label.

- ✗ "Results" / "Method overview" / "Ablation study"
- ✓ "Core attention drops from quadratic to linear-in-k"
- Test: cover the body; the title alone must still make the slide's point.
- One message per slide (relaxed in the dense 组会 register — but the title still states ONE
  primary claim, and everything on the slide serves it).

**AI-cliché blocklist** for titles and bullets — never: "Delve into…", "Unlocking…",
"Revolutionizing…", "A deep dive…", "Navigating the landscape…", "In today's world…",
"Game-changing…". Titles state findings, not vibes.

## Arc-tension check (run before CKPT-2)

Walk the outline top-to-bottom and verify:

1. **A stated gap.** Some early slide names the problem/tension the paper attacks.
2. **Every results slide visibly answers the gap** — its action title should read as a reply
   to the motivation slide. A result that answers no stated question is trivia: cut it or
   restate the gap.
3. **The critique slide has real teeth** (组会): concerns a reviewer would actually raise —
   baselines, confounds, external validity — not "more experiments would help".
4. **Slide budget respected** (`deck-types.md` time→slides row); check estimated talk time
   with `node scripts/speaker_notes.mjs` after specs exist.
5. **Rhythm**: no 4+ identical layouts in a row (qa nudges this); bullet-slides ≤ ⅓ of the
   deck (the QA report nudges past that).

At **CKPT-2** show the user: ordered slide list (layout + action title each), where the gap is
stated, and which slides answer it. Get the arc approved *before* writing per-slide specs.
