import { useCallback, useEffect, useRef, useState } from "react";
import { api, ErreurApi } from "../api/client";
import type { ListeRendus, Projet } from "../types";

const STYLE = "realiste";
const DELAI_MS = 3000;

function preferenceAuto(): boolean {
  try {
    return localStorage.getItem("rendu-auto") !== "0";
  } catch {
    return true;
  }
}

interface Props {
  projet: Projet;
  /** Renvoie une capture PNG de la maquette 3D (null tant que la 3D n'est pas prête). */
  capteur: (() => string) | null;
  peutModifier: boolean;
}

/** Rendu réaliste (Nano Banana) de la maison, produit automatiquement à partir de la maquette 3D après chaque étape. */
export default function RenduAuto({ projet, capteur, peutModifier }: Props) {
  const [liste, setListe] = useState<ListeRendus | null>(null);
  const [auto, setAuto] = useState(preferenceAuto);
  const [image, setImage] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const echec = useRef<string | null>(null); // empreinte pour laquelle une tentative a échoué : pas de nouvelle tentative automatique

  const charger = useCallback(() => api.rendus(projet.id).then(setListe).catch(() => setListe(null)), [projet.id]);
  useEffect(() => {
    void charger();
  }, [charger, projet.version]);

  const dernier = liste?.rendus.find((r) => r.style === STYLE) ?? null;
  const aJour = !!dernier && new Date(dernier.date).getTime() >= new Date(projet.modifie_le).getTime();

  useEffect(() => {
    if (!dernier) {
      setImage(null);
      return;
    }
    let lien: string | null = null;
    let annule = false;
    api
      .imageRendu(dernier.url)
      .then((b) => {
        if (annule) return;
        lien = URL.createObjectURL(b);
        setImage(lien);
      })
      .catch(() => !annule && setImage(null));
    return () => {
      annule = true;
      if (lien) URL.revokeObjectURL(lien);
    };
  }, [dernier?.url]); // eslint-disable-line react-hooks/exhaustive-deps

  const generer = useCallback(async () => {
    if (!capteur) return;
    setEnCours(true);
    setErreur(null);
    try {
      await api.creerRendu(projet.id, STYLE, capteur());
      echec.current = null;
    } catch (e) {
      echec.current = projet.empreinte;
      setErreur(e instanceof ErreurApi || e instanceof Error ? e.message : "Rendu impossible.");
    } finally {
      setEnCours(false);
      void charger();
    }
  }, [capteur, projet.id, projet.empreinte, charger]);

  const restant = liste ? liste.quota.max - liste.quota.utilises : 0;
  const actif = !!liste?.ia_image_configuree && peutModifier;
  useEffect(() => {
    if (!actif || !auto || !capteur || aJour || enCours || restant <= 0 || echec.current === projet.empreinte) return;
    const t = setTimeout(() => void generer(), DELAI_MS);
    return () => clearTimeout(t);
  }, [actif, auto, capteur, aJour, enCours, restant, projet.empreinte, generer]);

  function basculer(v: boolean) {
    setAuto(v);
    try {
      localStorage.setItem("rendu-auto", v ? "1" : "0");
    } catch {
      /* préférence non enregistrée */
    }
  }

  if (!liste || !liste.ia_image_configuree) {
    return liste ? (
      <p className="texte-2 petit">Rendu réaliste désactivé : aucune clé Nano Banana n'est configurée sur ce serveur.</p>
    ) : null;
  }
  return (
    <section className="carte-atelier rendu-auto" aria-labelledby="titre-rendu-auto">
      <div className="entete-section">
        <h2 id="titre-rendu-auto">Rendu réaliste</h2>
        {peutModifier && (
          <label className="case">
            <input type="checkbox" checked={auto} onChange={(e) => basculer(e.target.checked)} /> Automatique
          </label>
        )}
      </div>
      {image ? (
        <figure className="vignette-rendu">
          <img src={image} alt="Rendu réaliste de la maison, image de présentation non contractuelle" />
          <figcaption>
            <div className="mention-rendu">{dernier?.mention}</div>
            {!aJour && !enCours && <p className="texte-2 petit">Cette image date d'une étape précédente.</p>}
          </figcaption>
        </figure>
      ) : (
        !enCours && <p className="texte-2 petit">Le rendu réaliste apparaîtra ici après le calcul de la maison.</p>
      )}
      {enCours && (
        <p role="status" className="texte-2 petit">
          Rendu réaliste en cours (jusqu'à 90 s)…
        </p>
      )}
      {erreur && <p className="message-erreur">{erreur}</p>}
      <div className="actions">
        {peutModifier && (
          <button className="bouton" onClick={() => void generer()} disabled={enCours || !capteur || restant <= 0}>
            {aJour ? "Refaire le rendu" : "Générer le rendu"}
          </button>
        )}
        <span className="texte-2 petit">{restant > 0 ? `${restant} rendu${restant > 1 ? "s" : ""} restant${restant > 1 ? "s" : ""} aujourd'hui` : "Quota du jour atteint."}</span>
      </div>
    </section>
  );
}
