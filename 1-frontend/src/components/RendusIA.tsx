import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi } from "../api/client";
import { dateHeure } from "../lib/format";
import { rasteriser } from "../lib/rasteriserSvg";
import { nomFichier, telecharger } from "../lib/telecharger";
import type { ListeRendus, Projet, RenduIA } from "../types";
import { Chargement, MessageErreur } from "./Etat";

const DESCRIPTIONS: Record<string, string> = {
  plan_meuble: "Vue de dessus, sols texturés, mobilier, ombres douces.",
  iso_coupe: "Maison sans toit, vue à 45°.",
  facade: "Rendu photoréaliste de la façade principale.",
  perspective: "Vue d'ensemble avec la véranda.",
};

function Vignette({ rendu, peutSupprimer, onSupprimer, nomProjet }: { rendu: RenduIA; peutSupprimer: boolean; onSupprimer: () => void; nomProjet: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  useEffect(() => {
    let lien: string | null = null;
    api
      .imageRendu(rendu.url)
      .then((b) => {
        setBlob(b);
        lien = URL.createObjectURL(b);
        setUrl(lien);
      })
      .catch(() => setUrl(""));
    return () => {
      if (lien) URL.revokeObjectURL(lien);
    };
  }, [rendu.url]);
  return (
    <figure className="vignette-rendu">
      {url ? <img src={url} alt={`${rendu.libelle} — image de présentation non contractuelle`} loading="lazy" /> : url === "" ? <div className="vignette-vide">Image indisponible</div> : <Chargement />}
      <figcaption>
        <strong>{rendu.libelle}</strong> <span className="texte-2 petit">· {dateHeure(rendu.date)}</span>
        <div className="mention-rendu">{rendu.mention}</div>
        <div className="actions">
          <button className="lien" disabled={!blob} onClick={() => blob && telecharger(blob, nomFichier(`${nomProjet}-${rendu.style}-${rendu.id}`, "jpg"))}>
            Télécharger
          </button>
          {peutSupprimer && (
            <button className="lien" onClick={onSupprimer}>
              Supprimer
            </button>
          )}
        </div>
      </figcaption>
    </figure>
  );
}

export default function RendusIA({ projet, peutModifier }: { projet: Projet; peutModifier: boolean }) {
  const [liste, setListe] = useState<ListeRendus | null>(null);
  const [style, setStyle] = useState("plan_meuble");
  const [etape, setEtape] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    api
      .rendus(projet.id)
      .then(setListe)
      .catch((e) => setErreur(e instanceof ErreurApi ? e.message : "Erreur inattendue."));
  }, [projet.id]);
  useEffect(charger, [charger]);

  async function generer() {
    setErreur(null);
    try {
      setEtape("Préparation de l'image du plan (murs et ouvertures)…");
      const svg = await api.planSvg(projet.id, ["murs"]);
      const png = await rasteriser(svg);
      setEtape("Génération de l'image par le service d'IA (jusqu'à 90 s)…");
      await api.creerRendu(projet.id, style, png);
      charger();
    } catch (e) {
      setErreur(e instanceof ErreurApi || e instanceof Error ? e.message : "Génération impossible.");
      charger();
    } finally {
      setEtape(null);
    }
  }

  async function supprimer(r: RenduIA) {
    if (!confirm("Supprimer cette image ?")) return;
    try {
      await api.supprimerRendu(projet.id, r.id);
      charger();
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Suppression impossible.");
    }
  }

  if (!liste) return erreur ? <MessageErreur message={erreur} onReessayer={charger} /> : <Chargement />;
  const restant = liste.quota.max - liste.quota.utilises;
  return (
    <div className="onglet-module">
      <section className="module-etat">
        <h2>Rendus de présentation</h2>
        <p className="avertissement-rendu">
          Images de présentation pour le client, <strong>non contractuelles</strong>. Les cotes et quantités font foi sur le plan technique.
        </p>
        {!liste.ia_image_configuree ? (
          <p className="message-erreur" role="status">
            Les rendus IA sont désactivés : aucune clé du service d'images n'est configurée sur ce serveur.
          </p>
        ) : (
          <>
            <fieldset className="styles-rendu" disabled={etape !== null}>
              <legend>Style</legend>
              {Object.entries(liste.styles).map(([id, libelle]) => (
                <label key={id} className={`carte-style ${style === id ? "actif" : ""}`}>
                  <input type="radio" name="style" value={id} checked={style === id} onChange={() => setStyle(id)} />
                  <strong>{libelle}</strong>
                  <span className="texte-2 petit">{DESCRIPTIONS[id]}</span>
                </label>
              ))}
            </fieldset>
            <div className="actions">
              <button className="bouton bouton-principal" onClick={generer} disabled={etape !== null || restant <= 0}>
                {etape ? "Génération…" : "Générer l'image"}
              </button>
              <span className="texte-2 petit">
                {restant > 0 ? `${restant} rendu${restant > 1 ? "s" : ""} restant${restant > 1 ? "s" : ""} aujourd'hui` : "Quota du jour atteint, réessayez demain."}
              </span>
            </div>
            {etape && <Chargement texte={etape} />}
          </>
        )}
        {erreur && <MessageErreur message={erreur} />}
      </section>
      <section>
        <h2>Galerie ({liste.rendus.length})</h2>
        {liste.rendus.length === 0 ? (
          <p className="texte-2">Aucune image pour l'instant.</p>
        ) : (
          <div className="galerie">
            {liste.rendus.map((r) => (
              <Vignette key={r.id} rendu={r} nomProjet={projet.nom} peutSupprimer={peutModifier} onSupprimer={() => supprimer(r)} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
