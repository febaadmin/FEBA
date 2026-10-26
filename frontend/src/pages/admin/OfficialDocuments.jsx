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
import { AlertTriangle, Building2, Download, Eye, FileCheck, Layers, Plus, Stamp, XCircle } from "lucide-react";
import toast from "react-hot-toast";
import { classesAPI, documentsAPI, studentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { useAcademy } from "../../context/AcademyContext";
import { extractApiError } from "../../utils/errors";
import { blobErrorDetail } from "../../utils/templateLayout";
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
  const [form, setForm] = useState({ student: null, kind: "diploma", values: {} });
  const [batchOpen, setBatchOpen] = useState(false);
  const [batch, setBatch] = useState({ kind: "certificate", class_id: "", values: {} });
  const [batchResult, setBatchResult] = useState(null);
  const [revokeItem, setRevokeItem] = useState(null);
  const [revokeReason, setRevokeReason] = useState("");
  // P8 — Académie explicitement confirmée par l'utilisateur avant
  // production. Réinitialisée dès que l'élève ou le gabarit change : une
  // confirmation donnée pour un autre document n'en vaut pas une.
  const [confirmedAcademy, setConfirmedAcademy] = useState(null);

  const { data: templatesData } = useQuery({
    queryKey: ["document-scope", academyKey],
    queryFn: documentsAPI.templates,
  });
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

  // Vérification préalable : gabarit résolu PAR LE SERVEUR pour l'académie
  // de l'élève, données manquantes, règle d'émission. Rien n'est créé.
  const { data: checkData, isFetching: checking } = useQuery({
    queryKey: ["document-check", academyKey, form.student, form.kind, JSON.stringify(form.values)],
    queryFn: () => documentsAPI.check({ student: form.student, kind: form.kind, values: form.values }),
    enabled: createOpen && Boolean(form.student),
    retry: false,
  });
  const check = form.student ? checkData?.data || null : null;

  const { data: classesData } = useQuery({
    queryKey: ["classes", academyKey],
    queryFn: () => classesAPI.list(),
    enabled: batchOpen,
  });
  const classes = classesData?.data?.results || classesData?.data || [];

  const preview = useMutation({
    mutationFn: () => documentsAPI.preview({ student: form.student, kind: form.kind, values: form.values }),
    onSuccess: (response) => {
      const url = URL.createObjectURL(response.data);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    },
    onError: async (err) => toast.error((await blobErrorDetail(err)) || extractApiError(err)),
  });

  const runBatch = useMutation({
    mutationFn: () => documentsAPI.batch({ kind: batch.kind, class_id: batch.class_id, values: batch.values }),
    onSuccess: (response) => { setBatchResult(response.data); invalidate(); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const issueBatch = useMutation({
    mutationFn: (ids) => documentsAPI.batchIssue(ids),
    onSuccess: (response) => {
      toast.success(t("{n} document(s) délivré(s).", { n: response.data.issued }));
      const refused = response.data.results.filter((r) => !r.ok);
      if (refused.length) toast.error(refused.map((r) => r.reason).join(" "));
      setBatchResult(null);
      setBatchOpen(false);
      invalidate();
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const create = useMutation({
    mutationFn: () => documentsAPI.create({ student: form.student, kind: form.kind, values: form.values }),
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

  // L'élève choisi détermine l'académie émettrice : on la lit dans la
  // réponse du serveur, seule source qui ne peut pas se désynchroniser du
  // document produit.
  const targetAcademyCode = check?.academy?.code || null;
  const targetAcademyName = check?.academy?.name || null;
  // Rien ne se produit tant que l'académie n'est pas confirmée : le
  // document engage une personne morale précise.
  const canProduce = Boolean(
    form.student && check?.can_produce && !checking && confirmedAcademy === targetAcademyCode,
  );
  const resetConfirm = () => setConfirmedAcademy(null);

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
    { key: "template", label: t("Type"),
      render: r => `${r.kind === "certificate" ? t("Certificat") : t("Diplôme")} · ${
        r.template_source === "uploaded" ? t("gabarit v{v}", { v: r.template_version }) : t("gabarit intégré")}` },
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
        action={(
          <div className="flex flex-wrap gap-2">
            {!consolidated && (
              <button type="button" className="btn-secondary flex items-center gap-2"
                      onClick={() => { setBatchResult(null); setBatchOpen(true); }}>
                <Layers className="w-4 h-4" />{t("Production par classe")}
              </button>
            )}
            <button type="button" className="btn-primary flex items-center gap-2"
                    onClick={() => {
                      setForm({ student: null, kind: "diploma", values: {} });
                      setConfirmedAcademy(null);
                      setCreateOpen(true);
                    }}>
              <Plus className="w-4 h-4" />{t("Produire un document")}
            </button>
          </div>
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

      {/* Les gabarits se gèrent dans leur propre écran ; celui-ci produit. */}
      <div className="card flex items-start gap-3 text-sm text-slate-600">
        <Stamp className="w-5 h-5 text-slate-500 shrink-0 mt-0.5" />
        <p>
          {t("Chaque document est produit sur le gabarit ACTIF de l'académie de l'élève (rubrique « Gabarits des documents »), à défaut sur le gabarit intégré prévu pour elle. Un document délivré garde son fichier et sa version de gabarit, même après un remplacement.")}
        </p>
      </div>

      <div className="card">
        <DataTable columns={cols} data={documents} loading={isLoading} />
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)}
             title={t("Produire un document officiel")} size="md">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1" htmlFor="doc-kind">
              {t("Type de document")}
            </label>
            <select id="doc-kind" className="input" value={form.kind}
                    onChange={(e) => { setForm({ ...form, kind: e.target.value, values: {} }); resetConfirm(); }}>
              <option value="diploma">{t("Diplôme")}</option>
              <option value="certificate">{t("Certificat")}</option>
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
              onChange={(value) => { setForm({ ...form, student: value, values: {} }); resetConfirm(); }}
              placeholder={t("Rechercher un élève…")}
            />
          </div>

          {form.student && checking && !check && (
            <p className="text-sm text-slate-500">{t("Vérification des données…")}</p>
          )}

          {check && (
            <div className="space-y-3" data-testid="document-check">
              <p className="text-sm text-slate-700">
                {check.source === "uploaded" && t("Gabarit téléversé de l'académie — version {v}", { v: check.template.version })}
                {check.source === "builtin" && t("Gabarit intégré « {l} »", { l: check.template.label })}
                {!check.source && t("Aucun gabarit disponible")}
              </p>
              {check.values && Object.keys(check.values).length > 0 && check.labels && (
                <dl className="text-xs grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 bg-slate-50 rounded-xl p-3">
                  {Object.entries(check.labels).map(([name, label]) => (
                    <div key={name} className="contents">
                      <dt className="text-slate-500">{t(label)}</dt>
                      <dd className="text-slate-800">{check.values[name]
                        || (name === "document_number" ? t("(attribué à la délivrance)") : "—")}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {(check.inputs || []).includes("award_date") && (
                <label className="block">
                  <span className="block text-xs text-slate-500 mb-1">{t("Date d'obtention")}</span>
                  <input type="date" className="input" value={form.values.award_date || ""}
                         onChange={(e) => { setForm({ ...form, values: { ...form.values, award_date: e.target.value } }); resetConfirm(); }} />
                </label>
              )}
              {(check.inputs || []).includes("certificate_purpose") && (
                <label className="block">
                  <span className="block text-xs text-slate-500 mb-1">{t("Objet du certificat (facultatif, sinon celui du gabarit)")}</span>
                  <input className="input" maxLength={200} value={form.values.certificate_purpose || ""}
                         onChange={(e) => { setForm({ ...form, values: { ...form.values, certificate_purpose: e.target.value } }); resetConfirm(); }} />
                </label>
              )}
              {[...(check.blockers || []), ...(check.missing || []).map((m) => t("Donnée obligatoire manquante : {m}", { m: t(m) }))]
                .map((msg, i) => (
                  <div key={i} className="flex items-start gap-2 p-2.5 rounded-xl bg-red-50 border border-red-200 text-sm text-slate-700">
                    <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />{msg}
                  </div>
                ))}
              {(check.warnings || []).map((msg, i) => (
                <p key={i} className="text-xs text-amber-700">{msg}</p>
              ))}
            </div>
          )}

          {/* P8 — CONFIRMATION EXPLICITE DE L'ACADÉMIE.
              Un document officiel engage une personne morale précise. Le
              déduire du contexte, c'est accepter qu'une bascule oubliée
              produise un diplôme à l'en-tête de la mauvaise académie — une
              erreur que personne ne voit sur le document fini. */}
          {targetAcademyCode ? (
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
            <button type="button" className="btn-secondary flex items-center gap-1.5"
                    disabled={!check?.source || preview.isPending}
                    onClick={() => preview.mutate()}>
              <Eye className="w-4 h-4" />{preview.isPending ? t("Rendu…") : t("Aperçu")}
            </button>
            <button type="button" className="btn-primary"
                    disabled={!canProduce || create.isPending}
                    onClick={() => create.mutate()}>
              {create.isPending ? t("Production…") : t("Produire")}
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={batchOpen} onClose={() => setBatchOpen(false)}
             title={t("Production par classe")} size="md">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            {t("Un brouillon est produit pour chaque élève de la classe, sur le gabarit de son académie. Les élèves qui ne remplissent pas la règle d'émission ou dont une donnée obligatoire manque sont listés avec le motif.")}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="block text-xs text-slate-500 mb-1">{t("Type de document")}</span>
              <select className="input" value={batch.kind}
                      onChange={(e) => { setBatch({ ...batch, kind: e.target.value }); setBatchResult(null); }}>
                <option value="diploma">{t("Diplôme")}</option>
                <option value="certificate">{t("Certificat")}</option>
              </select>
            </label>
            <label className="block">
              <span className="block text-xs text-slate-500 mb-1">{t("Classe")}</span>
              <select className="input" value={batch.class_id}
                      onChange={(e) => { setBatch({ ...batch, class_id: e.target.value }); setBatchResult(null); }}>
                <option value="">{t("Choisir…")}</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          </div>
          {batch.kind === "diploma" && (
            <label className="block">
              <span className="block text-xs text-slate-500 mb-1">{t("Date d'obtention (si le gabarit l'affiche)")}</span>
              <input type="date" className="input" value={batch.values.award_date || ""}
                     onChange={(e) => setBatch({ ...batch, values: { ...batch.values, award_date: e.target.value } })} />
            </label>
          )}
          {batchResult && (
            <div className="space-y-2" data-testid="batch-result">
              <p className="text-sm font-medium text-slate-700">
                {t("{c} brouillon(s) produit(s), {r} refusé(s).", { c: batchResult.created, r: batchResult.refused })}
              </p>
              <ul className="text-xs divide-y divide-slate-100 max-h-60 overflow-y-auto">
                {batchResult.results.map((r) => (
                  <li key={r.student_id} className="py-1.5 flex gap-2">
                    <span className={r.ok ? "text-green-700" : "text-red-700"}>{r.ok ? "✓" : "✗"}</span>
                    <span className="font-medium">{r.student}</span>
                    {!r.ok && <span className="text-slate-600">— {r.reason}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setBatchOpen(false)}>{t("Fermer")}</button>
            {batchResult && batchResult.created > 0 ? (
              <button type="button" className="btn-primary" disabled={issueBatch.isPending}
                      onClick={() => issueBatch.mutate(batchResult.results.filter((r) => r.ok).map((r) => r.document.id))}>
                {t("Délivrer les {n} brouillon(s)", { n: batchResult.created })}
              </button>
            ) : (
              <button type="button" className="btn-primary" disabled={!batch.class_id || runBatch.isPending}
                      onClick={() => runBatch.mutate()}>
                {runBatch.isPending ? t("Production…") : t("Produire les brouillons")}
              </button>
            )}
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
