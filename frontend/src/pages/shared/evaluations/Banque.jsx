/** Banque de questions : création simple, filtres, duplication, archivage, import et export. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import toast from "react-hot-toast";
import { evaluationsAPI, subjectsAPI, suiviAPI } from "../../../api";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import Modal from "../../../components/ui/Modal";
import AideModule from "../../../components/ui/AideModule";
import PageHeader from "../../../components/ui/PageHeader";
import { useAcademy } from "../../../context/AcademyContext";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { TYPES_QUESTION, construireQuestion, erreursQuestion, formulaireDepuis, libelle, lignes, telecharger } from "./commun";

const AIDES = {
  courte: "Une réponse acceptée par ligne. Exemple : Paris, puis à la ligne : paris (75).",
  trous: "Un trou par ligne, dans l'ordre. Séparez les réponses acceptées par |. Exemple : chat | le chat",
  association: "Une paire par ligne : gauche = droite. Exemple : France = Paris",
  classement: "Un élément par ligne, dans le bon ordre. L'ordre sera mélangé pour l'élève.",
};
const DIFFICULTES = [[1, "Facile"], [2, "Moyenne"], [3, "Difficile"]];
const AIDE_TYPE = {
  qcm_unique: "L'élève choisit une seule réponse. Correction automatique.",
  qcm_multiple: "L'élève coche plusieurs réponses. Points partiels : bonnes cochées moins mauvaises cochées.",
  vrai_faux: "L'élève répond vrai ou faux. Correction automatique.",
  ouverte: "L'élève rédige. Vous corrigez vous-même.",
  courte: "L'élève écrit un mot ou une courte phrase, comparé aux réponses acceptées, sans tenir compte des majuscules.",
  numerique: "L'élève écrit un nombre, accepté dans la marge de tolérance.",
  trous: "L'élève remplit chaque trou. Écrivez le texte complet dans l'énoncé, en numérotant les trous.",
  association: "L'élève relie chaque élément de gauche à un élément de droite.",
  classement: "L'élève remet les éléments dans l'ordre.",
  fichier: "L'élève dépose un fichier. Vous corrigez vous-même.",
};
const FORM_VIDE = { type: "qcm_unique", difficulte: 2, points: 1, vrai: "vrai", choix: [{ texte: "" }, { texte: "" }, { texte: "" }, { texte: "" }] };

const ACCEPT = { image: "image/*", document: ".pdf,.doc,.docx", audio: "audio/*", video: "video/*" };

function Erreur({ texte }) {
  return texte ? <p role="alert" className="text-xs text-red-700 mt-1">{t(texte)}</p> : null;
}

function ChoixQcm({ type, choix, changer }) {
  const unique = type === "qcm_unique";
  const maj = (i, d) => changer(choix.map((c, j) => {
    if (j === i) return { ...c, ...d };
    return unique && d.bon ? { ...c, bon: false } : c;
  }));
  return (
    <fieldset>
      <legend className="label">{t("Réponses")} *</legend>
      <p className="text-xs text-slate-500 mb-2">{unique ? t("Cochez la bonne réponse.") : t("Cochez toutes les bonnes réponses.")}</p>
      <div className="space-y-2">
        {choix.map((c, i) => (
          <div key={i} className="flex items-center gap-2">
            <input type={unique ? "radio" : "checkbox"} name="bonne-reponse" checked={!!c.bon} aria-label={t("Bonne réponse {n}", { n: i + 1 })} onChange={(e) => maj(i, { bon: e.target.checked })} />
            <input className="input flex-1" aria-label={t("Réponse {n}", { n: i + 1 })} value={c.texte} onChange={(e) => maj(i, { texte: e.target.value })} />
          </div>
        ))}
      </div>
      <button type="button" className="text-xs text-primary underline mt-2" onClick={() => changer([...choix, { texte: "" }])}>{t("Ajouter une réponse")}</button>
    </fieldset>
  );
}

export default function Banque() {
  const qc = useQueryClient();
  const { hasFeature } = useAcademy();
  const [filtres, setFiltres] = useState({ subject: "", difficulte: "", type: "", archive: "false" });
  const [ouvert, setOuvert] = useState(false);
  const [f, setF] = useState(FORM_VIDE);
  const [erreurs, setErreurs] = useState({});
  const [aSupprimer, setASupprimer] = useState(null);
  const fermer = () => { setOuvert(false); setErreurs({}); setF(FORM_VIDE); };
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
      const corps = {
        enonce: f.enonce, contenu, corrige, points: f.points, difficulte: f.difficulte, criteres: f.criteres || "",
        explication: f.explication || "", prive: !!f.prive, subject: f.subject || null, competences: f.competence ? [f.competence] : [],
      };
      const r = f.id ? await evaluationsAPI.modifierQuestion(f.id, corps) : await evaluationsAPI.creerQuestion({ ...corps, type: f.type });
      if (f.media) {
        const d = new FormData();
        d.append("media", f.media);
        d.append("media_type", f.media_type || "document");
        await evaluationsAPI.modifierQuestion(r.data.id, d);
      }
    },
    onSuccess: () => { toast.success(t("Question enregistrée dans la banque.")); fermer(); setFiltres({ subject: "", difficulte: "", type: "", archive: "false" }); rafraichir(); },
    onError: (e) => { const m = extractApiError(e); setErreurs({ serveur: m }); toast.error(m); },
  });
  const archiver = useMutation({ mutationFn: ({ id, archive }) => evaluationsAPI.archiverQuestion(id, archive), onSuccess: rafraichir, ...erreur });
  const dupliquer = useMutation({ mutationFn: (id) => evaluationsAPI.dupliquerQuestion(id), onSuccess: () => { toast.success(t("Question dupliquée.")); rafraichir(); }, ...erreur });
  const importer = useMutation({
    mutationFn: (fichier) => { const d = new FormData(); d.append("fichier", fichier); return evaluationsAPI.importerQuestions(d); },
    onSuccess: (r) => { toast.success(t("{n} question(s) importée(s).", { n: r.data.importees })); rafraichir(); },
    ...erreur,
  });
  const supprimer = useMutation({ mutationFn: (id) => evaluationsAPI.supprimerQuestion(id), onSuccess: () => { toast.success(t("Question supprimée.")); setASupprimer(null); rafraichir(); }, onError: (e) => { toast.error(extractApiError(e)); setASupprimer(null); } });
  const avecLignes = AIDES[f.type];

  return (
    <div className="space-y-4">
      <PageHeader title={t("Banque de questions")} subtitle={t("Réutilisez vos questions d'une épreuve à l'autre")}
        action={<Link to=".." relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <AideModule cle="banque" description={t("Créez ici les questions à réutiliser dans vos quiz et examens. Chacune peut être liée à une matière, une difficulté et une compétence.")}
        etapes={[t("Cliquez sur Nouvelle question."), t("Choisissez le type, puis saisissez l'énoncé et les réponses."), t("Indiquez les points, puis enregistrez."), t("Dans la page d'une épreuve, ajoutez la question depuis la banque.")]}
        conditions={t("Une question déjà utilisée reste figée dans les épreuves publiées, même si vous la modifiez ici.")} />
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
        {!isLoading && questions.length === 0 && (
          <div className="text-center py-6 space-y-2">
            <p className="text-sm text-slate-600">{params.subject || params.type || params.difficulte ? t("Aucune question pour ces filtres.") : t("Aucune question pour le moment. Ajoutez la première pour constituer votre banque.")}</p>
            <button type="button" className="btn-primary" onClick={() => setOuvert(true)}>{t("Nouvelle question")}</button>
          </div>
        )}
        <ul className="divide-y divide-slate-100">
          {questions.map((q) => (
            <li key={q.id} className="py-3 flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-900">{q.version?.enonce}</p>
                <p className="text-xs text-slate-500">{libelle(TYPES_QUESTION, q.type)} - {q.subject_name || t("Toutes matières")} - {libelle(DIFFICULTES, q.difficulte)} - {q.version?.points} pt{q.prive ? ` - ${t("Privée")}` : ""}</p>
              </div>
              <div className="flex gap-3 text-xs">
                <button type="button" className="text-primary underline" onClick={() => { setErreurs({}); setF({ ...FORM_VIDE, ...formulaireDepuis(q) }); setOuvert(true); }}>{t("Modifier")}</button>
                <button type="button" className="text-primary underline" onClick={() => dupliquer.mutate(q.id)}>{t("Dupliquer")}</button>
                <button type="button" className="text-red-700 underline" onClick={() => setASupprimer(q)}>{t("Supprimer")}</button>
                <button type="button" className="text-primary underline" onClick={() => archiver.mutate({ id: q.id, archive: !q.archive })}>{q.archive ? t("Restaurer") : t("Archiver")}</button>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <ConfirmDialog open={!!aSupprimer} onClose={() => setASupprimer(null)} loading={supprimer.isPending} onConfirm={() => supprimer.mutate(aSupprimer.id)} message={t("Supprimer cette question ? Une question déjà utilisée dans une épreuve s'archive, elle ne se supprime pas.")} />
      <Modal open={ouvert} onClose={fermer} title={f.id ? t("Modifier la question") : t("Nouvelle question")} size="lg">
        <form className="space-y-3" noValidate onSubmit={(e) => {
          e.preventDefault();
          const trouvees = erreursQuestion(f.type, f);
          setErreurs(trouvees);
          if (!Object.keys(trouvees).length) creer.mutate();
        }}>
          {f.id && <p className="text-xs rounded bg-amber-50 border border-amber-200 text-amber-800 p-2">{t("Une nouvelle version sera créée. Les épreuves déjà publiées gardent l'ancienne.")}</p>}
          {erreurs.serveur && <p role="alert" className="text-sm text-red-700">{erreurs.serveur}</p>}
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label" htmlFor="q-type">{t("Type")}</label>
              <select id="q-type" className="input" disabled={!!f.id} value={f.type} onChange={(e) => { setErreurs({}); setF({ ...f, type: e.target.value }); }}>{TYPES_QUESTION.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select>
              <p className="text-xs text-slate-500 mt-1">{t(AIDE_TYPE[f.type])}</p></div>
            <div><label className="label" htmlFor="q-matiere">{t("Matière")}</label>
              <select id="q-matiere" className="input" value={f.subject || ""} onChange={(e) => setF({ ...f, subject: e.target.value })}><option value="">{t("Toutes matières")}</option>{matieres.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
          </div>
          <div><label className="label" htmlFor="q-enonce">{t("Énoncé")} *</label><textarea id="q-enonce" className="input" rows={3} placeholder={t("Exemple : Quelle est la capitale de la France ?")} value={f.enonce || ""} onChange={(e) => setF({ ...f, enonce: e.target.value })} />
            <Erreur texte={erreurs.enonce} /></div>
          {(f.type === "qcm_unique" || f.type === "qcm_multiple") && <div><ChoixQcm type={f.type} choix={f.choix} changer={(choix) => setF({ ...f, choix })} /><Erreur texte={erreurs.reponses} /></div>}
          {avecLignes && <div><label className="label" htmlFor="q-lignes">{t("Réponses")} *</label><textarea id="q-lignes" className="input" rows={4} value={f.lignes || ""} onChange={(e) => setF({ ...f, lignes: e.target.value })} /><p className="text-xs text-slate-500 mt-1">{t(AIDES[f.type])}</p>
            <p className="text-xs text-slate-600 mt-1" aria-live="polite">{t("{n} ligne(s) détectée(s).", { n: lignes(f.lignes).length })}</p><Erreur texte={erreurs.reponses} /></div>}
          {f.type === "vrai_faux" && <div><label className="label" htmlFor="q-vrai">{t("Bonne réponse")}</label><select id="q-vrai" className="input" value={f.vrai} onChange={(e) => setF({ ...f, vrai: e.target.value })}><option value="vrai">{t("Vrai")}</option><option value="faux">{t("Faux")}</option></select></div>}
          {f.type === "numerique" && <div className="grid grid-cols-2 gap-3">
            <div><label className="label" htmlFor="q-val">{t("Valeur attendue")} *</label><input id="q-val" className="input" inputMode="decimal" value={f.valeur ?? ""} onChange={(e) => setF({ ...f, valeur: e.target.value })} /><Erreur texte={erreurs.valeur} /></div>
            <div><label className="label" htmlFor="q-tol">{t("Tolérance")}</label><input id="q-tol" className="input" value={f.tolerance ?? ""} onChange={(e) => setF({ ...f, tolerance: e.target.value })} /></div></div>}
          {(f.type === "ouverte" || f.type === "fichier") && <div><label className="label" htmlFor="q-crit">{t("Critères de correction")}</label><textarea id="q-crit" className="input" rows={2} value={f.criteres || ""} onChange={(e) => setF({ ...f, criteres: e.target.value })} /></div>}
          <div className="grid sm:grid-cols-3 gap-3">
            <div><label className="label" htmlFor="q-pts">{t("Points")}</label><input id="q-pts" type="number" min="0" step="0.25" className="input" value={f.points} onChange={(e) => setF({ ...f, points: e.target.value })} /><Erreur texte={erreurs.points} /><p className="text-xs text-slate-500 mt-1">{t("Modifiable pour chaque épreuve.")}</p></div>
            <div><label className="label" htmlFor="q-dif">{t("Difficulté")}</label><select id="q-dif" className="input" value={f.difficulte} onChange={(e) => setF({ ...f, difficulte: Number(e.target.value) })}>{DIFFICULTES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></div>
            <div><label className="label" htmlFor="q-comp">{t("Compétence")}</label><select id="q-comp" className="input" value={f.competence || ""} onChange={(e) => setF({ ...f, competence: e.target.value })}><option value="">{t("Aucune")}</option>{(comps?.data?.results || []).map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}</select><p className="text-xs text-slate-500 mt-1">{t("Facultatif. Relie la question au suivi de l'élève.")}</p></div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label" htmlFor="q-media">{t("Illustration ou document")}</label><input id="q-media" type="file" className="input" accept={ACCEPT[f.media_type || "document"]} onChange={(e) => setF({ ...f, media: e.target.files[0] })} /></div>
            <div><label className="label" htmlFor="q-mt">{t("Nature du fichier")}</label><select id="q-mt" className="input" value={f.media_type || "document"} onChange={(e) => setF({ ...f, media_type: e.target.value })}><option value="image">{t("Image")}</option><option value="document">{t("Document")}</option><option value="audio">{t("Audio")}</option><option value="video">{t("Vidéo")}</option></select></div>
          </div>
          <div><label className="label" htmlFor="q-exp">{t("Explication, montrée après publication")}</label><textarea id="q-exp" className="input" rows={2} value={f.explication || ""} onChange={(e) => setF({ ...f, explication: e.target.value })} /></div>
          <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={!!f.prive} onChange={(e) => setF({ ...f, prive: e.target.checked })} />{t("Question privée")}</label>
          <div className="flex gap-3 justify-end"><button type="button" className="btn-secondary" onClick={fermer}>{t("Annuler")}</button><button type="submit" className="btn-primary" disabled={creer.isPending}>{t("Enregistrer")}</button></div>
        </form>
      </Modal>
    </div>
  );
}
