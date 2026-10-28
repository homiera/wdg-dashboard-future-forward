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
        return "Lost", "critical"
    if prop in CONTRACTING:
        return "In Contract", "good"
    if prop in PRE_RFP:
        return "Pre-RFP", "muted"
    return "In Flight", "warning"

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
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg-1:#11282F; --bg-2:#162E37;
  --olive:#BDCF03; --neon:#E7FE55;
  --ink:#F3F6F2; --ink-muted:#9FB3AE;
  --card:#17333C; --card-border:#24454F; --card-hover:#1C3C46;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b; --muted:#6b8c87;
}
*{box-sizing:border-box;}
body{
  margin:0; padding:32px 40px 60px; background:var(--bg-1);
  font-family:'Poppins',sans-serif; color:var(--ink);
}
h1{ font-family:'Playfair Display',serif; font-weight:800; font-size:30px; margin:0 0 4px 0; }
.sub{ color:var(--ink-muted); font-size:14px; margin:0; }
.topline{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:30px; flex-wrap:wrap; gap:16px; }
.asof{ text-align:right; }
.asof-label{ font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-muted); margin-bottom:2px; }
.asof-date{ font-family:'Playfair Display',serif; font-weight:700; font-size:16px; color:var(--neon); }
.tiles{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:40px; }
.tile{
  background:var(--card); border:1px solid var(--card-border); border-radius:10px;
  padding:18px 20px; position:relative; overflow:hidden;
}
.tile-wide{ grid-column:span 3; }
.volbar{ display:flex; width:100%; height:14px; border-radius:7px; overflow:hidden; background:var(--bg-2); margin-top:6px; }
.volseg{ height:100%; }
.volseg.good{ background:var(--good); } .volseg.warning{ background:var(--warning); } .volseg.muted{ background:var(--muted); }
.volseg.olive{ background:var(--olive); }
@media (max-width:900px){ .tiles{ grid-template-columns:repeat(2,1fr); } .tile-wide{ grid-column:span 2; } }
@media (max-width:560px){ .tiles{ grid-template-columns:1fr; } .tile-wide{ grid-column:span 1; } }
.tile::before{ content:""; position:absolute; top:0; left:0; right:0; height:3px; background:var(--olive); }
.tile.accent::before{ background:var(--neon); }
.tlabel{ font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-muted); font-weight:500; margin-bottom:8px; }
.tnum{ font-family:'Playfair Display',serif; font-weight:800; font-size:36px; line-height:1; color:var(--neon); }
.tile.olive .tnum{ color:var(--olive); }
.tbreak{ margin-top:8px; font-size:12px; color:var(--ink-muted); }
.dot{ display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:5px; }
.dot.good{ background:var(--good); } .dot.critical{ background:var(--critical); }
.dot.warning{ background:var(--warning); } .dot.muted{ background:var(--muted); }
.wl{ display:flex; gap:14px; margin-top:6px; font-size:12px; }

h2.section{ font-family:'Playfair Display',serif; font-size:20px; font-weight:700; margin:0 0 16px 0; color:var(--ink); }
.grid{ display:grid; grid-template-columns:repeat(auto-fill, minmax(260px,1fr)); gap:16px; }

.pcard{
  background:var(--card); border:1px solid var(--card-border); border-radius:10px;
  padding:16px 18px; cursor:pointer; position:relative;
  transition:background .15s ease, border-color .15s ease;
}
.pcard:hover, .pcard:focus{ background:var(--card-hover); border-color:var(--olive); }
.pcard:focus{ outline:2px solid var(--neon); outline-offset:2px; }
.pname{ font-weight:600; font-size:15px; margin-bottom:6px; padding-right:70px; }
.badge{
  position:absolute; top:16px; right:16px; font-size:10px; letter-spacing:.04em; text-transform:uppercase;
  padding:3px 8px; border-radius:20px; font-weight:600;
}
.badge.good{ background:rgba(12,163,12,.18); color:#7fe07f; }
.badge.warning{ background:rgba(250,178,25,.18); color:#ffcf6b; }
.badge.critical{ background:rgba(208,59,59,.18); color:#ff9b9b; }
.badge.muted{ background:rgba(107,140,135,.2); color:var(--ink-muted); }
.pdue{ font-size:13px; color:var(--ink-muted); margin-bottom:4px; }
.pdue b{ color:var(--ink); font-weight:500; }
.powners{ font-size:12px; color:var(--ink-muted); }
.hint{ font-size:10px; color:var(--muted); margin-top:10px; letter-spacing:.03em; text-transform:uppercase; }

.pdetail{ display:none; }
.pdetail .row{ margin-bottom:6px; }
.pdetail .k{ color:var(--ink); font-weight:600; }
.placeholder{ color:var(--muted); font-style:italic; }

/* ---- modal ---- */
.modal-backdrop{
  position:fixed; inset:0; background:rgba(8,16,18,.72); backdrop-filter:blur(2px);
  display:none; align-items:center; justify-content:center; z-index:100; padding:24px;
}
.modal-backdrop.show{ display:flex; }
.modal-box{
  background:var(--card-hover); border:1px solid var(--olive); border-radius:14px;
  max-width:480px; width:100%; padding:28px 28px 24px; position:relative;
  box-shadow:0 24px 60px rgba(0,0,0,.55);
  animation:modalIn .15s ease;
}
@keyframes modalIn{ from{ opacity:0; transform:translateY(8px) scale(.98);} to{ opacity:1; transform:none; } }
.modal-close{
  position:absolute; top:14px; right:16px; background:none; border:none; color:var(--ink-muted);
  font-size:20px; line-height:1; cursor:pointer; padding:4px;
}
.modal-close:hover{ color:var(--neon); }
.modal-badge{
  display:inline-block; font-size:10px; letter-spacing:.04em; text-transform:uppercase;
  padding:3px 8px; border-radius:20px; font-weight:600; margin-bottom:10px;
}
.modal-badge.good{ background:rgba(12,163,12,.18); color:#7fe07f; }
.modal-badge.warning{ background:rgba(250,178,25,.18); color:#ffcf6b; }
.modal-badge.critical{ background:rgba(208,59,59,.18); color:#ff9b9b; }
.modal-badge.muted{ background:rgba(107,140,135,.2); color:var(--ink-muted); }
.modal-title{ font-family:'Playfair Display',serif; font-weight:700; font-size:22px; margin:0 0 16px 0; }
.modal-box .row{ margin-bottom:10px; font-size:13.5px; color:var(--ink-muted); line-height:1.5; }
.modal-box .k{ color:var(--ink); font-weight:600; }

footer{ margin-top:48px; font-size:11px; color:var(--muted); }
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
  <div class="tile olive">
    <div class="tlabel">Contracts In Progress</div>
    <div class="tnum">{len(contracts_in_progress)}</div>
    <div class="tbreak">{esc(', '.join(contracts_in_progress)) if contracts_in_progress else 'none currently'}</div>
  </div>
  <div class="tile">
    <div class="tlabel">Proposals Due This Week</div>
    <div class="tnum">{len(due_this_week)}</div>
    <div class="tbreak"><span class="dot warning"></span>{esc(', '.join(due_this_week)) if due_this_week else 'nothing pending'}</div>
  </div>
  <div class="tile">
    <div class="tlabel">Presentations This Week</div>
    <div class="tnum">{len(presentations_this_week)}</div>
    <div class="tbreak"><span class="dot muted"></span>{esc(presentations_label)}</div>
  </div>
  <div class="tile accent">
    <div class="tlabel">Win Rate (decided)</div>
    <div class="tnum">{win_rate}%</div>
    <div class="wl">
      <span><span class="dot good"></span>{len(won_list)} won</span>
      <span><span class="dot critical"></span>{len(lost_list)} lost</span>
    </div>
  </div>
  <div class="tile tile-wide">
    <div class="tlabel">Pipeline Volume &mdash; Total Projected</div>
    <div class="tnum" style="font-size:28px;">
      {fmt_money(known_low) if known_low == known_high else f"{fmt_money(known_low)}&ndash;{fmt_money(known_high)}"}
      <span style="font-size:13px; color:var(--ink-muted); font-family:'Poppins',sans-serif; font-weight:500;"> known</span>
    </div>
    <div class="volbar">
      <div class="volseg olive" style="width:{seg_pct(len(quantified))}%" title="{len(quantified)} quantified"></div>
      <div class="volseg muted" style="width:{seg_pct(len(unquantified))}%" title="{len(unquantified)} unquantified"></div>
    </div>
    <div class="wl" style="margin-top:10px;">
      <span><span class="dot good"></span>{len(quantified)} of {pipeline_total} pursuits have a real budget figure</span>
    </div>
    <div class="tbreak" style="margin-top:6px;">
      Not yet quantified, no real number in state.json: {esc(', '.join(unquantified)) if unquantified else 'none'}.
      This total excludes them rather than guessing &mdash; give me budget figures for those and the total updates.
    </div>
  </div>
</div>
"""

def card_html(c, i):
    tier = f'<span class="placeholder">TBD</span>' if c["tier"] == "TBD" else esc(c["tier"])
    deck = f'<a href="{esc(c["deck_link"])}" style="color:var(--neon)">Open deck</a>' if c["deck_link"] else '<span class="placeholder">not linked yet</span>'
    slack = f'<a href="{esc(c["slack_link"])}" style="color:var(--neon)">Open channel</a>' if c["slack_link"] else '<span class="placeholder">not linked yet</span>'
    rfp_folder = (f'<a href="{esc(c["rfp_folder_link"])}" style="color:var(--neon)">Open folder</a>'
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
  <div class="topline">
    <div>
      <h1>WDG's New Business Pipeline Overview</h1>
      <p class="sub">{quarter_label(AS_OF)} &middot; internal view &middot; lost pursuits removed from the list below</p>
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
  <footer>Tier, deck link, and Slack link are placeholders until that data is provided per pursuit.</footer>
  {MODAL_HTML}
</body>
</html>
"""

import os
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "internal"), exist_ok=True)
open(os.path.join(OUT_DIR, "internal", "index.html"), "w").write(INTERNAL_HTML)
print("built internal dashboard:", len(cards), "cards,", len(in_flight), "in flight,", win_rate, "% win rate")
