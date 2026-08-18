# Video assets — what to deliver, and how they map

Generated from the fault keys in `wedge.py`, `putt.py` and `chip.py`, so this
list cannot drift from what the engine actually detects.

---

## How to hand the files over

Drop them into this folder on the project machine:

```
C:\Users\DELL\Downloads\GolfCoachNow\assets\videos\ 
```

with this structure:

```
assets/videos/
  instructional/
    swing.mp4
    putt.mp4
    short_game.mp4
  correction/
    swing_correction.mp4       <- Version 1: one clip per mode
    putt_correction.mp4
    shortgame_correction.mp4
    swing/                     <- Version 2 only: one clip per fault
    putt/
    short_game/
  marketing/
    intro.mp4
  images/
    camera_setup.png           <- the shared setup slide
    biometrics_swing.png
    biometrics_putt.png
    biometrics_short_game.png
```

**The filename is the mapping.** Drop a file in with the right name and it
wires itself up — no spreadsheet, no cross-referencing, nothing for either of
us to transcribe wrongly. That holds for the three V1 clips above and for the
per-fault clips later: `open_clubface.mp4` in the `swing` folder becomes the
clip that plays when the engine detects `open_clubface`.

Anything is fine for transfer — a shared folder, a zip, a drive. What matters
is that the names match, because that is what removes the guesswork.

### Version 1 needs three correction clips, not sixty

Per the correction module spec, V1 ships **one correction clip per mode**.
The clip reinforces the identity of the correction rather than the specific
fault, so it does not branch on what the engine detected.

```
correction/swing_correction.mp4
correction/putt_correction.mp4
correction/shortgame_correction.mp4
```

Each 10-20 seconds, clean background, single speaker, no music, no branding.

Note `shortgame` there, against `short_game` used elsewhere. That is the
filename as specified, and the code matches it exactly.

With those three plus the three instructional clips already delivered, the
whole four-wire pipeline is real end to end. **Six files is the complete
Version 1 set.**

The per-fault list further down is Version 2 scope, included so the scale of
that expansion is visible. Nothing in it is needed to ship V1.

---

## Version 2: the per-fault expansion

Fault counts currently in the engine: Swing 20 · Putt 20 · Short Game 20. **Not required for V1.**

> Worth confirming: you mentioned Putt and Short Game have **6** variables
> each. The engine currently carries **20** for each. If the biometric slides
> on screen list 6, the engine should be trimmed to match so the two agree —
> that would cut this list considerably.

### Swing — 20 clips

`assets/videos/correction/swing/`

| Filename | Plays when the engine detects |
| --- | --- |
| `open_clubface.mp4` | open clubface |
| `closed_clubface.mp4` | closed clubface |
| `weak_grip.mp4` | weak grip |
| `strong_grip.mp4` | strong grip |
| `over_the_top.mp4` | over the top |
| `under_plane.mp4` | under plane |
| `early_extension.mp4` | early extension |
| `casting.mp4` | casting |
| `chicken_wing.mp4` | chicken wing |
| `reverse_pivot.mp4` | reverse pivot |
| `sway.mp4` | sway |
| `slide.mp4` | slide |
| `spine_angle_loss.mp4` | spine angle loss |
| `tempo_imbalance.mp4` | tempo imbalance |
| `poor_alignment.mp4` | poor alignment |
| `ball_position_error.mp4` | ball position error |
| `grip_pressure.mp4` | grip pressure |
| `hip_stall.mp4` | hip stall |
| `flat_shoulder_turn.mp4` | flat shoulder turn |
| `steep_shoulder_turn.mp4` | steep shoulder turn |

### Putt — 20 clips

`assets/videos/correction/putt/`

| Filename | Plays when the engine detects |
| --- | --- |
| `poor_alignment.mp4` | poor alignment |
| `deceleration.mp4` | deceleration |
| `wrist_breakdown.mp4` | wrist breakdown |
| `poor_speed_control.mp4` | poor speed control |
| `head_movement.mp4` | head movement |
| `open_face_at_impact.mp4` | open face at impact |
| `closed_face_at_impact.mp4` | closed face at impact |
| `poor_aim.mp4` | poor aim |
| `inconsistent_strike.mp4` | inconsistent strike |
| `too_wristy.mp4` | too wristy |
| `backstroke_too_long.mp4` | backstroke too long |
| `poor_green_read.mp4` | poor green read |
| `stance_too_wide.mp4` | stance too wide |
| `stance_too_narrow.mp4` | stance too narrow |
| `ball_position_error.mp4` | ball position error |
| `grip_pressure_too_tight.mp4` | grip pressure too tight |
| `poor_distance_control.mp4` | poor distance control |
| `pushing_putts.mp4` | pushing putts |
| `pulling_putts.mp4` | pulling putts |
| `yips.mp4` | yips |

### Short Game — 20 clips

`assets/videos/correction/short_game/`

| Filename | Plays when the engine detects |
| --- | --- |
| `flipping.mp4` | flipping |
| `scooping.mp4` | scooping |
| `poor_ball_position.mp4` | poor ball position |
| `no_weight_forward.mp4` | no weight forward |
| `too_much_wrist.mp4` | too much wrist |
| `decelerating.mp4` | decelerating |
| `poor_club_selection.mp4` | poor club selection |
| `fat_contact.mp4` | fat contact |
| `thin_contact.mp4` | thin contact |
| `poor_distance_control.mp4` | poor distance control |
| `open_clubface.mp4` | open clubface |
| `closed_clubface.mp4` | closed clubface |
| `poor_trajectory.mp4` | poor trajectory |
| `no_bounce_use.mp4` | no bounce use |
| `steep_attack.mp4` | steep attack |
| `shallow_attack.mp4` | shallow attack |
| `poor_landing_spot.mp4` | poor landing spot |
| `poor_setup.mp4` | poor setup |
| `no_follow_through.mp4` | no follow through |
| `tension.mp4` | tension |

---

## Totals

| Set | Files |
| --- | --- |
| Instructional | 3 |
| Marketing | 1 |
| Correction, one per mode (V1) | 3 |
| Correction, one per fault (V2 only) | 60 |
| **Version 1 complete** | **6** videos, of which 3 are already delivered |
| Version 2 complete | 67 videos |
| Images to insert | 4 |

---

## Format

Whatever came out of the camera is fine — I will transcode. If there is a
choice: **MP4, H.264, AAC audio**, since that plays natively on iOS, Android
and every browser without a player library.

Please send the **originals rather than the YouTube copies**. Re-downloading
from YouTube costs a generation of quality, and the images have to be inserted
into a clean master.

