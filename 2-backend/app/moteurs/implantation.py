"""Implantation : plan 2D d'une maison rectangulaire en trois bandes (CdC § 6.1).

Repère : x vers la droite, y vers le bas, façade principale en bas, unités en mètres.
Les rectangles des pièces sont donnés « à l'axe » des murs ; les dimensions nettes
(entre nus intérieurs) en sont déduites par la demi-épaisseur de chaque mur adjacent.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.moteurs import normes
from app.moteurs.commun import Controle, Hypothese, fmt
from app.moteurs.programme import Programme

N = normes.IMPLANTATION
H = normes.HABITABILITE
MODULE = "implantation"
EPS = 1e-6

TypePiece = Literal["chambre", "sdb", "wc", "placard", "couloir", "sejour", "cuisine", "bureau", "garage",
                    "veranda"]
TYPES_AVEC_PORTE = {"chambre", "sdb", "wc", "sejour", "bureau", "garage", "cuisine"}
TYPES_HABITABLES = {"chambre", "sejour", "bureau", "cuisine"}


class Rect(BaseModel):
    x: float
    y: float
    l: float
    p: float

    @property
    def x2(self) -> float:
        return self.x + self.l

    @property
    def y2(self) -> float:
        return self.y + self.p

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x + self.l / 2, self.y + self.p / 2)


class Piece(BaseModel):
    id: str
    type: TypePiece
    nom: str
    axe: Rect
    net: Rect
    surface_nette: float
    habitable: bool
    exterieure: bool = False


class Mur(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    epaisseur: float
    type: Literal["exterieur", "refend", "cloison"]
    porteur: bool

    @property
    def horizontal(self) -> bool:
        return abs(self.y1 - self.y2) < EPS

    @property
    def longueur(self) -> float:
        return abs(self.x2 - self.x1) + abs(self.y2 - self.y1)


class Ouverture(BaseModel):
    id: str
    type: Literal["porte", "fenetre", "baie", "placard"]
    piece_id: str
    mur_id: str
    horizontal: bool  # orientation du mur porteur de l'ouverture
    x: float  # centre de l'ouverture sur l'axe du mur
    y: float
    largeur: float
    hauteur: float
    epaisseur: float
    sens: int  # +1 / -1 : côté de la pièce desservie (selon y si mur horizontal, selon x sinon)
    charniere: int = -1  # -1 : côté des coordonnées basses ; +1 : côté des coordonnées hautes
    style: str = ""


class Cote(BaseModel):
    id: str
    cote: Literal["bas", "gauche"]
    chaine: int
    debut: float
    fin: float

    @property
    def valeur(self) -> float:
        return self.fin - self.debut


class Emprise(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    largeur: float
    profondeur: float
    surface_plancher: float
    surface_habitable: float
    contour: list[tuple[float, float]]  # polygone à l'axe des murs extérieurs (sens horaire à l'écran)
    epaisseur_ext: float


class ResultatImplantation(BaseModel):
    emprise: Emprise
    pieces: list[Piece]
    murs: list[Mur]
    ouvertures: list[Ouverture]
    cotes: list[Cote]
    parametres: dict[str, float]
    controles: list[Controle]
    hypotheses: list[Hypothese]

    def piece(self, piece_id: str) -> Piece:
        return next(p for p in self.pieces if p.id == piece_id)


# ---------------------------------------------------------------------------


def _epaisseur_bord(murs: list[Mur], horizontal: bool, coord: float, a: float, b: float, defaut: float) -> float:
    """Épaisseur du mur porté par un bord de pièce (le plus épais si plusieurs)."""
    ep = 0.0
    for m in murs:
        if m.horizontal != horizontal:
            continue
        if horizontal:
            if abs(m.y1 - coord) > EPS:
                continue
            lo, hi = sorted((m.x1, m.x2))
        else:
            if abs(m.x1 - coord) > EPS:
                continue
            lo, hi = sorted((m.y1, m.y2))
        if min(hi, b) - max(lo, a) > EPS:
            ep = max(ep, m.epaisseur)
    return ep or defaut


def _mur_du_bord(murs: list[Mur], horizontal: bool, coord: float, centre: float) -> Mur:
    for m in murs:
        if m.horizontal != horizontal:
            continue
        if horizontal and abs(m.y1 - coord) < EPS and min(m.x1, m.x2) - EPS <= centre <= max(m.x1, m.x2) + EPS:
            return m
        if not horizontal and abs(m.x1 - coord) < EPS and min(m.y1, m.y2) - EPS <= centre <= max(m.y1, m.y2) + EPS:
            return m
    raise ValueError(f"aucun mur en {'y' if horizontal else 'x'} = {coord:.3f} au droit de {centre:.3f}")


def calculer(programme: Programme) -> ResultatImplantation:
    p = programme
    e_ext = N["epaisseur_mur_ext"][p.maconnerie]
    e_c = N["epaisseur_cloison"]
    dn = N["profondeur_bande_nuit"]
    lc = N["largeur_couloir"]
    hyp: list[Hypothese] = []
    ctl: list[Controle] = []

    def h(libelle: str, valeur: str, source: str = N["reference"]) -> None:
        hyp.append(Hypothese(module=MODULE, libelle=libelle, valeur=valeur, source=source))

    # 1. Bande nuit -----------------------------------------------------------
    nuit: list[tuple[str, str, str, float]] = []  # (id, type, nom, largeur)
    for i in range(p.chambres):
        if i == 0:
            nuit.append(("CH1", "chambre", "Chambre parentale", N["surface_chambre_parentale"] / dn))
        else:
            nuit.append((f"CH{i + 1}", "chambre", f"Chambre {i + 1}", N["surface_chambre"] / dn))
    nuit.append(("COL", "colonne", "", N["largeur_colonne_wc"]))
    for k in range(p.salles_de_bain):
        nom = "Salle de bains" if p.salles_de_bain == 1 else f"Salle de bains {k + 1}"
        nuit.append((f"SDB{k + 1}", "sdb", nom, N["largeur_sdb"]))
    w_nuit = sum(x[3] for x in nuit)

    # 2-3. Bande jour ---------------------------------------------------------
    s_sejour = max(N["surface_sejour_base"] + N["surface_sejour_par_chambre"] * p.chambres, p.surface_sejour)
    s_cuisine = N["surface_cuisine"]
    s_bureau = N["surface_bureau"] if p.bureau else 0.0
    w = w_nuit
    dj = min(N["profondeur_jour_max"], max(N["profondeur_jour_min"], (s_sejour + s_cuisine + s_bureau) / w))
    l_cuisine = s_cuisine / dj
    l_bureau = s_bureau / dj
    l_sejour = w - l_cuisine - l_bureau
    if l_sejour < N["largeur_sejour_min"]:
        # La bande jour ne tient pas dans la largeur de la bande nuit : on élargit la maison.
        l_sejour = max(N["largeur_sejour_min"], s_sejour / dj)
        w = l_sejour + l_cuisine + l_bureau
        surplus = w - w_nuit
        idx = 0 if p.chambres else len(nuit) - 1
        i_, t_, n_, l_ = nuit[idx]
        nuit[idx] = (i_, t_, n_, l_ + surplus)
        h("Élargissement de la bande nuit", f"+{fmt(surplus)} m sur « {n_ or i_} » pour loger la bande jour")

    yj = dn + lc
    d = yj + dj
    wg = N["largeur_garage"] if p.garage else 0.0
    ordre_jour = [("SEJ", "sejour", "Séjour", l_sejour)]
    jour_suite = [("CUI", "cuisine", "Cuisine", l_cuisine)]
    if p.bureau:
        bureau = ("BUR", "bureau", "Bureau", l_bureau)
        # Cuisine ouverte : elle doit toucher le séjour, le bureau passe donc en bout de bande.
        jour_suite = [jour_suite[0], bureau] if p.cuisine_ouverte else [bureau, jour_suite[0]]
    ordre_jour += jour_suite

    # 5. Murs -----------------------------------------------------------------
    murs: list[Mur] = []
    terrasse = p.toiture == "terrasse"

    def mur(x1, y1, x2, y2, ep, type_, porteur) -> None:
        murs.append(Mur(id=f"M{len(murs) + 1}", x1=x1, y1=y1, x2=x2, y2=y2, epaisseur=ep, type=type_,
                        porteur=porteur))

    if p.garage:
        contour = [(-wg, yj), (0.0, yj), (0.0, 0.0), (w, 0.0), (w, d), (-wg, d)]
    else:
        contour = [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)]
    for a, b in zip(contour, contour[1:] + contour[:1]):
        mur(a[0], a[1], b[0], b[1], e_ext, "exterieur", True)
    if p.garage:
        mur(0.0, yj, 0.0, d, e_ext, "refend", True)
    # Murs longitudinaux du couloir : porteurs (refends) sous une toiture terrasse
    ep_couloir, type_couloir = (e_ext, "refend") if terrasse else (e_c, "cloison")
    mur(0.0, dn, w, dn, ep_couloir, type_couloir, terrasse)
    mur(0.0, yj, w, yj, ep_couloir, type_couloir, terrasse)
    xs_nuit = [0.0]
    for _, _, _, larg in nuit:
        xs_nuit.append(xs_nuit[-1] + larg)
    for x in xs_nuit[1:-1]:
        mur(x, 0.0, x, dn, e_c, "cloison", False)
    i_col = next(i for i, n in enumerate(nuit) if n[0] == "COL")
    x_col = xs_nuit[i_col]
    lpw = N["largeur_colonne_wc"]
    mur(x_col, N["profondeur_wc"], x_col + lpw, N["profondeur_wc"], e_c, "cloison", False)
    xs_jour = [0.0]
    for _, _, _, larg in ordre_jour:
        xs_jour.append(xs_jour[-1] + larg)
    for x in xs_jour[1:-1]:
        mur(x, yj, x, d, e_c, "cloison", False)

    # Pièces ------------------------------------------------------------------
    pieces: list[Piece] = []

    def piece(id_: str, type_: str, nom: str, x: float, y: float, l_: float, p_: float, ext: bool = False):
        axe = Rect(x=x, y=y, l=l_, p=p_)
        if ext:
            net = axe
        else:
            tg = _epaisseur_bord(murs, False, x, y, y + p_, e_c)
            td = _epaisseur_bord(murs, False, x + l_, y, y + p_, e_c)
            th = _epaisseur_bord(murs, True, y, x, x + l_, e_c)
            tb = _epaisseur_bord(murs, True, y + p_, x, x + l_, e_c)
            net = Rect(x=x + tg / 2, y=y + th / 2, l=l_ - (tg + td) / 2, p=p_ - (th + tb) / 2)
        pieces.append(Piece(id=id_, type=type_, nom=nom, axe=axe, net=net, surface_nette=net.l * net.p,
                            habitable=type_ in TYPES_HABITABLES, exterieure=ext))

    for (id_, type_, nom, larg), x in zip(nuit, xs_nuit):
        if type_ == "colonne":
            pw = N["profondeur_wc"]
            piece("PLA", "placard", "Placard", x, 0.0, larg, pw)
            if p.wc_separe:
                piece("WC", "wc", "WC", x, pw, larg, dn - pw)
            else:
                piece("RGT", "placard", "Rangement", x, pw, larg, dn - pw)
        else:
            piece(id_, type_, nom, x, 0.0, larg, dn)
    piece("CLR", "couloir", "Dégagement", 0.0, dn, w, lc)
    for (id_, type_, nom, larg), x in zip(ordre_jour, xs_jour):
        piece(id_, type_, nom, x, yj, larg, dj)
    if p.garage:
        piece("GAR", "garage", "Garage", -wg, yj, wg, dj)
    if p.veranda:
        piece("VER", "veranda", "Véranda", 0.0, d + e_ext / 2, l_sejour, N["profondeur_veranda"], ext=True)

    par_id = {pc.id: pc for pc in pieces}

    # 6. Ouvertures -----------------------------------------------------------
    ouvertures: list[Ouverture] = []
    marge = N["distance_angle_ouverture"]

    def ouvrir(piece_id: str, bord: str, type_: str, dims: tuple[float, float], position="centre",
               style: str = "") -> None:
        pc = par_id[piece_id]
        n, a = pc.net, pc.axe
        larg, haut = dims
        horiz = bord in ("haut", "bas")
        lo, hi = (n.x, n.x2) if horiz else (n.y, n.y2)
        if isinstance(position, float):
            c = lo + position * (hi - lo)
        elif position == "debut":
            c = lo + marge + larg / 2
        elif position == "fin":
            c = hi - marge - larg / 2
        else:
            c = (lo + hi) / 2
        c = min(max(c, lo + marge + larg / 2), hi - marge - larg / 2) if hi - lo > larg + 2 * marge else (lo + hi) / 2
        coord = {"haut": a.y, "bas": a.y2, "gauche": a.x, "droite": a.x2}[bord]
        m = _mur_du_bord(murs, horiz, coord, c)
        sens = {"haut": 1, "bas": -1, "gauche": 1, "droite": -1}[bord]
        charniere = 1 if position == "fin" else -1
        x, y = (c, coord) if horiz else (coord, c)
        ouvertures.append(Ouverture(id=f"O{len(ouvertures) + 1}", type=type_, piece_id=piece_id, mur_id=m.id,
                                    horizontal=horiz, x=x, y=y, largeur=larg, hauteur=haut, epaisseur=m.epaisseur,
                                    sens=sens, charniere=charniere, style=style))

    def repartir(piece_id: str, bord: str, elements: list[tuple[str, tuple[float, float], str]]) -> None:
        """Répartit régulièrement plusieurs ouvertures sur un même bord (en retirant des fenêtres si besoin)."""
        pc = par_id[piece_id]
        longueur = pc.net.l if bord in ("haut", "bas") else pc.net.p
        elts = list(elements)
        while sum(e[0] == "fenetre" for e in elts) > 1 and \
                (longueur - sum(e[1][0] for e in elts)) / (len(elts) + 1) < marge:
            idx = max(i for i, e in enumerate(elts) if e[0] == "fenetre")
            elts.pop(idx)
        ecart = (longueur - sum(e[1][0] for e in elts)) / (len(elts) + 1)
        cur = ecart
        for type_, dims, style in elts:
            ouvrir(piece_id, bord, type_, dims, position=(cur + dims[0] / 2) / longueur, style=style)
            cur += dims[0] + ecart

    for pc in pieces:
        if pc.type == "chambre":
            ouvrir(pc.id, "bas", "porte", N["porte_interieure"], "fin")
            ouvrir(pc.id, "haut", "fenetre", N["fenetre_chambre"])
        elif pc.type == "sdb":
            ouvrir(pc.id, "bas", "porte", N["porte_interieure"], "debut")
            ouvrir(pc.id, "haut", "fenetre", N["fenetre_sdb"], style="allege haute")
        elif pc.type == "wc":
            ouvrir(pc.id, "bas", "porte", N["porte_wc"])
        elif pc.id == "PLA":
            ouvrir(pc.id, "gauche" if p.chambres else "droite", "placard", N["ouverture_placard"])
        elif pc.id == "RGT":
            ouvrir(pc.id, "bas", "placard", N["ouverture_placard"])
        elif pc.type == "sejour":
            fen = ("fenetre", N["fenetre_sejour"], "")
            elements = [fen, ("porte", N["porte_entree"], "entree")]
            elements += [fen] * (N["nb_fenetres_sejour"] - 1)
            repartir(pc.id, "bas", elements)
            ouvrir(pc.id, "haut", "baie", N["baie_sejour_couloir"], 0.8)
        elif pc.type == "cuisine":
            if p.cuisine_ouverte:
                ouvrir(pc.id, "gauche", "baie", N["baie_cuisine_ouverte"])
            else:
                ouvrir(pc.id, "haut", "porte", N["porte_interieure"], "debut")
            ouvrir(pc.id, "bas", "fenetre", N["fenetre_cuisine"])
        elif pc.type == "bureau":
            ouvrir(pc.id, "haut", "porte", N["porte_interieure"], "debut")
            ouvrir(pc.id, "bas", "fenetre", N["fenetre_bureau"])
        elif pc.type == "garage":
            ouvrir(pc.id, "bas", "porte", N["porte_garage"], style="basculante")

    # Emprise -----------------------------------------------------------------
    x_min, y_min, x_max, y_max = -wg - e_ext / 2, -e_ext / 2, w + e_ext / 2, d + e_ext / 2
    surface_plancher = (w + e_ext) * (d + e_ext) + (wg * (dj + e_ext) if p.garage else 0.0)
    surface_hab = sum(pc.surface_nette for pc in pieces if pc.type not in ("garage", "veranda"))
    emprise = Emprise(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, largeur=x_max - x_min,
                      profondeur=y_max - y_min, surface_plancher=surface_plancher, surface_habitable=surface_hab,
                      contour=contour, epaisseur_ext=e_ext)

    # Cotes -------------------------------------------------------------------
    cotes: list[Cote] = []

    def chaine(cote: str, rang: int, points: list[float]) -> None:
        for a, b in zip(points, points[1:]):
            cotes.append(Cote(id=f"K{len(cotes) + 1}", cote=cote, chaine=rang, debut=a, fin=b))

    facade = sorted((pc for pc in pieces if pc.axe.y == yj and pc.type != "couloir"), key=lambda q: q.axe.x)
    pts = [x_min]
    for pc in facade:
        pts += [pc.net.x, pc.net.x2]
    chaine("bas", 1, pts + [x_max])
    chaine("bas", 2, [x_min, x_max])
    gauche = [pieces[0], par_id["CLR"], next(pc for pc in facade if pc.axe.x >= -EPS)]
    pts = [y_min]
    for pc in gauche:
        pts += [pc.net.y, pc.net.y2]
    chaine("gauche", 1, pts + [y_max])
    chaine("gauche", 2, [y_min, y_max])

    # 4 et contrôles -----------------------------------------------------------
    def c(id_, niveau, titre, detail, ref=N["reference"], corrigeable=False) -> None:
        ctl.append(Controle(id=id_, module=MODULE, niveau=niveau, titre=titre, detail=detail, reference_norme=ref,
                            corrigeable=corrigeable))

    if p.niveaux > 1:
        c("IMPL-NIVEAUX", "bloquant", "Plusieurs niveaux : non pris en charge",
          f"{p.niveaux} niveaux demandés ; le MVP ne traite que les maisons de plain-pied (R+0).")

    besoin_l = emprise.largeur + 2 * p.recul
    if besoin_l <= p.terrain_largeur + EPS:
        c("IMPL-EMPRISE-L", "ok", "Emprise en largeur",
          f"{fmt(emprise.largeur)} m + 2 × {fmt(p.recul)} m de recul = {fmt(besoin_l)} m ≤ {fmt(p.terrain_largeur)} m.")
    else:
        c("IMPL-EMPRISE-L", "bloquant", "Emprise trop large pour le terrain",
          f"{fmt(emprise.largeur)} m + 2 × {fmt(p.recul)} m de recul = {fmt(besoin_l)} m > "
          f"terrain {fmt(p.terrain_largeur)} m.", corrigeable=True)
    prof_ver = N["profondeur_veranda"] if p.veranda else 0.0
    besoin_p = emprise.profondeur + prof_ver + 2 * p.recul
    detail_p = (f"{fmt(emprise.profondeur)} m{' + véranda ' + fmt(prof_ver) + ' m' if p.veranda else ''} + "
                f"2 × {fmt(p.recul)} m de recul = {fmt(besoin_p)} m")
    if besoin_p <= p.terrain_profondeur + EPS:
        c("IMPL-EMPRISE-P", "ok", "Emprise en profondeur", f"{detail_p} ≤ {fmt(p.terrain_profondeur)} m.")
    else:
        c("IMPL-EMPRISE-P", "bloquant", "Emprise trop profonde pour le terrain",
          f"{detail_p} > terrain {fmt(p.terrain_profondeur)} m.", corrigeable=True)

    for pc in pieces:
        mini = {"chambre": H["surface_min_chambre"], "sejour": H["surface_min_sejour"]}.get(pc.type)
        if mini is None:
            continue
        if pc.surface_nette + EPS >= mini:
            c(f"IMPL-SURF-{pc.id}", "ok", f"{pc.nom} : surface", f"{fmt(pc.surface_nette)} m² ≥ {fmt(mini, 0)} m².",
              ref=H["reference"])
        else:
            c(f"IMPL-SURF-{pc.id}", "bloquant", f"{pc.nom} : surface insuffisante",
              f"{fmt(pc.surface_nette)} m² < {fmt(mini, 0)} m² minimum.", ref=H["reference"], corrigeable=True)

    clr = par_id["CLR"]
    if clr.net.p + EPS >= H["largeur_min_couloir"]:
        c("IMPL-COULOIR", "ok", "Largeur du dégagement", f"{fmt(clr.net.p)} m ≥ {fmt(H['largeur_min_couloir'])} m.",
          ref=H["reference"])
    else:
        c("IMPL-COULOIR", "bloquant", "Dégagement trop étroit",
          f"{fmt(clr.net.p)} m < {fmt(H['largeur_min_couloir'])} m.", ref=H["reference"])

    for pc in pieces:
        if pc.habitable:
            fen = [o for o in ouvertures if o.piece_id == pc.id and o.type == "fenetre"]
            s_baies = sum(o.largeur * o.hauteur for o in fen)
            requis = pc.surface_nette * H["ratio_eclairement"]
            if not fen:
                c(f"IMPL-FEN-{pc.id}", "bloquant", f"{pc.nom} : aucune fenêtre",
                  "Toute pièce habitable doit avoir au moins une fenêtre.", ref=H["reference"])
            elif s_baies + EPS >= requis:
                c(f"IMPL-FEN-{pc.id}", "ok", f"{pc.nom} : éclairement naturel",
                  f"{fmt(s_baies)} m² de baies ≥ 1/6 × {fmt(pc.surface_nette)} m² = {fmt(requis)} m².",
                  ref=H["reference"])
            else:
                c(f"IMPL-FEN-{pc.id}", "avertissement", f"{pc.nom} : éclairement naturel faible",
                  f"{fmt(s_baies)} m² de baies < 1/6 × {fmt(pc.surface_nette)} m² = {fmt(requis)} m². "
                  "Agrandir la fenêtre ou en ajouter une.", ref=H["reference"])
        if pc.type in TYPES_AVEC_PORTE:
            acces = [o for o in ouvertures if o.piece_id == pc.id and o.type in ("porte", "baie")]
            if not acces:
                c(f"IMPL-PORTE-{pc.id}", "bloquant", f"{pc.nom} : aucun accès", "La pièce n'a ni porte ni baie.")

    # Hypothèses --------------------------------------------------------------
    h("Profondeur de la bande nuit", f"{fmt(dn)} m")
    h("Largeur du dégagement (à l'axe)", f"{fmt(lc)} m")
    h("Profondeur de la bande jour", f"{fmt(dj)} m (bornée à [{fmt(N['profondeur_jour_min'], 1)} ; "
      f"{fmt(N['profondeur_jour_max'], 1)}] m)")
    h("Surface cible du séjour", f"{fmt(s_sejour, 1)} m²")
    h("Épaisseur des murs extérieurs", f"{fmt(e_ext)} m ({p.maconnerie})")
    h("Épaisseur des cloisons", f"{fmt(e_c)} m")
    h("Hauteur des fenêtres (chambre / séjour)",
      f"{fmt(N['fenetre_chambre'][1])} m / {fmt(N['fenetre_sejour'][1])} m")
    if p.veranda:
        h("Profondeur de la véranda", f"{fmt(N['profondeur_veranda'])} m, hors murs")

    parametres = {"largeur_axe": w, "profondeur_axe": d, "profondeur_nuit": dn, "profondeur_jour": dj,
                  "y_jour": yj, "largeur_couloir": lc, "largeur_garage": wg, "epaisseur_ext": e_ext,
                  "epaisseur_cloison": e_c}
    return ResultatImplantation(emprise=emprise, pieces=pieces, murs=murs, ouvertures=ouvertures, cotes=cotes,
                                parametres=parametres, controles=ctl, hypotheses=hyp)
