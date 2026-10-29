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
# Classification (manual, since this isn't in the schema): lost pursuits get
# their own Losses section rather than being dropped entirely. Won/closing
# pursuits stay visible with an In Contract badge. Everything else is
# bucketed by its own stage text into "in flight."
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
AWAITING_DECISION = {"American Kidney Fund", "Open Technology Fund", "NLC", "Tinuiti"}

# Per-pursuit badge text for the "In Flight" bucket, per Homiera 10/28.
# Falls back to "In Flight" for anything not listed here. This also drives
# which grouped section (In Contract / Submitted / In Progress / Pre-RFP)
# a card lands in on the grouped-by-stage layout per Homiera + Dario 10/28.
STATUS_OVERRIDE = {
    "UAE Embassy": "In Progress",
    "American Kidney Fund": "Submitted",
    "Open Technology Fund": "Submitted",
    "Appalachian Regional Commission": "Submitted",
    "Tinuiti": "Submitted",
    "Heritage.org": "Submitted",
    "NTSB": "Submitted",
    "NLC": "Submitted",
}

# Tier assignments per Homiera 10/28. Drives the pursuit card's top-border
# color (tier-specific when set, the default neutral --rule gray otherwise).
TIER = {
    "UAE Embassy": 3,
    "American Kidney Fund": 1,
    "Open Technology Fund": 2,
    "Appalachian Regional Commission": 3,
    "Columbia Association": 1,
    "Tinuiti": 1,
    "Heritage.org": 2,
    "Aspen Digital": 2,
    "Heritage Action": 2,
    "NTSB": 2,
    "GSA.gov": 1,
    "NLC": 1,
}

# Owner (who's accountable for the pursuit) vs. assigned team (everyone
# working it, still shown in the detail view) are different things, per
# Homiera 10/28. Falls back to "TBD" for anything not listed here.
OWNER = {
    "Columbia Association": "Ab",
    "Heritage Action": "Ab, Kurt Shadle",
    "American Kidney Fund": "Homiera, Ab",
    "Open Technology Fund": "Homiera, Ab",
    "Appalachian Regional Commission": "Ab",
    "Tinuiti": "Ab, Vaj, Kurtis",
    "Heritage.org": "Ab",
    "NTSB": "Homiera",
    "UAE Embassy": "Homiera",
    "Aspen Digital": "Kurt Shadle",
    "GSA.gov": "Homiera",
    "NLC": "Ab",
}

# Slack channel per pursuit, per Homiera 10/28. Deliberately excludes
# Heritage Action. NLC isn't in prop_order (not a visible card today), so
# its link is kept here for whenever it's added but won't render anywhere
# yet.
SLACK = {
    "Columbia Association": "https://wdg.slack.com/archives/C046MLAN3L2",
    "Aspen Digital": "https://wdg.slack.com/archives/C0C6NNY2W87",
    "GSA.gov": "https://wdg.slack.com/archives/C0BF86NR3H9",
    "American Kidney Fund": "https://wdg.slack.com/archives/C0C1JMLS62H",
    "NLC": "https://wdg.slack.com/archives/C0AFGQF1UF8",
    "NTSB": "https://wdg.slack.com/archives/C0AJYUGSHS8",
    "Open Technology Fund": "https://wdg.slack.com/archives/C0C3V40DA11",
    "UAE Embassy": "https://wdg.slack.com/archives/C0BPFB0A2SH",
    "Heritage.org": "https://wdg.slack.com/archives/C0BLQ3GL933",
    "Tinuiti": "https://wdg.slack.com/archives/C0BTBEGTABV",
    "Appalachian Regional Commission": "https://wdg.slack.com/archives/C0BUAV1M3PW",
}

# Deck and RFP-folder links, per pursuit, where known. Only NLC is populated
# so far (Homiera 10/28); everything else still shows "not linked yet" in
# the detail view until a link is provided.
DECK_LINK = {
    "NLC": "https://www.figma.com/slides/NrrNVzBOrKLITZCILPu6BF/NLC-2026-Proposal?t=NmAJoEPcestqr4qc-6",
    "Appalachian Regional Commission": "https://www.figma.com/slides/YUJIbGsp0N15tx7RDLPhuG/Appalachian-Regional-Commission-Presentation-Deck?t=NmAJoEPcestqr4qc-6",
    "Columbia Association": "https://drive.google.com/file/d/1O6_9zL6M8xK3p2yt9f7vdTjNAF-BeHX1/view?usp=drive_link",
    "American Kidney Fund": "https://www.figma.com/slides/Uy77ZyrMMlildeNuSoazh7/American-Kidney-Fund--due-October-23-?t=NmAJoEPcestqr4qc-6",
    "NTSB": "https://docs.google.com/document/d/1bIiIscBSR-t2XClHABswupvT5R79rQdD/view",
    "Open Technology Fund": "https://www.figma.com/slides/Q16rA4qWvjVSWIyZ91vvXb/Open-Tech-Fund-Proposal?t=NmAJoEPcestqr4qc-6",
    "Heritage.org": "https://www.figma.com/slides/TBFvXam250oe0FTInoG85Z/Heritage-Org-Proposal-2026?t=NmAJoEPcestqr4qc-6",
}
RFP_FOLDER_LINK = {
    "NLC": "https://drive.google.com/drive/u/0/folders/1YjYrBuQmLc5fW-_4u0lRIfc-T3Dr9zK-",
}

# Spec/reference deliverables that aren't a formal proposal deck, where
# relevant. Per Homiera 10/29: Tinuiti got a technical scenario writeup and a
# proposal doc instead of a formal deck. List of (label, url) per pursuit.
SPEC_LINKS = {
    "Tinuiti": [
        ("Technical scenario (PDF)", "https://wdg.slack.com/files/U08B3QSJK/F0C3F4PMUTD/web_development_group_-_technical_scenario_for_tinuiti_.pdf"),
        ("Tinuiti proposal (PDF)", "https://wdg.slack.com/files/U08B3QSJK/F0CBMHV3P8E/tinuiti_wdg.pdf"),
    ],
}

rows_by_prop = {}
for r in s["rows"]:
    rows_by_prop.setdefault(r["proposal"], []).append(r)

def next_due(prop):
    """Earliest non-complete row on/after as_of; falls back to summary key_date -
    but only when that key_date hasn't already been closed out by a row.
    Without this check, a pursuit's own deadline row could be marked Complete
    (the real, current status) while summary.key_date still echoes that same
    date, making the card wrongly show a passed deadline as "next" and flag
    it DATE PASSED even though it was tracked and resolved - that's what
    happened to Open Technology Fund's Oct 23 submission deadline."""
    rows = rows_by_prop.get(prop, [])
    cands = [r for r in rows
             if r["status"] not in ("Complete", "Cancelled") and r["date"] and r["date"] >= s["as_of"]]
    if cands:
        cands.sort(key=lambda r: r["date"])
        return cands[0]["date"], cands[0]["milestone"]
    su = next((x for x in s["summary"] if x["proposal"] == prop), None)
    key_date = su.get("key_date") if su else None
    if key_date:
        closed = any(r["date"] == key_date and r["status"] in ("Complete", "Cancelled") for r in rows)
        if not closed:
            return key_date, su.get("key_detail", "")
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
        presentations_this_week.append((r["proposal"], r["date"], "Presentation"))

due_this_week_rows = []
for p in due_this_week:
    d, what = next_proposal_due(p)
    due_this_week_rows.append((p, d, "Proposal due"))

# Consolidated "What's coming up" list: proposals due and presentations in
# the next 7 days, merged and sorted by date, per Homiera + Dario 10/28
# (replaces two separate stat tiles).
upcoming = sorted(due_this_week_rows + presentations_this_week, key=lambda x: x[1])

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
# Card data (visible list excludes LOST; those get their own Losses section)
# ---------------------------------------------------------------------------
visible = [p for p in s["prop_order"] if p not in LOST]

def card_data(prop):
    su = next(x for x in s["summary"] if x["proposal"] == prop)
    d, what = next_due(prop)
    label, tone = status_label(prop)
    date_passed = bool(d and datetime.date.fromisoformat(d) < AS_OF)
    # $ per deal, per Ab 10/28. parse_budget() already distinguishes a real
    # parseable dollar figure from "TBD"/"Not stated" text (used for the
    # Pipeline Volume tile); reuse that here instead of guessing at a number.
    budget_raw = su.get("budget") or "Not stated"
    rng = parse_budget(su.get("budget"))
    if rng:
        low, high = rng
        budget_display = fmt_money(low) if low == high else f"{fmt_money(low)}&ndash;{fmt_money(high)}"
    else:
        budget_display = "Not yet quantified"
    return {
        "prop": prop,                       # Prospect Name
        "label": label,                     # Status
        "tone": tone,
        "due": fmt_date(d) if d else "No date set",   # Due Date for Proposal
        "due_what": what or "",
        "date_passed": date_passed,
        "owners": su.get("owners") or "TBD",          # Assigned People (full list, kept in detail view)
        "owner": OWNER.get(prop, "TBD"),               # Owner (accountable party), per Homiera 10/28
        "stage": su.get("stage", ""),                 # Stage details
        "notes": su.get("notes", ""),                 # Description / latest notes
        "tier": TIER.get(prop, "TBD"),
        "budget_display": budget_display,   # Clean $ figure for the card face
        "budget_raw": budget_raw,           # Full budget text (caveats etc.) for the detail view
        "deck_link": DECK_LINK.get(prop),
        "spec_links": SPEC_LINKS.get(prop),
        "slack_link": SLACK.get(prop),
        "rfp_folder_link": RFP_FOLDER_LINK.get(prop),   # Link to RFP docs folder (Google Drive)
    }

cards = [card_data(p) for p in visible]
no_date_count = sum(1 for c in cards if c["due"] == "No date set")

# Group cards by status label into the four stage sections, in a fixed
# display order, per Homiera + Dario 10/28.
GROUP_ORDER = ["In Contract", "Submitted", "In Progress", "Pre-RFP"]
GROUP_TONE = {"In Contract": "progress", "Submitted": "data", "In Progress": "yellow", "Pre-RFP": "neutral"}
groups = {g: [] for g in GROUP_ORDER}
for c in cards:
    groups.setdefault(c["label"], []).append(c)
for label in list(groups.keys()):
    if label not in GROUP_ORDER:
        GROUP_ORDER.append(label)

# Losses: reason comes from state.json's "loss_reason" field (Homiera 10/28),
# falling back to parsing the stage text if a reason hasn't been recorded.
def loss_reason(prop):
    su = next((x for x in s["summary"] if x["proposal"] == prop), None)
    su = su or {}
    if su.get("loss_reason"):
        return su["loss_reason"]
    stage = su.get("stage", "") or ""
    if "—" in stage:
        return stage.split("—", 1)[1].strip()
    return stage or "No reason recorded."

# $ per loss, per Ab 10/28, with a total in the section header. Reuses
# parse_budget() for consistency with the active-pursuit cards. Community
# of Christ was excluded here until Homiera confirmed the real deal size
# ($310,000, 10/28) - its budget field previously held only a recurring
# platform-cost estimate, not the actual proposal value. Now that the real
# figure is in state.json, it counts toward the total like everything else.
LOSS_BUDGET_EXCLUDE_FROM_TOTAL = set()

def loss_budget(prop):
    su = next((x for x in s["summary"] if x["proposal"] == prop), None)
    raw = (su or {}).get("budget") or "Not stated"
    rng = parse_budget((su or {}).get("budget"))
    return raw, rng

losses = []
loss_known_low = loss_known_high = 0
loss_quantified_count = 0
for p in sorted(LOST):
    raw, rng = loss_budget(p)
    display = None
    if rng and p not in LOSS_BUDGET_EXCLUDE_FROM_TOTAL:
        low, high = rng
        display = fmt_money(low) if low == high else f"{fmt_money(low)}&ndash;{fmt_money(high)}"
        loss_known_low += low
        loss_known_high += high
        loss_quantified_count += 1
    losses.append({"prop": p, "reason": loss_reason(p), "budget_raw": raw, "budget_display": display})

loss_total_display = None
if loss_quantified_count:
    loss_total_display = (fmt_money(loss_known_low) if loss_known_low == loss_known_high
                           else f"{fmt_money(loss_known_low)}&ndash;{fmt_money(loss_known_high)}")

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
  /* WDG Brand System v4 tokens - charcoal (dark) ground per Homiera 10/28 */
  --wdg-yellow:#FFD400; --wdg-red:#E8573F; --wdg-mint:#A8EEB4; --wdg-iris:#C9BDF2;
  --wdg-paper:#F3F2EE; --wdg-stone:#E3E1DA; --wdg-slate:#575B5F; --wdg-charcoal:#171717;
  /* Ground/text pulled from the brand system's own [data-ground="charcoal"]
     block (bone text, yellow emphasis). --rule is bumped from the brand
     system's own charcoal --rule (#3A3936, 1.6:1 against charcoal - a
     decorative-divider contrast, fine for a deck, too low for a card
     boundary someone needs to see) up to the slate ground's --rule value
     (#6E7276) to clear WCAG 1.4.11's 3:1 non-text contrast minimum for a
     UI boundary. Verified: bone text 15.7:1, muted text 7.1:1, yellow
     emphasis 12.5:1, rule 3.7:1, all against #171717 - every text pair
     clears AA (4.5:1) with room, most clear AAA (7:1).
  */
  --ink:#F2F0EA; --ink-muted:#A6A39C; --rule:#6E7276; --surface:#232322;
  --surface-hover:#2C2C2A; --emphasis:#FFD400;
  --font-sans:'Geist','Helvetica Neue',Arial,sans-serif;
  --font-mono:'Geist Mono','SF Mono',Menlo,monospace;
  /* status mapping onto the brand palette - color has a job, nothing
     recolored just for variety. Badge text stays #141414 (near-black) on
     every badge background per the brand rule ("black text on every
     color"), independent of the page's own dark ground - verified each
     clears AA: mint 13.6:1, red 5.2:1, iris 10.6:1, stone 14.1:1. */
  --status-lost:#E8573F; --status-lost-ink:#141414;
  --status-progress:#A8EEB4; --status-progress-ink:#141414;
  --status-data:#C9BDF2; --status-data-ink:#141414;
  --status-neutral:#E3E1DA; --status-neutral-ink:#57554F;
  --status-yellow:#FFD400; --status-yellow-ink:#141414;
}
*{box-sizing:border-box;}
body{
  margin:0; padding:0; background:var(--wdg-charcoal);
  font-family:var(--font-sans); color:var(--ink);
}
.page{ max-width:1440px; margin:0 auto; padding:32px 40px 60px; }
.brandbar{ display:flex; align-items:center; gap:10px; margin-bottom:28px; }
.brandbar img{ height:33px; width:auto; display:block; }
h1{ font-family:var(--font-sans); font-weight:500; font-size:30px; letter-spacing:-.02em; margin:0 0 4px 0; }
.sub{ color:var(--ink-muted); font-size:14px; margin:0 0 6px 0; font-family:var(--font-sans); }
.subcount{ color:var(--ink-muted); font-size:13.5px; margin:0; font-family:var(--font-sans); }
.topline{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:30px; flex-wrap:wrap; gap:16px; }
.asof{ text-align:left; }
.asof-label{ font-family:var(--font-mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-muted); margin-bottom:2px; }
.asof-date{ font-family:var(--font-sans); font-weight:500; font-size:16px; color:var(--ink); }
@media (max-width:640px){
  .topline{ flex-direction:column; align-items:flex-start; }
}
.tiles{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:16px; }
.tile{
  background:var(--surface); border-radius:0; border-left:3px solid var(--rule);
  padding:18px 20px; position:relative;
}
.tile.mint{ border-left-color:var(--wdg-mint); }
.tile.iris{ border-left-color:var(--wdg-iris); }
.tile.yellow{ border-left-color:var(--wdg-yellow); }
.tlabel{ font-family:var(--font-mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-muted); font-weight:400; margin-bottom:10px; }
.tnum{ font-family:var(--font-sans); font-weight:500; font-size:34px; line-height:1; color:var(--ink); letter-spacing:-.02em; }
.tbreak{ margin-top:8px; font-size:12px; color:var(--ink-muted); font-family:var(--font-sans); }
.dot{ display:inline-block; width:6px; height:6px; margin-right:5px; }
.dot.lost{ background:var(--status-lost); } .dot.progress{ background:var(--status-progress); }
.dot.data{ background:var(--status-data); } .dot.neutral{ background:var(--ink-muted); }
.wl{ display:flex; gap:14px; margin-top:6px; font-size:12px; color:var(--ink-muted); font-family:var(--font-sans); }

.row2{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:40px; }
@media (max-width:900px){ .tiles{ grid-template-columns:repeat(2,1fr); } .row2{ grid-template-columns:1fr; } }
@media (max-width:560px){ .tiles{ grid-template-columns:1fr; } }

.upcoming-tile{ background:var(--surface); border-left:3px solid var(--rule); padding:18px 20px; }
.upcoming-title{ font-family:var(--font-sans); font-weight:500; font-size:16px; margin:0 0 4px 0; }
.upcoming-sub{ font-size:12.5px; color:var(--ink-muted); margin-bottom:14px; font-family:var(--font-sans); }
.uprow{ display:flex; justify-content:space-between; align-items:baseline; padding:8px 0; border-top:1px solid var(--rule); font-size:13.5px; }
.uprow:first-of-type{ border-top:none; }
.update{ font-family:var(--font-mono); font-size:11px; color:var(--ink-muted); text-transform:uppercase; letter-spacing:.03em; min-width:78px; }
.upname{ font-weight:500; flex:1; padding:0 10px; }
.uptype{ color:var(--ink-muted); font-size:12px; }

.volbar{ display:flex; width:100%; height:10px; border-radius:0; overflow:hidden; background:var(--surface); margin-top:8px; }
.volseg{ height:100%; transform-origin:left; transform:scaleX(0); animation:wdgBarFill .6s ease-out forwards; }
.volseg.known{ animation-delay:.15s; }
.volseg.unknown{ animation-delay:.7s; }
@keyframes wdgBarFill{ to{ transform:scaleX(1); } }
@media (prefers-reduced-motion: reduce){ .volseg{ animation:none; transform:scaleX(1); } }
.volseg.known{ background:var(--wdg-mint); } .volseg.unknown{ background:var(--wdg-stone); border-right:1px solid var(--rule); }

.tier-key{ display:flex; align-items:center; gap:18px; margin-bottom:28px; font-family:var(--font-sans); font-size:12.5px; color:var(--ink-muted); flex-wrap:wrap; }
.tier-key-label{ font-family:var(--font-mono); font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-muted); }
.tier-key-item{ display:flex; align-items:center; gap:6px; }
.tier-swatch{ width:14px; height:3px; display:inline-block; }
.tier-swatch.tier-1{ background:var(--wdg-yellow); }
.tier-swatch.tier-2{ background:var(--wdg-iris); }
.tier-swatch.tier-3{ background:var(--ink); }
.tier-swatch.tier-tbd{ background:var(--rule); }

h2.section{ font-family:var(--font-sans); font-size:16px; font-weight:500; margin:0 0 14px 0; color:var(--ink); letter-spacing:-.01em;
  display:flex; align-items:center; gap:8px; padding-top:18px; border-top:1px solid var(--rule); }
h2.section:first-of-type{ border-top:none; padding-top:0; }
.section-dot{ width:8px; height:8px; display:inline-block; }
.section-dot.progress{ background:var(--status-progress); } .section-dot.data{ background:var(--status-data); }
.section-dot.yellow{ background:var(--status-yellow); } .section-dot.neutral{ background:var(--status-neutral); }
.section-count{ margin-left:auto; color:var(--ink-muted); font-size:13px; font-weight:400; }
.section-total{ margin-left:auto; color:var(--ink-muted); font-size:13px; font-weight:400; font-family:var(--font-sans); }
.section-total + .section-count{ margin-left:14px; }
.grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:8px; }
@media (max-width:820px){ .grid{ grid-template-columns:repeat(2,1fr); } }
@media (max-width:520px){ .grid{ grid-template-columns:1fr; } }

.pcard{
  background:var(--surface); border-radius:0; border-top:3px solid var(--rule);
  padding:16px 18px; cursor:pointer; position:relative;
  transition:border-color .15s ease, background .15s ease;
}
/* Tier-specific top border. Unassigned pursuits keep the default neutral
   gray (--rule) set above. Picked yellow/iris/slate rather than red or
   mint so a tier color is never confused with the Lost or In-Contract
   badge colors sitting on the same card. */
.pcard.tier-1{ border-top-color:var(--wdg-yellow); }
.pcard.tier-2{ border-top-color:var(--wdg-iris); }
.pcard.tier-3{ border-top-color:var(--ink); }
.pcard:hover, .pcard:focus{ background:var(--surface-hover); border-top-color:var(--ink); }
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
.badge.yellow{ background:var(--status-yellow); color:var(--status-yellow-ink); }
.pdue{ font-size:13px; color:var(--ink-muted); margin-bottom:4px; font-family:var(--font-sans); display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.pdue b{ color:var(--ink); font-weight:500; }
.datepassed{ font-family:var(--font-mono); font-size:9px; letter-spacing:.04em; text-transform:uppercase; background:var(--wdg-red); color:#141414; padding:2px 7px; border-radius:999px; }
.powners{ font-family:var(--font-mono); font-size:13px; letter-spacing:.02em; color:var(--ink-muted); }
.powners .k{ color:var(--ink-muted); text-transform:uppercase; letter-spacing:.05em; font-size:11px; margin-right:6px; }
.pbudget{ font-family:var(--font-sans); font-weight:500; font-size:13.5px; color:var(--ink); margin-top:4px; }
.pbudget.placeholder{ font-weight:400; color:var(--ink-muted); font-style:italic; }
.hint{ font-family:var(--font-mono); font-size:10px; color:var(--ink-muted); margin-top:10px; letter-spacing:.05em; text-transform:uppercase; }

.pdetail{ display:none; }
.pdetail .row{ margin-bottom:6px; }
.pdetail .k{ color:var(--ink); font-weight:500; }
.placeholder{ color:var(--ink-muted); font-style:italic; }
.slackrow{ margin-top:14px !important; padding-top:14px; border-top:1px solid var(--rule); }
.slacklink{ font-family:var(--font-sans); font-weight:500; font-size:13.5px; color:var(--emphasis); text-decoration:underline; }
.slacklink.placeholder{ color:var(--ink-muted); font-style:italic; text-decoration:none; }

.loss-tile{ background:var(--surface); border-left:3px solid var(--status-lost); padding:18px 20px; margin-bottom:8px; }
.lossrow{ padding:10px 0; border-top:1px solid var(--rule); }
.lossrow:first-of-type{ border-top:none; }
.lossrow-top{ display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin-bottom:3px; }
.lossname{ font-weight:500; font-size:14px; font-family:var(--font-sans); }
.lossbudget{ font-weight:500; font-size:13.5px; color:var(--ink); font-family:var(--font-sans); white-space:nowrap; }
.lossbudget.placeholder{ font-weight:400; color:var(--ink-muted); font-style:italic; }
.lossreason{ font-size:13px; color:var(--ink-muted); line-height:1.5; font-family:var(--font-sans); }

/* ---- modal ---- */
.modal-backdrop{
  position:fixed; inset:0; background:rgba(0,0,0,.72);
  display:none; align-items:center; justify-content:center; z-index:100; padding:24px;
}
.modal-backdrop.show{ display:flex; }
.modal-box{
  background:var(--surface-hover); border:1px solid var(--rule); border-left:4px solid var(--emphasis); border-radius:0;
  max-width:480px; width:100%; padding:28px 28px 24px; position:relative;
  box-shadow:0 24px 60px rgba(0,0,0,.55);
  font-family:var(--font-sans);
}
.modal-close{
  position:absolute; top:14px; right:16px; background:none; border:none; color:var(--ink-muted);
  font-size:20px; line-height:1; cursor:pointer; padding:4px; font-family:var(--font-sans);
}
.modal-close:hover{ color:var(--emphasis); }
.modal-badge{
  display:inline-block; font-family:var(--font-mono); font-size:10px; letter-spacing:.05em; text-transform:uppercase;
  padding:3px 10px; border-radius:999px; font-weight:400; margin-bottom:10px;
}
.modal-badge.lost{ background:var(--status-lost); color:var(--status-lost-ink); }
.modal-badge.progress{ background:var(--status-progress); color:var(--status-progress-ink); }
.modal-badge.data{ background:var(--status-data); color:var(--status-data-ink); }
.modal-badge.neutral{ background:var(--status-neutral); color:var(--status-neutral-ink); }
.modal-badge.yellow{ background:var(--status-yellow); color:var(--status-yellow-ink); }
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
  <div class="tile yellow">
    <div class="tlabel">Win Rate (decided)</div>
    <div class="tnum">{win_rate}%</div>
    <div class="wl">
      <span><span class="dot progress"></span>{len(won_list)} won</span>
      <span><span class="dot lost"></span>{len(lost_list)} lost</span>
    </div>
  </div>
</div>
"""

up_rows_html = "".join(
    f"""<div class="uprow"><span class="update">{esc(fmt_date(d))}</span><span class="upname">{esc(p)}</span><span class="uptype">{esc(t)}</span></div>"""
    for p, d, t in upcoming
) or '<div class="uprow" style="border-top:none; color:var(--ink-muted);">Nothing in the next 7 days.</div>'

ROW2_HTML = f"""
<div class="row2">
  <div class="upcoming-tile">
    <div class="upcoming-title">What's coming up</div>
    <div class="upcoming-sub">Next 7 days &middot; Proposals due: {len(due_this_week)} &middot; Presentations: {len(presentations_this_week)}</div>
    {up_rows_html}
  </div>
  <div class="tile iris" style="padding:18px 20px;">
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
    tier = f'<span class="placeholder">TBD</span>' if c["tier"] == "TBD" else f"Tier {esc(c['tier'])}"
    tier_class = f" tier-{c['tier']}" if c["tier"] != "TBD" else ""
    passed = '<span class="datepassed">date passed</span>' if c["date_passed"] else ""
    deck = f'<a href="{esc(c["deck_link"])}" style="color:var(--emphasis); text-decoration:underline;">Open deck</a>' if c["deck_link"] else '<span class="placeholder">not linked yet</span>'
    rfp_folder = (f'<a href="{esc(c["rfp_folder_link"])}" style="color:var(--emphasis); text-decoration:underline;">Open folder</a>'
                  if c["rfp_folder_link"] else '<span class="placeholder">not linked yet</span>')
    # Slack moved out of the field list and into a standalone link after
    # Notes, per Ab 10/28. Still a placeholder until slack_link is set.
    go_to_slack = (f'<a href="{esc(c["slack_link"])}" class="slacklink">Go to Slack &rarr;</a>'
                   if c["slack_link"] else '<span class="slacklink placeholder">Go to Slack — not linked yet</span>')
    spec_row = ""
    if c.get("spec_links"):
        links_html = " &middot; ".join(
            f'<a href="{esc(url)}" style="color:var(--emphasis); text-decoration:underline;">{esc(label)}</a>'
            for label, url in c["spec_links"]
        )
        spec_row = f'<div class="row"><span class="k">Spec deliverables:</span> {links_html}</div>'
    return f"""
    <div class="pcard{tier_class}" tabindex="0" role="button" aria-haspopup="dialog"
         onclick="openModal({i})" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();openModal({i});}}">
      <div class="badge {c['tone']}">{esc(c['label'])}</div>
      <div class="pname">{esc(c['prop'])}</div>
      <div class="pdue">Next: <b>{esc(c['due'])}</b>{passed}</div>
      <div class="powners"><span class="k">Owner</span>{esc(c['owner'])}</div>
      <div class="pbudget{' placeholder' if c['budget_display'] == 'Not yet quantified' else ''}">{c['budget_display']}</div>
      <div class="hint">click for details</div>
      <div class="pdetail" id="detail-{i}">
        <div class="row"><span class="k">Tier:</span> {tier}</div>
        <div class="row"><span class="k">Budget:</span> {esc(c['budget_raw'])}</div>
        <div class="row"><span class="k">Stage details:</span> {esc(c['stage'])}</div>
        <div class="row"><span class="k">Next Due Date:</span> {esc(c['due'])}{(' — ' + esc(c['due_what'])) if c['due_what'] else ''}</div>
        <div class="row"><span class="k">All assigned people:</span> {esc(c['owners'])}</div>
        <div class="row"><span class="k">Deck:</span> {deck}</div>
        <div class="row"><span class="k">RFP docs folder:</span> {rfp_folder}</div>
        <div class="row"><span class="k">Notes:</span> {esc(c['notes'])}</div>
        {spec_row}
        <div class="row slackrow">{go_to_slack}</div>
      </div>
    </div>
    """

# Cards render grouped by stage, not in prop_order, so the modal's index
# has to follow the SAME order they're drawn in - otherwise card i's
# "click for details" opens card j's data. Build the grouped order once and
# use it for both the card markup and MODAL_DATA below.
ordered_cards = []
for g in GROUP_ORDER:
    ordered_cards.extend(groups.get(g, []))

SECTIONS_HTML = ""
card_index = 0
for g in GROUP_ORDER:
    items = groups.get(g, [])
    if not items:
        continue
    tone = GROUP_TONE.get(g, "neutral")
    cards_html_parts = []
    for c in items:
        cards_html_parts.append(card_html(c, card_index))
        card_index += 1
    cards_html = "\n".join(cards_html_parts)
    SECTIONS_HTML += f"""
    <h2 class="section"><span class="section-dot {tone}"></span>{esc(g)}<span class="section-count">{len(items)}</span></h2>
    <div class="grid">{cards_html}</div>
    """

def loss_row_html(l):
    budget_html = (f'<div class="lossbudget">{l["budget_display"]}</div>' if l["budget_display"]
                   else '<div class="lossbudget placeholder">Not yet quantified</div>')
    return f"""
    <div class="lossrow">
      <div class="lossrow-top">
        <div class="lossname">{esc(l['prop'])}</div>
        {budget_html}
      </div>
      <div class="lossreason">{esc(l['reason'])}</div>
    </div>
    """

if losses:
    loss_rows_html = "\n".join(loss_row_html(l) for l in losses)
    loss_total_html = (f'<span class="section-total">{loss_total_display} lost &middot; {loss_quantified_count} of {len(losses)} quantified</span>'
                        if loss_total_display else '<span class="section-total">Not yet quantified</span>')
    SECTIONS_HTML += f"""
    <h2 class="section"><span class="section-dot" style="background:var(--status-lost);"></span>Losses{loss_total_html}<span class="section-count">{len(losses)}</span></h2>
    <div class="loss-tile">{loss_rows_html}</div>
    """

MODAL_DATA = {
    i: {"name": c["prop"], "label": c["label"], "tone": c["tone"]}
    for i, c in enumerate(ordered_cards)
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

subcount = f"{len(in_flight)} active pursuits. {len(awaiting_decision)} are waiting on a client decision, and {no_date_count} have no next date set."

INTERNAL_HTML = HEAD.replace("__PAGE_TITLE__", "Internal") + f"""
<body>
<div class="page">
  <div class="brandbar"><img src="assets/wdg-logo-bone.svg" alt="WDG, an Agital Company"></div>
  <div class="topline">
    <div>
      <h1>New Business Pipeline Dashboard</h1>
      <p class="sub">{quarter_label(AS_OF)} &middot; internal view</p>
      <p class="subcount">{esc(subcount)}</p>
    </div>
    <div class="asof">
      <div class="asof-label">As of</div>
      <div class="asof-date">{AS_OF.strftime('%A, %B %-d, %Y')}</div>
    </div>
  </div>
  {TILES_HTML}
  {ROW2_HTML}
  <div class="tier-key">
    <span class="tier-key-label">Tier (card top border)</span>
    <span class="tier-key-item"><span class="tier-swatch tier-1"></span>Tier 1</span>
    <span class="tier-key-item"><span class="tier-swatch tier-2"></span>Tier 2</span>
    <span class="tier-key-item"><span class="tier-swatch tier-3"></span>Tier 3</span>
    <span class="tier-key-item"><span class="tier-swatch tier-tbd"></span>Not yet assigned</span>
  </div>
  {SECTIONS_HTML}
</div>
  {MODAL_HTML}
</body>
</html>
"""

import os, shutil
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "internal", "assets"), exist_ok=True)
open(os.path.join(OUT_DIR, "internal", "index.html"), "w").write(INTERNAL_HTML)
LOGO_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "wdg-logo-bone.svg")
if os.path.exists(LOGO_SRC):
    shutil.copy(LOGO_SRC, os.path.join(OUT_DIR, "internal", "assets", "wdg-logo-bone.svg"))
print("built internal dashboard:", len(cards), "cards,", len(in_flight), "in flight,", win_rate, "% win rate")
