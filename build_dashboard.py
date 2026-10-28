import json, sys, datetime, html

STATE_PATH = sys.argv[1] if len(sys.argv) > 1 else "state.json"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "site"

s = json.load(open(STATE_PATH))
AS_OF = datetime.date.fromisoformat(s["as_of"])

def esc(x):
    return html.escape(str(x)) if x is not None else ""

def fmt_date(d):
    if not d:
        return None
    dt = datetime.date.fromisoformat(d)
    return dt.strftime("%a, %b ") + str(dt.day)

# ---------------------------------------------------------------------------
# Classification (manual, since this isn't in the schema): lost pursuits are
# dropped from the visible card list per Homiera's instruction. Won/closing
# pursuits stay visible with a Won badge. Everything else is "in flight."
# ---------------------------------------------------------------------------
LOST = {"PHI", "AGA", "Community of Christ"}
WON = {"Columbia Association", "Heritage Action"}       # used for win-rate (decided bids)
PRE_RFP = {"Aspen Digital", "GSA.gov"}
CONTRACTING = {"Columbia Association", "Heritage Action"}   # status shown as "In Contract"
# Manual call, not derived from a status field: these are the pursuits whose
# own stage text says the proposal is submitted and WDG is waiting on the
# CLIENT's decision, as opposed to still drafting/shaping/presenting.
# Flag to Homiera: currently AKF ("pending AKF's next steps") and Open
# Technology Fund ("pending OTF's next steps"). UAE Embassy's "pending ...
# decision" is WDG's own internal/legal call, not the client's, so it's
# left out of this set on purpose.
AWAITING_DECISION = {"AKF", "Open Technology Fund"}

# Per-pursuit badge text for the "In Flight" bucket, per Homiera 10/28.
# Falls back to "In Flight" for anything not listed here.
STATUS_OVERRIDE = {
    "UAE Embassy": "In Progress",
    "AKF": "Submitted",
    "Open Technology Fund": "Submitted",
    "ARC": "Submitted",
    "Tinuiti": "Submitted",
    "Heritage.org": "Submitted",
    "NTSB": "Submitted",
}

rows_by_prop = {}
for r in s["rows"]:
    rows_by_prop.setdefault(r["proposal"], []).append(r)

def next_due(prop):
    """Earliest non-complete row on/after as_of; falls back to summary key_date."""
    cands = [r for r in rows_by_prop.get(prop, [])
             if r["status"] not in ("Complete", "Cancelled") and r["date"] and r["date"] >= s["as_of"]]
    if cands:
        cands.sort(key=lambda r: r["date"])
        return cands[0]["date"], cands[0]["milestone"]
    su = next((x for x in s["summary"] if x["proposal"] == prop), None)
    if su and su.get("key_date"):
        return su["key_date"], su.get("key_detail", "")
    return None, None

def status_label(prop):
    if prop in LOST:
        return "Lost", "lost"
    if prop in CONTRACTING:
        return "In Contract", "progress"
    if prop in PRE_RFP:
        return "Pre-RFP", "data"
    if prop in STATUS_OVERRIDE:
        return STATUS_OVERRIDE[prop], "neutral"
    return "In Flight", "neutral"

# ---------------------------------------------------------------------------
# Stat tiles
# ---------------------------------------------------------------------------
all_props = [x["proposal"] for x in s["summary"]]
# "In Flight" is deliberately broad: everything still being worked, in
# progress, or pending a decision - i.e. everything that isn't lost and
# isn't already in contract. Pre-RFP and awaiting-decision pursuits are
# both part of this count.
in_flight = [p for p in all_props if p not in LOST and p not in CONTRACTING]
awaiting_decision = [p for p in all_props if p in AWAITING_DECISION]
won_list = [p for p in all_props if p in WON]
lost_list = [p for p in all_props if p in LOST]
decided = len(won_list) + len(lost_list)
win_rate = round(100 * len(won_list) / decided) if decided else 0

def next_proposal_due(prop):
    """Earliest upcoming row that's actually a submission deadline (milestone
    text says 'due' or 'deadline'), not any upcoming milestone - a
    presentation or review step doesn't count as a proposal due date."""
    cands = [r for r in rows_by_prop.get(prop, [])
             if r["status"] not in ("Complete", "Cancelled") and r["date"] and r["date"] >= s["as_of"]
             and ("due" in r["milestone"].lower() or "deadline" in r["milestone"].lower())]
    if cands:
        cands.sort(key=lambda r: r["date"])
        return cands[0]["date"], cands[0]["milestone"]
    return None, None

due_this_week = []
for p in all_props:
    if p in LOST:
        continue
    d, what = next_proposal_due(p)
    if d:
        delta = (datetime.date.fromisoformat(d) - AS_OF).days
        if 0 <= delta <= 7:
            due_this_week.append(p)

# Presentations scheduled this week: rows whose milestone mentions a
# presentation, not cancelled/complete, dated within the next 7 days.
presentations_this_week = []
for r in s["rows"]:
    if r["status"] in ("Cancelled", "Complete"):
        continue
    if "present" not in r["milestone"].lower():
        continue
    if r["proposal"] in LOST or not r["date"]:
        continue
    delta = (datetime.date.fromisoformat(r["date"]) - AS_OF).days
    if 0 <= delta <= 7:
        presentations_this_week.append((r["proposal"], r["date"]))
presentations_this_week.sort(key=lambda x: x[1])

contracts_in_progress = [p for p in all_props if p in CONTRACTING]

# ---------------------------------------------------------------------------
# Budget / dollar-value parsing. Most pursuits have "TBD" or "Not stated" in
# the budget field, not a real number. Parse what's actually a parseable
# dollar figure or range; everything else is counted as unquantified rather
# than guessed at.
# ---------------------------------------------------------------------------
import re

def parse_budget(text):
    if not text:
        return None
    nums = [float(n.replace(",", "")) for n in re.findall(r"\$([\d,]+(?:\.\d+)?)", text)]
    if not nums:
        return None
    # Take the first one or two dollar figures as a low/high range (skip a
    # trailing recurring/monthly figure like "$6,500 a month" by only using
    # the first 1-2 numbers mentioned).
    low = nums[0]
    high = nums[1] if len(nums) > 1 and nums[1] >= nums[0] else nums[0]
    return (low, high)

active_props_all = [p for p in s["prop_order"] if p not in LOST]
quantified = []
unquantified = []
for p in active_props_all:
    su = next(x for x in s["summary"] if x["proposal"] == p)
    rng = parse_budget(su.get("budget"))
    if rng:
        quantified.append((p, rng))
    else:
        unquantified.append(p)

known_low = sum(r[0] for _, r in quantified)
known_high = sum(r[1] for _, r in quantified)

def fmt_money(n):
    return f"${n:,.0f}"

# ---------------------------------------------------------------------------
# Card data (visible list excludes LOST)
# ---------------------------------------------------------------------------
visible = [p for p in s["prop_order"] if p not in LOST]

def card_data(prop):
    su = next(x for x in s["summary"] if x["proposal"] == prop)
    d, what = next_due(prop)
    label, tone = status_label(prop)
    return {
        "prop": prop,                       # Prospect Name
        "label": label,                     # Status
        "tone": tone,
        "due": fmt_date(d) if d else "No date set",   # Due Date for Proposal
        "due_what": what or "",
        "owners": su.get("owners") or "TBD",          # Assigned People
        "stage": su.get("stage", ""),                 # Stage details
        "notes": su.get("notes", ""),                 # Description / latest notes
        "tier": "TBD",
        "deck_link": None,
        "slack_link": None,
        "rfp_folder_link": None,            # Link to RFP docs folder (Google Drive)
    }

cards = [card_data(p) for p in visible]

# ---------------------------------------------------------------------------
# HTML / CSS
# ---------------------------------------------------------------------------
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WDG Proposals — __PAGE_TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300..700&family=Geist+Mono:wght@400..600&display=swap" rel="stylesheet">
<style>
:root{
  /* WDG Brand System v4 tokens */
  --wdg-yellow:#FFD400; --wdg-red:#E8573F; --wdg-mint:#A8EEB4; --wdg-iris:#C9BDF2;
  --wdg-paper:#F3F2EE; --wdg-stone:#E3E1DA; --wdg-slate:#575B5F; --wdg-charcoal:#171717;
  --ink:#141414; --ink-muted:#57554F; --rule:#D3D1CA; --surface:#E7E6E1;
  --font-sans:'Geist','Helvetica Neue',Arial,sans-serif;
  --font-mono:'Geist Mono','SF Mono',Menlo,monospace;
  /* status mapping onto the brand palette - color has a job, nothing
     recolored just for variety */
  --status-lost:#E8573F; --status-lost-ink:#141414;
  --status-progress:#A8EEB4; --status-progress-ink:#141414;
  --status-data:#C9BDF2; --status-data-ink:#141414;
  --status-neutral:#E3E1DA; --status-neutral-ink:#57554F;
}
*{box-sizing:border-box;}
body{
  margin:0; padding:0; background:var(--wdg-paper);
  font-family:var(--font-sans); color:var(--ink);
}
.page{ max-width:1440px; margin:0 auto; padding:32px 40px 60px; }
.brandbar{ display:flex; align-items:center; gap:10px; margin-bottom:28px; }
.brandbar img{ height:22px; width:auto; display:block; }
h1{ font-family:var(--font-sans); font-weight:500; font-size:30px; letter-spacing:-.02em; margin:0 0 4px 0; }
.sub{ color:var(--ink-muted); font-size:14px; margin:0; font-family:var(--font-sans); }
.topline{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:30px; flex-wrap:wrap; gap:16px; }
.asof{ text-align:left; }
.asof-label{ font-family:var(--font-mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-muted); margin-bottom:2px; }
.asof-date{ font-family:var(--font-sans); font-weight:500; font-size:16px; color:var(--ink); }
@media (max-width:640px){
  .topline{ flex-direction:column; align-items:flex-start; }
}
.tiles{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:40px; }
.tile{
  background:var(--surface); border-radius:0; border-left:3px solid var(--rule);
  padding:18px 20px; position:relative;
}
.tile.mint{ border-left-color:var(--wdg-mint); }
.tile.iris{ border-left-color:var(--wdg-iris); }
.tile.yellow{ border-left-color:var(--wdg-yellow); }
.tile-wide{ grid-column:span 3; }
.volbar{ display:flex; width:100%; height:10px; border-radius:0; overflow:hidden; background:var(--wdg-stone); margin-top:8px; }
.volseg{ height:100%; }
.volseg.known{ background:var(--wdg-mint); } .volseg.unknown{ background:var(--wdg-stone); border-right:1px solid var(--rule); }
@media (max-width:900px){ .tiles{ grid-template-columns:repeat(2,1fr); } .tile-wide{ grid-column:span 2; } }
@media (max-width:560px){ .tiles{ grid-template-columns:1fr; } .tile-wide{ grid-column:span 1; } }
.tlabel{ font-family:var(--font-mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-muted); font-weight:400; margin-bottom:10px; }
.tnum{ font-family:var(--font-sans); font-weight:500; font-size:34px; line-height:1; color:var(--ink); letter-spacing:-.02em; }
.tbreak{ margin-top:8px; font-size:12px; color:var(--ink-muted); font-family:var(--font-sans); }
.dot{ display:inline-block; width:6px; height:6px; margin-right:5px; }
.dot.lost{ background:var(--status-lost); } .dot.progress{ background:var(--status-progress); }
.dot.data{ background:var(--status-data); } .dot.neutral{ background:var(--ink-muted); }
.wl{ display:flex; gap:14px; margin-top:6px; font-size:12px; color:var(--ink-muted); font-family:var(--font-sans); }

h2.section{ font-family:var(--font-sans); font-size:18px; font-weight:500; margin:0 0 16px 0; color:var(--ink); letter-spacing:-.01em; }
.grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
@media (max-width:820px){ .grid{ grid-template-columns:repeat(2,1fr); } }
@media (max-width:520px){ .grid{ grid-template-columns:1fr; } }

.pcard{
  background:var(--surface); border-radius:0; border-top:3px solid var(--rule);
  padding:16px 18px; cursor:pointer; position:relative;
  transition:border-color .15s ease, background .15s ease;
}
.pcard:hover, .pcard:focus{ background:var(--wdg-stone); border-top-color:var(--ink); }
.pcard:focus{ outline:2px solid var(--ink); outline-offset:2px; }
.pname{ font-weight:500; font-size:15px; margin-bottom:6px; padding-right:90px; font-family:var(--font-sans); }
.badge{
  position:absolute; top:16px; right:16px; font-family:var(--font-mono); font-size:10px; letter-spacing:.05em; text-transform:uppercase;
  padding:3px 10px; border-radius:999px; font-weight:400;
}
.badge.lost{ background:var(--status-lost); color:var(--status-lost-ink); }
.badge.progress{ background:var(--status-progress); color:var(--status-progress-ink); }
.badge.data{ background:var(--status-data); color:var(--status-data-ink); }
.badge.neutral{ background:var(--status-neutral); color:var(--status-neutral-ink); }
.pdue{ font-size:13px; color:var(--ink-muted); margin-bottom:4px; font-family:var(--font-sans); }
.pdue b{ color:var(--ink); font-weight:500; }
.powners{ font-family:var(--font-mono); font-size:11px; letter-spacing:.02em; color:var(--ink-muted); }
.hint{ font-family:var(--font-mono); font-size:10px; color:var(--ink-muted); margin-top:10px; letter-spacing:.05em; text-transform:uppercase; }

.pdetail{ display:none; }
.pdetail .row{ margin-bottom:6px; }
.pdetail .k{ color:var(--ink); font-weight:500; }
.placeholder{ color:var(--ink-muted); font-style:italic; }

/* ---- modal ---- */
.modal-backdrop{
  position:fixed; inset:0; background:rgba(23,23,23,.55);
  display:none; align-items:center; justify-content:center; z-index:100; padding:24px;
}
.modal-backdrop.show{ display:flex; }
.modal-box{
  background:var(--wdg-paper); border-left:4px solid var(--ink); border-radius:0;
  max-width:480px; width:100%; padding:28px 28px 24px; position:relative;
  box-shadow:0 24px 60px rgba(0,0,0,.35);
  font-family:var(--font-sans);
}
.modal-close{
  position:absolute; top:14px; right:16px; background:none; border:none; color:var(--ink-muted);
  font-size:20px; line-height:1; cursor:pointer; padding:4px; font-family:var(--font-sans);
}
.modal-close:hover{ color:var(--ink); }
.modal-badge{
  display:inline-block; font-family:var(--font-mono); font-size:10px; letter-spacing:.05em; text-transform:uppercase;
  padding:3px 10px; border-radius:999px; font-weight:400; margin-bottom:10px;
}
.modal-badge.lost{ background:var(--status-lost); color:var(--status-lost-ink); }
.modal-badge.progress{ background:var(--status-progress); color:var(--status-progress-ink); }
.modal-badge.data{ background:var(--status-data); color:var(--status-data-ink); }
.modal-badge.neutral{ background:var(--status-neutral); color:var(--status-neutral-ink); }
.modal-title{ font-family:var(--font-sans); font-weight:500; font-size:22px; margin:0 0 16px 0; letter-spacing:-.01em; }
.modal-box .row{ margin-bottom:10px; font-size:13.5px; color:var(--ink-muted); line-height:1.5; font-family:var(--font-sans); }
.modal-box .k{ color:var(--ink); font-weight:500; }

footer{ margin-top:48px; font-size:11px; color:var(--ink-muted); font-family:var(--font-mono); letter-spacing:.02em; }
</style>
</head>
"""

pipeline_total = len([p for p in all_props if p not in LOST])
def seg_pct(n):
    return round(100 * n / pipeline_total) if pipeline_total else 0

presentations_label = (', '.join(f"{p} ({fmt_date(d)})" for p, d in presentations_this_week)
                        if presentations_this_week else "none scheduled")

TILES_HTML = f"""
<div class="tiles">
  <div class="tile">
    <div class="tlabel">In Flight</div>
    <div class="tnum">{len(in_flight)}</div>
    <div class="tbreak">active pursuits</div>
  </div>
  <div class="tile">
    <div class="tlabel">Awaiting Decision</div>
    <div class="tnum">{len(awaiting_decision)}</div>
    <div class="tbreak">{esc(', '.join(awaiting_decision)) if awaiting_decision else 'none currently'}</div>
  </div>
  <div class="tile mint">
    <div class="tlabel">Contracts In Progress</div>
    <div class="tnum">{len(contracts_in_progress)}</div>
    <div class="tbreak">{esc(', '.join(contracts_in_progress)) if contracts_in_progress else 'none currently'}</div>
  </div>
  <div class="tile">
    <div class="tlabel">Proposals Due This Week</div>
    <div class="tnum">{len(due_this_week)}</div>
    <div class="tbreak"><span class="dot neutral"></span>{esc(', '.join(due_this_week)) if due_this_week else 'nothing pending'}</div>
  </div>
  <div class="tile">
    <div class="tlabel">Presentations This Week</div>
    <div class="tnum">{len(presentations_this_week)}</div>
    <div class="tbreak"><span class="dot neutral"></span>{esc(presentations_label)}</div>
  </div>
  <div class="tile yellow">
    <div class="tlabel">Win Rate (decided)</div>
    <div class="tnum">{win_rate}%</div>
    <div class="wl">
      <span><span class="dot progress"></span>{len(won_list)} won</span>
      <span><span class="dot lost"></span>{len(lost_list)} lost</span>
    </div>
  </div>
  <div class="tile tile-wide iris">
    <div class="tlabel">Pipeline Volume &mdash; Total Projected</div>
    <div class="tnum" style="font-size:28px;">
      {fmt_money(known_low) if known_low == known_high else f"{fmt_money(known_low)}&ndash;{fmt_money(known_high)}"}
      <span style="font-size:13px; color:var(--ink-muted); font-family:var(--font-sans); font-weight:400;"> known</span>
    </div>
    <div class="volbar">
      <div class="volseg known" style="width:{seg_pct(len(quantified))}%" title="{len(quantified)} quantified"></div>
      <div class="volseg unknown" style="width:{seg_pct(len(unquantified))}%" title="Unquantified: {esc(', '.join(unquantified)) if unquantified else 'none'}"></div>
    </div>
    <div class="wl" style="margin-top:10px;">
      <span><span class="dot progress"></span>{len(quantified)} of {pipeline_total} pursuits have a real budget figure</span>
    </div>
  </div>
</div>
"""

def card_html(c, i):
    tier = f'<span class="placeholder">TBD</span>' if c["tier"] == "TBD" else esc(c["tier"])
    deck = f'<a href="{esc(c["deck_link"])}" style="color:var(--ink)">Open deck</a>' if c["deck_link"] else '<span class="placeholder">not linked yet</span>'
    slack = f'<a href="{esc(c["slack_link"])}" style="color:var(--ink)">Open channel</a>' if c["slack_link"] else '<span class="placeholder">not linked yet</span>'
    rfp_folder = (f'<a href="{esc(c["rfp_folder_link"])}" style="color:var(--ink)">Open folder</a>'
                  if c["rfp_folder_link"] else '<span class="placeholder">not linked yet</span>')
    return f"""
    <div class="pcard" tabindex="0" role="button" aria-haspopup="dialog"
         onclick="openModal({i})" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();openModal({i});}}">
      <div class="badge {c['tone']}">{esc(c['label'])}</div>
      <div class="pname">{esc(c['prop'])}</div>
      <div class="pdue">Next: <b>{esc(c['due'])}</b></div>
      <div class="powners">{esc(c['owners'])}</div>
      <div class="hint">click for details</div>
      <div class="pdetail" id="detail-{i}">
        <div class="row"><span class="k">Prospect:</span> {esc(c['prop'])}</div>
        <div class="row"><span class="k">Status:</span> {esc(c['label'])}</div>
        <div class="row"><span class="k">Stage details:</span> {esc(c['stage'])}</div>
        <div class="row"><span class="k">Due date for proposal:</span> {esc(c['due'])}{(' — ' + esc(c['due_what'])) if c['due_what'] else ''}</div>
        <div class="row"><span class="k">Assigned people:</span> {esc(c['owners'])}</div>
        <div class="row"><span class="k">Tier:</span> {tier}</div>
        <div class="row"><span class="k">Deck:</span> {deck}</div>
        <div class="row"><span class="k">Slack channel:</span> {slack}</div>
        <div class="row"><span class="k">RFP docs folder:</span> {rfp_folder}</div>
        <div class="row"><span class="k">Notes:</span> {esc(c['notes'])}</div>
      </div>
    </div>
    """

CARDS_HTML = "\n".join(card_html(c, i) for i, c in enumerate(cards))

MODAL_DATA = {
    i: {"name": c["prop"], "label": c["label"], "tone": c["tone"]}
    for i, c in enumerate(cards)
}

MODAL_HTML = """
<div class="modal-backdrop" id="modalBackdrop" onclick="if(event.target===this)closeModal()">
  <div class="modal-box" role="dialog" aria-modal="true" id="modalBox">
    <button class="modal-close" aria-label="Close" onclick="closeModal()">&times;</button>
    <div id="modalBadge" class="modal-badge"></div>
    <h3 class="modal-title" id="modalTitle"></h3>
    <div id="modalBody"></div>
  </div>
</div>
<script>
const MODAL_META = """ + json.dumps(MODAL_DATA) + """;
function openModal(i){
  const meta = MODAL_META[i];
  const detail = document.getElementById('detail-' + i);
  document.getElementById('modalTitle').textContent = meta.name;
  const b = document.getElementById('modalBadge');
  b.textContent = meta.label;
  b.className = 'modal-badge ' + meta.tone;
  document.getElementById('modalBody').innerHTML = detail.innerHTML;
  document.getElementById('modalBackdrop').classList.add('show');
}
function closeModal(){
  document.getElementById('modalBackdrop').classList.remove('show');
}
document.addEventListener('keydown', function(e){
  if(e.key === 'Escape') closeModal();
});
</script>
"""

def quarter_label(d):
    q = (d.month - 1) // 3 + 1
    return f"Q{q} {d.year}"

INTERNAL_HTML = HEAD.replace("__PAGE_TITLE__", "Internal") + f"""
<body>
<div class="page">
  <div class="brandbar"><img src="assets/wdg-logo-black.svg" alt="WDG, an Agital Company"></div>
  <div class="topline">
    <div>
      <h1>WDG's New Business Pipeline Overview</h1>
      <p class="sub">{quarter_label(AS_OF)} &middot; internal view</p>
    </div>
    <div class="asof">
      <div class="asof-label">As of</div>
      <div class="asof-date">{AS_OF.strftime('%A, %B %-d, %Y')}</div>
    </div>
  </div>
  {TILES_HTML}
  <h2 class="section">Active Pursuits</h2>
  <div class="grid">
    {CARDS_HTML}
  </div>
</div>
  {MODAL_HTML}
</body>
</html>
"""

import os, shutil
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "internal", "assets"), exist_ok=True)
open(os.path.join(OUT_DIR, "internal", "index.html"), "w").write(INTERNAL_HTML)
LOGO_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "wdg-logo-black.svg")
if os.path.exists(LOGO_SRC):
    shutil.copy(LOGO_SRC, os.path.join(OUT_DIR, "internal", "assets", "wdg-logo-black.svg"))
print("built internal dashboard:", len(cards), "cards,", len(in_flight), "in flight,", win_rate, "% win rate")
