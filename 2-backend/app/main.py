"""API REST FastAPI (CdC § 9)."""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time
from pathlib import Path
from time import perf_counter

from apiconnect import nano_banana
from apiconnect.erreurs import ErreurIA, IAIndisponible, IANonConfiguree
from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config as config_mod
from app import ia, orchestrateur, schemas, stockage
from app.auth import ErreurApi, creer_jeton, exiger_role, hacher, utilisateur_courant, verifier
from app.moteurs import chaine
from app.moteurs.normes import VERSION_MOTEURS
from app.moteurs.programme import Programme
from app.moteurs.regles import MODULES
from app.rendu import dxf, images, pdf, plan_svg, rapport, unifilaire, xlsx
from app.stockage import PrixMateriau, Projet, Rendu, Utilisateur, Validation

log = logging.getLogger("api")
cfg = config_mod.charger()


@asynccontextmanager
async def cycle_de_vie(_app: FastAPI):
    config_mod.charger().verifier()
    stockage.configurer(config_mod.charger().database_url)
    stockage.initialiser()
    yield


app = FastAPI(title="Assistant Plan Ingénierie", version=VERSION_MOTEURS, docs_url="/api/docs",
              openapi_url="/api/openapi.json", lifespan=cycle_de_vie)
app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ---------------------------------------------------------------------------
# Erreurs au format {code, message}
# ---------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def _erreur_http(_req: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        corps = exc.detail
    else:
        messages = {404: "Ressource introuvable.", 405: "Méthode non autorisée."}
        corps = {"code": "erreur", "message": messages.get(exc.status_code, str(exc.detail))}
    return JSONResponse(corps, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def _erreur_validation(_req: Request, exc: RequestValidationError):
    details = [f"{'.'.join(str(x) for x in e['loc'][1:]) or 'corps'} : {e['msg']}" for e in exc.errors()]
    return JSONResponse({"code": "donnees_invalides", "message": "Données invalides. " + " ; ".join(details)},
                        status_code=422)


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _utilisateur(u: Utilisateur) -> dict:
    return schemas.UtilisateurSortie(id=u.id, email=u.email, nom=u.nom, role=u.role,
                                     numero_ordre=u.numero_ordre).model_dump()


def _charger(s: Session, projet_id: int, u: Utilisateur, ecriture: bool = False) -> Projet:
    p = s.get(Projet, projet_id)
    if p is None:
        raise ErreurApi(404, "projet_introuvable", "Projet introuvable.")
    lecture_libre = u.role in ("ingenieur", "admin")
    if p.proprietaire_id != u.id and (ecriture and u.role != "admin" or not ecriture and not lecture_libre):
        raise ErreurApi(403, "acces_refuse", "Vous n'avez pas accès à ce projet.")
    return p


def _iso(d: datetime) -> str:
    """SQLite rend des dates sans fuseau : elles sont en UTC, on l'indique toujours."""
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).isoformat()


def _validations(s: Session, p: Projet) -> list[dict]:
    vs = s.scalars(select(Validation).where(Validation.projet_id == p.id).order_by(Validation.date)).all()
    return [{"id": v.id, "module": v.module, "ingenieur_id": v.ingenieur_id, "nom": v.nom,
             "numero_ordre": v.numero_ordre, "empreinte": v.empreinte, "date": _iso(v.date),
             "commentaire": v.commentaire, "encore_valide": v.empreinte == p.empreinte} for v in vs]


def _resume(p: Projet) -> dict:
    return {"id": p.id, "nom": p.nom, "statut": p.statut, "cree_le": _iso(p.cree_le),
            "modifie_le": _iso(p.modifie_le), "proprietaire_id": p.proprietaire_id, "version": p.version}


def _detail(s: Session, p: Projet) -> dict:
    return {**_resume(p), "texte_initial": p.texte_initial, "programme": p.programme, "resultats": p.resultats,
            "empreinte": p.empreinte, "journal_ia": p.journal_ia, "remarques": p.remarques,
            "version_moteurs": p.version_moteurs, "validations": _validations(s, p)}


def _appliquer(p: Projet, res: dict) -> None:
    resultats: chaine.Resultats = res["resultats"]
    p.programme = res["programme"].model_dump(mode="json")
    p.resultats = resultats.model_dump(mode="json")
    p.statut = resultats.statut
    p.empreinte = res["empreinte"]
    p.version_moteurs = VERSION_MOTEURS
    p.modifie_le = datetime.now(UTC)


def _statut_cartouche(s: Session, p: Projet, module: str = "implantation") -> str:
    v = next((v for v in _validations(s, p) if v["module"] == module and v["encore_valide"]), None)
    if v is None:
        return "À valider par un ingénieur"
    return f"Signé par {v['nom']}" + (f" (n° {v['numero_ordre']})" if v["numero_ordre"] else "")


# ---------------------------------------------------------------------------
# Santé et authentification
# ---------------------------------------------------------------------------

@app.get("/api/sante", tags=["système"])
def sante() -> dict:
    c = config_mod.charger()
    return {"etat": "ok", "version_moteurs": VERSION_MOTEURS, "ia_texte_configuree": c.ia_texte_configuree,
            "ia_image_configuree": c.ia_image_configuree}


@app.post("/api/auth/inscription", tags=["auth"], status_code=201)
def inscription(d: schemas.Inscription, s: Session = Depends(stockage.session)) -> schemas.SessionUtilisateur:
    email = d.email.strip().lower()
    if s.scalar(select(Utilisateur).where(Utilisateur.email == email)):
        raise ErreurApi(409, "email_existant", "Un compte existe déjà avec cet email.")
    admin = os.getenv("ADMIN_EMAIL", "").strip().lower()
    u = Utilisateur(email=email, nom=d.nom.strip(), mot_de_passe_hache=hacher(d.mot_de_passe),
                    role="admin" if admin and email == admin else "constructeur")
    s.add(u)
    s.commit()
    return schemas.SessionUtilisateur(jeton=creer_jeton(u), utilisateur=_utilisateur(u))


@app.post("/api/auth/connexion", tags=["auth"])
def connexion(d: schemas.Connexion, s: Session = Depends(stockage.session)) -> schemas.SessionUtilisateur:
    u = s.scalar(select(Utilisateur).where(Utilisateur.email == d.email.strip().lower()))
    if u is None or not verifier(d.mot_de_passe, u.mot_de_passe_hache):
        raise ErreurApi(401, "identifiants_invalides", "Email ou mot de passe incorrect.")
    return schemas.SessionUtilisateur(jeton=creer_jeton(u), utilisateur=_utilisateur(u))


@app.get("/api/auth/moi", tags=["auth"])
def moi(u: Utilisateur = Depends(utilisateur_courant)) -> dict:
    return _utilisateur(u)


# ---------------------------------------------------------------------------
# IA et projets
# ---------------------------------------------------------------------------

@app.post("/api/ia/interpreter", tags=["ia"])
def interpreter(d: schemas.DemandeInterpreter, _u: Utilisateur = Depends(utilisateur_courant),
                client=Depends(ia.client_texte)) -> dict:
    journal = orchestrateur.Journal()
    prog, remarques = orchestrateur.interpreter(d.texte, client, journal)
    return {"programme": prog.model_dump(mode="json"), "remarques": remarques,
            "source": journal.entrees[-1]["modele"]}


@app.post("/api/projets/generer", tags=["projets"], status_code=201)
def generer(d: schemas.DemandeGenerer, reponse: Response, u: Utilisateur = Depends(utilisateur_courant),
            s: Session = Depends(stockage.session), client=Depends(ia.client_texte)) -> dict:
    if not d.texte and d.programme is None:
        raise ErreurApi(422, "donnees_invalides", "Fournissez une description (texte) ou un programme.")
    existant = _charger(s, d.projet_id, u, ecriture=True) if d.projet_id is not None else None
    res = orchestrateur.generer(d.texte, d.programme, client, stockage.table_prix(s))
    if existant is not None:
        p = existant
        if d.nom:
            p.nom = d.nom
        p.texte_initial = d.texte or p.texte_initial
        p.remarques = res["remarques"]
        p.journal_ia = [*p.journal_ia, *res["journal_ia"]]
        p.version += 1
        reponse.status_code = 200
    else:
        nom = d.nom or (d.texte or "").strip().split(",")[0][:80] or res["programme"].nom
        p = Projet(proprietaire_id=u.id, nom=nom, texte_initial=d.texte or "", remarques=res["remarques"],
                   journal_ia=res["journal_ia"])
        s.add(p)
    _appliquer(p, res)
    s.commit()
    return {**_detail(s, p), "corrections": res["corrections"]}


@app.get("/api/projets", tags=["projets"])
def lister(u: Utilisateur = Depends(utilisateur_courant), s: Session = Depends(stockage.session)) -> list[dict]:
    q = select(Projet).order_by(Projet.modifie_le.desc())
    if u.role == "constructeur":
        q = q.where(Projet.proprietaire_id == u.id)
    return [_resume(p) for p in s.scalars(q)]


@app.get("/api/projets/{projet_id}", tags=["projets"])
def detail(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
           s: Session = Depends(stockage.session)) -> dict:
    return _detail(s, _charger(s, projet_id, u))


@app.put("/api/projets/{projet_id}/programme", tags=["projets"])
def modifier_programme(projet_id: int, programme: Programme, u: Utilisateur = Depends(utilisateur_courant),
                       s: Session = Depends(stockage.session)) -> dict:
    """Modifie le programme : recalcul complet ; les validations existantes ne sont plus valides."""
    p = _charger(s, projet_id, u, ecriture=True)
    res = orchestrateur.generer(None, programme, None, stockage.table_prix(s))
    _appliquer(p, res)
    p.version += 1
    s.commit()
    return _detail(s, p)


@app.post("/api/projets/{projet_id}/expliquer", tags=["ia"])
def expliquer(projet_id: int, d: schemas.DemandeExpliquer, u: Utilisateur = Depends(utilisateur_courant),
              s: Session = Depends(stockage.session), client=Depends(ia.client_texte)) -> dict:
    """Explique un contrôle ou un circuit en français simple. L'IA ne change aucune valeur."""
    p = _charger(s, projet_id, u)
    ctx = orchestrateur.contexte_element(p.resultats, d.element_id)
    if ctx is None:
        raise ErreurApi(404, "element_introuvable", f"Aucun contrôle ni circuit « {d.element_id} » dans ce projet.")
    journal = orchestrateur.Journal()
    texte, source = orchestrateur.expliquer(ctx, client, journal)
    if journal.entrees:
        # Journal seulement : la date de modification du projet ne change pas
        s.execute(update(Projet).where(Projet.id == p.id)
                  .values(journal_ia=[*p.journal_ia, *journal.entrees], modifie_le=Projet.modifie_le))
        s.commit()
    return {"element_id": d.element_id, "texte": texte, "source": source}


@app.delete("/api/projets/{projet_id}", tags=["projets"], status_code=204)
def supprimer(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
              s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u, ecriture=True)
    for v in s.scalars(select(Validation).where(Validation.projet_id == p.id)):
        s.delete(v)
    for r in s.scalars(select(Rendu).where(Rendu.projet_id == p.id)):
        Path(r.chemin_fichier).unlink(missing_ok=True)
        s.delete(r)
    s.delete(p)
    s.commit()
    return Response(status_code=204)


@app.get("/api/projets/{projet_id}/plan.svg", tags=["exports"])
def plan(projet_id: int, calques: str | None = Query(None, description="ex. murs,cotes,elec"),
         u: Utilisateur = Depends(utilisateur_courant), s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u)
    r = chaine.Resultats.model_validate(p.resultats)
    liste = [c.strip() for c in calques.split(",")] if calques else None
    if liste and any(c not in plan_svg.CALQUES for c in liste):
        raise ErreurApi(422, "calque_inconnu", f"Calques possibles : {', '.join(plan_svg.CALQUES)}.")
    svg = plan_svg.rendre_plan(r.implantation, nom_projet=p.nom, date=p.modifie_le.date().isoformat(),
                               version=str(p.version), statut=_statut_cartouche(s, p), calques=liste,
                               elec=r.electricite.model_dump(), structure=r.structure.model_dump())
    return Response(svg, media_type="image/svg+xml")


@app.get("/api/projets/{projet_id}/unifilaire.svg", tags=["exports"])
def schema_unifilaire(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
                      s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u)
    r = chaine.Resultats.model_validate(p.resultats)
    return Response(unifilaire.rendre(r.electricite), media_type="image/svg+xml")


@app.get("/api/projets/{projet_id}/rapport.txt", tags=["exports"])
def rapport_txt(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
                s: Session = Depends(stockage.session)) -> PlainTextResponse:
    p = _charger(s, projet_id, u)
    valides = [v for v in _validations(s, p) if v["encore_valide"]]
    texte = rapport.rendre(_detail(s, p), valides)
    return PlainTextResponse(texte, headers={"Content-Disposition": f'attachment; filename="rapport-{p.id}.txt"'})


def _signes(s: Session, p: Projet) -> list[dict]:
    return [v for v in _validations(s, p) if v["encore_valide"]]


@app.get("/api/projets/{projet_id}/plan.dxf", tags=["exports"])
def plan_dxf(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
             s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u)
    r = chaine.Resultats.model_validate(p.resultats)
    contenu = dxf.exporter(r.implantation, nom_projet=p.nom, statut=_statut_cartouche(s, p),
                           elec=r.electricite.model_dump(), structure=r.structure.model_dump())
    return Response(contenu, media_type="application/dxf",
                    headers={"Content-Disposition": f'attachment; filename="plan-{p.id}.dxf"'})


@app.get("/api/projets/{projet_id}/dossier.pdf", tags=["exports"])
def dossier_pdf(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
                s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u)
    r = chaine.Resultats.model_validate(p.resultats)
    contenu = pdf.rendre({"nom": p.nom, "version": p.version, "empreinte": p.empreinte,
                          "modifie_le": _iso(p.modifie_le), "version_moteurs": p.version_moteurs}, r, _signes(s, p))
    return Response(contenu, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="dossier-{p.id}.pdf"'})


@app.get("/api/projets/{projet_id}/metre.xlsx", tags=["exports"])
def metre_xlsx(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
               s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u)
    r = chaine.Resultats.model_validate(p.resultats)
    signes = {v["module"] for v in _signes(s, p)}
    contenu = xlsx.rendre(p.nom, r, all(m in signes for m in MODULES))
    return Response(contenu, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="metre-{p.id}.xlsx"'})


# ---------------------------------------------------------------------------
# Rendus de présentation Nano Banana (CdC § 8)
# ---------------------------------------------------------------------------

def _rendus_du_jour(s: Session, u: Utilisateur) -> int:
    debut = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    return s.scalar(select(func.count()).select_from(Rendu)
                    .where(Rendu.utilisateur_id == u.id, Rendu.date >= debut)) or 0


def _rendu(r: Rendu) -> dict:
    return {"id": r.id, "style": r.style, "libelle": nano_banana.LIBELLES_STYLES.get(r.style, r.style),
            "date": _iso(r.date), "modele": r.modele, "mention": images.MENTION,
            "url": f"/api/projets/{r.projet_id}/rendus/{r.id}.jpg"}


@app.get("/api/projets/{projet_id}/rendus", tags=["rendus"])
def lister_rendus(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
                  s: Session = Depends(stockage.session)) -> dict:
    p = _charger(s, projet_id, u)
    cfg = config_mod.charger()
    rs = s.scalars(select(Rendu).where(Rendu.projet_id == p.id).order_by(Rendu.date.desc())).all()
    return {"rendus": [_rendu(r) for r in rs], "styles": nano_banana.LIBELLES_STYLES,
            "ia_image_configuree": cfg.ia_image_configuree,
            "quota": {"max": cfg.rendus_max_par_jour, "utilises": _rendus_du_jour(s, u)}}


@app.post("/api/projets/{projet_id}/rendus", tags=["rendus"], status_code=201)
def creer_rendu(projet_id: int, d: schemas.DemandeRendu, u: Utilisateur = Depends(utilisateur_courant),
                s: Session = Depends(stockage.session), client=Depends(ia.client_image)) -> dict:
    """Image de présentation à partir du plan exact rasterisé par le navigateur. Non contractuelle."""
    p = _charger(s, projet_id, u)
    cfg = config_mod.charger()
    if client is None:
        raise ErreurApi(503, "ia_image_non_configuree",
                        "Les rendus IA sont désactivés : aucune clé du service d'images n'est configurée.")
    if d.style not in nano_banana.STYLES:
        raise ErreurApi(422, "style_inconnu", f"Styles possibles : {', '.join(nano_banana.STYLES)}.")
    if _rendus_du_jour(s, u) >= cfg.rendus_max_par_jour:
        raise ErreurApi(429, "quota_atteint",
                        f"Quota atteint : {cfg.rendus_max_par_jour} rendus par jour. Réessayez demain.")
    try:
        image_b64, _taille = images.lire_png_base64(d.image_base64)
    except images.ImageInvalide as e:
        raise ErreurApi(422, "image_invalide", str(e)) from e

    impl = p.resultats["implantation"]
    pieces = [{"nom": x["nom"], "largeur": x["net"]["l"], "profondeur": x["net"]["p"], "surface": x["surface_nette"]}
              for x in impl["pieces"]]
    toit = p.resultats["toiture"]
    toiture = f"{toit['type']}, {toit['couverture']}" + (f", pente {toit['pente']:.0f} %" if toit["type"] != "terrasse" else "")
    journal = orchestrateur.Journal()
    debut = perf_counter()
    try:
        rendu = client.generer_rendu(image_b64, d.style, pieces, toiture)
    except ErreurIA as e:
        journal.ajouter("rendre", {"style": d.style}, f"erreur : {e.__class__.__name__}", client.modele, debut,
                        erreur=True)
        s.execute(update(Projet).where(Projet.id == p.id)
                  .values(journal_ia=[*p.journal_ia, *journal.entrees], modifie_le=Projet.modifie_le))
        s.commit()
        if isinstance(e, IANonConfiguree):
            raise ErreurApi(503, "ia_image_non_configuree", e.message) from e
        if isinstance(e, IAIndisponible):
            raise ErreurApi(503, "ia_image_indisponible", nano_banana.MESSAGE_INDISPONIBLE) from e
        raise ErreurApi(502, "rendu_invalide", e.message) from e
    try:
        jpeg = images.ajouter_mention(rendu.image)
    except Exception as e:
        raise ErreurApi(502, "rendu_invalide", "Le service d'images a renvoyé une image illisible.") from e

    dossier = Path(cfg.stockage_rendus) / str(p.id)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{uuid.uuid4().hex}.jpg"
    chemin.write_bytes(jpeg)
    r = Rendu(projet_id=p.id, utilisateur_id=u.id, style=d.style, chemin_fichier=str(chemin), prompt=rendu.prompt,
              modele=rendu.modele)
    s.add(r)
    journal.ajouter("rendre", {"style": d.style}, f"image {len(jpeg)} octets", rendu.modele, debut)
    s.execute(update(Projet).where(Projet.id == p.id)
              .values(journal_ia=[*p.journal_ia, *journal.entrees], modifie_le=Projet.modifie_le))
    s.commit()
    return _rendu(r)


@app.get("/api/projets/{projet_id}/rendus/{rendu_id}.jpg", tags=["rendus"])
def image_rendu(projet_id: int, rendu_id: int, u: Utilisateur = Depends(utilisateur_courant),
                s: Session = Depends(stockage.session)) -> FileResponse:
    p = _charger(s, projet_id, u)
    r = s.get(Rendu, rendu_id)
    if r is None or r.projet_id != p.id or not Path(r.chemin_fichier).is_file():
        raise ErreurApi(404, "rendu_introuvable", "Image introuvable.")
    return FileResponse(r.chemin_fichier, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400"})


@app.delete("/api/projets/{projet_id}/rendus/{rendu_id}", tags=["rendus"], status_code=204)
def supprimer_rendu(projet_id: int, rendu_id: int, u: Utilisateur = Depends(utilisateur_courant),
                    s: Session = Depends(stockage.session)) -> Response:
    p = _charger(s, projet_id, u, ecriture=True)
    r = s.get(Rendu, rendu_id)
    if r is None or r.projet_id != p.id:
        raise ErreurApi(404, "rendu_introuvable", "Image introuvable.")
    Path(r.chemin_fichier).unlink(missing_ok=True)
    s.delete(r)
    s.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Validations par l'ingénieur
# ---------------------------------------------------------------------------

@app.post("/api/projets/{projet_id}/validations", tags=["validations"], status_code=201)
def valider(projet_id: int, d: schemas.DemandeValidation,
            u: Utilisateur = Depends(exiger_role("ingenieur")), s: Session = Depends(stockage.session)) -> dict:
    p = _charger(s, projet_id, u)
    r = p.resultats
    bloquants = [c for c in r["controles"] if c["module"] == d.module and c["niveau"] == "bloquant"]
    if bloquants:
        raise ErreurApi(409, "module_bloque",
                        f"Validation impossible : {len(bloquants)} point(s) bloquant(s) dans le module {d.module}.")
    v = Validation(projet_id=p.id, module=d.module, ingenieur_id=u.id, nom=u.nom, numero_ordre=u.numero_ordre,
                   empreinte=p.empreinte, commentaire=d.commentaire)
    s.add(v)
    s.commit()
    return next(x for x in _validations(s, p) if x["id"] == v.id)


@app.get("/api/projets/{projet_id}/validations", tags=["validations"])
def lister_validations(projet_id: int, u: Utilisateur = Depends(utilisateur_courant),
                       s: Session = Depends(stockage.session)) -> dict:
    p = _charger(s, projet_id, u)
    vs = _validations(s, p)
    return {"validations": vs, "modules": {m: any(v["module"] == m and v["encore_valide"] for v in vs)
                                           for m in MODULES}}


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------

@app.get("/api/admin/prix", tags=["admin"])
def prix(_u: Utilisateur = Depends(exiger_role("admin")), s: Session = Depends(stockage.session)) -> list[dict]:
    return [{"code": x.code, "libelle": x.libelle, "unite": x.unite, "prix": x.prix, "devise": x.devise,
             "mis_a_jour_le": _iso(x.mis_a_jour_le)} for x in s.scalars(select(PrixMateriau)
                                                                              .order_by(PrixMateriau.code))]


@app.put("/api/admin/prix", tags=["admin"])
def modifier_prix(entrees: list[schemas.PrixEntree], u: Utilisateur = Depends(exiger_role("admin")),
                  s: Session = Depends(stockage.session)) -> list[dict]:
    for e in entrees:
        x = s.get(PrixMateriau, e.code)
        if x is None:
            if not (e.libelle and e.unite):
                raise ErreurApi(422, "prix_incomplet", f"Nouveau poste « {e.code} » : libellé et unité requis.")
            x = PrixMateriau(code=e.code, libelle=e.libelle, unite=e.unite, prix=e.prix, devise=e.devise or "USD")
            s.add(x)
        else:
            x.prix = e.prix
            x.libelle = e.libelle or x.libelle
            x.unite = e.unite or x.unite
            x.devise = e.devise or x.devise
        x.mis_a_jour_le = datetime.now(UTC)
    s.commit()
    return prix(u, s)


@app.get("/api/admin/utilisateurs", tags=["admin"])
def utilisateurs(_u: Utilisateur = Depends(exiger_role("admin")),
                 s: Session = Depends(stockage.session)) -> list[dict]:
    return [_utilisateur(x) for x in s.scalars(select(Utilisateur).order_by(Utilisateur.id))]


@app.put("/api/admin/utilisateurs/{utilisateur_id}", tags=["admin"])
def modifier_utilisateur(utilisateur_id: int, d: schemas.ModifUtilisateur,
                         _u: Utilisateur = Depends(exiger_role("admin")),
                         s: Session = Depends(stockage.session)) -> dict:
    x = s.get(Utilisateur, utilisateur_id)
    if x is None:
        raise ErreurApi(404, "utilisateur_introuvable", "Utilisateur introuvable.")
    x.role, x.numero_ordre = d.role, d.numero_ordre
    s.commit()
    return _utilisateur(x)
