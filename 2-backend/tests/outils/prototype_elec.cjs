// Exécute le moteur de calcul du prototype « Module Électrification » (docs/reference) sur une entrée JSON.
// Usage : node prototype_elec.cjs <prototype.html> < entree.json > sortie.json
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const debut = html.indexOf('const U = 230');
const fin = html.indexOf('/* ---------- Rendu');
const moteur = html.slice(debut, fin).replace(/^let state;[\s\S]*?\nlet filtre/m, 'let filtre');
const entree = JSON.parse(fs.readFileSync(0, 'utf8'));
const ctx = { Math, Object, Array, Set, JSON, Number, String, console };
vm.createContext(ctx);
vm.runInContext(moteur + '\nstate = ' + JSON.stringify(entree) + ';\nresultat = calc();', ctx);
const r = ctx.resultat;
process.stdout.write(JSON.stringify({
  circuits: r.circ.map(c => ({ key: c.key, nom: c.nom, det: c.det, n: c.n, P: c.P, In: c.In, S: c.S, L: c.L,
    Ib: c.Ib, du: c.du, etat: c.etat, num: c.num, id: c.id })),
  ids: r.ids.map(d => ({ nom: d.nom, type: d.type, In: d.In, I: d.I, circuits: d.circuits.map(c => c.key) })),
  inst: r.inst, dem: r.dem, kva: r.kva, branch: r.branch, Pess: r.Pess, ond: r.ond, bat: r.bat, kwc: r.kwc,
}, null, 1));
