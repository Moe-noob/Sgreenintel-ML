"""
Step 3 patch: two planting seasons per crop (autumn pick + spring pick), shown side by side.

  heatmap/advisor.py : attaches scan["season_picks"] to every annual crop (via the new heatmap/season_picks.py) and prints
                       the two seasons in the console report. The headline pick (scan["best"]) is NOT changed.
  index.html         : a "Two planting seasons" block in each crop card (autumn row, spring row, the AquaCrop cost of
                       choosing spring) and a dashed outline on the season picks in the "Crop water by planting start date"
                       chart.

Prerequisite: heatmap/season_picks.py must already be in place (it holds the pick logic and the AquaCrop cost table).

Same safety rules as the other patch scripts: every anchor must match exactly once or the file is left untouched, a .bak3
copy is saved, running twice is harmless, --dry-run reports without writing.

Run from the project root:
    python apply_step3_patch.py --dry-run
    python apply_step3_patch.py
"""

import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv

ADVISOR = ("heatmap/advisor.py", "add_season_picks", [
    ("import",
     '''from season_simulator import scan_planting_dates, simulate_perennial_cycle, contiguous_windows''',
     '''from season_simulator import scan_planting_dates, simulate_perennial_cycle, contiguous_windows
from season_picks import add_season_picks, season_picks_lines''', False),
    ("attach picks",
     '''    annual = {name: scan_planting_dates(name, clim, elevation, lat, step_days, raw_years) for name in SCAN_CROPS}''',
     '''    annual = {name: scan_planting_dates(name, clim, elevation, lat, step_days, raw_years) for name in SCAN_CROPS}
    _city_key = location.strip().lower() if isinstance(location, str) else None
    for _name, _scan in annual.items():          # autumn + spring picks next to the (unchanged) headline pick
        add_season_picks(_name, _scan, clim, _city_key)''', False),
    ("console report",
     '''        print(f"   Basis: {scan['selection_basis']}")''',
     '''        print(f"   Basis: {scan['selection_basis']}")
        for _line in season_picks_lines(scan):
            print(_line)''', False),
])

SEASON_JS = '''function seasonPicksHtml(scan) {
  const sp = scan.season_picks;
  if (!sp || (!sp.autumn && !sp.spring)) return '';
  const runs = scan.runs || [];
  const headlineDoy = scan.best ? scan.best.start_doy : null;
  const rowHtml = (title, starts, pick) => {
    const r = pick ? runs.find(x => x.start_doy === pick.start_doy) : null;
    const head = `<div style="font-size:12px;color:var(--paper-faint);">${title} <span style="opacity:0.8;">(${starts} starts)</span></div>`;
    if (!r) return `<div style="padding:8px 0;border-top:1px solid var(--border-soft);">${head}<div style="font-size:13px;color:var(--paper-dim);">No viable start date in this season.</div></div>`;
    const tag = r.start_doy === headlineDoy ? ' <span style="color:var(--gold);font-size:12px;">· card headline</span>' : '';
    return `<div style="padding:8px 0;border-top:1px solid var(--border-soft);">${head}` +
      `<div style="font-size:14px;color:var(--paper);">${r.start_date} → ${r.end_date} · ${r.total_days} days · ${Math.round(r.seasonal_etc_mm)} mm (${(r.seasonal_etc_mm / r.total_days).toFixed(1)} mm/day)${tag}</div>` +
      `<div style="font-size:12px;color:var(--paper-faint);">Exceedance days: ${r.heat_shock_days} heat, ${r.cold_shock_days} cold. Chosen for: ${pick.rule}.</div></div>`;
  };
  const c = sp.spring_cost;
  const costLine = c
    ? `AquaCrop estimates about ${c.pct}% lower water productivity (yield per m³) for the spring date than for the best date of the year (${c.scope}; range ${c.low}–${c.high}% across ${c.n} cities). `
    : '';
  return `<div style="margin:4px 0 14px;">` +
    `<div class="section-label" style="margin:0 0 4px;">Two planting seasons</div>` +
    rowHtml('Autumn', sp.autumn_starts, sp.autumn) + rowHtml('Spring', sp.spring_starts, sp.spring) +
    `<div class="basis-line" style="margin:6px 0 0;">${costLine}${sp.spring_cost_note}</div></div>`;
}

function toggleCard(id) {'''

HTML = ("index.html", "seasonPicksHtml", [
    ("season block function", '''function toggleCard(id) {''', SEASON_JS, False),
    ("season block in the card",
     '''<div class="basis-line">${scan.selection_basis}</div>''',
     '''<div class="basis-line">${scan.selection_basis}</div>
          ${seasonPicksHtml(scan)}''', False),
    ("chart: signature", '''function profileSvg(runs, bestDoy, valueOf, axisLabel) {''',
     '''function profileSvg(runs, bestDoy, valueOf, axisLabel, altDoys) {''', False),
    ("chart: alt flag", '''const isBest = r.start_doy === bestDoy;''',
     '''const isBest = r.start_doy === bestDoy;
    const isAlt = !isBest && Array.isArray(altDoys) && altDoys.includes(r.start_doy);''', False),
    ("chart: alt style", '''(isBest ? 'stroke:var(--paper);stroke-width:2;' : 'opacity:0.85;')''',
     '''(isBest ? 'stroke:var(--paper);stroke-width:2;' : (isAlt ? 'stroke:var(--paper);stroke-width:2;stroke-dasharray:3 2;' : 'opacity:0.85;'))''', False),
    ("chart: alt tooltip", '''${isBest ? ' (MODEL PICK)' : ''}''',
     '''${isBest ? ' (MODEL PICK)' : (isAlt ? ' (SEASON PICK)' : '')}''', False),
    ("chart: compute alt picks", '''const bestDoy = scan.best ? scan.best.start_doy : null;''',
     '''const bestDoy = scan.best ? scan.best.start_doy : null;
  const sp = scan.season_picks;
  const altDoys = sp ? [sp.autumn, sp.spring].filter(Boolean).map(p => p.start_doy) : [];''', False),
    ("chart: pass alt (total)", '''profileSvg(runs, bestDoy, r => r.seasonal_etc_mm, v => `${Math.round(v)} mm`)''',
     '''profileSvg(runs, bestDoy, r => r.seasonal_etc_mm, v => `${Math.round(v)} mm`, altDoys)''', False),
    ("chart: pass alt (daily)", '''profileSvg(runs, bestDoy, r => r.seasonal_etc_mm / r.total_days, v => `${v.toFixed(1)} mm/day`)''',
     '''profileSvg(runs, bestDoy, r => r.seasonal_etc_mm / r.total_days, v => `${v.toFixed(1)} mm/day`, altDoys)''', False),
    ("chart: legend", '''<span>outlined bar = model pick</span></div>''',
     '''<span>outlined bar = model pick</span>${altDoys.length ? '<span>dashed outline = season pick</span>' : ''}</div>''', False),
])

PLAN = [ADVISOR, HTML]


def process(path_str, marker, edits):
    path = Path(path_str)
    if not path.exists():
        return f"{path_str}: NOT FOUND. Run this from the project root."
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    if marker in raw:
        return f"{path_str}: already applied."
    text, failed = raw, []
    for label, old, new, optional in edits:
        o, n = old.replace("\n", nl), new.replace("\n", nl)
        c = text.count(o)
        if c == 1:
            text = text.replace(o, n)
        elif not optional:
            failed.append(f"'{label}' (anchor found {c} times, expected 1)")
    if failed:
        return f"{path_str}: NOT CHANGED -- " + "; ".join(failed)
    if path_str.endswith(".py"):
        try:
            compile(text, path_str, "exec")
        except SyntaxError as exc:
            return f"{path_str}: NOT CHANGED -- the edit would break the file ({exc})"
    if not DRY:
        path.with_name(path.name + ".bak3").write_bytes(raw.encode("utf-8"))
        path.write_bytes(text.encode("utf-8"))
    return f"{path_str}: " + ("would be changed" if DRY else f"done (backup {path.name}.bak3)")


def main():
    if not Path("heatmap/season_picks.py").exists():
        print("heatmap/season_picks.py is missing. Move season_picks.py into the heatmap folder first, then run this again.")
        return 1
    print("DRY RUN: nothing will be written.\n" if DRY else "")
    for entry in PLAN:
        print(process(*entry))
    print("\nNext: restart the API server and hard-refresh the page (Ctrl+Shift+R).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
