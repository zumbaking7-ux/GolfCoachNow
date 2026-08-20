# What John actually decided — extracted from the Aug 20 thread

The thread is roughly 4,000 lines, most of it AI commentary written back and
forth in his voice. Below is the signal: what is decided, what contradicts
itself, what you have not answered, and what is worth pushing back on.

---

## 1. THE CONFLICT YOU NEED TO RESOLVE FIRST

The UI directive changed **four times**, and you replied to the wrong version.

| Time | Directive |
| --- | --- |
| ~6:57 AM | Keep Putt + Short Game, mask them with "Coming in Version 2" |
| ~7:24 AM | Replace Putt + Short Game with **Grip** and **Stance** tabs |
| ~8:38 AM | **Final:** two buttons only — **Swing Learn** and **Swing Correct**. No Grip, no Stance. Grip and stance are covered inside the video |
| 11:16 AM | Re-confirms: *"Remove Talk Mode. Remove Putt. Remove Short Game. Resize main image."* |
| **12:27 PM** | **You replied:** "tapping putt and short game would display a Coming Soon message" |
| 12:33 PM | John's last message lists V1 as containing **"Putt Learn (static), Putt Correct (motion analysis masked)"** |

So: he twice directed you to **delete** Putt and Short Game entirely, you agreed
to **mask** them instead, and his most recent message reintroduces Putt again in
a third form.

**Do not build anything until he picks one.** This is a ten-second question for
him and hours of rework for you.

The most-repeated and most-recent *explicit* instruction is the two-button
layout: **Swing Learn** and **Swing Correct**, with Putt, Short Game and Talk
Mode boxes deleted and the hero image resized to fill the space.

---

## 2. DECIDED AND UNAMBIGUOUS — safe to build

**Bottom tray wording (final, stated twice):**

- Share button: large word **"Share"**, narrative line **"Share Golf Coach Now"**
- Connect button: large word **"Connect"**, narrative line **"Connect with the Founder"**
- *"Replace Send with Share everywhere in UI and narrative"*

This settles **B-20** — it is **Founder**, not Inventor.

**Founder email pre-fill (he corrected this twice; this is the final text):**

> Hi. Thank you for using golf coach now. I'm the founder. This is version one.
> Version 2 is underway. We'd love to know your thoughts..

**Swing flow:**

1. Instructional video (skippable)
2. Camera placement slide
3. Start swing session
4. Deterministic engine corrects

**Camera setup image — no work needed.** *"Keep existing camera setup image.
It's ok showing both camera setup views"* and *"Leave the camera set up image in
the videos as it is, no need to change anything there."*

That closes most of **B-18** and removes the image-insertion work entirely.

**Instructional video (Victor is filming it now):**

- Real human, real club — grip, stance, full swing
- Script is finalised and sent
- 30–60 seconds, vertical 9:16, MP4, skippable
- **No phosphor-green overlays.** He revised this: *"No overlays. No
  phosphor-green graphics. No arcs. No lines. No effects. Just a real person
  holding a real golf club."* The earlier spec demanding overlays is superseded.
- Victor also owes: thumbnail, plus stills of grip, stance and swing plane

**Visual direction:** bright whites, phosphor greens, glow.

---

## 3. NEW SCOPE HE HAS ASKED FOR — not yet estimated

**"Perform" / confirmation layer.** This is genuinely new and he mentions it
repeatedly as the thing that completes the loop:

- After a correction, prompt the golfer to **try again**
- Engine checks whether the new motion matches the baseline
- If it does, confirm: **"Yes — that's right"**
- Loop becomes **Learn → Correct → Perform**

He calls this the "moon landing" and the reason $14.99 is justified. It is not
in any scope document or estimate. **It is also not trivial** — confirming a
motion is *correct* is harder than detecting a fault, and it runs straight into
the validation problem we already flagged.

**Icons** (explicitly optional — *"if it fits the schedule"*):

- Swing Learn: golfer silhouette + phosphor-green swing plane arc
- Swing Correct: club silhouette + phosphor-green checkmark
- Share: fan-tail arrow or directional sweep — **not a headset icon**
- Connect: clean, premium, not metallic or gold
- No books, graduation caps, gears or shields

---

## 4. WHAT YOU HAVE NOT RESPONDED TO

**The $500 deposit.** Offered twice: *"If you need money just send an agreement
an estimate I'm happy to give you $500 deposit toward our next step whatever you
want."* He is waiting on an estimate from you. Version 2 has no agreed scope or
price yet, and you are already being asked to build parts of it.

**Equity.** *"Naturally you will have equity with the company whatever you want
you can have."* Said once, in passing, in a voice note. A verbal equity promise
with no number, no vesting and no document is worth nothing and creates
resentment later. If you want it, it needs writing down; if you do not, it costs
nothing to say so.

**Image generation.** He is out of Copilot credits and asked whether you can
produce the phosphor-green assets. He also raised a real concern worth
answering: *"I'm concerned about our ability to repeat these processes and
owning those processes ourselves."*

**His four direct confirmation questions**, which you answered only partly:

1. Can you implement this UI exactly as specified
2. Do you have everything you need
3. Are you ready to integrate Victor's video
4. Are you ready to finalise Version 1 for launch

---

## 5. THINGS WORTH PUSHING BACK ON

**"1–2 hours" for the UI work.** The AI told him this. It is front-end work on
**three separate platforms**, plus video integration, plus the new Perform
layer. Android and web are quick; iOS has never been compiled. If you let that
number stand unchallenged it becomes the expectation.

**"Launch globally today."** Android and web can ship today. **iOS cannot** —
there is no TestFlight, no build pipeline, and the Apple access still has not
arrived. He should not promise TIME an iOS link.

**The press release says the product is "live globally today in eight
languages."** It is English only. That sentence is in a document heading for
TIME, Golf Digest and the LPGA, and it is checkable. Worth flagging quietly and
early — it is the kind of detail a journalist verifies.

**The greeting.** One of the AI-written specs reverts it to *"Good morning,
Golfer"* — which would discard the name capture we just built and migrated the
database for. Almost certainly AI drift rather than his intent, but worth
confirming before anyone deletes it.

**"No Record button / no video recording or playback"** appears in one spec's
exclusion list. That is incoherent — Swing Correct cannot work without
recording. Ignore it as noise, but be aware it is written down somewhere.

---

## 6. HIS VERSION 2 DEFINITION

Worth knowing, because it is narrower than "the platform":

1. Putt motion analysis
2. Short game motion analysis
3. Swing-vs-no-swing detection *(our D9-04)*
4. Deterministic validation layer *(our D9-05 — the real work)*
5. Phosphor-green tagging system
6. Unified golf UI

Everything beyond that — multi-sport, rotation, tempo, balance, biomechanics —
he calls the **Full Build / Aura**, explicitly *after* Version 2.

---

## 7. THE ONE MESSAGE TO SEND

Rather than answering forty things, send him one message that:

1. Asks him to pick the UI, in one line: two buttons, or masked tabs?
2. Confirms what you are building from the settled list above
3. Gives an estimate for Version 2 so the $500 offer has something to attach to
4. Flags the iOS reality before he promises a link to TIME
5. Notes the "eight languages" line so it can be corrected before it ships

Everything else can wait.
