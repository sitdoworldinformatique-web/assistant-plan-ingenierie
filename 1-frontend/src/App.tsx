import { useEffect, useState } from "react";

type Sante = { etat: string; version_moteurs: string; ia_texte_configuree: boolean; ia_image_configuree: boolean };

export default function App() {
  const [sante, setSante] = useState<Sante | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/sante")
      .then((r) => r.json())
      .then(setSante)
      .catch(() => setErreur("API injoignable"));
  }, []);

  return (
    <main className="accueil">
      <h1>Assistant Plan Ingénierie</h1>
      <p>Décrivez la maison, les moteurs calculent, l'ingénieur valide et signe.</p>
      {sante && (
        <p className="pastille pastille-ok">
          API {sante.etat} · moteurs {sante.version_moteurs}
        </p>
      )}
      {erreur && <p className="pastille pastille-bloquant">{erreur}</p>}
    </main>
  );
}
