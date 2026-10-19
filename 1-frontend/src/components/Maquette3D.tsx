import { useEffect, useRef, useState } from "react";
import type { Modele3D } from "../types";

type Three = typeof import("three");

const COULEURS: Record<string, number> = {
  mur_ext: 0xe8e0d0,
  mur_int: 0xf1ece2,
  pignon: 0xe8e0d0,
  chainage: 0xb9b3a6,
  soubassement: 0x9a968e,
  semelle: 0x8c8f94,
  dalle: 0xc8cbd0,
  dalle_veranda: 0xbfc3c8,
  vitre: 0x9cc7e6,
  porte: 0x7a5a3c,
  poteau_veranda: 0xa78a68,
  poutre_veranda: 0xa78a68,
  acrotere: 0xe0d8c8,
  dalle_toiture: 0xcfd2d6,
  toit_veranda: 0x9d8f84,
};
const COUVERTURES: Record<string, number> = { tuiles: 0xb4543a, "tole bac acier": 0x6f7f8f, "tole ondulee": 0x8d949b, "dalle beton": 0xcfd2d6 };
const SOUS_TERRE = new Set(["semelle", "soubassement"]);

interface Scene {
  rendre: () => void;
  vue: (nom: "face" | "trois-quarts" | "dessus") => void;
  montrer: (o: { toiture: boolean; fondations: boolean }) => void;
  /** Image PNG de la maison vue de trois quarts, toiture visible, fondations masquées (la vue de l'utilisateur est rétablie). */
  capturer: () => string;
  liberer: () => void;
}

function construire(T: Three, OrbitControls: typeof import("three/examples/jsm/controls/OrbitControls.js").OrbitControls, el: HTMLDivElement, m: Modele3D): Scene {
  const fond = getComputedStyle(el).getPropertyValue("--plan-fond").trim() || "#ffffff";
  const renderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;
  el.appendChild(renderer.domElement);
  const scene = new T.Scene();
  scene.background = new T.Color(fond);

  const cx = (m.emprise.x_min + m.emprise.x_max) / 2;
  const cz = (m.emprise.y_min + m.emprise.y_max) / 2;
  const rayon = Math.max(m.emprise.x_max - m.emprise.x_min, m.emprise.y_max - m.emprise.y_min, 8);
  const camera = new T.PerspectiveCamera(38, 1, 0.5, rayon * 40);
  const controles = new OrbitControls(camera, renderer.domElement);
  controles.target.set(cx, m.niveaux.haut_mur * 0.4, cz);
  controles.maxPolarAngle = Math.PI / 2 - 0.03;
  controles.minDistance = rayon * 0.6;
  controles.maxDistance = rayon * 4;

  scene.add(new T.HemisphereLight(0xffffff, 0x8a8f78, 1.0));
  const soleil = new T.DirectionalLight(0xffffff, 1.7);
  soleil.position.set(cx + rayon * 0.9, rayon * 1.4, cz + rayon * 0.6);
  soleil.target.position.set(cx, 0, cz);
  soleil.castShadow = true;
  soleil.shadow.mapSize.set(2048, 2048);
  const e = rayon * 1.2;
  Object.assign(soleil.shadow.camera, { left: -e, right: e, top: e, bottom: -e, near: 1, far: rayon * 6 });
  soleil.shadow.bias = -0.0005;
  scene.add(soleil, soleil.target);

  const materiaux = new Map<string, import("three").Material>();
  const matiere = (cle: string, couleur: number, opts: Record<string, unknown> = {}) => {
    let mat = materiaux.get(cle);
    if (!mat) {
      mat = new T.MeshStandardMaterial({ color: couleur, roughness: 0.9, metalness: 0, ...opts });
      materiaux.set(cle, mat);
    }
    return mat;
  };

  const groupes = { maison: new T.Group(), toiture: new T.Group(), fondations: new T.Group() };
  scene.add(groupes.maison, groupes.toiture, groupes.fondations);
  const aretes = new T.LineBasicMaterial({ color: 0x3a4350, transparent: true, opacity: 0.35 });

  // Terrain (le plancher fini est à z = 0, le terrain naturel à m.terrain.z)
  const t = m.terrain;
  const sol = new T.Mesh(new T.BoxGeometry(t.l, 0.3, t.p), matiere("terrain", 0x8fa56b, { transparent: true, opacity: 1 }));
  sol.position.set(t.x + t.l / 2, t.z - 0.15, t.y + t.p / 2);
  sol.receiveShadow = true;
  scene.add(sol);

  for (const b of m.boites) {
    const verre = b.t === "vitre";
    const g = new T.BoxGeometry(b.dx, b.dz, b.dy);
    const mesh = new T.Mesh(g, matiere(b.t, COULEURS[b.t] ?? 0xcccccc, verre ? { transparent: true, opacity: 0.55, roughness: 0.2 } : {}));
    mesh.position.set(b.x + b.dx / 2, b.z + b.dz / 2, b.y + b.dy / 2);
    mesh.castShadow = !verre;
    mesh.receiveShadow = true;
    const parent = SOUS_TERRE.has(b.t) ? groupes.fondations : b.t === "dalle_toiture" || b.t === "acrotere" ? groupes.toiture : groupes.maison;
    parent.add(mesh);
    if (b.t !== "vitre" && !SOUS_TERRE.has(b.t)) {
      const l = new T.LineSegments(new T.EdgesGeometry(g), aretes);
      l.position.copy(mesh.position);
      parent.add(l);
    }
  }

  for (const f of m.faces) {
    const pts = f.pts.map(([x, y, z]) => new T.Vector3(x, z, y));
    const geo = new T.BufferGeometry();
    const sommets: number[] = [];
    for (let i = 1; i < pts.length - 1; i++) sommets.push(...pts[0].toArray(), ...pts[i].toArray(), ...pts[i + 1].toArray());
    geo.setAttribute("position", new T.Float32BufferAttribute(sommets, 3));
    geo.computeVertexNormals();
    const couleur = f.t === "toit" ? (COUVERTURES[m.toiture.couverture] ?? 0xb4543a) : (COULEURS[f.t] ?? 0xe8e0d0);
    const mesh = new T.Mesh(geo, matiere(`face-${f.t}`, couleur, { side: T.DoubleSide, flatShading: true, roughness: 0.8 }));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    (f.t === "pignon" ? groupes.maison : groupes.toiture).add(mesh);
    const contour = new T.LineSegments(new T.EdgesGeometry(geo), aretes);
    (f.t === "pignon" ? groupes.maison : groupes.toiture).add(contour);
  }

  const dimensionner = () => {
    const w = Math.max(el.clientWidth, 120);
    const h = Math.max(el.clientHeight, 120);
    renderer.setSize(w, h, false);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  const rendre = () => renderer.render(scene, camera);
  const placer = (nom: "face" | "trois-quarts" | "dessus") => {
    const h = m.niveaux.haut;
    const positions = {
      face: [cx, h * 0.8, m.emprise.y_max + rayon * 1.6],
      "trois-quarts": [cx + rayon * 0.95, rayon * 0.62 + h * 0.4, m.emprise.y_max + rayon * 1.05],
      dessus: [cx, rayon * 2.1, cz + 0.01],
    } as const;
    camera.position.set(...positions[nom]);
    controles.target.set(cx, nom === "dessus" ? 0 : m.niveaux.haut_mur * 0.4, cz);
    controles.update();
    rendre();
  };
  controles.addEventListener("change", rendre);
  const obs = new ResizeObserver(() => {
    dimensionner();
    rendre();
  });
  obs.observe(el);
  dimensionner();
  placer("trois-quarts");

  return {
    rendre,
    vue: placer,
    montrer: ({ toiture, fondations }) => {
      groupes.toiture.visible = toiture;
      // Fondations : le terrain devient translucide pour les laisser voir
      (matiere("terrain", 0) as import("three").MeshStandardMaterial).opacity = fondations ? 0.18 : 1;
      (matiere("terrain", 0) as import("three").MeshStandardMaterial).depthWrite = !fondations;
      groupes.fondations.visible = fondations;
      rendre();
    },
    capturer: () => {
      const pos = camera.position.clone();
      const cible = controles.target.clone();
      const etat = [groupes.toiture.visible, groupes.fondations.visible, (matiere("terrain", 0) as import("three").MeshStandardMaterial).opacity] as const;
      groupes.toiture.visible = true;
      groupes.fondations.visible = false;
      (matiere("terrain", 0) as import("three").MeshStandardMaterial).opacity = 1;
      placer("trois-quarts");
      const png = renderer.domElement.toDataURL("image/png");
      groupes.toiture.visible = etat[0];
      groupes.fondations.visible = etat[1];
      (matiere("terrain", 0) as import("three").MeshStandardMaterial).opacity = etat[2];
      camera.position.copy(pos);
      controles.target.copy(cible);
      controles.update();
      rendre();
      return png;
    },
    liberer: () => {
      obs.disconnect();
      controles.dispose();
      scene.traverse((o) => {
        const mesh = o as import("three").Mesh;
        mesh.geometry?.dispose();
      });
      materiaux.forEach((mat) => mat.dispose());
      aretes.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}

/** Maquette 3D de la maison (three.js, chargé à la demande) : rotation, zoom, toiture et fondations affichables. */
export default function Maquette3D({ modele, onCapteur }: { modele: Modele3D; onCapteur?: (capturer: (() => string) | null) => void }) {
  const zone = useRef<HTMLDivElement>(null);
  const scene = useRef<Scene | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [toiture, setToiture] = useState(true);
  const [fondations, setFondations] = useState(false);

  useEffect(() => {
    const el = zone.current;
    if (!el) return;
    let annule = false;
    let courante: Scene | null = null;
    Promise.all([import("three"), import("three/examples/jsm/controls/OrbitControls.js")])
      .then(([T, { OrbitControls }]) => {
        if (annule) return;
        courante = construire(T, OrbitControls, el, modele);
        scene.current = courante;
        courante.montrer({ toiture, fondations });
        const c = courante;
        onCapteur?.(() => c.capturer());
      })
      .catch(() => !annule && setErreur("Votre navigateur ne peut pas afficher la 3D (WebGL indisponible)."));
    return () => {
      annule = true;
      onCapteur?.(null);
      courante?.liberer();
      scene.current = null;
    };
    // la scène est reconstruite quand le modèle change ; les cases sont appliquées par l'effet suivant
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modele]);

  useEffect(() => scene.current?.montrer({ toiture, fondations }), [toiture, fondations]);

  return (
    <div className="maquette">
      <div className="maquette-outils" role="toolbar" aria-label="Maquette 3D">
        <button className="bouton" onClick={() => scene.current?.vue("face")}>
          Face
        </button>
        <button className="bouton" onClick={() => scene.current?.vue("trois-quarts")}>
          3/4
        </button>
        <button className="bouton" onClick={() => scene.current?.vue("dessus")}>
          Dessus
        </button>
        <label className="case">
          <input type="checkbox" checked={toiture} onChange={(e) => setToiture(e.target.checked)} /> Toiture
        </label>
        <label className="case">
          <input type="checkbox" checked={fondations} onChange={(e) => setFondations(e.target.checked)} /> Fondations
        </label>
      </div>
      {erreur ? (
        <p className="texte-2 petit maquette-erreur">{erreur}</p>
      ) : (
        <div ref={zone} className="maquette-zone" data-testid="maquette-3d" role="img" aria-label="Maquette 3D de la maison, faites-la tourner avec la souris ou le doigt" />
      )}
    </div>
  );
}
