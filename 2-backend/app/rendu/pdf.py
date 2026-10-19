"""Dossier PDF (reportlab) : plan à l'échelle avec cartouche, synthèse de conformité, notes de calcul, métré.

Police Helvetica (WinAnsi) : les symboles hors Latin-1 des textes des moteurs sont remplacés par `ascii_pdf`.
Le document porte « À valider par un ingénieur qualifié » tant que les six modules ne sont pas signés.
"""
from __future__ import annotations

import io
import math
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.moteurs import chaine
from app.moteurs.commun import fmt
from app.moteurs.implantation import Ouverture, ResultatImplantation

MENTION = "À valider par un ingénieur qualifié"
STATUTS = {"bloque": "Bloqué", "conforme_avec_reserves": "Conforme avec réserves", "conforme": "Conforme"}
NIVEAUX = {"ok": "Conforme", "avertissement": "Avertissement", "bloquant": "Bloquant"}
MODULES = {"implantation": "Plan et implantation", "electricite": "Électricité", "structure": "Structure et fondations",
           "toiture": "Toiture", "solaire": "Solaire", "metre": "Métré et devis"}
ABREGES = {"placard": "Plac.", "sdb": "SdB", "wc": "WC", "couloir": "Dég."}
ECHELLES = (50, 100, 125, 150, 200, 250, 300)

BLEU = colors.HexColor("#1f5fae")
ENCRE = colors.HexColor("#16202c")
GRIS = colors.HexColor("#4a5768")
FILET = colors.HexColor("#d3dae3")
VERT, ORANGE, ROUGE = colors.HexColor("#1b7a3d"), colors.HexColor("#a85b00"), colors.HexColor("#b3261e")
COULEUR_NIVEAU = {"ok": VERT, "avertissement": ORANGE, "bloquant": ROUGE}
COULEUR_STATUT = {"conforme": VERT, "conforme_avec_reserves": ORANGE, "bloque": ROUGE}

_REMPLACEMENTS = {
    "Ω": "ohm", "σ": "sigma", "Σ": "somme", "Δ": "D", "φ": "phi", "ρ": "rho", "≤": "<=", "≥": ">=", "≈": "~",
    "→": "->", "←": "<-", "−": "-", "‑": "-", " ": " ", " ": " ", "′": "'", "″": '"', "✓": "ok",
}


def ascii_pdf(texte: object) -> str:
    """Remplace ce que Helvetica (cp1252) ne sait pas dessiner ; jamais de carré noir dans le document."""
    s = str(texte)
    for k, v in _REMPLACEMENTS.items():
        s = s.replace(k, v)
    return s.encode("cp1252", errors="replace").decode("cp1252")


def _esc(texte: object) -> str:
    return ascii_pdf(texte).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _argent(v: float, devise: str) -> str:
    return f"{fmt(v, 2)} {'$' if devise == 'USD' else devise}"


# ---------------------------------------------------------------------------
# Plan à l'échelle (dessin vectoriel direct, mêmes données que le SVG)
# ---------------------------------------------------------------------------

class Cartouche:
    def __init__(self, nom: str, date: str, version: str, statut: str, empreinte: str):
        self.nom, self.date, self.version, self.statut, self.empreinte = nom, date, version, statut, empreinte


class PlanFlowable(Flowable):
    """Plan du rez-de-chaussée à une échelle normalisée (1:100 si possible) avec cotes, nord, échelle graphique."""

    def __init__(self, impl: ResultatImplantation, cartouche: Cartouche, largeur: float, hauteur: float):
        super().__init__()
        self.impl, self.cartouche = impl, cartouche
        self.largeur, self.hauteur = largeur, hauteur
        em = impl.emprise
        ver = next((p for p in impl.pieces if p.type == "veranda"), None)
        self.y_bas = max(em.y_max, ver.axe.y2 if ver else em.y_max)
        self.x0, self.y0 = em.x_min - 1.9, em.y_min - 0.4  # marge de cotes à gauche
        self.l_m = (em.x_max - self.x0) + 0.6
        self.h_m = (self.y_bas - self.y0) + 1.9  # cotes en bas
        zone_l, zone_h = largeur - 62 * mm, hauteur - 6 * mm  # cartouche à droite
        self.echelle = next((e for e in ECHELLES if self.l_m * 1000 / e * mm <= zone_l and self.h_m * 1000 / e * mm <= zone_h),
                            ECHELLES[-1])
        self.k = 1000 / self.echelle * mm  # points PDF par mètre

    def wrap(self, *_):
        return self.largeur, self.hauteur

    # coordonnées plan (m, y vers le bas) -> page (pt)
    def X(self, x: float) -> float:
        return (x - self.x0) * self.k + 2 * mm

    def Y(self, y: float) -> float:
        return self.hauteur - 3 * mm - (y - self.y0) * self.k

    def _ligne(self, c, x1, y1, x2, y2):
        c.line(self.X(x1), self.Y(y1), self.X(x2), self.Y(y2))

    def draw(self):
        c, impl = self.canv, self.impl
        em = impl.emprise
        # Murs
        c.setFillColor(ENCRE)
        c.setStrokeColor(ENCRE)
        c.setLineWidth(0.3)
        for m in impl.murs:
            h = m.epaisseur / 2
            if m.horizontal:
                x0, x1 = sorted((m.x1, m.x2))
                xa, ya, xb, yb = x0 - h, m.y1 - h, x1 + h, m.y1 + h
            else:
                y0, y1 = sorted((m.y1, m.y2))
                xa, ya, xb, yb = m.x1 - h, y0 - h, m.x1 + h, y1 + h
            c.rect(self.X(xa), self.Y(yb), (xb - xa) * self.k, (yb - ya) * self.k, fill=1, stroke=0)
        # Véranda (pointillés) et poteaux
        ver = next((p for p in impl.pieces if p.type == "veranda"), None)
        if ver:
            a = ver.axe
            c.setDash(2, 2)
            c.setLineWidth(0.4)
            c.rect(self.X(a.x), self.Y(a.y2), a.l * self.k, a.p * self.k, fill=0, stroke=1)
            c.setDash()
            for px in (a.x + 0.1, a.x2 - 0.1):
                c.rect(self.X(px - 0.1), self.Y(a.y2), 0.2 * self.k, 0.2 * self.k, fill=1, stroke=0)
        for o in impl.ouvertures:
            self._ouverture(o)
        # Étiquettes
        c.setFillColor(ENCRE)
        for pc in impl.pieces:
            if pc.exterieure:
                continue
            cx, cy = pc.net.centre
            etroite = pc.net.l * self.k < 30 * mm
            nom = ABREGES.get(pc.type, pc.nom) if pc.net.l * self.k < 22 * mm else pc.nom
            if etroite:  # petite pièce : texte dans la moitié haute, loin du débattement de la porte (côté couloir)
                cy = pc.net.y + pc.net.p * 0.32
            taille = 6.5 if not etroite else 5
            c.setFont("Helvetica-Bold", taille)
            c.drawCentredString(self.X(cx), self.Y(cy) + 1, ascii_pdf(nom))
            c.setFont("Helvetica", taille - 0.5)
            c.drawCentredString(self.X(cx), self.Y(cy) - taille, ascii_pdf(f"{fmt(pc.surface_nette)} m²"))
        self._cotes(em)
        self._annotations(em)

    def _ouverture(self, o: Ouverture):
        c = self.canv
        w, e, s = o.largeur, o.epaisseur, o.sens

        def P(t, n):
            return (t, o.y + n) if o.horizontal else (o.x + n, t)

        ctr = o.x if o.horizontal else o.y
        a0, a1 = ctr - w / 2, ctr + w / 2
        # Percement
        p1, p2 = P(a0, -e / 2 - 0.01), P(a1, e / 2 + 0.01)
        c.setFillColor(colors.white)
        c.rect(self.X(min(p1[0], p2[0])), self.Y(max(p1[1], p2[1])), abs(p2[0] - p1[0]) * self.k,
               abs(p2[1] - p1[1]) * self.k, fill=1, stroke=0)
        c.setStrokeColor(ENCRE)
        c.setLineWidth(0.3)
        for t in (a0, a1):
            (xa, ya), (xb, yb) = P(t, -e / 2), P(t, e / 2)
            self._ligne(c, xa, ya, xb, yb)
        if o.type == "fenetre":
            for k in (-e / 2, 0.0, e / 2):
                (xa, ya), (xb, yb) = P(a0, k), P(a1, k)
                self._ligne(c, xa, ya, xb, yb)
        elif o.type == "baie":
            c.setDash(1.5, 1.5)
            for k in (-e / 2, e / 2):
                (xa, ya), (xb, yb) = P(a0, k), P(a1, k)
                self._ligne(c, xa, ya, xb, yb)
            c.setDash()
        elif o.type == "placard":
            (xa, ya), (xb, yb) = P(a0, s * 0.03), P(a1, s * 0.03)
            self._ligne(c, xa, ya, xb, yb)
        elif o.style == "basculante":
            (xa, ya), (xb, yb) = P(a0, s * e / 2), P(a1, s * e / 2)
            self._ligne(c, xa, ya, xb, yb)
        else:
            t_ch, t_lib = (a1, a0) if o.charniere > 0 else (a0, a1)
            face = s * e / 2
            ch, bout, jamb = P(t_ch, face), P(t_ch, face + s * w), P(t_lib, face)
            self._ligne(c, ch[0], ch[1], bout[0], bout[1])
            # angles dans le repère de la page (y vers le haut)
            ab = math.degrees(math.atan2(-(bout[1] - ch[1]), bout[0] - ch[0]))
            aj = math.degrees(math.atan2(-(jamb[1] - ch[1]), jamb[0] - ch[0]))
            etendue = ((aj - ab + 180) % 360) - 180
            cx, cy, r = self.X(ch[0]), self.Y(ch[1]), w * self.k
            c.setLineWidth(0.2)
            c.arc(cx - r, cy - r, cx + r, cy + r, ab, etendue)

    def _cotes(self, em):
        c, impl = self.canv, self.impl
        c.setStrokeColor(BLEU)
        c.setFillColor(BLEU)
        c.setLineWidth(0.25)
        tick = 0.08
        for k in impl.cotes:
            decal = 0.75 + 0.6 * (k.chaine - 1)
            v = k.valeur
            texte = f"{round(v * 100):d}" if v < 0.5 else fmt(v)
            c.setFont("Helvetica", 5)
            if k.cote == "bas":
                y = self.y_bas + decal
                self._ligne(c, k.debut, y, k.fin, y)
                for x in (k.debut, k.fin):
                    self._ligne(c, x, em.y_max + 0.12, x, y + 0.1)
                    self._ligne(c, x - tick, y + tick, x + tick, y - tick)
                if v * self.k > 6 * mm:
                    c.drawCentredString(self.X((k.debut + k.fin) / 2), self.Y(y) + 1.5, texte)
            else:
                x = em.x_min - decal
                self._ligne(c, x, k.debut, x, k.fin)
                for y in (k.debut, k.fin):
                    self._ligne(c, em.x_min - 0.12, y, x - 0.1, y)
                    self._ligne(c, x - tick, y + tick, x + tick, y - tick)
                if v * self.k > 6 * mm:
                    c.saveState()
                    c.translate(self.X(x) - 1.5, self.Y((k.debut + k.fin) / 2))
                    c.rotate(90)
                    c.drawCentredString(0, 0, texte)
                    c.restoreState()

    def _annotations(self, em):
        c, ct = self.canv, self.cartouche
        # Flèche du nord
        nx, ny = self.X(em.x_max) + 8 * mm, self.hauteur - 10 * mm
        c.setStrokeColor(ENCRE)
        c.setFillColor(ENCRE)
        c.setLineWidth(0.5)
        c.circle(nx, ny, 4 * mm, fill=0, stroke=1)
        p = c.beginPath()
        p.moveTo(nx, ny + 3.4 * mm)
        p.lineTo(nx - 1.4 * mm, ny - 2.4 * mm)
        p.lineTo(nx, ny - 1.2 * mm)
        p.lineTo(nx + 1.4 * mm, ny - 2.4 * mm)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(nx, ny + 5 * mm, "N")
        # Échelle graphique 0-5 m
        sx, sy = nx - 4 * mm, 24 * mm
        for i in range(5):
            c.setFillColor(ENCRE if i % 2 == 0 else colors.white)
            c.rect(sx + i * self.k, sy, self.k, 1.6 * mm, fill=1, stroke=1)
        c.setFillColor(ENCRE)
        c.setFont("Helvetica", 5.5)
        for i in range(6):
            c.drawCentredString(sx + i * self.k, sy - 3 * mm, str(i))
        c.drawString(sx + 5 * self.k + 2 * mm, sy - 3 * mm, "m")
        # Cartouche
        bl, bh = 56 * mm, 45 * mm
        bx = self.largeur - bl
        c.setStrokeColor(ENCRE)
        c.setLineWidth(0.7)
        c.rect(bx, 0, bl, bh)
        lignes = [("PROJET", ct.nom), ("PLAN", "Rez-de-chaussée"), ("ÉCHELLE", f"1:{self.echelle}"),
                  ("DATE · VERSION", f"{ct.date} · v{ct.version}"), ("STATUT", ct.statut)]
        pas = bh / len(lignes)
        for i, (k, v) in enumerate(lignes):
            y = bh - (i + 1) * pas
            c.setLineWidth(0.25)
            if i:
                c.line(bx, y + pas, bx + bl, y + pas)
            c.setFillColor(GRIS)
            c.setFont("Helvetica", 4.5)
            c.drawString(bx + 2 * mm, y + pas - 4.6, ascii_pdf(k))
            c.setFillColor(ENCRE)
            c.setFont("Helvetica-Bold", 7)
            texte = ascii_pdf(v)
            while c.stringWidth(texte, "Helvetica-Bold", 7) > bl - 4 * mm and len(texte) > 6:
                texte = texte[:-2] + "."
            c.drawString(bx + 2 * mm, y + 3.4, texte)
        c.setFont("Helvetica", 4.5)
        c.setFillColor(GRIS)
        c.drawRightString(bx + bl, -3.5, f"Empreinte {ct.empreinte[:12]}")


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle("titre", parent=base["Title"], fontName="Helvetica-Bold", fontSize=15, textColor=ENCRE,
                                alignment=0, spaceAfter=4),
        "h1": ParagraphStyle("h1", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=BLEU,
                             spaceBefore=10, spaceAfter=4),
        "corps": ParagraphStyle("corps", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.4,
                                textColor=ENCRE),
        "petit": ParagraphStyle("petit", parent=base["BodyText"], fontName="Helvetica", fontSize=7, leading=8.8,
                                textColor=GRIS),
        "cellule": ParagraphStyle("cellule", fontName="Helvetica", fontSize=7.2, leading=8.8, textColor=ENCRE),
        "cellule_d": ParagraphStyle("cellule_d", fontName="Helvetica", fontSize=7.2, leading=8.8, textColor=ENCRE,
                                    alignment=2),
        "entete": ParagraphStyle("entete", fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=colors.white),
        "entete_d": ParagraphStyle("entete_d", fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=colors.white,
                                   alignment=2),
    }


def _tableau(st, entetes, lignes, largeurs, droite=()):
    """Tableau à en-tête bleu, cellules qui passent à la ligne, nombres alignés à droite."""
    def cell(v, i, tete=False):
        if isinstance(v, Paragraph):
            return v
        return Paragraph(_esc(v), st[("entete" if tete else "cellule") + ("_d" if i in droite else "")])

    data = [[cell(h, i, True) for i, h in enumerate(entetes)]] + [[cell(v, i) for i, v in enumerate(l)] for l in lignes]
    t = Table(data, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, FILET),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _cle_valeur(st, lignes, largeurs):
    data = [[Paragraph(_esc(k), st["cellule"]), Paragraph(_esc(v), st["cellule_d"])] for k, v in lignes]
    t = Table(data, colWidths=largeurs)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, FILET), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def rendre(projet: dict, res: chaine.Resultats, validations: list[dict]) -> bytes:
    """`projet` : nom, version, empreinte, modifie_le, version_moteurs ; `validations` : encore valides seulement."""
    st = _styles()
    signes = {v["module"]: v for v in validations}
    tous_signes = all(m in signes for m in MODULES)
    mention = None if tous_signes else MENTION
    impl = res.implantation
    pagesize = landscape(A4)
    L, H = pagesize
    marge = 12 * mm
    zone_l, zone_h = L - 2 * marge, H - 2 * marge - 6 * mm
    date = (projet.get("modifie_le") or datetime.now(UTC).isoformat())[:10]

    sig = signes.get("implantation")
    statut_cartouche = (f"Signé par {sig['nom']}" + (f" (n° {sig['numero_ordre']})" if sig.get("numero_ordre") else "")
                        ) if sig else MENTION

    def decor(canv, doc):
        canv.saveState()
        canv.setStrokeColor(FILET)
        canv.setLineWidth(0.5)
        canv.line(marge, 10 * mm, L - marge, 10 * mm)
        canv.setFont("Helvetica", 6.5)
        canv.setFillColor(GRIS)
        canv.drawString(marge, 6.5 * mm, ascii_pdf(f"Assistant Plan Ingénierie · {projet['nom']} · version {projet['version']}"
                                                    f" · moteurs {projet['version_moteurs']}"))
        canv.drawRightString(L - marge, 6.5 * mm, f"Page {doc.page}")
        if mention:
            canv.setFillColor(ROUGE)
            canv.setFont("Helvetica-Bold", 7.5)
            canv.drawCentredString(L / 2, 6.5 * mm, mention + " · document non contractuel")
        canv.restoreState()

    tampon = io.BytesIO()
    doc = BaseDocTemplate(tampon, pagesize=pagesize, leftMargin=marge, rightMargin=marge, topMargin=marge,
                          bottomMargin=marge + 6 * mm, title=ascii_pdf(f"Dossier — {projet['nom']}"),
                          author="Assistant Plan Ingénierie", subject="Plan, conformité, notes de calcul et métré")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(marge, marge + 6 * mm, zone_l, zone_h, 0, 0, 0, 0)],
                                       onPage=decor)])
    S: list = []
    cart = Cartouche(projet["nom"], date, str(projet["version"]), statut_cartouche, projet["empreinte"])
    S.append(PlanFlowable(impl, cart, zone_l, zone_h))
    S.append(PageBreak())

    # --- Synthèse -----------------------------------------------------------
    S.append(Paragraph(_esc(f"Dossier technique — {projet['nom']}"), st["titre"]))
    S.append(Paragraph(_esc(f"Statut global : {STATUTS[res.statut]} · version des moteurs {res.version_moteurs} · "
                            f"empreinte {projet['empreinte'][:12]} · mis à jour le {date}"), st["corps"]))
    S.append(Paragraph("Signature par module", st["h1"]))
    lignes = []
    for m, lib in MODULES.items():
        v = signes.get(m)
        signature = (f"Signé par {v['nom']}" + (f" (n° {v['numero_ordre']})" if v.get("numero_ordre") else "")
                     + f" le {v['date'][:10]}" + (f" — « {v['commentaire']} »" if v.get("commentaire") else "")) if v else MENTION
        nb = sum(1 for c in res.controles if c.module == m and c.niveau == "bloquant")
        nw = sum(1 for c in res.controles if c.module == m and c.niveau == "avertissement")
        lignes.append((lib, STATUTS[res.statuts_modules[m]], f"{nb} bloquant(s), {nw} avertissement(s)", signature))
    S.append(_tableau(st, ["Module", "Statut", "Points ouverts", "Validation"], lignes,
                      [48 * mm, 40 * mm, 45 * mm, zone_l - 133 * mm]))

    S.append(Paragraph("Contrôles", st["h1"]))
    ordre = {"bloquant": 0, "avertissement": 1, "ok": 2}
    ctrl = sorted(res.controles, key=lambda c: ordre[c.niveau])
    lignes = []
    for c in ctrl:
        lignes.append((Paragraph(f'<font color="{COULEUR_NIVEAU[c.niveau].hexval().replace("0x", "#")}">'
                                 f"<b>{NIVEAUX[c.niveau]}</b></font>", st["cellule"]),
                       c.id, MODULES[c.module], f"{c.titre} — {c.detail}", c.reference_norme))
    S.append(_tableau(st, ["Niveau", "Identifiant", "Module", "Constat", "Référence"], lignes,
                      [22 * mm, 33 * mm, 33 * mm, zone_l - 22 * mm - 33 * mm - 33 * mm - 60 * mm, 60 * mm]))

    # --- Électricité ----------------------------------------------------------
    el = res.electricite
    S.append(PageBreak())
    S.append(Paragraph("Électricité — notes de calcul", st["h1"]))
    S.append(Paragraph(_esc("230 V monophasé, cos phi 0,9, cuivre (rho = 0,023 ohm.mm²/m). Chute de tension "
                            "dU % = 2 x rho x L x Ib / (S x U) x 100 ; limites 3 % éclairage, 5 % autres circuits. "
                            "Longueurs estimées depuis le plan (distance au tableau + 2 m, +10 %) sauf saisie."), st["petit"]))
    S.append(Spacer(1, 3))
    par_cle = {c.key: c for c in el.circuits}
    lignes = []
    for d in el.differentiels:
        lignes.append((Paragraph(f"<b>{_esc(d.nom)}</b>", st["cellule"]),
                       Paragraph(_esc(f"Différentiel 30 mA type {d.type} · {d.in_} A · {fmt(d.i, 1)} A estimés"),
                                 st["cellule"]), "", "", "", "", "", "", ""))
        for k in d.circuits:
            c = par_cle[k]
            lignes.append((f"C{c.num}", f"{c.nom} — {c.det}", f"{c.n} {c.unite}", f"{fmt(c.p, 0)} W", f"{c.in_} A",
                           f"{fmt(c.s, 1)} mm²", fmt(c.l, 1), f"{fmt(c.du)} % / {fmt(c.lim, 0)} %",
                           {"ok": "Conforme", "warn": "Section augmentée", "bad": "Non conforme"}.get(c.etat, c.etat)))
    S.append(_tableau(st, ["N°", "Circuit", "Points", "Puissance", "Protection", "Section", "L (m)", "Chute de tension",
                           "État"], lignes,
                      [14 * mm, zone_l - 14 * mm - 17 * mm - 20 * mm - 19 * mm - 18 * mm - 14 * mm - 30 * mm - 28 * mm,
                       17 * mm, 20 * mm, 19 * mm, 18 * mm, 14 * mm, 30 * mm, 28 * mm], droite=(2, 3, 4, 5, 6, 7)))
    b = el.bilan
    S.append(Spacer(1, 4))
    S.append(_cle_valeur(st, [("Puissance installée", f"{fmt(b.p_installee / 1000, 1)} kW"),
                              ("Puissance demandée", f"{fmt(b.p_demandee / 1000, 1)} kW"),
                              ("Puissance apparente", f"{fmt(b.kva, 1)} kVA"),
                              ("Courant d'abonnement", f"{fmt(b.i_abonnement, 1)} A"),
                              ("Branchement conseillé", f"{b.branchement} A")], [60 * mm, 40 * mm]))

    # --- Structure ------------------------------------------------------------
    s = res.structure
    S.append(PageBreak())
    S.append(Paragraph("Structure et fondations", st["h1"]))
    S.append(Paragraph(_esc(f"Dallage : {fmt(s.dallage["surface"])} m², épaisseur {fmt(s.dallage["epaisseur"] * 100, 0)} cm, "
                            f"hérisson {fmt(s.dallage["herisson"] * 100, 0)} cm, treillis {s.dallage["treillis"]}, béton "
                            f"{fmt(s.dallage["volume_beton"])} m³ · hauteur des murs {fmt(s.hauteur_mur)} m"), st["corps"]))
    S.append(Spacer(1, 3))
    S.append(_tableau(st, ["Semelle", "Mur", "Longueur", "Charge ELS", "B x h", "Ferraillage"],
                      [(x.id, x.mur_id, f"{fmt(x.longueur)} m", f"{fmt(x.q_els)} kN/m",
                        f"{fmt(x.largeur)} x {fmt(x.hauteur)} m", x.ferraillage) for x in s.semelles],
                      [20 * mm, 16 * mm, 24 * mm, 26 * mm, 28 * mm, zone_l - 114 * mm], droite=(2, 3, 4)))
    S.append(Spacer(1, 4))
    S.append(_tableau(st, ["Poteau", "x (m)", "y (m)", "Section (cm)", "Armatures", "Cadres", "Motif"],
                      [(p.id, fmt(p.x), fmt(p.y), p.section, p.armatures, p.cadres, p.motif) for p in s.poteaux],
                      [18 * mm, 20 * mm, 20 * mm, 24 * mm, 28 * mm, 32 * mm, zone_l - 142 * mm], droite=(1, 2)))
    S.append(Spacer(1, 4))
    S.append(_tableau(st, ["Repère", "Type", "Référence", "Longueur", "Section (cm)"],
                      [(c.id, "Linteau" if c.type == "linteau" else "Chaînage horizontal", c.reference,
                        f"{fmt(c.longueur)} m", c.section) for c in s.chainages],
                      [22 * mm, 50 * mm, 26 * mm, 28 * mm, 30 * mm], droite=(3,)))

    # --- Toiture et solaire ---------------------------------------------------
    t, so = res.toiture, res.solaire
    S.append(PageBreak())
    S.append(Paragraph("Toiture", st["h1"]))
    lig = [("Type / couverture", f"{t.type} / {t.couverture}")]
    if t.type == "terrasse":
        lig += [("Surface de dalle", f"{fmt(t.surface)} m²"), ("Béton de dalle", f"{fmt(t.dalle_volume)} m³"),
                ("Acrotère", f"{fmt(t.acrotere_ml, 1)} m")]
    else:
        lig += [("Pente / débord", f"{fmt(t.pente, 0)} % / {fmt(t.debord)} m"),
                ("Surface en plan / rampante", f"{fmt(t.surface_plan)} m² / {fmt(t.surface)} m²"),
                ("Fermes", str(t.fermes)), ("Bois des fermes", f"{fmt(t.longueur_fermes_ml, 1)} m"),
                ("Pannes", f"{fmt(t.pannes_ml, 1)} m"), ("Faîtage", f"{fmt(t.faitage_ml, 1)} m"),
                ("Total charpente", f"{fmt(t.charpente_ml, 1)} m")]
        if t.aretiers_ml:
            lig.append(("Arêtiers", f"{fmt(t.aretiers_ml, 1)} m"))
        if t.liteaux_ml:
            lig.append(("Liteaux", f"{fmt(t.liteaux_ml, 1)} m"))
    lig += [("Gouttières", f"{fmt(t.gouttieres, 1)} m"), ("Descentes d'eaux pluviales", str(t.descentes))]
    S.append(_cle_valeur(st, lig, [80 * mm, 60 * mm]))
    S.append(Paragraph("Solaire", st["h1"]))
    if so.demande:
        S.append(_cle_valeur(st, [("Charges essentielles", f"{fmt(so.charges_essentielles_w / 1000, 1)} kW"),
                                  ("Énergie par jour", f"{fmt(so.energie_jour_kwh, 1)} kWh"),
                                  ("Onduleur", f"{fmt(so.onduleur_kva, 1)} kVA"),
                                  ("Batteries", f"{fmt(so.batteries_kwh, 1)} kWh"),
                                  ("Panneaux", f"{fmt(so.panneaux_kwc, 2)} kWc")], [80 * mm, 60 * mm]))
    else:
        S.append(Paragraph("Pas d'installation solaire dans le programme.", st["corps"]))

    # --- Métré ----------------------------------------------------------------
    me = res.metre
    S.append(PageBreak())
    S.append(Paragraph("Métré et devis estimatif", st["h1"]))
    S.append(Paragraph(_esc(f"Prix {me.mention_prix}."), st["petit"]))
    S.append(Spacer(1, 3))
    lignes = []
    for lot in dict.fromkeys(x.lot for x in me.lignes):
        ls = [x for x in me.lignes if x.lot == lot]
        lignes.append((Paragraph(f"<b>{_esc(lot)}</b>", st["cellule"]), "", "", "",
                       Paragraph(f"<b>{_esc(_argent(sum(x.total for x in ls), me.devise))}</b>", st["cellule_d"])))
        lignes += [(x.poste, fmt(x.quantite, 0 if x.quantite >= 100 or float(x.quantite).is_integer() else 2), x.unite,
                    _argent(x.prix_unitaire, me.devise), _argent(x.total, me.devise)) for x in ls]
    lignes.append((Paragraph("<b>Total estimatif</b>", st["cellule"]), "", "", "",
                   Paragraph(f"<b>{_esc(_argent(me.total, me.devise))}</b>", st["cellule_d"])))
    S.append(_tableau(st, ["Poste", "Quantité", "Unité", "Prix unitaire", "Total"], lignes,
                      [zone_l - 100 * mm - 22 * mm, 22 * mm, 18 * mm, 30 * mm, 30 * mm + 0], droite=(1, 3, 4)))

    # --- Hypothèses -----------------------------------------------------------
    S.append(PageBreak())
    S.append(Paragraph("Hypothèses de calcul", st["h1"]))
    S.append(_tableau(st, ["Module", "Hypothèse", "Valeur", "Source"],
                      [(MODULES[h.module], h.libelle, h.valeur, h.source) for h in res.hypotheses],
                      [36 * mm, 70 * mm, 60 * mm, zone_l - 166 * mm]))
    S.append(Spacer(1, 8))
    S.append(KeepTogether([Paragraph(_esc(
        "Les calculs de sécurité (sections, calibres, semelles, ferraillage, chutes de tension) sont produits par des "
        "moteurs déterministes. L'IA ne fait que proposer le programme et rédiger des explications. "
        + (MENTION + " : modules non signés, document non contractuel." if mention else
           "Tous les modules sont signés par un ingénieur.")), st["petit"])]))
    doc.build(S)
    return tampon.getvalue()
