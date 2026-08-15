"""
Render the Golf Coach Now home screen as a high-resolution reference.

Every number here is read off the app's own source, not measured from a
screenshot:
  Theme.swift                 palette, radii, padding, icon box, banner height
  HomeViewController.swift    font sizes, weights, per-constraint spacing
  GolfModule.swift            module titles and card copy

That is the point: a screenshot can only ever be traced, and tracing is how
spacing drifts. Regenerating from source means the reference cannot disagree
with the build.

Usage:  python3 build.py            (writes reference + redline PNGs)
"""
import base64, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
BANNER = ROOT / 'iosapp/GolfCoachNow/Assets.xcassets/banner.imageset/banner@3x.png'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# iPhone 15 / 14 Pro logical width. The layout is width-driven, so this is the
# canvas everything else is measured against.
W_PT = 393
SCALE = 3                       # @3x — 1179 px wide, the density Xcode ships

# ── values lifted from Theme.swift ────────────────────────────────────────
T = dict(
    background='#000000',
    card='#121212',              # 0.07 × 255 ≈ 18
    green='#99B32E',             # 0.60, 0.70, 0.18
    green_dark='#80941F',
    green_border='rgba(128,148,31,0.5)',
    green_dim='rgba(153,179,46,0.12)',
    text='#FFFFFF',
    muted='#999999',             # white 0.6
    text_dark='#121212',
    screen_padding=16,
    card_gap=8,
    card_radius=14,
    icon_box=48,
    icon_box_radius=12,
    cta_radius=8,
    banner_height=180,
    greeting_overlap=-24,
)

MODULES = [
    ('SWING',      'Analyze your swing. Get instant feedback.',        'START SWING'),
    ('PUTT',       'Analyze your putting. Improve your stroke.',       'START PUTT'),
    ('SHORT GAME', 'Master your chipping, pitching &amp; bunker play.', 'START SHORT GAME'),
]
ACTIONS = [
    ('SEND',    'Share a video or swing for feedback.'),
    ('CONNECT', "We're here to listen and help."),
]

# Inline SVG icons — stroked, not filled, matching the outlined treatment.
ICON_SWING = ('<svg viewBox="0 0 28 28" fill="none" stroke="{g}" stroke-width="1.35" '
              'stroke-linecap="round" stroke-linejoin="round">'
              '<circle cx="13.2" cy="5" r="2.2"/>'
              '<path d="M13.2 7.6c-1.5 1-2 2.6-1.8 4.3l.5 3.4"/>'
              '<path d="M11.9 15.3 10.2 24"/>'
              '<path d="M12.4 15.6 16 18.4 17.4 24"/>'
              '<path d="M12.1 10.4c1.6-.5 3.2-.2 4.3.9"/>'
              '<path d="M16.4 11.3 23 5.4"/></svg>')
ICON_PUTT = ('<svg viewBox="0 0 28 28" fill="none" stroke="{g}" stroke-width="1.4" '
             'stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M9.4 4h.6v15"/>'
             '<path d="M10 4.4l7.6 2.7L10 10.2z"/>'
             '<ellipse cx="10" cy="21.4" rx="6.4" ry="2.3"/></svg>')
ICON_SHORT = ('<svg viewBox="0 0 28 28" fill="none" stroke="{g}" stroke-width="1.4" '
              'stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M5.4 4.6 16 15.2"/>'
              '<path d="M16 15.2c1.6 1.6 3.4 2.2 4.6 1.1 1.2-1.2.5-3-1.1-4.6"/>'
              '<circle cx="21.6" cy="21.4" r="2"/></svg>')
ICON_SEND = ('<svg viewBox="0 0 28 28" fill="none" stroke="{g}" stroke-width="1.4" '
             'stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M4 12.6c0-4 4.1-6.8 9.2-6.8s9.2 2.8 9.2 6.8-4.1 6.8-9.2 6.8'
             'c-1.1 0-2.2-.1-3.2-.4L5.4 22l.9-3.7C4.9 17 4 14.9 4 12.6Z"/>'
             '<circle cx="9.6" cy="12.6" r=".9" fill="{g}" stroke="none"/>'
             '<circle cx="13.2" cy="12.6" r=".9" fill="{g}" stroke="none"/>'
             '<circle cx="16.8" cy="12.6" r=".9" fill="{g}" stroke="none"/></svg>')
ICON_CONNECT = ('<svg viewBox="0 0 28 28" fill="none" stroke="{g}" stroke-width="1.4" '
                'stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M5.6 16.4v-3a8.4 8.4 0 0 1 16.8 0v3"/>'
                '<rect x="3.4" y="14.6" width="4.4" height="6.4" rx="1.6"/>'
                '<rect x="20.2" y="14.6" width="4.4" height="6.4" rx="1.6"/>'
                '<path d="M22.4 21v.8a3 3 0 0 1-3 3H15"/></svg>')
MOD_ICONS = [ICON_SWING, ICON_PUTT, ICON_SHORT]


def build_html(redline: bool) -> str:
    banner = base64.b64encode(BANNER.read_bytes()).decode()
    g = T['green']

    cards = ''
    for i, (title, desc, cta) in enumerate(MODULES):
        # Two-sentence copy breaks at the sentence, which is where the design
        # breaks it. Leaving it to the wrap put "Get instant / feedback." on
        # three lines and knocked the card out of step with its neighbours.
        # Single-sentence copy (Short Game) wraps naturally.
        if desc.count('.') > 1:
            head, tail = desc.split('. ', 1)
            desc = f'{head}.<br>{tail}'
        # The pill is 97px wide and its label must not wrap. "START SHORT
        # GAME" measures 89.5px at 8px against an 81px budget, so the long
        # label drops a size rather than overflowing the pill. Measured, not
        # guessed — see the note in the spec.
        cta_fit = ' sm' if len(cta) > 12 else ''
        cards += f'''
        <div class="mcard">
          <div class="iconbox">{MOD_ICONS[i].format(g=g)}</div>
          <div class="mtitle">{title}</div>
          <div class="mdesc">{desc}</div>
          <div class="ctawrap"><div class="cta{cta_fit}"><span>{cta}</span><span class="arw">&rarr;</span></div></div>
        </div>'''

    actions = ''
    for i, (title, desc) in enumerate(ACTIONS):
        icon = (ICON_SEND if i == 0 else ICON_CONNECT).format(g=g)
        actions += f'''
        <div class="acard">
          <div class="aicon">{icon}</div>
          <div class="atext"><div class="atitle">{title}</div><div class="adesc">{desc}</div></div>
          <div class="aarw">&rarr;</div>
        </div>'''

    rl = ''
    if redline:
        # Measurement overlay. Drawn as absolutely-positioned rules so the
        # numbers sit against the thing they describe rather than in a legend.
        rl = '''
        <style>
          .rl{position:absolute;pointer-events:none;font:600 7px ui-monospace,Menlo,monospace;
              color:#FF3B6B;letter-spacing:.02em}
          .rl b{background:#FF3B6B;color:#fff;padding:1px 3px;border-radius:2px;font-weight:700}
          .vline{position:absolute;border-left:1px dashed rgba(255,59,107,.85)}
          .hline{position:absolute;border-top:1px dashed rgba(255,59,107,.85)}
          .box{position:absolute;border:1px solid rgba(255,59,107,.85);border-radius:2px}
        </style>'''

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{background:{T['background']}}}
  body{{width:{W_PT}px;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif;
        -webkit-font-smoothing:antialiased;position:relative}}

  .banner{{height:{T['banner_height']}px;width:100%;object-fit:cover;display:block}}

  .greet{{position:relative;margin:{T['greeting_overlap']}px {T['screen_padding']}px 0;
          background:{T['card']};border:1px solid {T['green_border']};
          border-radius:{T['card_radius']}px;padding:14px}}
  .accent{{position:absolute;left:14px;top:14px;bottom:14px;width:3px;background:{g};border-radius:2px}}
  .greet .inner{{margin-left:15px}}
  .hello{{font-size:24px;font-weight:700;color:{T['text']};line-height:1.18}}
  .hello .name{{color:{g}}}
  .q{{font-size:14px;font-weight:400;color:{T['muted']};margin-top:4px;line-height:1.32}}

  .row{{display:flex;gap:{T['card_gap']}px;margin:12px {T['screen_padding']}px 0;align-items:stretch}}
  .row.actions{{margin-top:{T['card_gap']}px}}

  .mcard{{flex:1 1 0;min-width:0;background:{T['card']};border:1px solid {T['green_border']};
          border-radius:{T['card_radius']}px;padding:14px 6px 12px;text-align:center;
          display:flex;flex-direction:column;align-items:center}}
  .iconbox{{width:{T['icon_box']}px;height:{T['icon_box']}px;border:1px solid {T['green_border']};
            border-radius:{T['icon_box_radius']}px;display:flex;align-items:center;justify-content:center}}
  .iconbox svg{{width:28px;height:28px}}
  .mtitle{{margin-top:10px;font-size:12px;font-weight:800;color:{T['text']};letter-spacing:.02em}}
  .mdesc{{margin-top:4px;font-size:9px;font-weight:400;color:{T['muted']};line-height:1.34;
          padding:0;align-self:stretch}}
  /* min-width:0 on the card, and stretch here rather than the column's
     default fit-content. Flex items default to min-width:auto, so the
     nowrap "START SHORT GAME" CTA set a min-content floor on the third
     card and stole width from the other two — squeezing them to 93.8px,
     just under the 94.6px "Get instant feedback." needs, which is why it
     fell onto a third line and knocked that card out of step. */
  .ctawrap{{margin-top:auto;padding-top:10px;align-self:stretch;padding-left:2px;padding-right:2px}}
  .cta{{height:30px;background:{g};border-radius:{T['cta_radius']}px;display:flex;
        align-items:center;justify-content:center;gap:5px;color:{T['text_dark']};
        font-size:8px;font-weight:800;letter-spacing:.01em;white-space:nowrap}}
  .cta.sm{{font-size:7px}}
  .cta .arw{{font-size:11px;font-weight:600}}
  .cta.sm .arw{{font-size:10px}}

  .acard{{flex:1;height:72px;background:{T['card']};border:1px solid {T['green_border']};
          border-radius:{T['card_radius']}px;display:flex;align-items:center;padding:0 12px 0 11px}}
  .aicon{{width:28px;height:28px;flex:0 0 28px}}
  .aicon svg{{width:28px;height:28px}}
  .atext{{margin-left:9px;flex:1;min-width:0}}
  .atitle{{font-size:14px;font-weight:700;color:{T['text']}}}
    /* 9.5px, not 10. The arrow glyph is wider than it looks, leaving a ~92.5px
     text column; "swing for feedback." measures 94.8px at 10px and fell to a
     third line. At 9.5px it is 90.7px and sits where the design puts it. */
  .adesc{{margin-top:2px;font-size:9.5px;font-weight:400;color:{T['muted']};line-height:1.3}}
  .aarw{{font-size:16px;font-weight:500;color:{g};margin-left:6px;flex:0 0 auto}}

  .tail{{height:32px}}
  {rl}
</style></head><body>
  <img class="banner" src="data:image/png;base64,{banner}">
  <div class="greet"><div class="accent"></div><div class="inner">
    <div class="hello">Good morning,<br><span class="name">John</span></div>
    <div class="q">What would you like<br>to learn today?</div>
  </div></div>
  <div class="row">{cards}</div>
  <div class="row actions">{actions}</div>
  <div class="tail"></div>
</body></html>'''


def render(html: str, out: pathlib.Path):
    tmp = HERE / '_tmp.html'
    tmp.write_text(html)
    subprocess.run([
        CHROME, '--headless', '--disable-gpu', '--hide-scrollbars',
        f'--force-device-scale-factor={SCALE}',
        f'--window-size={W_PT},900',
        '--screenshot=' + str(out),
        '--default-background-color=00000000',
        str(tmp),
    ], check=True, capture_output=True)
    tmp.unlink()
    from PIL import Image
    im = Image.open(out)
    # Trim the empty page below the content — Chrome pads to the window height.
    bbox_h = im.size[1]
    print(f'  {out.name}  {im.size[0]}x{bbox_h}')
    return im


def trim(path: pathlib.Path):
    """Chrome pads the shot to the window height; cut back to the content."""
    from PIL import Image
    im = Image.open(path).convert('RGB')
    w, h = im.size
    px = im.load()
    last = next(y for y in range(h - 1, -1, -1)
                if any(sum(px[x, y]) > 24 for x in range(0, w, 7)))
    im.crop((0, 0, w, last + 30)).save(path)
    return Image.open(path)


def main():
    if not BANNER.exists():
        sys.exit(f'banner not found: {BANNER}')
    global SCALE
    html = build_html(redline=False)
    for scale in (3, 2):
        SCALE = scale
        out = HERE / f'home-reference@{scale}x.png'
        render(html, out)
        im = trim(out)
        print(f'  {out.name}  {im.size[0]}x{im.size[1]}')
        if scale == 3:
            im.resize((im.size[0] // 3, im.size[1] // 3), __import__('PIL.Image', fromlist=['Image']).LANCZOS)\
              .save(HERE / 'preview@1x.png')
    print('done')


if __name__ == '__main__':
    main()
