"""Schéma unifilaire du tableau électrique en SVG (repris du prototype, couleurs par variables CSS)."""
from __future__ import annotations

from xml.sax.saxutils import escape

from app.moteurs import normes
from app.moteurs.electricite import ResultatElectricite

STYLE = """
.fond{fill:var(--plan-fond,#ffffff)}
.w-ph{stroke:var(--elec-phase,#7a4a2a);fill:none}
.box{fill:var(--plan-sol,#ffffff);stroke:var(--plan-trait,#16202e);stroke-width:1.2}
.boxA{fill:var(--accent-doux,#e2ebf7);stroke:var(--accent,#1d4f91);stroke-width:1.4}
text{fill:var(--plan-texte,#16202e);font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:10.5px}
text.lb{font-family:'IBM Plex Sans Condensed','Arial Narrow',sans-serif;font-size:11.5px;font-weight:600}
text.mu{fill:var(--texte-2,#5a6676)}
"""


def _fs(v: float) -> str:
    s = f"{v:g}"
    return s.replace(".", ",")


def _nf(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def _t(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def rendre(elec: ResultatElectricite) -> str:
    col_w, gap, left = 58, 26, 24
    x = left
    groupes = []
    par_key = {c.key: c for c in elec.circuits}
    for d in elec.differentiels:
        w = max(len(d.circuits), 1) * col_w
        groupes.append((d, x, w))
        x += w + gap
    W = max(x - gap + left, 420)
    H, bus_y = 470, 96
    b = elec.bilan
    ma = normes.ELECTRICITE["differentiel_branchement_ma"]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"'
         ' class="unifilaire">',
         "<title>Schéma unifilaire du tableau électrique</title>", f"<style>{STYLE}</style>",
         f'<rect x="0" y="0" width="{W}" height="{H}" class="fond"/>',
         f'<rect class="box" x="{left}" y="14" width="200" height="44" rx="4"/>',
         f'<text class="lb" x="{left + 10}" y="32">Disjoncteur de branchement</text>',
         f'<text x="{left + 10}" y="49">{b.branchement} A · {ma} mA</text>' if b.branchement else
         f'<text x="{left + 10}" y="49">Triphasé · {ma} mA</text>',
         f'<line class="w-ph" x1="{left + 100}" y1="58" x2="{left + 100}" y2="{bus_y}" stroke-width="2.5"/>',
         f'<line class="w-ph" x1="{left}" y1="{bus_y}" x2="{W - left}" y2="{bus_y}" stroke-width="4"/>',
         f'<text class="mu" x="{left + 240}" y="40">Alimentation 230 V · {_nf(b.kva)} kVA appelés</text>']
    for d, gx, gw in groupes:
        cx = gx + gw / 2
        a = d.type == "A"
        s.append(f'<line class="w-ph" x1="{cx}" y1="{bus_y}" x2="{cx}" y2="120" stroke-width="2"/>')
        s.append(f'<rect class="{"boxA" if a else "box"}" x="{gx + 3}" y="120" width="{gw - 6}" height="46" rx="4"/>')
        s.append(f'<text class="lb" x="{cx}" y="139" text-anchor="middle">{d.nom} · {d.in_} A</text>')
        s.append(f'<text x="{cx}" y="156" text-anchor="middle">30 mA {d.type}</text>')
        s.append(f'<line class="w-ph" x1="{cx}" y1="166" x2="{cx}" y2="186" stroke-width="2"/>')
        x1, x2 = gx + col_w / 2, gx + gw - col_w / 2
        if x2 > x1:
            s.append(f'<line class="w-ph" x1="{x1}" y1="186" x2="{x2}" y2="186" stroke-width="2"/>')
        for i, key in enumerate(d.circuits):
            c = par_key[key]
            ci = gx + col_w * i + col_w / 2
            s.append(f'<line class="w-ph" x1="{ci}" y1="186" x2="{ci}" y2="206" stroke-width="1.5"/>')
            s.append(f'<rect class="box" x="{ci - 14}" y="206" width="28" height="34" rx="3"/>')
            s.append(f'<text x="{ci}" y="227" text-anchor="middle">{c.in_}A</text>')
            s.append(f'<line class="w-ph" x1="{ci}" y1="240" x2="{ci}" y2="262" stroke-width="1.5"/>')
            lab = f"{c.nom} {c.det}" if c.cat == "spe" and c.det != "Circuit spécialisé" else c.nom
            s.append(f'<text class="lb" transform="translate({ci - 3},270) rotate(90)">C{c.num} '
                     f"{escape(_t(lab, 24))}</text>")
            s.append(f'<text class="mu" transform="translate({ci + 11},270) rotate(90)">{_fs(c.s)} mm² · '
                     f"{round(c.l)} m</text>")
    s.append("</svg>\n")
    return "".join(s)
