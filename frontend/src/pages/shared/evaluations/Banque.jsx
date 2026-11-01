/** Banque de questions : création simple, filtres, duplication, archivage, import et export. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import toast from "react-hot-toast";
import { evaluationsAPI, subjectsAPI, suiviAPI } from "../../../api";
import Modal from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";
import { useAcademy } from "../../../context/AcademyContext";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { TYPES_QUESTION, construireQuestion, libelle, telecharger } from "./commun";

const AIDES = {
  qcm_unique: "Un choix par ligne. Commencez la bonne réponse par *.",
  qcm_multiple: "Un choix par ligne. Commencez chaque bonne réponse par *.",
  courte: "Une réponse acceptée par ligne.",
  trous: "Un trou par ligne, dans l'ordre. Séparez les réponses acceptées par |.",
  association: "Une paire par ligne : gauche = droite.",
  classement: "Un élément par ligne, dans le bon ordre. L'ordre sera mélangé pour l'élève.",
};
const DIFFICULTES = [[1, "Facile"], [2, "Moyenne"], [3, "Difficile"]];

export default function Banque() {
  const qc = useQueryClient();
  const { hasFeature } = useAcademy();
  const [filtres, setFiltres] = useState({ subject: "", difficulte: "", type: "", archive: "false" });
  const [ouvert, setOuvert] = useState(false);
  const [f, setF] = useState({ type: "qcm_unique", difficulte: 2, points: 1, vrai: "vrai" });
  const params = Object.fromEntries(Object.entries(filtres).filter(([, v]) => v));
  const { data, isLoading } = useQuery({ queryKey: ["eval-questions", params], queryFn: () => evaluationsAPI.questions(params) });
  const { data: mats } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: comps } = useQuery({ queryKey: ["suivi-competences"], queryFn: () => suiviAPI.competences({ actif: true }), enabled: hasFeature("suivi_pedagogique") });
  const matieres = mats?.data?.results || mats?.data || [];
  const questions = data?.data?.results || [];
  const rafraichir = () => qc.invalidateQueries({ queryKey: ["eval-questions"] });
  const erreur = { onError: (e) => toast.error(extractApiError(e)) };

  const creer = useMutation({
    mutationFn: async () => {
      const { contenu, corrige } = construireQuestion(f.type, f);
      const r = await evaluationsAPI.creerQuestion({
        type: f.type, enonce: f.enonce, contenu, corrige, points: f.points, difficulte: f.difficulte, criteres: f.criteres || "",
        explication: f.explication || "", prive: !!f.prive, ...(f.subject && { subject: f.subject }), ...(f.competence && { competences: [f.competence] }),
      });
      if (f.media) {
        const d = new FormData();
        d.append("media", f.media);
        d.append("media_type", f.media_type || "document");
        await evaluationsAPI.modifierQuestion(r.data.id, d);
      }
    },
    onSuccess: () => { toast.success(t("Enregistré.")); setOuvert(false); setF({ type: "qcm_unique", difficulte: 2, points: 1, vrai: "vrai" }); rafraichir(); },
    ...erreur,
  });
  const archiver = useMutation({ mutationFn: ({ id, archive }) => evaluationsAPI.archiverQuestion(id, archive), onSuccess: rafraichir, ...erreur });
  const dupliquer = useMutation({ mutationFn: (id) => evaluationsAPI.dupliquerQuestion(id), onSuccess: () => { toast.success(t("Question dupliquée.")); rafraichir(); }, ...erreur });
  const importer = useMutation({
    mutationFn: (fichier) => { const d = new FormData(); d.append("fichier", fichier); return evaluationsAPI.importerQuestions(d); },
    onSuccess: (r) => { toast.success(t("{n} question(s) importée(s).", { n: r.data.importees })); rafraichir(); },
    ...erreur,
  });
  const avecLignes = AIDES[f.type];

  return (
    <div className="space-y-4">
      <PageHeader title={t("Banque de questions")} subtitle={t("Réutilisez vos questions d'une épreuve à l'autre")}
        action={<Link to=".." relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <div className="card flex flex-wrap gap-2 items-end">
        <select className="input w-auto" aria-label={t("Matière")} value={filtres.subject} onChange={(e) => setFiltres({ ...filtres, subject: e.target.value })}>
          <option value="">{t("Toutes matières")}</option>{matieres.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <select className="input w-auto" aria-label={t("Type")} value={filtres.type} onChange={(e) => setFiltres({ ...filtres, type: e.target.value })}>
          <option value="">{t("Tous les types")}</option>{TYPES_QUESTION.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
        </select>
        <select className="input w-auto" aria-label={t("Difficulté")} value={filtres.difficulte} onChange={(e) => setFiltres({ ...filtres, difficulte: e.target.value })}>
          <option value="">{t("Toutes difficultés")}</option>{DIFFICULTES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}
        </select>
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={filtres.archive === "true"} onChange={(e) => setFiltres({ ...filtres, archive: e.target.checked ? "true" : "false" })} />{t("Archivées")}</label>
        <div className="flex-1" />
        <label className="btn-secondary text-sm cursor-pointer">{t("Importer un CSV")}<input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files[0] && importer.mutate(e.target.files[0])} /></label>
        <button type="button" className="btn-secondary text-sm" onClick={async () => telecharger((await evaluationsAPI.exporterQuestions()).data, "questions.csv")}>{t("Exporter")}</button>
        <button type="button" className="btn-primary flex items-center gap-2" onClick={() => setOuvert(true)}><Plus className="w-4 h-4" />{t("Nouvelle question")}</button>
      </div>
      <div className="card">
        {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
        {!isLoading && questions.length === 0 && <p className="text-sm text-slate-500">{t("Aucune question. Créez la première ou importez un fichier.")}</p>}
        <ul className="divide-y divide-slate-100">
          {questions.map((q) => (
            <li key={q.id} className="py-3 flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-900">{q.version?.enonce}</p>
                <p className="text-xs text-slate-500">{libelle(TYPES_QUESTION, q.type)} - {q.subject_name || t("Toutes matières")} - {libelle(DIFFICULTES, q.difficulte)} - {q.version?.points} pt{q.prive ? ` - ${t("Privée")}` : ""}</p>
              </div>
              <div className="flex gap-3 text-xs">
                <button type="button" className="text-primary underline" onClick={() => dupliquer.mutate(q.id)}>{t("Dupliquer")}</button>
                <button type="button" className="text-primary underline" onClick={() => archiver.mutate({ id: q.id, archive: !q.archive })}>{q.archive ? t("Restaurer") : t("Archiver")}</button>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <Modal open={ouvert} onClose={() => setOuvert(false)} title={t("Nouvelle question")} size="lg">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); creer.mutate(); }}>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label" htmlFor="q-type">{t("Type")}</label>
              <select id="q-type" className="input" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{TYPES_QUESTION.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></div>
            <div><label className="label" htmlFor="q-matiere">{t("Matière")}</label>
              <select id="q-matiere" className="input" value={f.subject || ""} onChange={(e) => setF({ ...f, subject: e.target.value })}><option value="">{t("Toutes matières")}</option>{matieres.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
          </div>
          <div><label className="label" htmlFor="q-enonce">{t("Énoncé")} *</label><textarea id="q-enonce" required className="input" rows={3} value={f.enonce || ""} onChange={(e) => setF({ ...f, enonce: e.target.value })} /></div>
          {avecLignes && <div><label className="label" htmlFor="q-lignes">{t("Réponses")} *</label><textarea id="q-lignes" required className="input" rows={4} value={f.lignes || ""} onChange={(e) => setF({ ...f, lignes: e.target.value })} /><p className="text-xs text-slate-500 mt-1">{t(AIDES[f.type])}</p></div>}
          {f.type === "vrai_faux" && <div><label className="label" htmlFor="q-vrai">{t("Bonne réponse")}</label><select id="q-vrai" className="input" value={f.vrai} onChange={(e) => setF({ ...f, vrai: e.target.value })}><option value="vrai">{t("Vrai")}</option><option value="faux">{t("Faux")}</option></select></div>}
          {f.type === "numerique" && <div className="grid grid-cols-2 gap-3">
            <div><label className="label" htmlFor="q-val">{t("Valeur attendue")} *</label><input id="q-val" required className="input" value={f.valeur || ""} onChange={(e) => setF({ ...f, valeur: e.target.value })} /></div>
            <div><label className="label" htmlFor="q-tol">{t("Tolérance")}</label><input id="q-tol" className="input" value={f.tolerance || ""} onChange={(e) => setF({ ...f, tolerance: e.target.value })} /></div></div>}
          {(f.type === "ouverte" || f.type === "fichier") && <div><label className="label" htmlFor="q-crit">{t("Critères de correction")}</label><textarea id="q-crit" className="input" rows={2} value={f.criteres || ""} onChange={(e) => setF({ ...f, criteres: e.target.value })} /></div>}
          <div className="grid sm:grid-cols-3 gap-3">
            <div><label className="label" htmlFor="q-pts">{t("Points")}</label><input id="q-pts" type="number" min="0" step="0.25" className="input" value={f.points} onChange={(e) => setF({ ...f, points: e.target.value })} /></div>
            <div><label className="label" htmlFor="q-dif">{t("Difficulté")}</label><select id="q-dif" className="input" value={f.difficulte} onChange={(e) => setF({ ...f, difficulte: Number(e.target.value) })}>{DIFFICULTES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></div>
            <div><label className="label" htmlFor="q-comp">{t("Compétence")}</label><select id="q-comp" className="input" value={f.competence || ""} onChange={(e) => setF({ ...f, competence: e.target.value })}><option value="">{t("Aucune")}</option>{(comps?.data?.results || []).map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}</select></div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label" htmlFor="q-media">{t("Illustration ou document")}</label><input id="q-media" type="file" className="input" onChange={(e) => setF({ ...f, media: e.target.files[0] })} /></div>
            <div><label className="label" htmlFor="q-mt">{t("Nature du fichier")}</label><select id="q-mt" className="input" value={f.media_type || "document"} onChange={(e) => setF({ ...f, media_type: e.target.value })}><option value="image">{t("Image")}</option><option value="document">{t("Document")}</option><option value="audio">{t("Audio")}</option><option value="video">{t("Vidéo")}</option></select></div>
          </div>
          <div><label className="label" htmlFor="q-exp">{t("Explication, montrée après publication")}</label><textarea id="q-exp" className="input" rows={2} value={f.explication || ""} onChange={(e) => setF({ ...f, explication: e.target.value })} /></div>
          <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={!!f.prive} onChange={(e) => setF({ ...f, prive: e.target.checked })} />{t("Question privée")}</label>
          <div className="flex gap-3 justify-end"><button type="button" className="btn-secondary" onClick={() => setOuvert(false)}>{t("Annuler")}</button><button type="submit" className="btn-primary" disabled={creer.isPending}>{t("Enregistrer")}</button></div>
        </form>
      </Modal>
    </div>
  );
}
