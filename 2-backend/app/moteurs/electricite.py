"""Électrification — port fidèle du prototype validé « Module Électrification » (CdC § 6.3).

Le calcul des circuits, sections, protections, différentiels et du bilan reprend exactement
la logique du prototype (docs/reference/prototype-electrification.html). Nouveautés :
placement des symboles sur le plan, longueur de chaque circuit déduite du plan, schéma unifilaire.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

from app.moteurs import normes
from app.moteurs.commun import Controle, Hypothese, fmt
from app.moteurs.implantation import Ouverture, Piece, ResultatImplantation
from app.moteurs.programme import Programme

E = normes.ELECTRICITE
MODULE = "electricite"
REF = E["reference"]


class Point(BaseModel):
    id: str
    type: Literal["lumiere", "prise", "prise_specialisee", "interrupteur", "tableau"]
    piece_id: str
    x: float
    y: float
    nx: float = 0.0  # normale vers l'intérieur de la pièce (prises)
    ny: float = 0.0
    circuit: str = ""


class Circuit(BaseModel):
    key: str
    cat: Literal["ecl", "pc", "spe"]
    nom: str
    det: str
    n: int
    unite: str
    p: float
    in_: int
    s0: float
    s: float
    ks: float
    lim: float
    ib: float
    l: float
    du0: float
    du: float
    iz: float
    etat: Literal["ok", "warn", "bad"]
    type_a: bool = False
    num: int = 0
    id: str = ""


class Differentiel(BaseModel):
    nom: str
    type: Literal["A", "AC"]
    circuits: list[str]
    i: float
    in_: int


class Bilan(BaseModel):
    surface: float
    p_installee: float
    p_demandee: float
    kva: float
    i_abonnement: float
    branchement: int | None


class ResultatElectricite(BaseModel):
    circuits: list[Circuit]
    differentiels: list[Differentiel]
    bilan: Bilan
    points: list[Point]
    controles: list[Controle]
    hypotheses: list[Hypothese]

    def circuit(self, key: str) -> Circuit:
        return next(c for c in self.circuits if c.key == key)


# ---------------------------------------------------------------------------
# Règles par pièce
# ---------------------------------------------------------------------------


def _regle(regle: tuple, s: float) -> int:
    if regle[0] == "fixe":
        return regle[1]
    if regle[0] == "par_m2":
        return max(regle[2], math.ceil(s / regle[1]))
    if regle[0] == "seuil":
        return regle[2] if s > regle[1] else regle[3]
    raise ValueError(regle)


def _pieces_electriques(impl: ResultatImplantation) -> list[Piece]:
    return [p for p in impl.pieces if p.type in E["regles_pieces"]]


def nb_points(piece: Piece) -> tuple[int, int]:
    """(points lumineux, prises) d'une pièce selon les règles du prototype."""
    r = E["regles_pieces"][piece.type]
    return _regle(r["lum"], piece.surface_nette), _regle(r["prises"], piece.surface_nette)


# ---------------------------------------------------------------------------
# Moteur de calcul (port du prototype)
# ---------------------------------------------------------------------------


def _chunk(seq: list, n: int) -> list[list]:
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def _uniq(noms: list[str]) -> str:
    return ", ".join(dict.fromkeys(noms))


def calculer_circuits(
    pieces: list[dict],
    equipements: dict[str, bool],
    longueurs: dict[str, float],
    longueur_defaut: float,
) -> tuple[list[Circuit], list[Differentiel], Bilan]:
    """Cœur du prototype. `pieces` : [{id, nom, type, surface, clim}] dans l'ordre de saisie."""
    u, rho, cosphi = E["tension"], E["resistivite_cuivre"], E["cos_phi"]
    ecl, pc, pcc = E["eclairage"], E["prises"], E["prises_cuisine"]
    circ: list[dict] = []
    pts: list[str] = []
    pcs: list[str] = []
    pc_cuis: list[str] = []
    for p in pieces:
        r = E["regles_pieces"][p["type"]]
        s = p["surface"]
        pts += [p["nom"]] * _regle(r["lum"], s)
        (pc_cuis if p["type"] == "cuisine" else pcs).extend([p["nom"]] * _regle(r["prises"], s))
    for i, g in enumerate(_chunk(pts, ecl["max_points"])):
        circ.append(dict(key=f"ecl-{i + 1}", cat="ecl", nom=f"Éclairage {i + 1}", det=_uniq(g), n=len(g),
                         unite="points", p=len(g) * ecl["p_point"], in_=ecl["in"], s0=ecl["section"], ks=ecl["ks"],
                         lim=E["limite_du_eclairage"], ib=len(g) * ecl["p_point"] / u))
    for i, g in enumerate(_chunk(pcs, pc["max_prises"])):
        circ.append(dict(key=f"pc-{i + 1}", cat="pc", nom=f"Prises {i + 1}", det=_uniq(g), n=len(g),
                         unite="prises", p=len(g) * pc["p_prise"], in_=pc["in"], s0=pc["section"], ks=pc["ks"],
                         lim=E["limite_du_autres"], ib=pc["ib"]))
    for i, g in enumerate(_chunk(pc_cuis, pcc["max_prises"])):
        circ.append(dict(key=f"pcc-{i + 1}", cat="pc", nom="Prises cuisine" + (f" {i + 1}" if i else ""),
                         det="Dont 4 au plan de travail", n=len(g), unite="prises", p=len(g) * pc["p_prise"],
                         in_=pc["in"], s0=pc["section"], ks=pcc["ks"], lim=E["limite_du_autres"], ib=pc["ib"]))
    cl = E["clim"]
    for p in pieces:
        if p["clim"]:
            circ.append(dict(key=f"clim-{p['id']}", cat="spe", nom=cl["libelle"], det=p["nom"], n=1,
                             unite="appareil", p=cl["p"], in_=cl["in"], s0=cl["section"], ks=cl["ks"],
                             lim=E["limite_du_autres"], ib=cl["p"] / (u * cosphi)))
    for k in E["ordre_specialises"]:
        if equipements.get(k):
            e = E["specialises"][k]
            circ.append(dict(key=f"spe-{k}", cat="spe", nom=e["libelle"], det="Circuit spécialisé", n=1,
                             unite="appareil", p=e["p"], in_=e["in"], s0=e["section"], ks=e["ks"],
                             lim=E["limite_du_autres"], ib=e["p"] / u, type_a=e["type_a"]))

    circuits: list[Circuit] = []
    for c in circ:
        L = longueurs.get(c["key"], longueur_defaut)

        def du(S: float, c=c, L=L) -> float:
            return 2 * rho * L * c["ib"] / S / u * 100

        du0 = du(c["s0"])
        S, etat = c["s0"], "ok"
        if du0 > c["lim"]:
            s_ok = next((x for x in E["sections"] if x >= c["s0"] and du(x) <= c["lim"]), None)
            if s_ok is not None:
                S, etat = s_ok, "warn"
            else:
                S, etat = E["sections"][-1], "bad"
        iz = E["iz"][S]
        if c["in_"] > iz or c["ib"] > c["in_"]:
            etat = "bad"
        circuits.append(Circuit(**c, l=L, du0=du0, s=S, du=du(S), iz=iz, etat=etat))

    surf = sum(p["surface"] for p in pieces)
    s1, s2 = E["id_seuils_surface"]
    n_surf = 1 if surf < s1 else 2 if surf <= s2 else 3
    a = [c for c in circuits if c.type_a]
    rest = [c for c in circuits if not c.type_a]
    n_ac = max(n_surf - (1 if a else 0), math.ceil(len(rest) / E["max_circuits_par_id"]), 1)
    groupes: list[tuple[str, list[Circuit]]] = []
    if a:
        groupes.append(("A", a))
    acs: list[list[Circuit]] = [[] for _ in range(n_ac)]
    for i, c in enumerate(rest):
        acs[i % n_ac].append(c)
    groupes += [("AC", g) for g in acs if g]
    diffs: list[Differentiel] = []
    num = 0
    bas, haut = E["id_calibres"]
    for i, (t, g) in enumerate(groupes):
        nom = f"ID{i + 1}"
        courant = sum(c.ib * c.ks for c in g)
        for c in g:
            num += 1
            c.num, c.id = num, nom
        diffs.append(Differentiel(nom=nom, type=t, circuits=[c.key for c in g], i=courant,
                                  in_=haut if courant > E["id_seuil_calibre"] else bas))

    inst = sum(c.p for c in circuits)
    dem = sum(c.p * c.ks for c in circuits)
    kva = dem * E["foisonnement"] / cosphi / 1000
    i_abo = kva * 1000 / u
    branch = next((b for b in E["branchements"] if b >= i_abo), None)
    bilan = Bilan(surface=surf, p_installee=inst, p_demandee=dem, kva=kva, i_abonnement=i_abo, branchement=branch)
    return circuits, diffs, bilan


# ---------------------------------------------------------------------------
# Placement des symboles et longueurs
# ---------------------------------------------------------------------------


def _zone_porte(o: Ouverture, marge: float = 0.05) -> tuple[float, float, float, float]:
    prof = o.largeur if o.type == "porte" and o.style != "basculante" else 0.6 if o.style == "basculante" else 0.45
    if o.horizontal:
        y0 = o.y + o.sens * o.epaisseur / 2
        y1 = y0 + o.sens * prof
        return (o.x - o.largeur / 2 - marge, min(y0, y1) - marge, o.x + o.largeur / 2 + marge, max(y0, y1) + marge)
    x0 = o.x + o.sens * o.epaisseur / 2
    x1 = x0 + o.sens * prof
    return (min(x0, x1) - marge, o.y - o.largeur / 2 - marge, max(x0, x1) + marge, o.y + o.largeur / 2 + marge)


def _bords_libres(piece: Piece, impl: ResultatImplantation) -> list[tuple[tuple, tuple, list[tuple[float, float]]]]:
    """Pour chaque mur de la pièce : (origine, direction, normale) et intervalles libres pour des prises."""
    n = piece.net
    d_angle = E["distance_prise_angle"]
    bords = [
        ((n.x, n.y), (1, 0), (0, 1), n.l),      # haut
        ((n.x2, n.y), (0, 1), (-1, 0), n.p),    # droite
        ((n.x2, n.y2), (-1, 0), (0, -1), n.l),  # bas
        ((n.x, n.y2), (0, -1), (1, 0), n.p),    # gauche
    ]
    if piece.exterieure:  # véranda : seulement contre la façade
        bords = bords[:1]
    zones = []
    for o in impl.ouvertures:
        if o.type in ("porte", "placard") or o.type == "baie":
            zones.append(_zone_porte(o) if o.type != "baie" else (
                (o.x - o.largeur / 2 - 0.05, o.y - 0.3, o.x + o.largeur / 2 + 0.05, o.y + 0.3) if o.horizontal else
                (o.x - 0.3, o.y - o.largeur / 2 - 0.05, o.x + 0.3, o.y + o.largeur / 2 + 0.05)))
        elif o.type == "fenetre":
            zones.append((o.x - o.largeur / 2, o.y - 0.3, o.x + o.largeur / 2, o.y + 0.3) if o.horizontal else
                         (o.x - 0.3, o.y - o.largeur / 2, o.x + 0.3, o.y + o.largeur / 2))
    resultat = []
    for (ox, oy), (dx, dy), nrm, longueur in bords:
        libres = [(d_angle, longueur - d_angle)] if longueur > 2 * d_angle else []
        for (zx0, zy0, zx1, zy1) in zones:
            # projection de la zone sur ce bord (si elle le touche)
            px, py = ox + nrm[0] * 0.05, oy + nrm[1] * 0.05  # point juste à l'intérieur du bord
            if dx:
                if not (zy0 <= py <= zy1):
                    continue
                t0, t1 = sorted(((zx0 - ox) * dx, (zx1 - ox) * dx))
            else:
                if not (zx0 <= px <= zx1):
                    continue
                t0, t1 = sorted(((zy0 - oy) * dy, (zy1 - oy) * dy))
            nouveaux = []
            for a, b in libres:
                if t1 <= a or t0 >= b:
                    nouveaux.append((a, b))
                    continue
                if t0 > a:
                    nouveaux.append((a, t0))
                if t1 < b:
                    nouveaux.append((t1, b))
            libres = [(a, b) for a, b in nouveaux if b - a > 0.05]
        resultat.append(((ox, oy), (dx, dy), nrm, libres))
    return resultat


def _repartir_prises(piece: Piece, impl: ResultatImplantation, nombre: int) -> list[tuple[float, float, float, float]]:
    """Répartit `nombre` prises le long des murs libres : [(x, y, nx, ny)]."""
    if nombre <= 0:
        return []
    bords = _bords_libres(piece, impl)
    segments = [(o, d, nrm, a, b) for o, d, nrm, libres in bords for a, b in libres]
    total = sum(b - a for *_, a, b in segments)
    retrait = 0.08
    if total <= 0:  # aucun mur libre : prises au centre (cas dégénéré)
        cx, cy = piece.net.centre
        return [(cx, cy, 0.0, -1.0)] * nombre
    pas = total / nombre
    out = []
    for i in range(nombre):
        cible = pas * (i + 0.5)
        for (ox, oy), (dx, dy), nrm, a, b in segments:
            if cible <= b - a:
                t = a + cible
                out.append((ox + dx * t + nrm[0] * retrait, oy + dy * t + nrm[1] * retrait, nrm[0], nrm[1]))
                break
            cible -= b - a
    return out


def _lumieres(piece: Piece, nombre: int) -> list[tuple[float, float]]:
    n = piece.net
    if n.l >= n.p:
        return [(n.x + n.l * (i + 0.5) / nombre, n.y + n.p / 2) for i in range(nombre)]
    return [(n.x + n.l / 2, n.y + n.p * (i + 0.5) / nombre) for i in range(nombre)]


def _interrupteur(o: Ouverture, piece: Piece) -> tuple[float, float]:
    """Côté poignée (opposé à la charnière), côté de la pièce desservie, 15 cm après l'ouverture."""
    d = o.largeur / 2 + 0.15
    signe = -o.charniere
    cote = o.sens if o.piece_id == piece.id else -o.sens
    if o.horizontal:
        return (o.x + signe * d, o.y + cote * (o.epaisseur / 2 + 0.08))
    return (o.x + cote * (o.epaisseur / 2 + 0.08), o.y + signe * d)


def _pieces_pour_prototype(impl: ResultatImplantation, programme: Programme) -> list[dict]:
    out = []
    for pc in _pieces_electriques(impl):
        clim = (pc.type == "chambre" and programme.clim_chambres) or (pc.type == "sejour" and programme.clim_sejour)
        out.append({"id": pc.id, "nom": pc.nom, "type": pc.type, "surface": pc.surface_nette, "clim": clim})
    return out


def placer_points(impl: ResultatImplantation, programme: Programme) -> list[Point]:
    """Tableau, points lumineux, prises (normales et spécialisées) et interrupteurs, avec leur circuit."""
    points: list[Point] = []
    par_id = {p.id: p for p in impl.pieces}

    def ajouter(type_, piece_id, x, y, nx=0.0, ny=0.0, circuit="") -> None:
        points.append(Point(id=f"P{len(points) + 1}", type=type_, piece_id=piece_id, x=x, y=y, nx=nx, ny=ny,
                            circuit=circuit))

    # Tableau près de l'entrée, côté intérieur de la façade du séjour
    entree = next(o for o in impl.ouvertures if o.style == "entree")
    sej = par_id[entree.piece_id]
    face_y = entree.y + entree.sens * (entree.epaisseur / 2 + 0.12)
    tx = entree.x - entree.largeur / 2 - 0.55
    if tx - 0.3 < sej.net.x:
        tx = entree.x + entree.largeur / 2 + 0.55
    ajouter("tableau", sej.id, tx, face_y)

    # Prises spécialisées par pièce (climatiseurs, puis équipements)
    specialises: dict[str, list[str]] = {}
    for pc in _pieces_pour_prototype(impl, programme):
        if pc["clim"]:
            specialises.setdefault(pc["id"], []).append(f"clim-{pc['id']}")
    for k in E["ordre_specialises"]:
        if k in programme.equipements:
            cible = next((p for t in E["piece_specialises"][k] for p in impl.pieces if p.type == t), None)
            if cible is not None:
                specialises.setdefault(cible.id, []).append(f"spe-{k}")

    for pc in _pieces_electriques(impl):
        n_lum, n_pc = nb_points(pc)
        for x, y in _lumieres(pc, n_lum):
            ajouter("lumiere", pc.id, x, y)
        spe = specialises.get(pc.id, [])
        positions = _repartir_prises(pc, impl, n_pc + len(spe))
        # Les prises spécialisées s'intercalent régulièrement parmi les prises normales
        rangs_spe = {round((i + 0.5) * len(positions) / len(spe) - 0.5) for i in range(len(spe))} if spe else set()
        k_spe = 0
        for i, (x, y, nx, ny) in enumerate(positions):
            if i in rangs_spe and k_spe < len(spe):
                ajouter("prise_specialisee", pc.id, x, y, nx, ny, spe[k_spe])
                k_spe += 1
            else:
                ajouter("prise", pc.id, x, y, nx, ny)
        acces = [o for o in impl.ouvertures if o.piece_id == pc.id and o.type in ("porte", "baie")]
        if pc.type in ("sejour", "veranda"):
            acces = [entree]
        if pc.type == "couloir":
            baie = next(o for o in impl.ouvertures if o.type == "baie" and o.piece_id == "SEJ")
            ajouter("interrupteur", pc.id, baie.x - baie.largeur / 2 - 0.15, baie.y - baie.epaisseur / 2 - 0.08)
        elif acces:
            x, y = _interrupteur(acces[0], pc)
            ajouter("interrupteur", pc.id, x, y)
    return points


def calculer(impl: ResultatImplantation, programme: Programme) -> ResultatElectricite:
    pieces = _pieces_pour_prototype(impl, programme)
    equipements = {k: (k in programme.equipements) for k in E["ordre_specialises"]}
    points = placer_points(impl, programme)
    par_id = {p.id: p for p in impl.pieces}

    # Attribution des points aux circuits : mêmes regroupements que le calcul (ordre des pièces)
    lum = [p for p in points if p.type == "lumiere"]
    prises = [p for p in points if p.type == "prise" and par_id[p.piece_id].type != "cuisine"]
    prises_cuis = [p for p in points if p.type == "prise" and par_id[p.piece_id].type == "cuisine"]
    for prefixe, liste, taille in (("ecl", lum, E["eclairage"]["max_points"]),
                                   ("pc", prises, E["prises"]["max_prises"]),
                                   ("pcc", prises_cuis, E["prises_cuisine"]["max_prises"])):
        for i, g in enumerate(_chunk(liste, taille)):
            for p in g:
                p.circuit = f"{prefixe}-{i + 1}"

    # Longueurs : Manhattan tableau → point le plus éloigné, + remontées, + majoration
    tableau = next(p for p in points if p.type == "tableau")
    longueurs: dict[str, float] = {}
    for p in points:
        if not p.circuit:
            continue
        dist = abs(p.x - tableau.x) + abs(p.y - tableau.y)
        longueurs[p.circuit] = max(longueurs.get(p.circuit, 0.0), dist)
    longueurs = {k: (v + E["longueur_remontees"]) * (1 + E["majoration_longueur"]) for k, v in longueurs.items()}
    longueurs.update(programme.longueurs_circuits)
    defaut = max(longueurs.values()) if longueurs else 15.0

    circuits, diffs, bilan = calculer_circuits(pieces, equipements, longueurs, defaut)

    # Interrupteurs : rattachés au circuit d'éclairage de leur pièce
    for p in points:
        if p.type == "interrupteur":
            p.circuit = next((q.circuit for q in points if q.type == "lumiere" and q.piece_id == p.piece_id), "")

    controles = _controles(circuits, diffs, bilan, pieces, programme)
    hyp = _hypotheses()
    return ResultatElectricite(circuits=circuits, differentiels=diffs, bilan=bilan, points=points,
                               controles=controles, hypotheses=hyp)


def _nom_circuit(c: Circuit) -> str:
    suffixe = f" – {c.det}" if c.cat == "spe" and c.det != "Circuit spécialisé" else ""
    return f"C{c.num} · {c.nom}{suffixe}"


def _controles(circuits, diffs, bilan, pieces, programme) -> list[Controle]:
    out: list[Controle] = []

    def c(id_, niveau, titre, detail):
        out.append(Controle(id=id_, module=MODULE, niveau=niveau, titre=titre, detail=detail, reference_norme=REF))

    for ci in sorted(circuits, key=lambda x: x.num):
        nom = _nom_circuit(ci)
        if ci.etat == "bad" and (ci.in_ > ci.iz or ci.ib > ci.in_):
            c(f"ELEC-PROT-C{ci.num}", "bloquant", f"{nom} : protection incompatible",
              f"Ib {fmt(ci.ib, 1)} A, In {ci.in_} A, Iz {fmt(ci.iz, 1)} A. Il faut Ib ≤ In ≤ Iz.")
        elif ci.etat == "bad":
            c(f"ELEC-DU-C{ci.num}", "bloquant", f"{nom} : chute de tension excessive",
              f"{fmt(ci.du)} % même en 16 mm² sur {fmt(ci.l, 1)} m (limite {fmt(ci.lim, 0)} %). "
              "Rapprocher le tableau ou créer un sous-tableau.")
        elif ci.etat == "warn":
            c(f"ELEC-DU-C{ci.num}", "avertissement", f"{nom} : section augmentée",
              f"{fmt(ci.s0, 1)} → {fmt(ci.s, 1)} mm² pour tenir la chute de tension ({fmt(ci.du0)} % → "
              f"{fmt(ci.du)} %, limite {fmt(ci.lim, 0)} %) sur {fmt(ci.l, 1)} m.")
        else:
            c(f"ELEC-C{ci.num}", "ok", nom,
              f"{fmt(ci.s, 1)} mm², disjoncteur {ci.in_} A, ΔU {fmt(ci.du)} % ≤ {fmt(ci.lim, 0)} %.")
    for d in diffs:
        n = len(d.circuits)
        c(f"ELEC-{d.nom}", "ok", f"{d.nom} · interrupteur différentiel 30 mA type {d.type}",
          f"{n} circuit{'s' if n > 1 else ''} ({E['max_circuits_par_id']} maximum), calibre {d.in_} A pour "
          f"{fmt(d.i, 1)} A estimés.")
    if any(ci.type_a for ci in circuits):
        c("ELEC-TYPE-A", "ok", "Différentiel type A pour plaque et lave-linge",
          "Ces circuits sont regroupés sous un interrupteur différentiel de type A.")
    if not pieces:
        c("ELEC-PIECES", "bloquant", "Aucune pièce saisie", "Ajoutez au moins une pièce pour générer l'installation.")
    r = programme.resistance_terre
    if r is None:
        c("ELEC-TERRE", "bloquant", "Prise de terre : mesure requise",
          "Saisissez la résistance de terre mesurée sur site.")
    elif r <= E["terre_ok"]:
        c("ELEC-TERRE", "ok", "Prise de terre", f"{fmt(r, 0)} Ω ≤ {fmt(E['terre_ok'], 0)} Ω recommandés.")
    elif r <= E["terre_max"]:
        c("ELEC-TERRE", "avertissement", "Prise de terre à améliorer",
          f"{fmt(r, 0)} Ω > {fmt(E['terre_ok'], 0)} Ω. Ajouter des piquets ou une boucle à fond de fouille.")
    else:
        c("ELEC-TERRE", "bloquant", "Prise de terre insuffisante",
          f"{fmt(r, 0)} Ω : la protection des personnes n'est pas assurée de façon fiable.")
    if bilan.branchement is None:
        c("ELEC-BRANCHEMENT", "avertissement", "Puissance élevée pour un branchement monophasé",
          f"{fmt(bilan.i_abonnement, 1)} A appelés. Étudier un branchement triphasé 400 V.")
    else:
        c("ELEC-BRANCHEMENT", "ok", "Branchement",
          f"Disjoncteur de branchement {bilan.branchement} A, {E['differentiel_branchement_ma']} mA, pour "
          f"{fmt(bilan.kva, 1)} kVA appelés.")
    if any(p["type"] == "sdb" for p in pieces):
        c("ELEC-SDB", "avertissement", "Salle de bains : volumes à vérifier sur plan",
          "Aucune prise ni interrupteur dans les volumes 0, 1 et 2 ; liaison équipotentielle locale.")
    if any(p["type"] == "veranda" for p in pieces):
        c("ELEC-EXT", "avertissement", "Extérieur : indice de protection", "Prises et luminaires extérieurs IP44 minimum.")
    c("ELEC-PARAFOUDRE", "avertissement", "Parafoudre",
      "Recommandé en tête de tableau dans les zones à forte activité orageuse.")
    return out


def _hypotheses() -> list[Hypothese]:
    def h(lib, val):
        return Hypothese(module=MODULE, libelle=lib, valeur=val, source=REF)

    return [
        h("Tension, réseau", "230 V mono, cos φ 0,9"),
        h("Résistivité du cuivre en service", "0,023 Ω·mm²/m"),
        h("Chute de tension admise", "éclairage 3 %, autres 5 %"),
        h("Puissance par point lumineux", "100 W"),
        h("Courant d'emploi d'un circuit prises", "16 A (0,8 × In)"),
        h("Éclairage", "1,5 mm², 16 A, 8 points max"),
        h("Prises", "2,5 mm², 20 A, 12 prises max"),
        h("Courant admissible Iz", "méthode B, PVC, 2 conducteurs"),
        h("Coefficients de simultanéité", "prises 0,25 ; cuisson 0,7 ; clim 0,8"),
        h("Foisonnement général du logement", "0,6"),
        h("Différentiels", "≤ 8 circuits par ID ; nombre selon surface"),
        h("Prises par pièce", "séjour 1 / 4 m² (min 5) ; chambre 3 ; cuisine 6"),
        h("Longueur d'un circuit", "Manhattan tableau → point le plus éloigné + 2 m de remontées + 10 %"),
    ]
