import { useEffect, useState } from "react";
import { api } from "../api/client";
import { metres, nombre, surface } from "../lib/format";
import type { Projet } from "../types";
import ModuleEtat from "./ModuleEtat";
import PlanViewer from "./PlanViewer";

export default function Structure({ projet }: { projet: Projet }) {
  const st = projet.resultats.structure;
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    api
      .planSvg(projet.id, ["murs", "cotes", "structure", "annotations"])
      .then(setSvg)
      .catch(() => setSvg(""));
  }, [projet.id, projet.empreinte]);

  return (
    <div className="onglet-module">
      <ModuleEtat projet={projet} module="structure" />
      <section>
        <h2>Plan de fondations</h2>
        <p className="texte-2 petit">Semelles en pointillé, poteaux en plein.</p>
        <PlanViewer svg={svg} selection={null} onSelection={() => undefined} />
      </section>
      <section>
        <h2>Semelles filantes ({st.semelles.length})</h2>
        <div className="defilement-x">
          <table className="tableau">
            <thead>
              <tr>
                <th>Repère</th>
                <th>Mur</th>
                <th className="nombre">Longueur</th>
                <th className="nombre">Charge ELS</th>
                <th className="nombre">Largeur × hauteur</th>
                <th>Ferraillage</th>
              </tr>
            </thead>
            <tbody>
              {st.semelles.map((s) => (
                <tr key={s.id}>
                  <th scope="row" className="mono">
                    {s.id}
                  </th>
                  <td className="mono">{s.mur_id}</td>
                  <td className="nombre">{metres(s.longueur)}</td>
                  <td className="nombre" title={`mur ${nombre(s.q_mur)} + chaînage ${nombre(s.q_chainage)} + toiture ${nombre(s.q_toiture)} kN/m`}>
                    {nombre(s.q_els)} kN/m
                  </td>
                  <td className="nombre">
                    {nombre(s.largeur)} × {nombre(s.hauteur)} m
                  </td>
                  <td className="petit">{s.ferraillage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h2>Poteaux ({st.poteaux.length})</h2>
        <div className="defilement-x">
          <table className="tableau">
            <thead>
              <tr>
                <th>Repère</th>
                <th>Position</th>
                <th>Section (cm)</th>
                <th>Armatures</th>
                <th>Cadres</th>
                <th>Motif</th>
              </tr>
            </thead>
            <tbody>
              {st.poteaux.map((p) => (
                <tr key={p.id}>
                  <th scope="row" className="mono">
                    {p.id}
                  </th>
                  <td className="nombre">
                    x {nombre(p.x)} · y {nombre(p.y)} m
                  </td>
                  <td>{p.section}</td>
                  <td>{p.armatures}</td>
                  <td>{p.cadres}</td>
                  <td className="texte-2 petit">{p.motif}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h2>Chaînages et linteaux ({st.chainages.length})</h2>
        <div className="defilement-x">
          <table className="tableau">
            <thead>
              <tr>
                <th>Repère</th>
                <th>Type</th>
                <th>Référence</th>
                <th className="nombre">Longueur</th>
                <th>Section (cm)</th>
              </tr>
            </thead>
            <tbody>
              {st.chainages.map((c) => (
                <tr key={c.id}>
                  <th scope="row" className="mono">
                    {c.id}
                  </th>
                  <td>{c.type === "linteau" ? "Linteau" : "Chaînage horizontal"}</td>
                  <td className="mono">{c.reference}</td>
                  <td className="nombre">{metres(c.longueur)}</td>
                  <td>{c.section}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h2>Dallage</h2>
        <dl className="bilan">
          <div>
            <dt>Surface</dt>
            <dd>{surface(st.dallage.surface)}</dd>
          </div>
          <div>
            <dt>Épaisseur</dt>
            <dd>{nombre(st.dallage.epaisseur * 100, 0)} cm</dd>
          </div>
          <div>
            <dt>Hérisson</dt>
            <dd>{nombre(st.dallage.herisson * 100, 0)} cm</dd>
          </div>
          <div>
            <dt>Treillis soudé</dt>
            <dd>{st.dallage.treillis}</dd>
          </div>
          <div>
            <dt>Béton</dt>
            <dd>{nombre(st.dallage.volume_beton)} m³</dd>
          </div>
          <div>
            <dt>Hauteur des murs</dt>
            <dd>{metres(st.hauteur_mur)}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
