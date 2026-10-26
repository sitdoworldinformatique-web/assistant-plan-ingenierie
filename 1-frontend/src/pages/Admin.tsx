import { useCallback, useEffect, useState } from "react";
import { api, ErreurApi } from "../api/client";
import { Chargement, MessageErreur } from "../components/Etat";
import { dateHeure, lireNombre, nombre } from "../lib/format";
import type { PrixMateriau, Role, Utilisateur } from "../types";

function Prix() {
  const [prix, setPrix] = useState<PrixMateriau[] | null>(null);
  const [saisies, setSaisies] = useState<Record<string, string>>({});
  const [filtre, setFiltre] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const charger = useCallback(() => {
    setErreur(null);
    api
      .prix()
      .then(setPrix)
      .catch((e) => setErreur(e instanceof ErreurApi ? e.message : "Erreur inattendue."));
  }, []);
  useEffect(charger, [charger]);

  const invalides = Object.values(saisies).some((t) => {
    const n = lireNombre(t);
    return n === null || n < 0;
  });

  async function enregistrer() {
    setEnCours(true);
    setMessage(null);
    try {
      const entrees = Object.entries(saisies).map(([code, t]) => ({ code, prix: lireNombre(t)! }));
      setPrix(await api.modifierPrix(entrees));
      setSaisies({});
      setMessage(`${entrees.length} prix enregistré${entrees.length > 1 ? "s" : ""}. Ils s'appliquent aux prochains calculs ; dans un projet existant, utilisez « Appliquer les prix actuels ».`);
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Enregistrement impossible.");
    } finally {
      setEnCours(false);
    }
  }

  if (erreur) return <MessageErreur message={erreur} onReessayer={charger} />;
  if (!prix) return <Chargement />;
  const visibles = prix.filter((p) => (p.libelle + " " + p.code).toLowerCase().includes(filtre.toLowerCase()));
  return (
    <section>
      <div className="entete-section">
        <h2>Prix des matériaux</h2>
        <label className="champ-recherche">
          <span className="visuellement-cache">Filtrer les prix</span>
          <input type="search" placeholder="Filtrer…" value={filtre} onChange={(e) => setFiltre(e.target.value)} />
        </label>
      </div>
      <p className="mention-prix">Prix indicatifs, à mettre à jour selon le marché local.</p>
      <div className="defilement-x">
        <table className="tableau">
          <thead>
            <tr>
              <th>Poste</th>
              <th>Unité</th>
              <th className="nombre">Prix</th>
              <th>Mis à jour</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((p) => (
              <tr key={p.code}>
                <td>
                  {p.libelle}
                  <div className="mono petit texte-2">{p.code}</div>
                </td>
                <td>{p.unite}</td>
                <td className="nombre">
                  <label className="visuellement-cache" htmlFor={`prix-${p.code}`}>
                    Prix de {p.libelle} en {p.devise}
                  </label>
                  <input
                    id={`prix-${p.code}`}
                    className="champ-court"
                    inputMode="decimal"
                    value={saisies[p.code] ?? nombre(p.prix, 2).replace(/ /g, "")}
                    onChange={(e) => setSaisies((s) => ({ ...s, [p.code]: e.target.value }))}
                  />{" "}
                  {p.devise}
                </td>
                <td className="petit texte-2">{dateHeure(p.mis_a_jour_le)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="actions">
        <button className="bouton bouton-principal" disabled={enCours || invalides || Object.keys(saisies).length === 0} onClick={enregistrer}>
          {enCours ? "Enregistrement…" : "Enregistrer les prix"}
        </button>
        {invalides && <span className="erreur-champ">Prix positif attendu.</span>}
        {message && (
          <span className="texte-2" role="status">
            {message}
          </span>
        )}
      </div>
    </section>
  );
}

function Utilisateurs({ moi }: { moi: Utilisateur }) {
  const [liste, setListe] = useState<Utilisateur[] | null>(null);
  const [modifs, setModifs] = useState<Record<number, { role: Role; numero_ordre: string }>>({});
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    api
      .utilisateurs()
      .then(setListe)
      .catch((e) => setErreur(e instanceof ErreurApi ? e.message : "Erreur inattendue."));
  }, []);
  useEffect(charger, [charger]);

  async function enregistrer(u: Utilisateur) {
    const m = modifs[u.id];
    try {
      const nouveau = await api.modifierUtilisateur(u.id, m.role, m.numero_ordre.trim() || null);
      setListe((l) => l?.map((x) => (x.id === u.id ? nouveau : x)) ?? null);
      setModifs(({ [u.id]: _, ...reste }) => reste);
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Enregistrement impossible.");
    }
  }

  if (!liste) return erreur ? <MessageErreur message={erreur} onReessayer={charger} /> : <Chargement />;
  return (
    <section>
      <h2>Utilisateurs</h2>
      {erreur && <MessageErreur message={erreur} />}
      <p className="texte-2 petit">Un ingénieur signe avec son numéro d'inscription à l'ordre, affiché dans le cartouche.</p>
      <div className="defilement-x">
        <table className="tableau">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Email</th>
              <th>Rôle</th>
              <th>N° d'ordre</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {liste.map((u) => {
              const m = modifs[u.id] ?? { role: u.role, numero_ordre: u.numero_ordre ?? "" };
              const change = modifs[u.id] !== undefined;
              const maj = (x: Partial<typeof m>) => setModifs((s) => ({ ...s, [u.id]: { ...m, ...x } }));
              return (
                <tr key={u.id}>
                  <td>{u.nom}</td>
                  <td className="petit">{u.email}</td>
                  <td>
                    <label className="visuellement-cache" htmlFor={`role-${u.id}`}>
                      Rôle de {u.nom}
                    </label>
                    <select id={`role-${u.id}`} value={m.role} onChange={(e) => maj({ role: e.target.value as Role })} disabled={u.id === moi.id}>
                      <option value="constructeur">constructeur</option>
                      <option value="ingenieur">ingénieur</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>
                    <label className="visuellement-cache" htmlFor={`ordre-${u.id}`}>
                      Numéro d'ordre de {u.nom}
                    </label>
                    <input id={`ordre-${u.id}`} value={m.numero_ordre} onChange={(e) => maj({ numero_ordre: e.target.value })} />
                  </td>
                  <td>
                    <button className="bouton" disabled={!change} onClick={() => enregistrer(u)}>
                      Enregistrer
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function Admin({ utilisateur }: { utilisateur: Utilisateur }) {
  if (utilisateur.role !== "admin") return <MessageErreur message="Page réservée aux administrateurs." />;
  return (
    <main className="page">
      <h1>Administration</h1>
      <Prix />
      <Utilisateurs moi={utilisateur} />
    </main>
  );
}
