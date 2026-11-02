/** Liste et création des épreuves, pour le personnel. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import toast from "react-hot-toast";
import { classesAPI, evaluationsAPI, subjectsAPI } from "../../../api";
import Modal from "../../../components/ui/Modal";
import AideModule from "../../../components/ui/AideModule";
import PageHeader from "../../../components/ui/PageHeader";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { STATUTS_EPREUVE, TYPES_EPREUVE, libelle } from "./commun";

const VIDE = { type: "quiz", duree_minutes: 30, tentatives_max: 1, seuil_reussite: 50, note_max: 20, melanger_questions: true, melanger_reponses: true, retour_autorise: true, reprise_autorisee: true, produit_note: false, note_type: "examen" };

export default function Epreuves() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const base = useLocation().pathname.replace(/\/$/, "");
  const [ouvert, setOuvert] = useState(false);
  const [f, setF] = useState(VIDE);
  const { data, isLoading } = useQuery({ queryKey: ["eval-epreuves"], queryFn: () => evaluationsAPI.epreuves() });
  const { data: mats } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: cls } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const liste = data?.data?.results || [];
  const creer = useMutation({
    mutationFn: () => evaluationsAPI.creerEpreuve({ ...Object.fromEntries(Object.entries(f).filter(([k, v]) => k !== "politique" || v)), ouverture: new Date(f.ouverture).toISOString(), fermeture: new Date(f.fermeture).toISOString(), ...(f.periode ? {} : { periode: "" }) }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["eval-epreuves"] }); nav(`${base}/${r.data.id}`); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const champ = (cle) => ({ value: f[cle] ?? "", onChange: (e) => setF({ ...f, [cle]: e.target.value }) });
  const coche = (cle) => ({ checked: !!f[cle], onChange: (e) => setF({ ...f, [cle]: e.target.checked }) });

  return (
    <div className="space-y-4">
      <PageHeader title={t("Examens et évaluations")} subtitle={t("Créez, publiez, corrigez et analysez vos épreuves")}
        action={<div className="flex gap-2"><Link to={`${base}/banque`} className="btn-secondary text-sm">{t("Banque de questions")}</Link>
          <button type="button" className="btn-primary flex items-center gap-2" onClick={() => setOuvert(true)}><Plus className="w-4 h-4" />{t("Nouvelle épreuve")}</button></div>} />
      <AideModule cle="epreuves" description={t("Un quiz sert à s'entraîner. Un examen officiel peut produire une note, seulement après votre validation.")}
        etapes={[t("Créez vos questions dans la banque."), t("Créez une épreuve : classe, dates, durée."), t("Ajoutez les questions, puis publiez."), t("Corrigez les copies et validez-les."), t("Publiez les résultats, puis transférez vers les notes si besoin.")]}
        conditions={t("Vous ne pouvez créer une épreuve que pour une matière qui vous est affectée dans la classe choisie.")} />
      <div className="card">
        {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
        {!isLoading && liste.length === 0 && (
          <div className="text-center py-6 space-y-2">
            <p className="text-sm text-slate-600">{t("Aucune épreuve pour le moment. Créez d'abord vos questions, puis votre première épreuve.")}</p>
            <button type="button" className="btn-primary" onClick={() => setOuvert(true)}>{t("Nouvelle épreuve")}</button>
          </div>
        )}
        <ul className="divide-y divide-slate-100">
          {liste.map((e) => (
            <li key={e.id}><Link to={`${base}/${e.id}`} className="py-3 px-2 flex flex-wrap justify-between gap-2 hover:bg-slate-50 rounded-lg">
              <span><span className="block text-sm font-medium text-slate-900">{e.titre}</span>
                <span className="block text-xs text-slate-500">{libelle(TYPES_EPREUVE, e.type)} - {e.subject_name} - {e.class_name}</span></span>
              <span className="text-sm text-slate-700">{t(STATUTS_EPREUVE[e.statut])}</span>
            </Link></li>
          ))}
        </ul>
      </div>
      <Modal open={ouvert} onClose={() => setOuvert(false)} title={t("Nouvelle épreuve")} size="lg">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); creer.mutate(); }}>
          <div><label className="label" htmlFor="e-titre">{t("Titre")} *</label><input id="e-titre" required className="input" {...champ("titre")} /></div>
          <div><label className="label" htmlFor="e-desc">{t("Description")}</label><textarea id="e-desc" className="input" rows={2} {...champ("description")} /></div>
          <div className="grid sm:grid-cols-3 gap-3">
            <div><label className="label" htmlFor="e-type">{t("Type")}</label><select id="e-type" className="input" {...champ("type")}>{TYPES_EPREUVE.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></div>
            <div><label className="label" htmlFor="e-mat">{t("Matière")} *</label><select id="e-mat" required className="input" {...champ("subject")}><option value="">{t("Choisir")}</option>{(mats?.data?.results || mats?.data || []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>
            <div><label className="label" htmlFor="e-cl">{t("Classe")} *</label><select id="e-cl" required className="input" {...champ("class_obj")}><option value="">{t("Choisir")}</option>{(cls?.data?.results || cls?.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><label className="label" htmlFor="e-ouv">{t("Ouverture")} *</label><input id="e-ouv" required type="datetime-local" className="input" {...champ("ouverture")} /></div>
            <div><label className="label" htmlFor="e-fer">{t("Fermeture")} *</label><input id="e-fer" required type="datetime-local" className="input" {...champ("fermeture")} /></div>
          </div>
          <p className="text-xs text-slate-500">{t("Heures de votre appareil ({z}). Après la fermeture, plus aucune épreuve ne peut commencer.", { z: Intl.DateTimeFormat().resolvedOptions().timeZone })}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div><label className="label" htmlFor="e-dur">{t("Durée (min)")}</label><input id="e-dur" type="number" min="1" className="input" {...champ("duree_minutes")} /></div>
            <div><label className="label" htmlFor="e-ten">{t("Tentatives")}</label><input id="e-ten" type="number" min="1" className="input" {...champ("tentatives_max")} /><p className="text-xs text-slate-500 mt-1">{t("Nombre de passages autorisés.")}</p></div>
            <div><label className="label" htmlFor="e-max">{t("Note maximale")}</label><input id="e-max" type="number" min="1" className="input" {...champ("note_max")} /></div>
            <div><label className="label" htmlFor="e-seu">{t("Seuil de réussite (%)")}</label><input id="e-seu" type="number" min="0" max="100" className="input" {...champ("seuil_reussite")} /></div>
          </div>
          <div><label className="label" htmlFor="e-con">{t("Consignes")}</label><textarea id="e-con" className="input" rows={2} {...champ("consignes")} /></div>
          <div className="grid sm:grid-cols-2 gap-2 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" {...coche("melanger_questions")} />{t("Mélanger les questions")}</label>
            <label className="flex items-center gap-2"><input type="checkbox" {...coche("melanger_reponses")} />{t("Mélanger les réponses")}</label>
            <label className="flex items-center gap-2"><input type="checkbox" {...coche("retour_autorise")} />{t("Retour aux questions autorisé")}</label>
            <label className="flex items-center gap-2"><input type="checkbox" {...coche("reprise_autorisee")} />{t("Reprise après coupure autorisée")}</label>
            <label className="flex items-center gap-2"><input type="checkbox" {...coche("produit_note")} />{t("Peut produire une note officielle")}</label>
          </div>
          {f.tentatives_max > 1 && <div><label className="label" htmlFor="e-pol">{t("Tentative retenue pour la note")}</label><select id="e-pol" className="input" {...champ("politique")}><option value="">{t("Par défaut : dernière pour un examen, meilleure sinon")}</option><option value="meilleure">{t("Meilleure tentative")}</option><option value="derniere">{t("Dernière tentative")}</option><option value="premiere">{t("Première tentative")}</option><option value="validee">{t("Choisie par l'enseignant")}</option></select></div>}
          {f.produit_note && <div><label className="label" htmlFor="e-per">{t("Trimestre")} *</label><select id="e-per" required className="input" {...champ("periode")}><option value="">{t("Choisir")}</option><option value="T1">T1</option><option value="T2">T2</option><option value="T3">T3</option></select></div>}
          <div className="flex gap-3 justify-end"><button type="button" className="btn-secondary" onClick={() => setOuvert(false)}>{t("Annuler")}</button><button type="submit" className="btn-primary" disabled={creer.isPending}>{t("Créer")}</button></div>
        </form>
      </Modal>
    </div>
  );
}
