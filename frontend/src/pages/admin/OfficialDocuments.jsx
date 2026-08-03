/**
 * Documents officiels — diplômes et certificats.
 *
 * CE QUE CET ÉCRAN MONTRE EN PREMIER
 * ----------------------------------
 * L'état réel des gabarits. Tant qu'un fond n'est pas installé ou qu'un
 * gabarit n'est pas calibré, le bouton d'émission est désactivé ET la
 * raison est affichée. Masquer le bouton laisserait croire à une
 * fonctionnalité absente ; l'afficher sans avertir produirait des
 * diplômes approximatifs.
 *
 * TÉLÉCHARGEMENT SANS URL PUBLIQUE
 * --------------------------------
 * Le fichier est récupéré en binaire par une requête authentifiée, puis
 * ouvert depuis un blob local. Il n'existe aucun lien qu'on puisse
 * copier, partager, ou deviner.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Building2, Download, FileCheck, Lock, Plus, XCircle } from "lucide-react";
import toast from "react-hot-toast";
import { documentsAPI, studentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useAcademy } from "../../context/AcademyContext";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

const STATUS_STYLES = {
  draft: "bg-slate-100 text-slate-600",
  to_validate: "bg-amber-50 text-amber-700",
  validated: "bg-blue-50 text-blue-700",
  issued: "bg-green-50 text-green-700",
  revoked: "bg-red-50 text-red-700",
  replaced: "bg-slate-100 text-slate-500",
};

export default function AdminOfficialDocuments() {
  const qc = useQueryClient();
  const { academyKey } = useAcademy();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ student: null, template: "" });
  const [revokeItem, setRevokeItem] = useState(null);
  const [revokeReason, setRevokeReason] = useState("");
  // P8 — Académie explicitement confirmée par l'utilisateur avant
  // production. Réinitialisée dès que l'élève ou le gabarit change : une
  // confirmation donnée pour un autre document n'en vaut pas une.
  const [confirmedAcademy, setConfirmedAcademy] = useState(null);

  const { data: templatesData } = useQuery({
    queryKey: ["document-templates", academyKey],
    queryFn: documentsAPI.templates,
  });
  const templates = templatesData?.data?.templates || [];
  // P8 — L'écran sait sous quelle identité il travaille, et le DIT.
  // `consolidated` vaut vrai en mode « Toutes les Académies » : aucune
  // académie n'est alors supposée, et la production exige un choix
  // explicite plutôt qu'un défaut silencieux.
  const scopeAcademy = templatesData?.data?.academy || null;
  const consolidated = Boolean(templatesData?.data?.consolidated);

  const { data: docsData, isLoading } = useQuery({
    queryKey: ["official-documents", academyKey],
    queryFn: () => documentsAPI.list(),
  });
  const documents = docsData?.data || [];

  const { data: studentsData } = useQuery({
    queryKey: ["students", academyKey],
    queryFn: () => studentsAPI.list(),
  });
  const students = studentsData?.data?.results || studentsData?.data || [];

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["official-documents", academyKey] });
  };

  const create = useMutation({
    mutationFn: () => documentsAPI.create({ student: form.student, template: form.template }),
    onSuccess: () => {
      toast.success(t("Brouillon produit. Il n'est pas encore délivré."));
      setCreateOpen(false);
      invalidate();
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const issue = useMutation({
    mutationFn: (id) => documentsAPI.issue(id),
    onSuccess: (response) => {
      toast.success(t("Document délivré sous le numéro {n}.",
                      { n: response?.data?.number }));
      invalidate();
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const revoke = useMutation({
    mutationFn: ({ id, reason }) => documentsAPI.revoke(id, reason),
    onSuccess: () => {
      toast.success(t("Document révoqué."));
      setRevokeItem(null);
      setRevokeReason("");
      invalidate();
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const download = useMutation({
    mutationFn: (id) => documentsAPI.download(id),
    onSuccess: (response) => {
      // Ouverture depuis un blob local : aucune URL du serveur n'est
      // exposée, donc rien à copier ni à partager par inadvertance.
      const url = URL.createObjectURL(response.data);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const usableTemplates = templates.filter((tpl) => tpl.can_issue);

  // En mode consolidé, l'élève choisi détermine l'académie. On la lit sur
  // lui plutôt que de la déduire du contexte : c'est la seule source qui
  // ne peut pas se désynchroniser du document produit.
  const selectedStudent = students.find((s) => s.id === form.student) || null;
  const targetAcademyCode =
    selectedStudent?.academy_code || scopeAcademy?.code || null;
  const targetAcademyName =
    selectedStudent?.academy_name || scopeAcademy?.name || null;
  const templateForForm = templates.find((tpl) => tpl.id === form.template) || null;
  const academyMismatch = Boolean(
    templateForForm && targetAcademyCode
    && (templateForForm.academies || []).length > 0
    && !templateForForm.academies.includes(targetAcademyCode),
  );
  // Rien ne se produit tant que l'académie n'est pas confirmée : le
  // document engage une personne morale précise.
  const canProduce = Boolean(
    form.student && form.template && targetAcademyCode
    && !academyMismatch && confirmedAcademy === targetAcademyCode,
  );

  const cols = [
    // P8 — L'académie figure sur chaque ligne dès qu'on n'est plus dans
    // une seule académie. Sans elle, deux diplômes voisins peuvent venir
    // d'établissements différents sans que rien ne le dise.
    ...(consolidated ? [{
      key: "academy", label: t("Académie"), sortable: false,
      render: r => (
        <span className={`badge whitespace-nowrap ${
          r.academy_code === "FEBA_FHA"
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
            : "bg-indigo-50 text-indigo-700 border border-indigo-200"}`}>
          {r.academy_code || "—"}
        </span>
      ),
    }] : []),
    { key: "number", label: t("Numéro"),
      render: r => r.number || <span className="text-slate-400">{t("(non délivré)")}</span> },
    { key: "student", label: t("Élève"), accessor: "student" },
    { key: "template", label: t("Type"), render: r => t(r.template_id) },
    {
      key: "status", label: t("État"),
      render: r => (
        <span className={`text-xs font-medium px-2 py-1 rounded-lg ${
          STATUS_STYLES[r.status] || "bg-slate-100"}`}>
          {t(r.status_display)}
        </span>
      ),
    },
    {
      key: "hash", label: t("Empreinte"), sortable: false,
      render: r => r.file_sha256
        ? <code className="text-xs text-slate-500">{r.file_sha256.slice(0, 12)}…</code>
        : <span className="text-slate-400">—</span>,
    },
    {
      key: "actions", label: "", sortable: false,
      render: r => (
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => download.mutate(r.id)}
                  className="flex items-center gap-1 text-xs text-primary hover:underline">
            <Download className="w-3 h-3" />{t("PDF")}
          </button>
          {["draft", "validated"].includes(r.status) && (
            <button type="button" onClick={() => issue.mutate(r.id)}
                    className="flex items-center gap-1 text-xs text-green-700 hover:underline">
              <FileCheck className="w-3 h-3" />{t("Délivrer")}
            </button>
          )}
          {r.status === "issued" && (
            <button type="button"
                    onClick={() => { setRevokeItem(r); setRevokeReason(""); }}
                    className="flex items-center gap-1 text-xs text-red-600 hover:underline">
              <XCircle className="w-3 h-3" />{t("Révoquer")}
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Documents officiels")}
        subtitle={t("Diplômes et certificats — {n} document(s)", { n: documents.length })}
        action={usableTemplates.length > 0 && (
          <button type="button" className="btn-primary flex items-center gap-2"
                  onClick={() => {
                    setForm({ student: null, template: usableTemplates[0].id });
                    setConfirmedAcademy(null);
                    setCreateOpen(true);
                  }}>
            <Plus className="w-4 h-4" />{t("Produire un document")}
          </button>
        )}
      />

      {/* P8 — La portée en cours, dite explicitement. Une page qui
          n'annonce pas son académie laisse l'utilisateur supposer la
          mauvaise, et la supposition ne se voit qu'après coup. */}
      <div className={`card border ${consolidated
        ? "border-amber-200 bg-amber-50/40" : "border-slate-200"}`}>
        <div className="flex items-start gap-3">
          <Building2 className={`w-5 h-5 shrink-0 mt-0.5 ${
            consolidated ? "text-amber-600" : "text-slate-500"}`} />
          <div>
            {consolidated ? (
              <>
                <p className="font-medium text-slate-800">
                  {t("Toutes les Académies")}
                </p>
                <p className="text-sm text-slate-600 mt-0.5">
                  {t("Aucune académie n'est sélectionnée. Les documents de toutes les académies sont listés, chacun étiqueté. La production exige de confirmer l'académie.")}
                </p>
              </>
            ) : (
              <>
                <p className="font-medium text-slate-800">
                  {scopeAcademy?.name || t("Académie active")}
                </p>
                <p className="text-sm text-slate-600 mt-0.5">
                  {t("Élèves, gabarits, documents et identité visuelle sont ceux de cette académie.")}
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* État des gabarits — affiché avant toute chose. */}
      <div className="grid gap-4 md:grid-cols-2">
        {templates.map((tpl) => (
          <div key={tpl.id}
               className={`card border ${tpl.can_issue ? "border-green-200" : "border-amber-200 bg-amber-50/40"}`}>
            <div className="flex items-start gap-3">
              {tpl.can_issue
                ? <FileCheck className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
                : <Lock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />}
              <div className="min-w-0">
                <p className="font-medium text-slate-800">{t(tpl.label || tpl.id)}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {tpl.background_file} · {t("tolérance")} {tpl.tolerance_mm} mm
                </p>
                {tpl.can_issue ? (
                  <p className="text-sm text-green-700 mt-2">
                    {t("Fond vérifié et gabarit calibré : émission possible.")}
                  </p>
                ) : (
                  <ul className="text-sm text-slate-700 mt-2 space-y-1 list-disc list-inside">
                    {(tpl.blockers || []).map((blocker, i) => <li key={i}>{blocker}</li>)}
                  </ul>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <DataTable columns={cols} data={documents} loading={isLoading} />
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)}
             title={t("Produire un document officiel")} size="sm">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1" htmlFor="doc-template">
              {t("Type de document")}
            </label>
            <select id="doc-template" className="input" value={form.template}
                    onChange={(e) => {
                      setForm({ ...form, template: e.target.value });
                      setConfirmedAcademy(null);
                    }}>
              {usableTemplates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>{t(tpl.label || tpl.id)}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">{t("Élève")}</label>
            <SearchableSelect
              options={students.map((s) => ({
                value: s.id,
                label: s.full_name || `${s.first_name} ${s.last_name}`,
              }))}
              value={form.student}
              onChange={(value) => {
                setForm({ ...form, student: value });
                setConfirmedAcademy(null);
              }}
              placeholder={t("Rechercher un élève…")}
            />
          </div>

          {/* P8 — CONFIRMATION EXPLICITE DE L'ACADÉMIE.
              Un document officiel engage une personne morale précise. Le
              déduire du contexte, c'est accepter qu'une bascule oubliée
              produise un diplôme à l'en-tête de la mauvaise académie — une
              erreur que personne ne voit sur le document fini. */}
          {academyMismatch ? (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-50 border border-red-200">
              <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              <p className="text-sm text-slate-700">
                {t("Ce gabarit n'est pas prévu pour l'académie de cet élève. Son fond porte l'identité d'une autre académie : le document sortirait au nom de l'une et à l'effigie de l'autre.")}
              </p>
            </div>
          ) : targetAcademyCode ? (
            <label className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200 cursor-pointer">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={confirmedAcademy === targetAcademyCode}
                onChange={(e) =>
                  setConfirmedAcademy(e.target.checked ? targetAcademyCode : null)}
              />
              <span className="text-sm text-slate-700">
                {t("Je confirme produire ce document au nom de {a}.",
                   { a: targetAcademyName || targetAcademyCode })}
              </span>
            </label>
          ) : (
            <p className="text-sm text-amber-700">
              {t("Sélectionnez un élève : c'est lui qui détermine l'académie émettrice.")}
            </p>
          )}

          <p className="text-xs text-slate-500">
            {t("Le document est produit à l'état de brouillon. Il ne reçoit son numéro officiel qu'au moment où il est délivré.")}
          </p>

          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>
              {t("Annuler")}
            </button>
            <button type="button" className="btn-primary"
                    disabled={!canProduce || create.isPending}
                    onClick={() => create.mutate()}>
              {create.isPending ? t("Production…") : t("Produire")}
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={Boolean(revokeItem)} onClose={() => setRevokeItem(null)}
             title={t("Révoquer un document")} size="sm">
        {revokeItem && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-amber-50 border border-amber-200">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-slate-700">
                {t("La révocation ne détruit pas le document : une copie imprimée circule peut-être. Elle enregistre qu'il ne vaut plus, et pourquoi.")}
              </p>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1" htmlFor="revoke-reason">
                {t("Motif (obligatoire)")}
              </label>
              <input id="revoke-reason" className="input" value={revokeReason}
                     onChange={(e) => setRevokeReason(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setRevokeItem(null)}>
                {t("Annuler")}
              </button>
              <button type="button" className="btn-primary"
                      disabled={!revokeReason.trim() || revoke.isPending}
                      onClick={() => revoke.mutate({ id: revokeItem.id, reason: revokeReason })}>
                {t("Révoquer")}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
