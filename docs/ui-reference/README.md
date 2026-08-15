# Home screen — UI reference

`home-reference@3x.png` (1179 px wide) is the reference image. `@2x` is the
same layout at 786 px; `preview@1x.png` is for pasting into chat.

**These were not traced from a screenshot.** They are rendered from the app's
own source by `build.py`, so the reference cannot drift from the build:

| value | read from |
|---|---|
| palette, radii, padding, icon box, banner height | `iosapp/GolfCoachNow/Theme.swift` |
| font sizes, weights, per-constraint spacing | `iosapp/GolfCoachNow/ViewControllers/HomeViewController.swift` |
| module titles and card copy | `iosapp/GolfCoachNow/Models/GolfModule.swift` |
| banner artwork | `Assets.xcassets/banner.imageset/banner@3x.png` |

Change any of those and re-run `python3 build.py` — the reference follows.

## Canvas

393 pt wide (iPhone 15 / 14 Pro). The layout is width-driven; everything below
is in points.

## Palette

| token | value | use |
|---|---|---|
| background | `#000000` | page |
| card | `#121212` | every card fill |
| green | `#99B32E` | accent, icons, CTA fill, arrows |
| green border | `#80941F` @ 50% | every card border, 1 pt |
| text | `#FFFFFF` | headings |
| muted | `#999999` | body copy |
| text on green | `#121212` | CTA label |

## Spacing

| | pt |
|---|---|
| screen padding (left/right) | 16 |
| gap between cards | 8 |
| card corner radius | 14 |
| card border | 1 |
| icon box | 48 × 48, radius 12, 1 pt border |
| icon glyph | 28 × 28 |
| banner height | 180 |
| greeting card overlap onto banner | **−24** |
| greeting → module row | 12 |
| module row → action row | 8 |

## Greeting card

Padding 14 all round. A 3 pt green rule inset 14 from the left, running the
full inner height, with the text block 12 pt to its right.

- "Good morning," — 24 pt bold, white
- "John" — 24 pt bold, green, on its own line
- "What would you like / to learn today?" — 14 pt regular, muted, 4 pt below

## Module cards (Swing · Putt · Short Game)

Three equal columns. Card padding: 14 top, 6 sides, 12 bottom.

- icon box centred at the top
- title 10 pt below the box — 12 pt heavy, uppercase, white
- description 4 pt below the title — 9 pt regular, muted, centred, 2 lines
- CTA pinned to the **bottom** of the card, 30 pt tall, radius 8, green fill,
  label 8 pt heavy on `#121212`, with a `→` 5 pt after it

Two details that are easy to get wrong, both found by measuring:

1. **The cards must be equal width.** The CTA label does not wrap, so
   "START SHORT GAME" sets a min-content floor on the third card. With the
   default `min-width: auto`, that card steals width and squeezes the other
   two to 93.8 pt — one pixel under the 94.6 pt "Get instant feedback."
   needs, which drops it to three lines and knocks that card out of step.
   Give each card an equal fixed share.

2. **"START SHORT GAME" is one size smaller** (7 pt against 8 pt). The pill is
   97 pt wide, leaving ~81 pt for the label; that string measures 89.5 pt at
   8 pt and only 79.1 pt at 7 pt. The other two stay at 8 pt.

Descriptions break at the sentence, not wherever the line runs out:

```
Analyze your swing.        Analyze your putting.     Master your chipping,
Get instant feedback.      Improve your stroke.      pitching & bunker play.
```

Short Game is a single sentence, so it wraps naturally.

## Action cards (Send · Connect)

Two equal columns, each **72 pt tall**, padding 11 left / 12 right.

- 28 × 28 icon, vertically centred
- text block 9 pt to its right: title 14 pt bold white, description 9.5 pt
  regular muted, 2 pt below
- `→` 16 pt green, right-aligned

The description is 9.5 pt rather than 10 pt: the arrow glyph is wider than it
looks, leaving a ~92.5 pt text column, and "swing for feedback." measures
94.8 pt at 10 pt — it falls to a third line.

## One thing to fix in the assets

`banner@2x.png` and `banner@3x.png` are **byte-identical** (both 1926 × 817).
Xcode will render the @3x slot undersized on the Pro Max. The @2x should be
two-thirds the @3x width — 1284 × 545 — or drop the @2x entry and let the
@3x scale.
