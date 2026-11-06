/**
 * Remises et exonérations : règles de l'académie (périmètre, valeur, période,
 * conditions, cumul), avec l'impact calculé par le serveur (élèves concernés et
 * montants réellement accordés). Une règle n'est jamais supprimée : elle est
 * annulée avec un motif, et toute modification est tracée au journal financier.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { BadgePercent, Plus, ShieldCheck } from "lucide-react";
import { classesAPI, parentsAPI, paymentsAPI, remisesAPI, studentsAPI } from "../../api";
import Modal from "../ui/Modal";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatCalendarDate } from "../../utils/datetime";
import { NATURES_FRAIS } from "../../utils/naturesFrais";

export const CATEGORIES = {
  remise: [["exceptionnelle", "Remise exceptionnelle"], ["fratrie", "Plusieurs enfants d'une même famille"],
    ["paiement_anticipe", "Paiement anticipé"], ["paiement_integral", "Paiement intégral"], ["sociale", "Remise sociale"],
    ["situation_particuliere", "Situation particulière"], ["decision_administrative", "Décision administrative"], ["autre", "Autre"]],
  exoneration: [["sociale", "Remise sociale"], ["situation_particuliere", "Situation particulière"],
    ["decision_administrative", "Décision administrative"], ["exceptionnelle", "Remise exceptionnelle"], ["autre", "Autre"]],
};
// Catégorie proposée par défaut : « Autre » pour une remise (aucune justification
// imposée), un motif social pour une exonération (toujours justifiée).
const DEFAUT = { remise: "autre", exoneration: "sociale" };
const JUSTIFIER = new Set(["exceptionnelle", "sociale", "situation_particuliere", "decision_administrative"]);
const liste = (q) => q.data?.data?.results || q.data?.data || [];
const VIDE = { nom: "", description: "", genre: "remise", categorie: "autre", mode: "pourcentage", pourcentage: "", montant: "",
  school_year: "", payment_type: "", level: "", class_obj: "", student: "", famille: "", debut: "", fin: "",
  rang_enfant_min: "", date_limite_paiement: "", cumulable: true, priorite: 0, justification: "", motif: "" };

function Champ({ libelle, aide, children, id }) {
  return (
    <label className="block text-sm" htmlFor={id}>
      <span className="label">{t(libelle)}</span>
      {children}
      {aide && <span className="block text-[11px] text-slate-500 mt-0.5">{t(aide)}</span>}
    </label>
  );
}

function Formulaire({ initial, options, onFermer }) {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const [f, setF] = useState(initial);
  const [erreurs, setErreurs] = useState({});
  const maj = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const enregistrer = useMutation({
    mutationFn: () => {
      const corps = { ...f };
      ["school_year", "level", "class_obj", "student", "famille", "debut", "fin", "rang_enfant_min", "date_limite_paiement"].forEach((k) => {
        if (corps[k] === "") corps[k] = null;
      });
      if (corps.mode === "pourcentage") delete corps.montant; else corps.pourcentage = null;
      if (!f.id) delete corps.motif;
      return f.id ? remisesAPI.update(f.id, corps) : remisesAPI.create(corps);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["regles-remise", academyKey] });
      qc.invalidateQueries({ queryKey: ["situation"] });
      qc.invalidateQueries({ queryKey: ["journal-financier", academyKey] });
      toast.success(f.genre === "exoneration" ? t("Exonération enregistrée.") : t("Remise enregistrée."));
      onFermer();
    },
    onError: (e) => { setErreurs(e?.response?.data || {}); toast.error(extractApiError(e)); },
  });
  const err = (k) => erreurs[k] && <span role="alert" className="block text-xs text-red-700 mt-0.5">{[].concat(erreurs[k]).join(" ")}</span>;
  const classes = options.classes.filter((c) => !f.level || c.niveau_id === Number(f.level));
  const justification = f.genre === "exoneration" || JUSTIFIER.has(f.categorie);
  return (
    <Modal open onClose={() => !enregistrer.isPending && onFermer()} size="xl"
      title={f.id ? t("Modifier la règle") : f.genre === "exoneration" ? t("Nouvelle exonération") : t("Nouvelle remise")}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); enregistrer.mutate(); }} data-testid="regle-formulaire">
        <div className="grid sm:grid-cols-2 gap-3">
          <Champ libelle="Nom" id="r-nom"><input id="r-nom" className="input" required maxLength={120} value={f.nom} onChange={maj("nom")} />{err("nom")}</Champ>
          <Champ libelle="Type" id="r-genre">
            <select id="r-genre" className="input" value={f.genre} disabled={Boolean(f.id)}
              onChange={(e) => setF((x) => ({ ...x, genre: e.target.value, categorie: DEFAUT[e.target.value] }))}>
              <option value="remise">{t("Remise")}</option><option value="exoneration">{t("Exonération")}</option>
            </select>
          </Champ>
          <Champ libelle="Catégorie" id="r-cat">
            <select id="r-cat" className="input" value={f.categorie} onChange={maj("categorie")}>
              {CATEGORIES[f.genre].map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
            </select>{err("categorie")}
          </Champ>
          <Champ libelle="Valeur" id="r-val" aide={f.genre === "exoneration" ? "100 % = exonération totale." : undefined}>
            <div className="flex gap-2">
              <select className="input !w-auto" aria-label={t("Mode")} value={f.mode} onChange={maj("mode")}>
                <option value="pourcentage">%</option><option value="montant">{t("Montant fixe")}</option>
              </select>
              {f.mode === "pourcentage"
                ? <input id="r-val" className="input" type="number" min="0.01" max="100" step="0.01" required value={f.pourcentage ?? ""} onChange={maj("pourcentage")} />
                : <input id="r-val" className="input" type="number" min="1" step="any" required value={f.montant ?? ""} onChange={maj("montant")} />}
            </div>{err("pourcentage")}{err("montant")}{err("montant_minor")}
          </Champ>
        </div>
        <Champ libelle="Description" id="r-desc"><textarea id="r-desc" className="input" rows={2} value={f.description} onChange={maj("description")} /></Champ>

        <fieldset className="rounded-xl border border-slate-100 p-3">
          <legend className="text-xs font-semibold text-slate-600 px-1">{t("Périmètre (vide : tous)")}</legend>
          <div className="grid sm:grid-cols-3 gap-3">
            <Champ libelle="Année scolaire" id="r-annee">
              <select id="r-annee" className="input" value={f.school_year ?? ""} onChange={maj("school_year")}>
                <option value="">{t("Toutes")}</option>{options.annees.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
              </select>
            </Champ>
            <Champ libelle="Nature de frais" id="r-nature">
              <select id="r-nature" className="input" value={f.payment_type} onChange={maj("payment_type")}>
                <option value="">{t("Toutes")}</option>{NATURES_FRAIS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
              </select>
            </Champ>
            <Champ libelle="Niveau" id="r-niveau">
              <select id="r-niveau" className="input" value={f.level ?? ""} onChange={maj("level")}>
                <option value="">{t("Tous")}</option>{options.niveaux.map((n) => <option key={n.id} value={n.id}>{n.nom}</option>)}
              </select>
            </Champ>
            <Champ libelle="Classe" id="r-classe">
              <select id="r-classe" className="input" value={f.class_obj ?? ""} onChange={maj("class_obj")}>
                <option value="">{t("Toutes")}</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
              </select>
            </Champ>
            <Champ libelle="Élève" id="r-eleve">
              <select id="r-eleve" className="input" value={f.student ?? ""} onChange={(e) => setF((x) => ({ ...x, student: e.target.value, famille: e.target.value ? "" : x.famille }))}>
                <option value="">{t("Tous")}</option>{options.eleves.map((s) => <option key={s.id} value={s.id}>{s.full_name || `${s.first_name} ${s.last_name}`}</option>)}
              </select>{err("student")}
            </Champ>
            <Champ libelle="Famille (responsable)" id="r-famille">
              <select id="r-famille" className="input" value={f.famille ?? ""} onChange={(e) => setF((x) => ({ ...x, famille: e.target.value, student: e.target.value ? "" : x.student }))}>
                <option value="">{t("Toutes")}</option>{options.familles.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
              </select>{err("famille")}
            </Champ>
            <Champ libelle="Du" id="r-debut" aide="Échéances concernées à partir de cette date."><input id="r-debut" className="input" type="date" value={f.debut ?? ""} onChange={maj("debut")} /></Champ>
            <Champ libelle="Au" id="r-fin"><input id="r-fin" className="input" type="date" value={f.fin ?? ""} onChange={maj("fin")} />{err("fin")}</Champ>
          </div>
        </fieldset>

        <div className="grid sm:grid-cols-3 gap-3">
          {f.categorie === "fratrie" && (
            <Champ libelle="À partir du N-ième enfant" id="r-rang" aide="Rang par date de naissance, l'aîné en premier.">
              <input id="r-rang" className="input" type="number" min="2" required value={f.rang_enfant_min ?? ""} onChange={maj("rang_enfant_min")} />{err("rang_enfant_min")}
            </Champ>
          )}
          {f.categorie === "paiement_anticipe" && (
            <Champ libelle="Solde réglé au plus tard le" id="r-limite">
              <input id="r-limite" className="input" type="date" required value={f.date_limite_paiement ?? ""} onChange={maj("date_limite_paiement")} />{err("date_limite_paiement")}
            </Champ>
          )}
          {f.genre === "remise" && (
            <label className="flex items-start gap-2 text-sm sm:col-span-2 pt-5">
              <input type="checkbox" className="mt-1" checked={f.cumulable} onChange={maj("cumulable")} />
              <span>{t("Cumulable avec les autres remises")}
                <span className="block text-[11px] text-slate-500">{t("Non cumulable : le serveur retient la solution la plus favorable à la famille et l'indique.")}</span></span>
            </label>
          )}
        </div>
        {justification && (
          <Champ libelle="Justification" id="r-just" aide="Obligatoire pour une exonération ou une décision individuelle. Non visible par les familles.">
            <textarea id="r-just" className="input" rows={2} required value={f.justification} onChange={maj("justification")} />{err("justification")}
          </Champ>
        )}
        {f.id && (
          <Champ libelle="Motif de la modification" id="r-motif"><input id="r-motif" className="input" required value={f.motif} onChange={maj("motif")} />{err("motif")}</Champ>
        )}
        {err("non_field_errors")}{err("detail")}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onFermer} disabled={enregistrer.isPending}>{t("Annuler")}</button>
          <button type="submit" className="btn-primary" disabled={enregistrer.isPending} data-testid="regle-enregistrer">{t("Enregistrer")}</button>
        </div>
      </form>
    </Modal>
  );
}

function Impact({ regle, onFermer }) {
  const q = useQuery({ queryKey: ["regle-impact", regle.id], queryFn: () => remisesAPI.impact(regle.id) });
  const d = q.data?.data;
  return (
    <Modal open onClose={onFermer} title={`${t("Élèves concernés")} : ${regle.nom}`} size="lg">
      {q.isPending ? <div className="h-24 rounded-xl bg-slate-100 animate-pulse motion-reduce:animate-none" /> : q.isError ? (
        <p role="alert" className="text-sm text-red-700">{extractApiError(q.error)}</p>
      ) : (
        <div className="space-y-2 text-sm" data-testid="regle-impact">
          <p>{d.nombre} {t("élève(s)")} · {t("Total accordé")} : <strong className="tabular-nums">{d.total}</strong></p>
          {d.eleves.length === 0 ? <p className="text-slate-500">{t("Aucun élève ne remplit actuellement les critères de cette règle.")}</p> : (
            <ul className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
              {d.eleves.map((e) => (
                <li key={e.eleve_id} className="py-1.5 flex justify-between gap-2">
                  <span>{e.nom}{e.ecartee.length > 0 && <span className="block text-xs text-slate-500">{e.ecartee.map((r) => t(r)).join(" ")}</span>}</span>
                  <span className="tabular-nums">{e.montant}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function RemisesExonerations() {
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const [genre, setGenre] = useState("remise");
  const [etat, setEtat] = useState("en_vigueur");
  const [edition, setEdition] = useState(null);
  const [impact, setImpact] = useState(null);
  const q = useQuery({ queryKey: ["regles-remise", academyKey, genre, etat], queryFn: () => remisesAPI.list({ genre, etat }) });
  const filtresQ = useQuery({ queryKey: ["paiements-filtres", academyKey], queryFn: () => paymentsAPI.filtres() });
  const elevesQ = useQuery({ queryKey: ["eleves-liste", academyKey], queryFn: () => studentsAPI.list({ is_active: true }), enabled: Boolean(edition) });
  const famillesQ = useQuery({ queryKey: ["parents-liste", academyKey], queryFn: () => parentsAPI.list(), enabled: Boolean(edition) });
  const classesQ = useQuery({ queryKey: ["classes-liste", academyKey], queryFn: () => classesAPI.list(), enabled: Boolean(edition) });
  const options = useMemo(() => { const fo = filtresQ.data?.data || {}; return {
    annees: fo.annees || [], niveaux: fo.niveaux || [],
    classes: (fo.classes?.length ? fo.classes : liste(classesQ).map((c) => ({ id: c.id, nom: c.name, niveau_id: c.level })) ),
    eleves: liste(elevesQ), familles: liste(famillesQ),
  }; }, [filtresQ.data, elevesQ, famillesQ, classesQ]);
  const regles = liste(q);
  const etatMut = useMutation({
    mutationFn: ({ regle, action, motif }) => (action === "annuler" ? remisesAPI.annuler(regle.id, motif) : remisesAPI.reactiver(regle.id, motif)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["regles-remise", academyKey] });
      qc.invalidateQueries({ queryKey: ["situation"] });
      toast.success(t("Règle mise à jour."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const changerEtat = (regle, action) => {
    const motif = window.prompt(action === "annuler" ? t("Motif de l'annulation (obligatoire) :") : t("Motif de la réactivation (obligatoire) :"));
    if (motif && motif.trim()) etatMut.mutate({ regle, action, motif: motif.trim() });
  };
  const ouvrir = (r) => setEdition(r ? {
    ...VIDE, ...r, montant: r.mode === "montant" ? (r.montant_valeur ?? "") : "", pourcentage: r.pourcentage ?? "",
    school_year: r.school_year ?? "", level: r.level ?? "", class_obj: r.class_obj ?? "", student: r.student ?? "",
    famille: r.famille ?? "", debut: r.debut ?? "", fin: r.fin ?? "", rang_enfant_min: r.rang_enfant_min ?? "",
    date_limite_paiement: r.date_limite_paiement ?? "", motif: "",
  } : { ...VIDE, genre, categorie: DEFAUT[genre] });

  return (
    <div className="space-y-3" data-testid="remises-exonerations">
      <div className="card space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {[["remise", "Remises", BadgePercent], ["exoneration", "Exonérations", ShieldCheck]].map(([v, l, Icone]) => (
            <button key={v} type="button" onClick={() => setGenre(v)} aria-pressed={genre === v} data-testid={`genre-${v}`}
              className={genre === v ? "onglet-actif" : "onglet"}>
              <Icone className="w-4 h-4" aria-hidden="true" />{t(l)}
            </button>
          ))}
          <select className="input !w-auto text-sm" aria-label={t("État")} value={etat} onChange={(e) => setEtat(e.target.value)}>
            <option value="en_vigueur">{t("En vigueur")}</option><option value="annulees">{t("Annulées")}</option><option value="">{t("Toutes")}</option>
          </select>
          <button type="button" className="btn-primary ml-auto inline-flex items-center gap-1.5" onClick={() => ouvrir(null)} data-testid="regle-nouvelle">
            <Plus className="w-4 h-4" aria-hidden="true" />{genre === "exoneration" ? t("Nouvelle exonération") : t("Nouvelle remise")}
          </button>
        </div>
        <p className="text-xs text-slate-500">
          {genre === "exoneration"
            ? t("Une exonération dispense de tout ou partie des frais, sur décision motivée. Elle est déduite avant les remises et n'est pas un paiement.")
            : t("Les remises cumulables s'additionnent ; une remise non cumulable ne se combine avec aucune autre. Une règle n'est jamais appliquée deux fois et ne rend jamais un montant négatif.")}
        </p>
        {q.isPending ? <div className="h-24 rounded-xl bg-slate-100 animate-pulse motion-reduce:animate-none" /> : q.isError ? (
          <p role="alert" className="text-sm text-red-700">{extractApiError(q.error)}</p>
        ) : regles.length === 0 ? (
          <p className="text-sm text-slate-500 py-4 text-center" data-testid="regles-vide">
            {genre === "exoneration" ? t("Aucune exonération pour ces critères.") : t("Aucune remise pour ces critères.")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="regles-liste">
              <thead><tr className="text-left text-xs text-slate-500">
                {["Nom", "Catégorie", "Valeur", "Périmètre", "Période", "Cumul", "Autorisée par", ""].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h && t(h)}</th>)}
              </tr></thead>
              <tbody>
                {regles.map((r) => (
                  <tr key={r.id} className={`border-t border-slate-100 align-top ${r.en_vigueur ? "" : "text-slate-400"}`}>
                    <td className="py-2 pr-3 font-medium">{r.nom}{!r.en_vigueur && <span className="block text-xs">{t("Annulée")} : {r.motif_annulation}</span>}</td>
                    <td className="py-2 pr-3">{t(r.categorie_libelle)}</td>
                    <td className="py-2 pr-3 tabular-nums whitespace-nowrap">{r.montant_affiche}</td>
                    <td className="py-2 pr-3">{r.perimetre.length ? r.perimetre.map((p) => t(p)).join(" · ") : t("Toute l'académie")}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">{r.debut || r.fin ? `${r.debut ? formatCalendarDate(r.debut) : "…"} → ${r.fin ? formatCalendarDate(r.fin) : "…"}` : t("Toute l'année")}</td>
                    <td className="py-2 pr-3">{r.genre === "remise" ? (r.cumulable ? t("Cumulable") : t("Non cumulable")) : "-"}</td>
                    <td className="py-2 pr-3">{r.autorise_par_nom || r.cree_par_nom || "-"}</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-right space-x-2">
                      <button type="button" className="text-xs text-feba-navy hover:underline" onClick={() => setImpact(r)}>{t("Élèves concernés")}</button>
                      {r.en_vigueur && <button type="button" className="text-xs text-feba-navy hover:underline" onClick={() => ouvrir(r)}>{t("Modifier")}</button>}
                      <button type="button" className="text-xs text-red-700 hover:underline" onClick={() => changerEtat(r, r.en_vigueur ? "annuler" : "reactiver")}
                        data-testid={`regle-etat-${r.id}`}>{r.en_vigueur ? t("Annuler") : t("Réactiver")}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {edition && <Formulaire initial={edition} options={options} onFermer={() => setEdition(null)} />}
      {impact && <Impact regle={impact} onFermer={() => setImpact(null)} />}
    </div>
  );
}
