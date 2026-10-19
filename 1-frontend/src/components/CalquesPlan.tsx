export const CALQUES_INTERFACE = [
  { id: "murs", libelle: "Murs et ouvertures" },
  { id: "textes", libelle: "Noms et surfaces" },
  { id: "cotes", libelle: "Cotes" },
  { id: "elec", libelle: "Électricité" },
  { id: "structure", libelle: "Structure" },
  { id: "annotations", libelle: "Cartouche et nord" },
] as const;

export const CALQUES_DEFAUT = ["murs", "textes", "cotes", "annotations"];

export default function CalquesPlan({ actifs, onChange }: { actifs: string[]; onChange: (c: string[]) => void }) {
  const basculer = (id: string) =>
    onChange(actifs.includes(id) ? actifs.filter((c) => c !== id) : CALQUES_INTERFACE.map((c) => c.id).filter((c) => c === id || actifs.includes(c)));
  return (
    <fieldset className="calques">
      <legend>Calques</legend>
      {CALQUES_INTERFACE.map((c) => (
        <label key={c.id} className="case">
          <input type="checkbox" checked={actifs.includes(c.id)} onChange={() => basculer(c.id)} disabled={c.id === "murs"} />
          {c.libelle}
        </label>
      ))}
    </fieldset>
  );
}
