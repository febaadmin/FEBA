/** Référentiels de compétences et niveaux de maîtrise, sans passer par le code. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { subjectsAPI, suiviAPI } from "../../../api";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";

export default function Referentiels() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const admin = user?.role === "admin" || user?.role === "superadmin";
  const [nouveau, setNouveau] = useState({ nom: "", subject: "" });
  const [choisi, setChoisi] = useState(null);
  const [competence, setCompetence] = useState({ nom: "", domaine: "", criteres: "" });
  const { data: refs, isLoading } = useQuery({ queryKey: ["suivi-referentiels"], queryFn: () => suiviAPI.referentiels() });
  const { data: comps } = useQuery({ queryKey: ["suivi-competences", choisi], queryFn: () => suiviAPI.competences({ referentiel: choisi }), enabled: !!choisi });
  const { data: niveaux } = useQuery({ queryKey: ["suivi-niveaux"], queryFn: () => suiviAPI.niveaux() });
  const { data: matieres } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const liste = refs?.data?.results || [];
  const opts = { onError: (e) => toast.error(extractApiError(e)) };
  const creerRef = useMutation({
    mutationFn: () => suiviAPI.creerReferentiel({ nom: nouveau.nom, ...(nouveau.subject && { subject: nouveau.subject }) }),
    onSuccess: () => { setNouveau({ nom: "", subject: "" }); qc.invalidateQueries({ queryKey: ["suivi-referentiels"] }); toast.success(t("Enregistré.")); }, ...opts,
  });
  const creerComp = useMutation({
    mutationFn: () => suiviAPI.creerCompetence({ ...competence, referentiel: choisi }),
    onSuccess: () => { setCompetence({ nom: "", domaine: "", criteres: "" }); qc.invalidateQueries({ queryKey: ["suivi-competences"] }); toast.success(t("Enregistré.")); }, ...opts,
  });
  const majComp = useMutation({ mutationFn: ({ id, d }) => suiviAPI.modifierCompetence(id, d), onSuccess: () => qc.invalidateQueries({ queryKey: ["suivi-competences"] }), ...opts });
  const majNiveau = useMutation({ mutationFn: ({ id, d }) => suiviAPI.modifierNiveau(id, d), onSuccess: () => { qc.invalidateQueries({ queryKey: ["suivi-niveaux"] }); toast.success(t("Enregistré.")); }, ...opts });

  return (
    <div className="space-y-4">
      <PageHeader title={t("Référentiels de compétences")} subtitle={t("Ce que chaque élève doit savoir faire")}
        action={<Link to=".." relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">{t("Référentiels")}</h2>
          {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
          {!isLoading && liste.length === 0 && <p className="text-sm text-slate-500">{t("Aucun référentiel. Créez le premier ci-dessous.")}</p>}
          <ul className="divide-y divide-slate-100">
            {liste.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => setChoisi(r.id)} className={`w-full text-left py-2 px-2 rounded text-sm ${choisi === r.id ? "bg-slate-100 font-medium" : ""}`}>
                  {r.nom} <span className="text-xs text-slate-500">({t("{n} compétence(s)", { n: r.nombre_competences })})</span>
                </button>
              </li>
            ))}
          </ul>
          <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); creerRef.mutate(); }}>
            <input className="input flex-1 min-w-40" required placeholder={t("Nom du référentiel")} aria-label={t("Nom du référentiel")} value={nouveau.nom} onChange={(e) => setNouveau({ ...nouveau, nom: e.target.value })} />
            <select className="input w-auto" aria-label={t("Matière")} value={nouveau.subject} onChange={(e) => setNouveau({ ...nouveau, subject: e.target.value })}>
              <option value="">{t("Toutes matières")}</option>
              {(matieres?.data?.results || matieres?.data || []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
            <button className="btn-primary" type="submit" disabled={creerRef.isPending}>{t("Créer")}</button>
          </form>
        </div>
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">{t("Compétences")}</h2>
          {!choisi && <p className="text-sm text-slate-500">{t("Choisissez un référentiel.")}</p>}
          {choisi && (
            <>
              <ul className="divide-y divide-slate-100">
                {(comps?.data?.results || []).map((c) => (
                  <li key={c.id} className="py-2 flex items-center justify-between gap-2 text-sm">
                    <span className={c.actif ? "text-slate-800" : "text-slate-400 line-through"}>{c.nom}{c.domaine ? ` - ${c.domaine}` : ""}</span>
                    <button type="button" className="text-xs text-primary underline" onClick={() => majComp.mutate({ id: c.id, d: { actif: !c.actif } })}>{c.actif ? t("Désactiver") : t("Réactiver")}</button>
                  </li>
                ))}
              </ul>
              <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); creerComp.mutate(); }}>
                <input className="input" required placeholder={t("Nom de la compétence")} aria-label={t("Nom de la compétence")} value={competence.nom} onChange={(e) => setCompetence({ ...competence, nom: e.target.value })} />
                <input className="input" placeholder={t("Domaine")} aria-label={t("Domaine")} value={competence.domaine} onChange={(e) => setCompetence({ ...competence, domaine: e.target.value })} />
                <textarea className="input" rows={2} placeholder={t("Critères de maîtrise")} aria-label={t("Critères de maîtrise")} value={competence.criteres} onChange={(e) => setCompetence({ ...competence, criteres: e.target.value })} />
                <button className="btn-primary" type="submit" disabled={creerComp.isPending}>{t("Ajouter la compétence")}</button>
              </form>
            </>
          )}
        </div>
      </div>
      <div className="card space-y-2">
        <h2 className="text-sm font-semibold text-slate-800">{t("Niveaux de maîtrise")}</h2>
        {(niveaux?.data || []).map((n) => (
          <div key={n.id} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="w-4 h-4 rounded" style={{ background: n.couleur }} aria-hidden="true" />
            {admin ? (
              <input key={n.libelle} className="input w-56" aria-label={t("Libellé")} defaultValue={n.libelle}
                onBlur={(e) => e.target.value && e.target.value !== n.libelle && majNiveau.mutate({ id: n.id, d: { libelle: e.target.value } })} />
            ) : <span>{n.libelle}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
