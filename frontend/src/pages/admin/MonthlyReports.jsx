/**
 * P3 — Rapports mensuels FEBA French Heritage Academy.
 *
 * CE QUE CET ÉCRAN NE FAIT PAS
 * ----------------------------
 * Il ne déduit rien. Trois informations viennent du serveur et sont
 * affichées telles quelles, parce que le navigateur ne peut pas les
 * connaître :
 *
 *  - `pdf_available` — le serveur a REGARDÉ le disque. Un booléen calculé
 *    ici à partir d'un chemin dirait « oui » pour un fichier effacé ;
 *  - `really_sent`   — un fournisseur externe a accepté le message. Le
 *    statut seul ne le dit pas : un backend de développement accepte
 *    tout et n'envoie rien ;
 *  - `is_editable`   — un rapport remis à une famille ne se corrige plus
 *    en place.
 *
 * Un écran qui recalcule ces trois choses finit par afficher « envoyé »
 * à un administrateur dont aucun parent n'a rien reçu.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  AlertTriangle, Archive, CheckCircle2, Download, Eye, FileText, Loader2,
  Play, RefreshCw, Search, Send, X, XCircle,
} from "lucide-react";

import { monthlyReportsAPI } from "../../api";
import DataTable from "../../components/ui/DataTable";
import DetailField from "../../components/ui/DetailField";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";

const MOIS = [
  "", "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

const STATUTS = [
  ["", "Tous les statuts"],
  ["draft", "Brouillon"],
  ["generated", "Généré"],
  ["ready", "Prêt à envoyer"],
  ["sending", "Envoi en cours"],
  ["sent", "Envoyé"],
  ["failed", "Échec"],
  ["cancelled", "Annulé"],
  ["archived", "Archivé"],
];

const TON = {
  draft: "bg-slate-100 text-slate-600",
  generated: "bg-sky-50 text-sky-700",
  ready: "bg-indigo-50 text-indigo-700",
  sending: "bg-amber-50 text-amber-700",
  sent: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700",
  cancelled: "bg-slate-100 text-slate-500",
  archived: "bg-slate-100 text-slate-500",
};

function telecharger(nomFichier, donnees) {
  const blob = donnees instanceof Blob ? donnees : new Blob([donnees]);
  const url = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nomFichier;
  lien.click();
  URL.revokeObjectURL(url);
}

/**
 * L'état d'envoi, dit sans être embelli.
 *
 * Un rapport au statut « envoyé » mais sans identifiant de fournisseur
 * n'est PAS parti. Afficher la même pastille verte dans les deux cas
 * ferait croire à un administrateur que les familles ont reçu quelque
 * chose.
 */
function EtatEnvoi({ ligne }) {
  if (ligne.status === "sent" && ligne.really_sent) {
    return (
      <span className="inline-flex items-center gap-1">
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" />
        <span className={`badge ${TON.sent}`}>{t("Envoyé")}</span>
      </span>
    );
  }
  if (ligne.status === "sent") {
    return (
      <span title={t("Aucun fournisseur externe n'a accepté ce message.")}
            className="inline-flex items-center gap-1">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" aria-hidden="true" />
        <span className={`badge ${TON.failed}`}>{t("Non confirmé")}</span>
      </span>
    );
  }
  if (ligne.status === "failed") {
    return (
      <span title={ligne.last_error} className="inline-flex items-center gap-1">
        <XCircle className="w-3.5 h-3.5 text-red-500" aria-hidden="true" />
        <span className={`badge ${TON.failed}`}>{t("Échec")}</span>
      </span>
    );
  }
  return (
    <span className={`badge ${TON[ligne.status] || TON.draft}`}>
      {ligne.status_display}
    </span>
  );
}

export default function MonthlyReports() {
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const maintenant = new Date();

  const [filtres, setFiltres] = useState({
    search: "", status: "",
    year: maintenant.getFullYear(),
    month: maintenant.getMonth() || 12,
  });
  const [detail, setDetail] = useState(null);

  const parametres = Object.fromEntries(
    Object.entries(filtres).filter(([, v]) => v !== "" && v != null));

  const { data, isLoading } = useQuery({
    queryKey: ["rapports-mensuels", academyKey, parametres],
    queryFn: () => monthlyReportsAPI.list(parametres),
  });
  const lignes = data?.data?.results || data?.data || [];

  const invalider = () =>
    qc.invalidateQueries({ queryKey: ["rapports-mensuels", academyKey] });

  const lotMut = useMutation({
    mutationFn: () => monthlyReportsAPI.generateMonth({
      year: Number(filtres.year), month: Number(filtres.month) }),
    onSuccess: (reponse) => {
      const r = reponse.data;
      invalider();
      toast.success(t("Lot produit :") +
        ` ${r.crees} ${t("créé(s)")}, ${r.existants} ${t("déjà présent(s)")}` +
        (r.echecs?.length ? `, ${r.echecs.length} ${t("échec(s)")}` : ""));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const pdfMut = useMutation({
    mutationFn: async (ligne) => {
      const reponse = await monthlyReportsAPI.pdf(ligne.id);
      telecharger(`${ligne.reference}.pdf`, reponse.data);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const actionMut = useMutation({
    mutationFn: ({ action, id }) => monthlyReportsAPI[action](id),
    onSuccess: (reponse, { action }) => {
      invalider();
      if (action === "send") {
        const r = reponse.data;
        if (r.really_sent) toast.success(t("Rapport envoyé."));
        // On ne dit PAS « envoyé » quand rien n'est parti : on montre le
        // motif tel que le serveur l'a enregistré.
        else toast.error(r.detail || t("L'envoi n'a pas abouti."));
      } else {
        toast.success(t("Action effectuée."));
      }
      if (detail) setDetail(reponse.data);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const colonnes = [
    { key: "reference", label: t("Référence"), accessor: "reference" },
    { key: "student", label: t("Élève"), accessor: "student_name" },
    { key: "period", label: t("Période"), accessor: "period_label" },
    { key: "version", label: t("Version"), render: (r) => `v${r.version}` },
    { key: "pdf", label: t("PDF"), sortable: false, render: (r) =>
        r.pdf_available
          ? <span className="badge bg-emerald-50 text-emerald-700">{t("Disponible")}</span>
          : <span className="badge bg-amber-50 text-amber-700">{t("Absent")}</span> },
    { key: "status", label: t("Statut"), sortable: false,
      render: (r) => <EtatEnvoi ligne={r} /> },
    { key: "attempts", label: t("Tentatives"), accessor: "attempts_count" },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Rapports mensuels FEBA FHA")}
        subtitle={t("Suivi mensuel des élèves de l'académie en ligne.")}
      />

      <div className="card space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="relative flex-1 min-w-[14rem]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    aria-hidden="true" />
            <input
              className="input pl-9" placeholder={t("Rechercher un élève, une référence…")}
              value={filtres.search}
              onChange={(e) => setFiltres({ ...filtres, search: e.target.value })}
            />
          </div>
          <div>
            <label className="label" htmlFor="mr-year">{t("Année")}</label>
            <input id="mr-year" type="number" className="input w-28"
                   value={filtres.year}
                   onChange={(e) => setFiltres({ ...filtres, year: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="mr-month">{t("Mois")}</label>
            <select id="mr-month" className="input w-40" value={filtres.month}
                    onChange={(e) => setFiltres({ ...filtres, month: e.target.value })}>
              {MOIS.slice(1).map((nom, i) => (
                <option key={i + 1} value={i + 1}>{t(nom)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="mr-status">{t("Statut")}</label>
            <select id="mr-status" className="input w-44" value={filtres.status}
                    onChange={(e) => setFiltres({ ...filtres, status: e.target.value })}>
              {STATUTS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
            </select>
          </div>
          <button type="button" onClick={() => lotMut.mutate()}
                  disabled={lotMut.isPending}
                  className="btn-primary inline-flex items-center gap-2">
            {lotMut.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              : <Play className="w-4 h-4" aria-hidden="true" />}
            {t("Produire le lot du mois")}
          </button>
        </div>

        <DataTable
          columns={colonnes} data={lignes} loading={isLoading}
          emptyMessage={t("Aucun rapport pour cette période.")}
          actions={(r) => (
            <div className="flex items-center gap-1">
              <button onClick={() => setDetail(r)} title={t("Ouvrir le rapport")}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700">
                <Eye className="w-4 h-4" aria-hidden="true" />
              </button>
              <button onClick={() => pdfMut.mutate(r)} disabled={!r.pdf_available}
                      title={t("Télécharger le PDF")}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 disabled:opacity-40">
                <FileText className="w-4 h-4" aria-hidden="true" />
              </button>
              <button onClick={() => actionMut.mutate({ action: "send", id: r.id })}
                      title={t("Envoyer aux responsables")}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700">
                <Send className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          )}
        />
      </div>

      {detail && (
        <ReportDetail
          id={detail.id} onClose={() => setDetail(null)}
          onAction={(action) => actionMut.mutate({ action, id: detail.id })}
          onDownload={() => pdfMut.mutate(detail)}
          busy={actionMut.isPending || pdfMut.isPending}
        />
      )}
    </div>
  );
}

function ReportDetail({ id, onClose, onAction, onDownload, busy }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["rapport-mensuel", id],
    queryFn: () => monthlyReportsAPI.get(id),
  });
  const rapport = data?.data;
  const [texte, setTexte] = useState(null);

  const enregistrerMut = useMutation({
    mutationFn: (contenu) => monthlyReportsAPI.update(id, {
      editable_content: contenu }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rapport-mensuel", id] });
      qc.invalidateQueries({ queryKey: ["rapports-mensuels"] });
      toast.success(t("Appréciation enregistrée."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const champs = [
    ["summary", "Synthèse du mois"],
    ["progress", "Progrès observés"],
    ["difficulties", "Difficultés rencontrées"],
    ["recommendations", "Recommandations"],
    ["next_goals", "Objectifs du mois suivant"],
    ["admin_message", "Message de l'administration"],
  ];
  const valeurs = texte ?? rapport?.editable_content ?? {};

  return (
    <Modal open onClose={onClose} title={t("Rapport mensuel")} size="lg">
      {isLoading && <p className="text-sm text-slate-500">{t("Chargement…")}</p>}
      {rapport && (
        <div className="space-y-5 text-sm min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="badge bg-slate-100 text-slate-600">{rapport.reference}</span>
            <EtatEnvoi ligne={rapport} />
            <span className="badge bg-slate-100 text-slate-600">
              {t("Version")} {rapport.version}
            </span>
            {rapport.pdf_available
              ? <span className="badge bg-emerald-50 text-emerald-700">{t("PDF disponible")}</span>
              : <span className="badge bg-amber-50 text-amber-700">{t("PDF absent")}</span>}
          </div>

          {rapport.last_error && (
            <div className="rounded-xl bg-red-50 border border-red-100 p-3">
              <p className="text-xs font-semibold text-red-700 mb-1">
                {t("Dernière erreur")}
              </p>
              <p className="text-xs text-red-700 text-longform">{rapport.last_error}</p>
            </div>
          )}

          <section className="min-w-0">
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
              {t("Dossier")}
            </h3>
            <div className="space-y-1 min-w-0">
              <DetailField label={t("Élève")} value={rapport.student_name} />
              <DetailField label={t("Période")} value={rapport.period_label} />
              <DetailField label={t("Généré le")}
                           value={rapport.generated_at?.slice(0, 16).replace("T", " ")}
                           emptyLabel={t("Jamais")} />
              <DetailField label={t("Envoyé le")}
                           value={rapport.sent_at?.slice(0, 16).replace("T", " ")}
                           emptyLabel={t("Jamais")} />
              <DetailField label={t("Destinataires")} value={rapport.recipients}
                           emptyLabel={t("Aucun")} />
              <DetailField label={t("Tentatives")} value={String(rapport.attempts_count)} />
              <DetailField label={t("Empreinte du PDF")} value={rapport.pdf_sha256}
                           emptyLabel={t("Aucune")} />
              <DetailField label={t("Identifiant fournisseur")}
                           value={rapport.provider_message_id}
                           emptyLabel={t("Aucun fournisseur n'a accepté ce message")} />
            </div>
          </section>

          <section className="min-w-0">
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
              {t("Appréciation de l'administration")}
            </h3>
            {rapport.is_editable ? (
              <div className="space-y-3">
                {champs.map(([cle, libelle]) => (
                  <div key={cle}>
                    <label className="label" htmlFor={`mr-${cle}`}>{t(libelle)}</label>
                    <textarea
                      id={`mr-${cle}`} rows={3} className="input"
                      value={valeurs[cle] || ""}
                      onChange={(e) =>
                        setTexte({ ...valeurs, [cle]: e.target.value })}
                    />
                  </div>
                ))}
                <div className="flex justify-end">
                  <button type="button" className="btn-secondary"
                          disabled={enregistrerMut.isPending || texte === null}
                          onClick={() => enregistrerMut.mutate(valeurs)}>
                    {t("Enregistrer le brouillon")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-1 min-w-0">
                {/* Un rapport remis à une famille ne se corrige plus en
                    place : le modifier produirait un document différent
                    portant la référence de celui qu'elle détient. */}
                <p className="text-xs text-slate-500 mb-2">
                  {t("Ce rapport a été transmis ou archivé. Produisez une nouvelle version pour le corriger.")}
                </p>
                {champs.map(([cle, libelle]) => (
                  <DetailField key={cle} label={t(libelle)} value={valeurs[cle]}
                               emptyLabel={t("Non renseigné")} />
                ))}
              </div>
            )}
          </section>

          {(rapport.attempts || []).length > 0 && (
            <section className="min-w-0">
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
                {t("Historique des tentatives")}
              </h3>
              <ul className="space-y-1.5">
                {rapport.attempts.map((essai) => (
                  <li key={essai.id} className="text-xs text-slate-500 text-longform">
                    {(essai.attempted_at || "").slice(0, 16).replace("T", " ")}
                    {" · "}
                    {essai.succeeded ? t("réussie") : t("échouée")}
                    {essai.used_real_provider ? "" : ` · ${t("sans fournisseur externe")}`}
                    {essai.error ? ` · ${essai.error}` : ""}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary inline-flex items-center gap-2"
                    disabled={busy} onClick={() => onAction("archive")}>
              <Archive className="w-4 h-4" aria-hidden="true" /> {t("Archiver")}
            </button>
            <button type="button" className="btn-secondary inline-flex items-center gap-2"
                    disabled={busy} onClick={() => onAction("cancel")}>
              <X className="w-4 h-4" aria-hidden="true" /> {t("Annuler")}
            </button>
            <button type="button" className="btn-secondary inline-flex items-center gap-2"
                    disabled={busy} onClick={() => onAction("newVersion")}>
              <RefreshCw className="w-4 h-4" aria-hidden="true" /> {t("Nouvelle version")}
            </button>
            <button type="button" className="btn-secondary inline-flex items-center gap-2"
                    disabled={busy || !rapport.is_editable}
                    onClick={() => onAction("regenerate")}>
              <RefreshCw className="w-4 h-4" aria-hidden="true" /> {t("Régénérer")}
            </button>
            <button type="button" className="btn-secondary inline-flex items-center gap-2"
                    disabled={busy || !rapport.pdf_available} onClick={onDownload}>
              <Download className="w-4 h-4" aria-hidden="true" /> {t("Télécharger")}
            </button>
            <button type="button" data-testid="mr-send"
                    className="btn-primary inline-flex items-center gap-2"
                    disabled={busy} onClick={() => onAction("send")}>
              <Send className="w-4 h-4" aria-hidden="true" />
              {rapport.really_sent ? t("Renvoyer") : t("Envoyer")}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
