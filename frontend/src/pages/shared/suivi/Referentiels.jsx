/**
 * Bibliothèque : référentiel, matière, domaine, compétence, critères.
 * Une compétence évaluée s'archive ; elle ne se supprime pas, son historique reste lisible.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Archive, ChevronRight, Copy, FolderTree, Pencil, Plus, Search, Trash2, Upload, Users } from "lucide-react";
import toast from "react-hot-toast";
import { classesAPI, schoolsAPI, subjectsAPI, suiviAPI } from "../../../api";
import AideModule from "../../../components/ui/AideModule";
import { CarteAnimee, Squelette, cascade } from "../../../components/ui/anime";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import Modal from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { AIDE_NIVEAUX } from "./niveaux";

const PERIODES = [["", "Toute l'année"], ["T1", "Trimestre 1"], ["T2", "Trimestre 2"], ["T3", "Trimestre 3"]];
const liste = (d) => d?.data?.results || d?.data || [];

function Champ({ id, label, children, aide }) {
  return <div><label className="label" htmlFor={id}>{label}</label>{children}{aide && <p className="text-xs text-slate-500 mt-1">{aide}</p>}</div>;
}

export default function Referentiels() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const admin = user?.role === "admin" || user?.role === "superadmin";
  const [recherche, setRecherche] = useState("");
  const [archives, setArchives] = useState(false);
  const [ouverts, setOuverts] = useState({});
  const [fRef, setFRef] = useState(null);
  const [fComp, setFComp] = useState(null);
  const [aSupprimer, setASupprimer] = useState(null);
  const { data: refs, isLoading } = useQuery({ queryKey: ["suivi-referentiels"], queryFn: () => suiviAPI.referentiels() });
  const { data: comps } = useQuery({ queryKey: ["suivi-competences", "tout"], queryFn: () => suiviAPI.competences() });
  const { data: niveaux } = useQuery({ queryKey: ["suivi-niveaux"], queryFn: () => suiviAPI.niveaux() });
  const { data: matieres } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: nivScol } = useQuery({ queryKey: ["levels"], queryFn: () => schoolsAPI.levels() });
  const { data: classes } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const rafraichir = () => { qc.invalidateQueries({ queryKey: ["suivi-referentiels"] }); qc.invalidateQueries({ queryKey: ["suivi-competences"] }); };
  const erreur = { onError: (e) => toast.error(extractApiError(e)) };
  const ok = (m) => () => { toast.success(m); rafraichir(); };
  const sauverRef = useMutation({
    mutationFn: () => {
      const { id, ...d } = fRef;
      const corps = { ...d, subject: d.subject || null, level: d.level || null, class_obj: d.class_obj || null };
      return id ? suiviAPI.modifierReferentiel(id, corps) : suiviAPI.creerReferentiel(corps);
    },
    onSuccess: (r) => { ok(t("Référentiel enregistré."))(); setFRef(null); setOuverts((o) => ({ ...o, [r.data.id]: true })); }, ...erreur,
  });
  const sauverComp = useMutation({
    mutationFn: () => {
      const { id, ...d } = fComp;
      const corps = { ...d, subject: d.subject || null, niveau_attendu: d.niveau_attendu || null };
      return id ? suiviAPI.modifierCompetence(id, corps) : suiviAPI.creerCompetence(corps);
    },
    onSuccess: () => { ok(t("Compétence enregistrée."))(); setFComp(null); }, ...erreur,
  });
  const action = useMutation({ mutationFn: (fn) => fn(), onSuccess: ok(t("Enregistré.")), ...erreur });
  const importer = useMutation({
    mutationFn: ({ referentiel, fichier }) => { const d = new FormData(); d.append("referentiel", referentiel); d.append("fichier", fichier); return suiviAPI.importerCompetences(d); },
    onSuccess: (r) => { toast.success(t("{a} compétence(s) ajoutée(s), {b} déjà présente(s).", { a: r.data.creees, b: r.data.ignorees })); rafraichir(); }, ...erreur,
  });
  const majNiveau = useMutation({ mutationFn: ({ id, d }) => suiviAPI.modifierNiveau(id, d), onSuccess: ok(t("Enregistré.")), ...erreur });

  const toutes = useMemo(() => liste(comps), [comps]);
  const q = recherche.toLowerCase();
  const arbre = liste(refs).filter((r) => archives || r.actif).map((r) => {
    const siennes = toutes.filter((c) => c.referentiel === r.id && (archives || c.actif) && (!q || `${c.nom} ${c.domaine} ${c.sous_domaine} ${c.description}`.toLowerCase().includes(q)));
    const domaines = {};
    siennes.forEach((c) => { (domaines[c.domaine || t("Sans domaine")] ||= []).push(c); });
    return { r, siennes, domaines };
  }).filter(({ r, siennes }) => !q || siennes.length || r.nom.toLowerCase().includes(q));
  const domainesConnus = [...new Set(toutes.map((c) => c.domaine).filter(Boolean))];
  const vide = !isLoading && liste(refs).length === 0;
  const nouvelleComp = (r, domaine = "") => setFComp({ referentiel: r.id, nom: "", domaine, sous_domaine: "", description: "", objectif: "", criteres: "", subject: r.subject || "", niveau_attendu: "", periode: r.periode || "" });

  return (
    <div className="space-y-4">
      <PageHeader title={t("Référentiels et compétences")} subtitle={t("Ce que chaque élève doit savoir faire")}
        action={<div className="flex flex-wrap gap-2"><Link to="../evaluer" relative="path" className="btn-secondary text-sm inline-flex items-center gap-1"><Users className="w-4 h-4" aria-hidden="true" />{t("Évaluer une classe")}</Link>
          <button type="button" className="btn-primary text-sm inline-flex items-center gap-1" onClick={() => setFRef({ nom: "", description: "", subject: "", level: "", class_obj: "", periode: "", programme: "" })}><Plus className="w-4 h-4" aria-hidden="true" />{t("Nouveau référentiel")}</button></div>} />
      <AideModule cle="referentiels" description={t("Une compétence décrit ce qu'un élève sait faire. Un référentiel les regroupe, par matière ou par programme.")}
        etapes={[t("Créez un référentiel, par exemple « Français CM1 »."), t("Ajoutez ses compétences, rangées par domaine."), t("Évaluez-les depuis la fiche d'un élève, ou pour toute une classe.")]}
        conditions={t("Une compétence déjà évaluée se désactive, elle ne se supprime pas : son historique est conservé.")} />
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-52"><Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input className="input pl-9" placeholder={t("Rechercher une compétence ou un domaine")} aria-label={t("Rechercher une compétence ou un domaine")} value={recherche} onChange={(e) => setRecherche(e.target.value)} /></div>
        <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={archives} onChange={(e) => setArchives(e.target.checked)} />{t("Afficher les archives")}</label>
      </div>
      {isLoading && <Squelette />}
      {vide && (
        <div className="card text-center py-10 space-y-3">
          <FolderTree className="w-10 h-10 mx-auto text-slate-400" aria-hidden="true" />
          <p className="text-sm text-slate-600">{t("Aucun référentiel pour le moment. Créez-en un pour y ranger vos compétences.")}</p>
          <button type="button" className="btn-primary" onClick={() => setFRef({ nom: "", description: "", subject: "", level: "", class_obj: "", periode: "", programme: "" })}>{t("Créer le premier référentiel")}</button>
        </div>
      )}
      <motion.div variants={cascade} initial="hidden" animate="show" className="space-y-3">
        {arbre.map(({ r, siennes, domaines }) => {
          const ouvert = ouverts[r.id] || !!q;
          return (
            <CarteAnimee key={r.id} className={`overflow-hidden ${r.actif ? "" : "opacity-70"}`}>
              <div className="flex flex-wrap items-center gap-2 p-4">
                <button type="button" aria-expanded={ouvert} onClick={() => setOuverts({ ...ouverts, [r.id]: !ouvert })} className="flex items-center gap-2 flex-1 min-w-48 text-left">
                  <motion.span animate={{ rotate: ouvert ? 90 : 0 }}><ChevronRight className="w-4 h-4 text-slate-500" aria-hidden="true" /></motion.span>
                  <span>
                    <span className="block font-semibold text-slate-900">{r.nom}{!r.actif && ` (${t("archivé")})`}</span>
                    <span className="block text-xs text-slate-500">{[r.subject_name, r.level_name, r.class_name, r.periode, r.programme].filter(Boolean).join(" - ") || t("Toutes matières")} - {t("{n} compétence(s)", { n: siennes.length })}</span>
                  </span>
                </button>
                <button type="button" className="btn-secondary text-xs inline-flex items-center gap-1" onClick={() => nouvelleComp(r)}><Plus className="w-3 h-3" aria-hidden="true" />{t("Compétence")}</button>
                <label className="btn-secondary text-xs inline-flex items-center gap-1 cursor-pointer"><Upload className="w-3 h-3" aria-hidden="true" />{t("Importer")}<input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files[0] && importer.mutate({ referentiel: r.id, fichier: e.target.files[0] })} /></label>
                <button type="button" title={t("Modifier")} aria-label={t("Modifier")} className="p-1.5 text-slate-500 hover:text-primary" onClick={() => setFRef({ id: r.id, nom: r.nom, description: r.description, subject: r.subject || "", level: r.level || "", class_obj: r.class_obj || "", periode: r.periode, programme: r.programme })}><Pencil className="w-4 h-4" /></button>
                <button type="button" title={t("Dupliquer")} aria-label={t("Dupliquer")} className="p-1.5 text-slate-500 hover:text-primary" onClick={() => action.mutate(() => suiviAPI.dupliquerReferentiel(r.id))}><Copy className="w-4 h-4" /></button>
                <button type="button" title={r.actif ? t("Archiver") : t("Restaurer")} aria-label={r.actif ? t("Archiver") : t("Restaurer")} className="p-1.5 text-slate-500 hover:text-primary" onClick={() => action.mutate(() => suiviAPI.modifierReferentiel(r.id, { actif: !r.actif }))}><Archive className="w-4 h-4" /></button>
              </div>
              <AnimatePresence initial={false}>
                {ouvert && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="px-4 pb-4 space-y-3">
                      {siennes.length === 0 && <p className="text-sm text-slate-500">{t("Aucune compétence. Ajoutez la première.")}</p>}
                      {Object.entries(domaines).map(([domaine, lignes]) => (
                        <div key={domaine}>
                          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">{domaine}</h3>
                          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
                            {lignes.map((c) => (
                              <li key={c.id} className="flex flex-wrap items-start gap-2 p-3 hover:bg-slate-50 transition-colors">
                                <div className="flex-1 min-w-48">
                                  <p className={`text-sm font-medium ${c.actif ? "text-slate-900" : "text-slate-400 line-through"}`}>{c.nom}{c.sous_domaine ? <span className="font-normal text-slate-500"> - {c.sous_domaine}</span> : null}</p>
                                  {c.description && <p className="text-xs text-slate-600">{c.description}</p>}
                                  {c.criteres && <p className="text-xs text-slate-500">{t("Critères")} : {c.criteres}</p>}
                                  <p className="text-xs text-slate-400 mt-0.5">{t("{a} évaluation(s), {b} élève(s)", { a: c.nombre_evaluations, b: c.nombre_eleves })}{c.subject_name ? ` - ${c.subject_name}` : ""}</p>
                                </div>
                                <button type="button" title={t("Modifier")} aria-label={t("Modifier {x}", { x: c.nom })} className="p-1.5 text-slate-500 hover:text-primary" onClick={() => setFComp({ id: c.id, referentiel: c.referentiel, nom: c.nom, domaine: c.domaine, sous_domaine: c.sous_domaine, description: c.description, objectif: c.objectif, criteres: c.criteres, subject: c.subject || "", niveau_attendu: c.niveau_attendu || "", periode: c.periode })}><Pencil className="w-4 h-4" /></button>
                                <button type="button" title={c.actif ? t("Archiver") : t("Restaurer")} aria-label={`${c.actif ? t("Archiver") : t("Restaurer")} ${c.nom}`} className="p-1.5 text-slate-500 hover:text-primary" onClick={() => action.mutate(() => suiviAPI.modifierCompetence(c.id, { actif: !c.actif }))}><Archive className="w-4 h-4" /></button>
                                {c.supprimable && <button type="button" title={t("Supprimer")} aria-label={`${t("Supprimer")} ${c.nom}`} className="p-1.5 text-slate-500 hover:text-red-700" onClick={() => setASupprimer(c)}><Trash2 className="w-4 h-4" /></button>}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </CarteAnimee>
          );
        })}
      </motion.div>
      <div className="card space-y-3">
        <h2 className="text-sm font-semibold text-slate-800">{t("Niveaux de maîtrise")}</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(niveaux?.data || []).map((n) => (
            <div key={n.id} className="rounded-xl border border-slate-200 p-3">
              <div className="h-1.5 rounded-full mb-2" style={{ background: n.couleur }} aria-hidden="true" />
              {admin ? <input key={n.libelle} className="input text-sm" aria-label={t("Libellé")} defaultValue={n.libelle} onBlur={(e) => e.target.value && e.target.value !== n.libelle && majNiveau.mutate({ id: n.id, d: { libelle: e.target.value } })} /> : <p className="text-sm font-medium">{n.libelle}</p>}
              <p className="text-xs text-slate-500 mt-1">{t(AIDE_NIVEAUX[n.code] || "")}</p>
            </div>
          ))}
        </div>
      </div>
      <details className="text-xs text-slate-500"><summary className="cursor-pointer">{t("Format du fichier d'import")}</summary><p className="mt-1">{t("CSV en UTF-8, première ligne : nom,domaine,sous_domaine,description,criteres. Seule la colonne nom est obligatoire. Les compétences déjà présentes sont ignorées.")}</p></details>

      <Modal open={!!fRef} onClose={() => setFRef(null)} title={fRef?.id ? t("Modifier le référentiel") : t("Nouveau référentiel")}>
        {fRef && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); sauverRef.mutate(); }}>
            <Champ id="r-nom" label={`${t("Nom")} *`} aide={t("Exemple : Français CM1")}><input id="r-nom" required className="input" value={fRef.nom} onChange={(e) => setFRef({ ...fRef, nom: e.target.value })} /></Champ>
            <div className="grid sm:grid-cols-2 gap-3">
              <Champ id="r-mat" label={t("Matière")} aide={<Link className="underline" to="/admin/subjects">{t("Créer une matière")}</Link>}><select id="r-mat" className="input" value={fRef.subject} onChange={(e) => setFRef({ ...fRef, subject: e.target.value })}><option value="">{t("Toutes matières")}</option>{liste(matieres).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Champ>
              <Champ id="r-niv" label={t("Niveau scolaire")}><select id="r-niv" className="input" value={fRef.level} onChange={(e) => setFRef({ ...fRef, level: e.target.value })}><option value="">{t("Tous les niveaux")}</option>{liste(nivScol).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Champ>
              <Champ id="r-cl" label={t("Classe")}><select id="r-cl" className="input" value={fRef.class_obj} onChange={(e) => setFRef({ ...fRef, class_obj: e.target.value })}><option value="">{t("Toutes les classes")}</option>{liste(classes).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Champ>
              <Champ id="r-per" label={t("Période")}><select id="r-per" className="input" value={fRef.periode} onChange={(e) => setFRef({ ...fRef, periode: e.target.value })}>{PERIODES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></Champ>
            </div>
            <Champ id="r-prog" label={t("Programme pédagogique")}><input id="r-prog" className="input" value={fRef.programme} onChange={(e) => setFRef({ ...fRef, programme: e.target.value })} /></Champ>
            <Champ id="r-desc" label={t("Description")}><textarea id="r-desc" className="input" rows={2} value={fRef.description} onChange={(e) => setFRef({ ...fRef, description: e.target.value })} /></Champ>
            <div className="flex gap-3 justify-end"><button type="button" className="btn-secondary" onClick={() => setFRef(null)}>{t("Annuler")}</button><button type="submit" className="btn-primary" disabled={sauverRef.isPending}>{t("Enregistrer")}</button></div>
          </form>
        )}
      </Modal>
      <Modal open={!!fComp} onClose={() => setFComp(null)} title={fComp?.id ? t("Modifier la compétence") : t("Nouvelle compétence")} size="lg">
        {fComp && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); sauverComp.mutate(); }}>
            <Champ id="c-nom" label={`${t("Nom de la compétence")} *`} aide={t("Exemple : Comprendre un texte court")}><input id="c-nom" required className="input" value={fComp.nom} onChange={(e) => setFComp({ ...fComp, nom: e.target.value })} /></Champ>
            <div className="grid sm:grid-cols-2 gap-3">
              <Champ id="c-dom" label={t("Domaine")} aide={t("Exemple : Lecture")}><input id="c-dom" list="domaines-connus" className="input" value={fComp.domaine} onChange={(e) => setFComp({ ...fComp, domaine: e.target.value })} /><datalist id="domaines-connus">{domainesConnus.map((d) => <option key={d} value={d} />)}</datalist></Champ>
              <Champ id="c-sd" label={t("Sous-domaine")}><input id="c-sd" className="input" value={fComp.sous_domaine} onChange={(e) => setFComp({ ...fComp, sous_domaine: e.target.value })} /></Champ>
              <Champ id="c-mat" label={t("Matière")}><select id="c-mat" className="input" value={fComp.subject} onChange={(e) => setFComp({ ...fComp, subject: e.target.value })}><option value="">{t("Celle du référentiel")}</option>{liste(matieres).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Champ>
              <Champ id="c-att" label={t("Niveau attendu")}><select id="c-att" className="input" value={fComp.niveau_attendu} onChange={(e) => setFComp({ ...fComp, niveau_attendu: e.target.value })}><option value="">{t("Aucun")}</option>{(niveaux?.data || []).map((n) => <option key={n.id} value={n.id}>{n.libelle}</option>)}</select></Champ>
              <Champ id="c-per" label={t("Période")}><select id="c-per" className="input" value={fComp.periode} onChange={(e) => setFComp({ ...fComp, periode: e.target.value })}>{PERIODES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></Champ>
            </div>
            <Champ id="c-desc" label={t("Description")}><textarea id="c-desc" className="input" rows={2} value={fComp.description} onChange={(e) => setFComp({ ...fComp, description: e.target.value })} /></Champ>
            <Champ id="c-obj" label={t("Objectif pédagogique")}><textarea id="c-obj" className="input" rows={2} value={fComp.objectif} onChange={(e) => setFComp({ ...fComp, objectif: e.target.value })} /></Champ>
            <Champ id="c-cri" label={t("Critères d'évaluation")} aide={t("Ce que l'enseignant observe pour décider du niveau.")}><textarea id="c-cri" className="input" rows={2} value={fComp.criteres} onChange={(e) => setFComp({ ...fComp, criteres: e.target.value })} /></Champ>
            <div className="flex gap-3 justify-end"><button type="button" className="btn-secondary" onClick={() => setFComp(null)}>{t("Annuler")}</button><button type="submit" className="btn-primary" disabled={sauverComp.isPending}>{t("Enregistrer")}</button></div>
          </form>
        )}
      </Modal>
      <ConfirmDialog open={!!aSupprimer} onClose={() => setASupprimer(null)} onConfirm={() => { action.mutate(() => suiviAPI.supprimerCompetence(aSupprimer.id)); setASupprimer(null); }} message={t("Supprimer cette compétence ? Elle n'a encore aucune évaluation.")} />
    </div>
  );
}
