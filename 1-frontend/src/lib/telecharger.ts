/** Propose un fichier au téléchargement (les exports passent par l'API authentifiée). */
export function telecharger(contenu: Blob | string, nom: string, type = "application/octet-stream"): void {
  const blob = typeof contenu === "string" ? new Blob([contenu], { type }) : contenu;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Nom de fichier sûr à partir du nom du projet. */
export function nomFichier(nom: string, extension: string): string {
  const base = nom
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  return `${base || "projet"}.${extension}`;
}
