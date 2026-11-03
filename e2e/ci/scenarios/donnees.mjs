// Données et droits côté serveur : notes, bulletins, paiements et reçus, fichiers, comptes, changement de rôle.
import { API, BASE, api, connecter, jeton, liste, ok, unique } from "../outils.mjs";

const S = "données";
export default async function () {
  const [ad, pr, el, pa] = await Promise.all(["admin", "teacher", "student", "parent"].map(jeton));
  const moi = (await api("GET", "/auth/me/", el)).donnees;
  const eleve = moi.student_id || moi.student_profile?.id || liste((await api("GET", "/students/?page_size=500&search=Estelle", ad)).donnees).find((x) => x.user === moi.id || x.email === moi.email)?.id;
  const annee = liste((await api("GET", "/schools/years/", ad)).donnees).find((y) => y.is_current).id;
  const matieres = liste((await api("GET", "/subjects/?page_size=200", pr)).donnees);

  // Notes : création par l'enseignant, visibilité, modification tracée, refus élève, suppression justifiée.
  let note;
  for (const m of matieres) {
    const r = await api("POST", "/grades/", pr, { student: eleve, subject: m.id, school_year: annee, period: "T3", value: 13.5, note_type: "devoir", type: "devoir" });
    if (r.statut === 201) { note = r.donnees; break; }
  }
  ok(S, "note créée par l'enseignant", Boolean(note));
  if (note) {
    ok(S, "note visible par l'élève", liste((await api("GET", "/grades/?page_size=500", el)).donnees).some((x) => x.id === note.id));
    ok(S, "note visible par son parent", liste((await api("GET", "/grades/?page_size=500", pa)).donnees).some((x) => x.id === note.id));
    const m = await api("PATCH", `/grades/${note.id}/`, pr, { value: 14, justification: "Correction e2e" });
    ok(S, "modification avec historique", m.statut === 200 && (await api("GET", `/grades/${note.id}/`, pr)).donnees.history?.length >= 1, m.statut);
    ok(S, "élève ne modifie pas une note", (await api("PATCH", `/grades/${note.id}/`, el, { value: 20 })).statut === 403);
    ok(S, "suppression sans justification refusée", (await api("DELETE", `/grades/${note.id}/`, pr, {})).statut === 400);
    ok(S, "suppression justifiée", [200, 204].includes((await api("DELETE", `/grades/${note.id}/`, pr, { justification: "Test e2e" })).statut));
    ok(S, "note supprimée invisible pour l'élève et son tableau de bord",
      !liste((await api("GET", "/grades/?page_size=500", el)).donnees).some((x) => x.id === note.id)
      && !((await api("GET", "/dashboard/student/", el)).donnees.recent_grades || []).some((x) => x.id === note.id));
  }
  for (const v of [99, -1]) ok(S, `note ${v} refusée`, (await api("POST", "/grades/", pr, { student: eleve, subject: matieres[0].id, school_year: annee, period: "T3", value: v })).statut === 400);

  // Bulletin : génération, PDF réel, régénération sans doublon, lien falsifié refusé.
  const corps = { student: eleve, student_id: eleve, period: "T1", school_year: annee, school_year_id: annee };
  const b = await api("POST", "/bulletins/generate/", ad, corps);
  ok(S, "bulletin généré", [200, 201].includes(b.statut), b.statut);
  if (b.statut < 300) {
    const lien = b.donnees.pdf_url || b.donnees.pdf_file;
    const pdf = await fetch(BASE.replace(/\/$/, "") + lien);
    ok(S, "PDF du bulletin téléchargeable", pdf.status === 200 && (await pdf.text()).startsWith("%PDF"));
    const n = async () => liste((await api("GET", `/bulletins/?page_size=500&student=${eleve}`, ad)).donnees).length;
    const avant = await n();
    await api("POST", "/bulletins/generate/", ad, corps);
    ok(S, "régénération sans doublon", avant === (await n()));
    ok(S, "lien de fichier falsifié refusé", (await fetch(BASE + lien.replace("/api/files/", "/api/files/x"))).status === 404);
  }

  // Paiement : création, reçu, lecture élève, refus enseignant, suppression admin.
  const p = await api("POST", "/payments/", ad, { student: eleve, school_year: annee, amount: "1000", payment_type: "inscription", payment_method: "cash", payment_date: "2026-11-02" });
  ok(S, "paiement créé", p.statut === 201, p.statut);
  if (p.statut === 201) {
    ok(S, "reçu généré", (await api("POST", `/payments/${p.donnees.id}/generate-receipt/`, ad)).statut === 200);
    ok(S, "élève lit son paiement", (await api("GET", `/payments/${p.donnees.id}/`, el)).statut === 200);
    ok(S, "enseignant ne supprime pas un paiement", (await api("DELETE", `/payments/${p.donnees.id}/`, pr)).statut === 403);
    ok(S, "admin supprime", [200, 204].includes((await api("DELETE", `/payments/${p.donnees.id}/`, ad, { reason: "e2e" })).statut));
  }
  ok(S, "montant négatif refusé", (await api("POST", "/payments/", ad, { student: eleve, school_year: annee, amount: "-5", payment_type: "inscription", payment_method: "cash", payment_date: "2026-11-02" })).statut === 400);

  // Fichiers : dépôt, téléchargement, droits, contenu actif refusé.
  const f = new FormData();
  f.append("name", "e2e");
  f.append("file", new Blob(["%PDF-1.4 test"], { type: "application/pdf" }), "a.pdf");
  const fichier = await api("POST", "/user-files/", ad, f);
  ok(S, "fichier déposé", fichier.statut === 201, fichier.statut);
  if (fichier.statut === 201) {
    ok(S, "fichier téléchargé", (await api("GET", `/user-files/${fichier.donnees.id}/download/`, ad)).statut === 200);
    ok(S, "élève sans accès au fichier", [403, 404].includes((await api("GET", `/user-files/${fichier.donnees.id}/download/`, el)).statut));
  }
  const html = new FormData();
  html.append("name", "x");
  html.append("file", new Blob(["<script>1</script>"], { type: "text/html" }), "x.html");
  ok(S, "fichier HTML refusé", (await api("POST", "/user-files/", ad, html)).statut === 400);
  const av = new FormData();
  av.append("avatar", new Blob(["<svg onload=alert(1)>"], { type: "image/svg+xml" }), "a.svg");
  ok(S, "avatar SVG refusé", (await api("POST", "/auth/avatar/", el, av)).statut === 400);

  // Compte : désactivation immédiate, puis changement de rôle appliqué sans reconnexion.
  const email = `e2e${unique()}@feba.bj`;
  const mdp = "Xy7!kPq9#Lm2";
  const cree = await api("POST", "/auth/users/", ad, { email, username: email, first_name: "E", last_name: "Deux", role: "teacher", password: mdp, password2: mdp });
  ok(S, "compte créé", cree.statut === 201, cree.statut);
  const id = liste((await api("GET", "/auth/users/?page_size=1000", ad)).donnees).find((x) => x.email === email)?.id;
  const connexion = async () => (await (await fetch(API + "/auth/login/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: mdp }) })).json());
  const j = (await connexion()).access;
  ok(S, "enseignant : pas d'accès à la gestion des comptes", (await api("GET", "/auth/users/", j)).statut === 403);
  ok(S, "un admin ne promeut pas un compte au rang d'admin", (await api("PATCH", `/auth/users/${id}/`, ad, { role: "admin" })).statut === 400);
  const sa = await jeton("superadmin");
  await api("PATCH", `/auth/users/${id}/`, sa, { role: "admin" });
  ok(S, "rôle élevé par le superadmin : appliqué sans reconnexion", (await api("GET", "/auth/users/", j)).statut === 200);
  await api("PATCH", `/auth/users/${id}/`, sa, { role: "teacher" });
  ok(S, "rôle abaissé : retiré sans reconnexion", (await api("GET", "/auth/users/", j)).statut === 403);
  await api("POST", `/auth/users/${id}/toggle-active/`, ad);
  ok(S, "compte désactivé : jeton refusé", (await api("GET", "/auth/me/", j)).statut === 401);
  ok(S, "compte désactivé : message exact", JSON.stringify(await connexion()).includes("désactivé"));

  // Interface : la liste des notes s'affiche sans erreur pour l'enseignant.
  const t = await connecter("teacher");
  await t.goto(BASE + "/teacher/grades");
  await t.waitForTimeout(1800);
  ok(S, "page Notes sans erreur", t.erreurs.length === 0, t.erreurs.join(" | "));
  await t.contexte.close();
}
