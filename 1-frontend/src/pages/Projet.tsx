import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { api, ErreurApi } from "../api/client";
import BarreIA, { type Bilan } from "../components/BarreIA";
import { Chargement, MessageErreur, Pastille } from "../components/Etat";
import { naviguer } from "../lib/routes";
import { nomFichier, telecharger } from "../lib/telecharger";
import { MODULES, type Programme, type Projet as TProjet, type Utilisateur } from "../types";

// Onglets chargés à la demande
const OngletPlan = lazy(() => import("../components/OngletPlan"));
const ProgrammeForm = lazy(() => import("../components/ProgrammeForm"));
const Electricite = lazy(() => import("../components/Electricite"));
const OngletValidation = lazy(() => import("../components/OngletValidation"));
const Structure = lazy(() => import("../components/Structure"));
const Toiture = lazy(() => import("../components/Toiture"));
const Solaire = lazy(() => import("../components/Solaire"));
const Metre = lazy(() => import("../components/Metre"));

const ONGLETS = [
  { id: "plan", libelle: "Plan" },
  { id: "programme", libelle: "Programme" },
  { id: "electricite", libelle: "Électricité" },
  { id: "structure", libelle: "Structure" },
  { id: "toiture", libelle: "Toiture" },
  { id: "solaire", libelle: "Solaire" },
  { id: "metre", libelle: "Métré & devis" },
  { id: "validation", libelle: "Validation" },
] as const;
type Onglet = (typeof ONGLETS)[number]["id"];

// Bilan de la dernière génération, conservé quand « nouveau projet » devient la page du projet créé
const bilans = new Map<number, Bilan>();

interface Props {
  id?: number;
  onglet?: string;
  utilisateur: Utilisateur;
}

export default function Projet({ id, onglet, utilisateur }: Props) {
  const [projet, setProjet] = useState<TProjet | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [bilan, setBilan] = useState<Bilan | null>(() => (id !== undefined ? (bilans.get(id) ?? null) : null));
  const [iaConfiguree, setIaConfiguree] = useState<boolean | null>(null);
  const actif: Onglet = (ONGLETS.find((o) => o.id === onglet)?.id ?? "plan") as Onglet;

  useEffect(() => {
    api
      .sante()
      .then((s) => setIaConfiguree(s.ia_texte_configuree))
      .catch(() => setIaConfiguree(null));
  }, []);

  const charger = useCallback(() => {
    if (id === undefined) return;
    setErreur(null);
    api
      .projet(id)
      .then(setProjet)
      .catch((e) => setErreur(e instanceof ErreurApi ? e.message : "Erreur inattendue."));
  }, [id]);
  useEffect(charger, [charger]);

  const peutModifier = projet !== null && (projet.proprietaire_id === utilisateur.id || utilisateur.role === "admin");

  async function executer(action: () => Promise<TProjet>) {
    setEnCours(true);
    setErreur(null);
    try {
      const p = await action();
      setProjet(p);
      return p;
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Erreur inattendue.");
      return null;
    } finally {
      setEnCours(false);
    }
  }

  async function generer(texte: string) {
    setBilan(null);
    const debut = Date.now() - 2000; // dates du journal à la seconde près
    const p = await executer(() => api.generer(texte, projet?.id));
    if (!p) return;
    const b: Bilan = {
      journal: p.journal_ia.filter((e) => new Date(e.date).getTime() >= debut),
      corrections: p.corrections ?? [],
      remarques: p.remarques,
      bloquants: p.resultats.controles.filter((c) => c.niveau === "bloquant").length,
    };
    bilans.set(p.id, b);
    setBilan(b);
    if (id === undefined) naviguer({ page: "projet", id: p.id, onglet: "plan" }, true);
  }

  const recalculer = (programme: Programme) => {
    if (projet) void executer(() => api.modifierProgramme(projet.id, programme));
  };

  const changerOnglet = (o: Onglet) => projet && naviguer({ page: "projet", id: projet.id, onglet: o }, true);

  const exporterPlan = async () => {
    if (!projet) return;
    try {
      telecharger(await api.planSvg(projet.id, ["murs", "textes", "cotes", "annotations"]), nomFichier(projet.nom, "svg"), "image/svg+xml");
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Export impossible.");
    }
  };
  const exporterRapport = async () => {
    if (!projet) return;
    try {
      telecharger(await api.rapport(projet.id), nomFichier(projet.nom + "-rapport", "txt"), "text/plain;charset=utf-8");
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Export impossible.");
    }
  };

  const tousSignes = projet !== null && MODULES.every((m) => projet.validations.some((v) => v.module === m && v.encore_valide));
  const aDesSignatures = projet !== null && projet.validations.some((v) => v.encore_valide);

  if (id !== undefined && !projet && !erreur) return <Chargement texte="Chargement du projet…" />;

  return (
    <main className="page page-projet">
      <div className="entete-projet">
        <div>
          <a className="lien petit" href="#/projets">
            ← Projets
          </a>
          <h1>{projet ? projet.nom : "Nouveau projet"}</h1>
          {projet && (
            <div className="entete-etat">
              <Pastille statut={projet.resultats.statut} />
              <span className="texte-2 petit">version {projet.version}</span>
            </div>
          )}
        </div>
        {projet && (
          <div className="exports" role="group" aria-label="Exports">
            <button className="bouton" onClick={exporterPlan}>
              Exporter le plan (SVG)
            </button>
            <button className="bouton" onClick={exporterRapport}>
              Rapport (TXT)
            </button>
            <button
              className="bouton bouton-principal"
              disabled={!tousSignes}
              onClick={exporterRapport}
              title={tousSignes ? "Tous les modules sont signés" : "Disponible quand tous les modules sont signés par un ingénieur"}
            >
              Bon pour exécution
            </button>
          </div>
        )}
      </div>

      {(projet === null || peutModifier) && (
        <BarreIA texteInitial={projet?.texte_initial ?? ""} iaConfiguree={iaConfiguree} enCours={enCours} bilan={bilan} onGenerer={generer} />
      )}
      {erreur && <MessageErreur message={erreur} onReessayer={projet ? undefined : id !== undefined ? charger : undefined} />}

      {projet && (
        <>
          <nav className="onglets" aria-label="Onglets du projet">
            <div className="onglets-liste" role="tablist">
              {ONGLETS.map((o) => (
                <button key={o.id} role="tab" aria-selected={actif === o.id} className={actif === o.id ? "actif" : ""} onClick={() => changerOnglet(o.id)}>
                  {o.libelle}
                </button>
              ))}
            </div>
            <label className="onglets-menu">
              <span className="visuellement-cache">Onglet</span>
              <select value={actif} onChange={(e) => changerOnglet(e.target.value as Onglet)}>
                {ONGLETS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.libelle}
                  </option>
                ))}
              </select>
            </label>
          </nav>
          <div className="contenu-onglet" role="tabpanel">
            <Suspense fallback={<Chargement />}>
              {actif === "plan" && <OngletPlan projet={projet} />}
              {actif === "programme" &&
                (peutModifier ? (
                  <ProgrammeForm programme={projet.programme} enCours={enCours} aDesSignatures={aDesSignatures} onRecalculer={recalculer} />
                ) : (
                  <pre className="mono petit">{JSON.stringify(projet.programme, null, 2)}</pre>
                ))}
              {actif === "electricite" && (
                <Electricite
                  projet={projet}
                  enCours={enCours || !peutModifier}
                  onLongueurs={(l) => recalculer({ ...projet.programme, longueurs_circuits: l })}
                />
              )}
              {actif === "structure" && <Structure projet={projet} />}
              {actif === "toiture" && <Toiture projet={projet} />}
              {actif === "solaire" && <Solaire projet={projet} />}
              {actif === "metre" && <Metre projet={projet} enCours={enCours} onRecalculer={peutModifier ? () => recalculer(projet.programme) : undefined} />}
              {actif === "validation" && <OngletValidation projet={projet} utilisateur={utilisateur} onSigne={charger} />}
            </Suspense>
          </div>
        </>
      )}
    </main>
  );
}
