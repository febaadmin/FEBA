/**
 * Admissions FEBA French Heritage Academy — back-office.
 *
 * P2 — CAUSE RACINE CORRIGÉE
 * ---------------------------
 * Les fiches d'inscription et les demandes de test FHA étaient bien
 * enregistrées en base, mais AUCUN écran ne les interrogeait : le
 * back-office n'appelait que `/website/admin/preregistrations/`, qui ne
 * contient que les demandes FEBA. Les soumissions existaient donc sans
 * être visibles nulle part. Cet écran expose les deux modèles FHA.
 *
 * P6 — En mode « Toutes les Académies », chaque ligne porte son académie
 * (badge), et les compteurs sont donnés PAR ACADÉMIE : rien n'est fusionné
 * dans une liste ambiguë.
 *
 * P4 — L'académie active fait partie des `queryKey` : une bascule ne peut
 * pas resservir le cache de l'académie précédente.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  AlertTriangle, CalendarClock, CheckCircle2, ClipboardList, Download,
  FileText, MailWarning, RefreshCw, Search, Send, X,
} from "lucide-react";
import { websiteAdminAPI } from "../../api";
import LongText from "../../components/ui/LongText";
import DetailField from "../../components/ui/DetailField";
import { useAcademyKey, useEntityContext } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";

/* États du dossier d'inscription — repris du cahier de structure. */
const APPLICATION_STATUSES = [
  ["new_contact", "Nouveau contact"],
  ["form_received", "Fiche reçue"],
  ["test_booked", "Test réservé"],
  ["test_done", "Test effectué"],
  ["admission_offered", "Admission proposée"],
  ["documents_pending", "Documents en attente"],
  ["payment_pending", "Paiement en attente"],
  ["enrollment_confirmed", "Inscription confirmée"],
  ["account_activated", "Compte activé"],
  ["student_active", "Élève actif"],
  ["suspended", "Suspendu"],
  ["cancelled", "Annulé"],
];

const STATUS_TONE = {
  form_received: "bg-blue-50 text-blue-700",
  test_booked: "bg-indigo-50 text-indigo-700",
  test_done: "bg-violet-50 text-violet-700",
  admission_offered: "bg-amber-50 text-amber-700",
  enrollment_confirmed: "bg-emerald-50 text-emerald-700",
  student_active: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-red-50 text-red-700",
  suspended: "bg-red-50 text-red-700",
};

function Badge({ children, tone = "bg-slate-100 text-slate-700" }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md text-[11px] font-semibold ${tone}`}>
      {children}
    </span>
  );
}

/** Regroupe des lignes par académie — jamais de fusion ambiguë (P6). */
function groupByAcademy(rows) {
  const groups = new Map();
  for (const row of rows) {
    const code = row.entity_code || "—";
    if (!groups.has(code)) groups.set(code, []);
    groups.get(code).push(row);
  }
  return [...groups.entries()];
}

function toCsv(rows, columns) {
  const escape = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const header = columns.map((c) => escape(c.label)).join(",");
  const body = rows
    .map((row) => columns.map((c) => escape(c.value(row))).join(","))
    .join("\n");
  return `${header}\n${body}`;
}

function downloadCsv(filename, content) {
  // BOM UTF-8 (\uFEFF) : sans lui, Excel lit mal les accents.
  const blob = new Blob(["\uFEFF" + content], { type: "text/csv;charset=utf-8;" });
  downloadBlob(filename, blob);
}

/**
 * Téléchargement d'un contenu produit PAR LE SERVEUR.
 *
 * P3 — Le fichier ne transite jamais par une URL publique : il arrive dans
 * la réponse d'une requête authentifiée, et l'objet URL temporaire est
 * révoqué aussitôt. Une fiche d'inscription contient l'adresse et les
 * besoins particuliers d'un mineur ; un lien qui resterait valide serait
 * partageable par mégarde.
 */
function downloadBlob(filename, data, mimetype) {
  const blob = data instanceof Blob
    ? data
    : new Blob([data], { type: mimetype || "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * État d'acheminement d'un e-mail, tel qu'il est — jamais embelli.
 *
 * P1 — L'écran affichait implicitement « envoyé » pour tout le monde. Un
 * accusé de réception jamais parti doit se voir DANS LA LISTE : c'est là
 * qu'un administrateur passe, et un défaut relégué au détail n'est vu que
 * par qui le cherche déjà.
 */
function EmailStatus({ state }) {
  if (!state) return <span className="text-slate-400">—</span>;

  if (state.status === "none") {
    return <Badge tone="bg-slate-100 text-slate-500">{t("Aucun envoi")}</Badge>;
  }
  if (state.status === "failed") {
    return (
      <span title={state.error} className="inline-flex items-center gap-1">
        <AlertTriangle className="w-3.5 h-3.5 text-red-500" aria-hidden="true" />
        <Badge tone="bg-red-50 text-red-700">{t("Échec")}</Badge>
      </span>
    );
  }
  if (state.status === "retry") {
    return (
      <span title={state.error} className="inline-flex items-center gap-1">
        <MailWarning className="w-3.5 h-3.5 text-amber-500" aria-hidden="true" />
        <Badge tone="bg-amber-50 text-amber-700">{t("Nouvel essai")}</Badge>
      </span>
    );
  }
  if (!state.used_real_provider) {
    // Le message a été écrit dans la console du serveur. L'annoncer comme
    // « envoyé » serait un mensonge poli.
    return (
      <Badge tone="bg-slate-100 text-slate-600">
        {t("Sans fournisseur")}
      </Badge>
    );
  }
  return (
    <span className="inline-flex items-center gap-1">
      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" />
      <Badge tone="bg-emerald-50 text-emerald-700">{t("Envoyé")}</Badge>
    </span>
  );
}

export default function FhaAdmissions() {
  const [tab, setTab] = useState("applications");
  const { allEntitiesMode } = useEntityContext();

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-800">
          {t("Admissions FEBA French Heritage Academy")}
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {t("Fiches d'inscription et demandes de test de placement.")}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          ["applications", t("Fiches d'inscription"), ClipboardList],
          ["placement", t("Tests de placement"), CalendarClock],
        ].map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            aria-pressed={tab === key}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
              tab === key
                ? "bg-indigo-600 text-white"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            <Icon className="w-4 h-4" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      {tab === "applications" ? (
        <ApplicationsTab consolidated={allEntitiesMode} />
      ) : (
        <PlacementTab consolidated={allEntitiesMode} />
      )}
    </div>
  );
}

/* ── Fiches d'inscription ────────────────────────────────────────────────── */

function ApplicationsTab({ consolidated }) {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [detail, setDetail] = useState(null);

  const { data, isLoading } = useQuery({
    // P4 : l'académie fait partie de la clé — pas de cache croisé.
    queryKey: ["fha-applications", academyKey],
    queryFn: () => websiteAdminAPI.fhaApplications(),
  });

  const rows = data?.data?.results || data?.data || [];

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter && row.status !== statusFilter) return false;
      if (!needle) return true;
      // P11 — Ces trois clés n'existent PAS dans la réponse : le
      // serializer expose « parent1_* ». La recherche lisait donc
      // « undefined » et ne trouvait jamais un dossier par le nom du
      // parent, sans que rien ne le signale.
      return [
        row.reference, row.child_first_name, row.child_last_name,
        row.parent1_first_name, row.parent1_last_name, row.parent1_email,
        row.parent1_phone, row.parent1_whatsapp,
      ].some((field) => String(field || "").toLowerCase().includes(needle));
    });
  }, [rows, search, statusFilter]);

  const statusMut = useMutation({
    mutationFn: ({ id, status }) => websiteAdminAPI.fhaChangeStatus(id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fha-applications", academyKey] });
      toast.success(t("Statut mis à jour."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  // P4 — L'EXPORT VIENT DU SERVEUR.
  //
  // L'export construit ici ne contenait que les dix colonnes affichées, et
  // trois d'entre elles lisaient des clés inexistantes : le fichier sortait
  // avec des cellules vides, sans erreur. Le serveur exporte désormais tous
  // les champs du modèle, sous le même filtrage par académie que la liste —
  // un export plus permissif que l'écran serait un moyen discret de
  // contourner l'isolation.
  const exportMut = useMutation({
    mutationFn: () => websiteAdminAPI.exportFhaApplications(),
    onSuccess: (response) => {
      downloadBlob(`dossiers-fha-${new Date().toISOString().slice(0, 10)}.csv`,
                   response.data);
      toast.success(t("Export téléchargé."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const sheetMut = useMutation({
    mutationFn: (id) => websiteAdminAPI.fhaApplicationSheet(id),
    onSuccess: (response, id) => {
      const row = rows.find((r) => r.id === id);
      downloadBlob(`${row?.reference || "fiche"}-fiche-inscription.pdf`,
                   response.data, "application/pdf");
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const resendMut = useMutation({
    mutationFn: (id) => websiteAdminAPI.fhaResendConfirmation(id),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["fha-applications", academyKey] });
      // On rapporte ce qui s'est réellement produit, pas un succès de
      // principe : « accepté par le fournisseur » n'est pas « reçu ».
      if (response.data.accepted && response.data.used_real_provider) {
        toast.success(t("E-mail accepté par le fournisseur."));
      } else if (response.data.accepted) {
        toast(t("Enregistré, mais aucun fournisseur réel n'est configuré."),
              { icon: "⚠️" });
      } else {
        toast.error(response.data.error || t("L'envoi a de nouveau échoué."));
      }
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  return (
    <div className="space-y-4">
      <Toolbar
        search={search}
        onSearch={setSearch}
        count={filtered.length}
        onExport={() => exportMut.mutate()}
        exporting={exportMut.isPending}
        extra={
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-slate-200 px-3 py-2 text-sm"
            aria-label={t("Filtrer par statut")}
          >
            <option value="">{t("Tous les statuts")}</option>
            {APPLICATION_STATUSES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        }
      />

      {isLoading ? (
        <div className="card py-12 text-center text-slate-400">{t("Chargement…")}</div>
      ) : filtered.length === 0 ? (
        <EmptyState label={t("Aucune fiche d'inscription pour le moment.")} />
      ) : consolidated ? (
        // P6 : vue consolidée SÉPARÉE par académie.
        groupByAcademy(filtered).map(([code, group]) => (
          <section key={code} className="card">
            <header className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-800">{code}</h2>
              <Badge>{group.length} {t("dossier(s)")}</Badge>
            </header>
            <ApplicationTable
              rows={group}
              onOpen={setDetail}
              onStatus={(id, status) => statusMut.mutate({ id, status })}
              onSheet={(id) => sheetMut.mutate(id)}
              onResend={(id) => resendMut.mutate(id)}
              busy={sheetMut.isPending || resendMut.isPending}
            />
          </section>
        ))
      ) : (
        <div className="card">
          <ApplicationTable
            rows={filtered}
            onOpen={setDetail}
            onStatus={(id, status) => statusMut.mutate({ id, status })}
            onSheet={(id) => sheetMut.mutate(id)}
            onResend={(id) => resendMut.mutate(id)}
            busy={sheetMut.isPending || resendMut.isPending}
          />
        </div>
      )}

      {detail && <ApplicationDetail id={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function ApplicationTable({ rows, onOpen, onStatus, onSheet, onResend, busy }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-100">
            <th className="py-2 pr-3 font-semibold">{t("Dossier")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Académie")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Enfant")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Groupe suggéré")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Parent")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Statut")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Fiche PDF")}</th>
            <th className="py-2 pr-3 font-semibold">{t("E-mail parent")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Reçue le")}</th>
            <th className="py-2 pr-3 font-semibold text-right">{t("Actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-slate-50 hover:bg-slate-50/60">
              <td className="py-2.5 pr-3">
                <button
                  type="button"
                  onClick={() => onOpen(row.id)}
                  className="font-semibold text-indigo-600 hover:underline"
                >
                  {row.reference}
                </button>
              </td>
              <td className="py-2.5 pr-3"><Badge>{row.entity_code}</Badge></td>
              <td className="py-2.5 pr-3">
                {row.child_first_name} {row.child_last_name}
                {row.child_age != null && (
                  <span className="text-slate-400"> · {row.child_age} {t("ans")}</span>
                )}
              </td>
              <td className="py-2.5 pr-3 text-slate-500">
                {(row.recommended_group || row.suggested_group || "—").replace(/_/g, " ")}
              </td>
              <td className="py-2.5 pr-3">
                <div>{row.parent1_first_name} {row.parent1_last_name}</div>
                <div className="text-slate-400 text-xs break-all">{row.parent1_email}</div>
                {row.parent1_whatsapp && (
                  <div className="text-slate-400 text-xs">
                    WhatsApp&nbsp;: {row.parent1_whatsapp}
                  </div>
                )}
              </td>
              <td className="py-2.5 pr-3">
                <select
                  value={row.status}
                  onChange={(e) => onStatus(row.id, e.target.value)}
                  aria-label={t("Changer le statut")}
                  className={`rounded-md px-2 py-1 text-xs font-semibold border-0 ${
                    STATUS_TONE[row.status] || "bg-slate-100 text-slate-700"
                  }`}
                >
                  {APPLICATION_STATUSES.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </td>
              <td className="py-2.5 pr-3">
                {row.has_sheet
                  ? <Badge tone="bg-emerald-50 text-emerald-700">{t("Produite")}</Badge>
                  : <Badge tone="bg-red-50 text-red-700">{t("Absente")}</Badge>}
              </td>
              <td className="py-2.5 pr-3">
                <EmailStatus state={row.confirmation_email} />
              </td>
              <td className="py-2.5 pr-3 text-slate-500 whitespace-nowrap">
                {(row.created_at || "").slice(0, 10)}
              </td>
              <td className="py-2.5 pr-3">
                <div className="flex items-center gap-1 justify-end">
                  <button
                    type="button" disabled={busy}
                    onClick={() => onSheet(row.id)}
                    title={t("Télécharger la fiche PDF")}
                    aria-label={t("Télécharger la fiche PDF")}
                    className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 disabled:opacity-40"
                  >
                    <FileText className="w-4 h-4" />
                  </button>
                  <button
                    type="button" disabled={busy}
                    onClick={() => onResend(row.id)}
                    title={t("Renvoyer l'e-mail de confirmation")}
                    aria-label={t("Renvoyer l'e-mail de confirmation")}
                    className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 disabled:opacity-40"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpen(row.id)}
                    title={t("Voir le détail complet")}
                    aria-label={t("Voir le détail complet")}
                    className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500"
                  >
                    <Search className="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** « Oui » / « Non » plutôt que « true » / « false ». */
function yesNo(value) {
  if (value === null || value === undefined) return "";
  return value ? t("Oui") : t("Non");
}

function ApplicationDetail({ id, onClose }) {
  const academyKey = useAcademyKey();
  const { data, isLoading } = useQuery({
    queryKey: ["fha-application", id, academyKey],
    queryFn: () => websiteAdminAPI.fhaApplication(id),
  });
  const row = data?.data;

  return (
    <DetailDrawer title={t("Fiche d'inscription")} onClose={onClose}>
      {isLoading || !row ? (
        <p className="text-slate-400">{t("Chargement…")}</p>
      ) : (
        <div className="space-y-5 text-sm">
          <Section title={t("Dossier")}>
            <Row label={t("Numéro")} value={row.reference} />
            <Row label={t("Académie")}
                 value={`${row.entity_short_name || ""} [${row.entity_code || "—"}]`} />
            <Row label={t("Statut")} value={row.status_display || row.status} />
            <Row label={t("Reçue le")} value={(row.created_at || "").slice(0, 16).replace("T", " ")} />
          </Section>

          {/* P1/P3 — Ce que l'administration doit voir en premier : le
              dossier a-t-il sa fiche, et l'accusé de réception est-il
              réellement parti ? Ces deux réponses conditionnent l'action. */}
          <Section title={t("Fiche et notifications")}>
            <Row label={t("Fiche PDF")}
                 value={row.has_sheet ? t("Produite") : t("Absente")} />
            <Row label={t("Produite le")}
                 value={(row.sheet_generated_at || "").slice(0, 16).replace("T", " ")} />
            <Row label={t("Version de la fiche")} value={row.sheet_version} />
            {row.sheet_error && (
              <Row label={t("Erreur de production")} value={row.sheet_error} />
            )}
            <Row label={t("E-mail au parent")}
                 value={row.confirmation_email?.status_display} />
            <Row label={t("Identifiant de suivi")}
                 value={row.confirmation_email?.tracking_id} />
            {row.confirmation_email?.error && (
              <Row label={t("Erreur d'envoi")} value={row.confirmation_email.error} />
            )}
            {row.confirmation_email?.status !== "none"
              && !row.confirmation_email?.used_real_provider && (
              <Row label={t("Fournisseur")}
                   value={t("Aucun fournisseur réel configuré — le message n'est pas parti sur Internet.")} />
            )}
            <Row label={t("Notification des administrateurs")}
                 value={row.admin_alert_email?.status_display} />
          </Section>

          <Section title={t("Enfant")}>
            <Row label={t("Nom")} value={`${row.child_first_name} ${row.child_last_name}`} />
            <Row label={t("Date de naissance")} value={row.child_birth_date} />
            <Row label={t("Âge")} value={row.child_age} />
            <Row label={t("Ville")} value={row.child_city} />
            <Row label={t("État / province")} value={row.child_state_province} />
            <Row label={t("Pays")} value={row.child_country} />
            <Row label={t("École actuelle")} value={row.child_current_school} />
            <Row label={t("Classe")} value={row.child_grade} />
          </Section>

          <Section title={t("Origines et langues")}>
            <Row label={t("Pays d'origine")} value={row.family_origin_country} />
            <Row label={t("Langue à la maison")} value={row.home_main_language} />
            <Row label={t("Autres langues")} value={row.other_languages} />
            <Row label={t("Parle français avec")} value={row.french_speakers_with_child} />
          </Section>

          {/* Les libellés viennent du serveur : afficher
              « understands_replies_english » à un administrateur ne lui
              apprend rien. */}
          <Section title={t("Niveau de français")}>
            <Row label={t("Niveaux déclarés")}
                 value={(row.labels?.french_levels || row.french_levels || []).join(", ")} />
            <Row label={t("Précisions")} value={row.french_level_notes} />
          </Section>

          <Section title={t("Expérience antérieure")}>
            <Row label={t("Cours déjà suivis")} value={yesNo(row.previous_courses)} />
            <Row label={t("École bilingue")} value={yesNo(row.bilingual_school)} />
            <Row label={t("Séjour en pays francophone")}
                 value={yesNo(row.stay_in_francophone_country)} />
            <Row label={t("Certifications")} value={row.certifications_obtained} />
            <Row label={t("Durée")} value={row.experience_duration} />
            <Row label={t("Commentaires")} value={row.experience_comments} />
          </Section>

          <Section title={t("Objectifs des parents")}>
            <Row label={t("Objectifs")}
                 value={(row.labels?.parent_goals || row.parent_goals || []).join(", ")} />
            <Row label={t("Autre")} value={row.parent_goals_other} />
          </Section>

          <Section title={t("Parent / responsable 1")}>
            <Row label={t("Nom")} value={`${row.parent1_first_name} ${row.parent1_last_name}`} />
            <Row label={t("Relation")} value={row.parent1_relation} />
            <Row label={t("Email")} value={row.parent1_email} />
            <Row label={t("Téléphone")} value={row.parent1_phone} />
            <Row label="WhatsApp" value={row.parent1_whatsapp} />
            <Row label={t("Adresse")} value={row.parent1_address} />
            <Row label={t("Ville")} value={row.parent1_city} />
            <Row label={t("État / province")} value={row.parent1_state_province} />
            <Row label={t("Code postal")} value={row.parent1_postal_code} />
            <Row label={t("Pays")} value={row.parent1_country} />
            <Row label={t("Langue préférée")}
                 value={row.labels?.parent1_preferred_language} />
            <Row label={t("Fuseau horaire")} value={row.parent1_timezone} />
          </Section>

          {row.parent2_last_name && (
            <Section title={t("Parent / responsable 2")}>
              <Row label={t("Nom")} value={`${row.parent2_first_name} ${row.parent2_last_name}`} />
              <Row label={t("Relation")} value={row.parent2_relation} />
              <Row label={t("Email")} value={row.parent2_email} />
              <Row label={t("Téléphone")} value={row.parent2_phone} />
              <Row label="WhatsApp" value={row.parent2_whatsapp} />
              <Row label={t("Adresse")} value={row.parent2_address} />
              <Row label={t("Ville")} value={row.parent2_city} />
              <Row label={t("État / province")} value={row.parent2_state_province} />
              <Row label={t("Code postal")} value={row.parent2_postal_code} />
              <Row label={t("Pays")} value={row.parent2_country} />
              <Row label={t("Langue préférée")}
                   value={row.labels?.parent2_preferred_language} />
              <Row label={t("Fuseau horaire")} value={row.parent2_timezone} />
            </Section>
          )}

          <Section title={t("Contact d'urgence")}>
            <Row label={t("Nom")} value={row.emergency_name} />
            <Row label={t("Relation")} value={row.emergency_relation} />
            <Row label={t("Téléphone")} value={row.emergency_phone} />
            <Row label={t("Email")} value={row.emergency_email} />
            <Row label={t("Autorisé à être contacté")}
                 value={yesNo(row.emergency_contact_authorized)} />
          </Section>

          <Section title={t("Disponibilités")}>
            <Row label={t("Jours")}
                 value={(row.labels?.available_days || row.available_days || []).join(", ")} />
            <Row
              label={t("Créneaux")}
              value={(row.available_time_slots || [])
                .map((s) => `${s.start}–${s.end}`)
                .join(", ")}
            />
            <Row label={t("Fuseau horaire")} value={row.family_timezone} />
            <Row label={t("Semaine / week-end")} value={row.labels?.weekday_or_weekend} />
            <Row label={t("Précisions")} value={row.availability_notes} />
          </Section>

          <Section title={t("Équipement")}>
            <Row
              label={t("Matériel")}
              value={[
                row.has_computer && t("Ordinateur"),
                row.has_tablet && t("Tablette"),
                row.has_camera && t("Caméra"),
                row.has_microphone && t("Micro"),
                row.has_headset && t("Casque"),
                row.has_internet && t("Internet"),
                row.can_print && t("Impression"),
              ].filter(Boolean).join(", ")}
            />
            <Row label={t("Précisions")} value={row.equipment_notes} />
          </Section>

          {/* Donnée sensible : le backend la vide pour tout profil non
              habilité, donc l'absence de valeur est déjà une protection. */}
          {row.special_needs && (
            <Section title={t("Besoins particuliers (confidentiel)")}>
              {/* P6 — Un besoin particulier peut tenir en trois pages.
                  Le tronquer, c'est prendre une décision pédagogique sur
                  une information amputée. */}
              <LongText value={row.special_needs} maxHeight="none" />
            </Section>
          )}

          <Section title={t("Consentements")}>
            <Row label={t("Règlement intérieur")} value={yesNo(row.consent_rules)} />
            <Row label={t("Visioconférence")} value={yesNo(row.consent_zoom)} />
            <Row label={t("Confidentialité")} value={yesNo(row.consent_privacy)} />
            <Row label={t("Traitement des données")} value={yesNo(row.consent_data_processing)} />
            <Row label={t("Photos et vidéos")} value={yesNo(row.consent_photo_video)} />
            <Row label={t("Communications")} value={yesNo(row.consent_communications)} />
            <Row label={t("Politique de paiement")} value={yesNo(row.consent_payment_policy)} />
            <Row label={t("Engagement annuel")} value={yesNo(row.consent_annual_commitment)} />
            <Row label={t("Autorisation parentale")}
                 value={yesNo(row.consent_parental_authorization)} />
            <Row label={t("Version")} value={row.consents_version} />
            <Row label={t("Acceptés le")} value={(row.consents_accepted_at || "").slice(0, 16)} />
          </Section>

          {(row.status_history || []).length > 0 && (
            <Section title={t("Historique")}>
              <ul className="space-y-1.5">
                {row.status_history.map((h, i) => (
                  <li key={i} className="text-xs text-slate-500 text-longform">
                    {(h.created_at || "").slice(0, 16)} · {h.from_status || "—"} → {h.to_status}
                    {h.changed_by && ` · ${h.changed_by}`}
                    {h.reason && ` · ${h.reason}`}
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>
      )}
    </DetailDrawer>
  );
}

/* ── Tests de placement ─────────────────────────────────────────────────── */

function PlacementTab({ consolidated }) {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const [search, setSearch] = useState("");
  const [scheduling, setScheduling] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["fha-placement-tests", academyKey],
    queryFn: () => websiteAdminAPI.fhaPlacementTests(),
  });

  const rows = data?.data?.results || data?.data || [];
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      [row.reference, row.child_first_name, row.child_last_name, row.parent_email]
        .some((f) => String(f || "").toLowerCase().includes(needle)),
    );
  }, [rows, search]);

  const scheduleMut = useMutation({
    mutationFn: ({ id, scheduled_at }) =>
      websiteAdminAPI.schedulePlacementTest(id, { scheduled_at }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fha-placement-tests", academyKey] });
      toast.success(t("Créneau confirmé — le parent a été notifié."));
      setScheduling(null);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const columns = [
    { label: t("Dossier"), value: (r) => r.reference },
    { label: t("Académie"), value: (r) => r.entity_code },
    { label: t("Enfant"), value: (r) => `${r.child_first_name} ${r.child_last_name}` },
    { label: t("Âge"), value: (r) => r.child_age },
    { label: t("Parent"), value: (r) => r.parent_email },
    { label: t("Fuseau"), value: (r) => r.parent_timezone },
    { label: t("Statut"), value: (r) => r.status },
  ];

  return (
    <div className="space-y-4">
      <Toolbar
        search={search}
        onSearch={setSearch}
        count={filtered.length}
        onExport={() => downloadCsv("fha-tests-placement.csv", toCsv(filtered, columns))}
      />

      {isLoading ? (
        <div className="card py-12 text-center text-slate-400">{t("Chargement…")}</div>
      ) : filtered.length === 0 ? (
        <EmptyState label={t("Aucune demande de test de placement.")} />
      ) : consolidated ? (
        groupByAcademy(filtered).map(([code, group]) => (
          <section key={code} className="card">
            <header className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-800">{code}</h2>
              <Badge>{group.length} {t("demande(s)")}</Badge>
            </header>
            <PlacementTable rows={group} onSchedule={setScheduling} />
          </section>
        ))
      ) : (
        <div className="card">
          <PlacementTable rows={filtered} onSchedule={setScheduling} />
        </div>
      )}

      {scheduling && (
        <ScheduleDialog
          request={scheduling}
          loading={scheduleMut.isPending}
          onCancel={() => setScheduling(null)}
          onConfirm={(iso) => scheduleMut.mutate({ id: scheduling.id, scheduled_at: iso })}
        />
      )}
    </div>
  );
}

function PlacementTable({ rows, onSchedule }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-100">
            <th className="py-2 pr-3 font-semibold">{t("Dossier")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Académie")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Enfant")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Parent")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Souhait")}</th>
            <th className="py-2 pr-3 font-semibold">{t("Statut")}</th>
            <th className="py-2 pr-3 font-semibold" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-slate-50 hover:bg-slate-50/60">
              <td className="py-2.5 pr-3 font-semibold">{row.reference}</td>
              <td className="py-2.5 pr-3"><Badge>{row.entity_code}</Badge></td>
              <td className="py-2.5 pr-3">
                {row.child_first_name} {row.child_last_name}
                {row.child_age != null && (
                  <span className="text-slate-400"> · {row.child_age} {t("ans")}</span>
                )}
              </td>
              <td className="py-2.5 pr-3">
                <div>{row.parent_first_name} {row.parent_last_name}</div>
                <div className="text-slate-400 text-xs">{row.parent_email}</div>
              </td>
              <td className="py-2.5 pr-3 text-slate-500">
                {row.preferred_date || "—"} {row.preferred_time || ""}
                {row.parent_timezone && (
                  <div className="text-xs text-slate-400">{row.parent_timezone}</div>
                )}
              </td>
              <td className="py-2.5 pr-3">
                <Badge tone="bg-indigo-50 text-indigo-700">
                  {row.status_display || row.status}
                </Badge>
                {row.scheduled_at && (
                  <div className="text-xs text-slate-400 mt-0.5">
                    {row.scheduled_at.slice(0, 16).replace("T", " ")} UTC
                  </div>
                )}
              </td>
              <td className="py-2.5 pr-3 text-right">
                <button
                  type="button"
                  onClick={() => onSchedule(row)}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold"
                >
                  {t("Planifier")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScheduleDialog({ request, loading, onCancel, onConfirm }) {
  const [value, setValue] = useState("");
  return (
    <DetailDrawer title={t("Planifier le test")} onClose={onCancel}>
      <div className="space-y-4 text-sm">
        <p>
          {t("Enfant")} : <strong>{request.child_first_name} {request.child_last_name}</strong>
        </p>
        <p className="text-slate-500">
          {t("Fuseau de la famille")} : {request.parent_timezone || t("non précisé")}
        </p>
        <label className="block">
          <span className="block text-xs font-semibold text-slate-600 mb-1.5">
            {t("Date et heure (votre heure locale)")}
          </span>
          <input
            type="datetime-local"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3 py-2"
          />
        </label>
        <p className="text-xs text-slate-400">
          {t("Le créneau est enregistré en UTC et communiqué au parent dans son propre fuseau horaire.")}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!value || loading}
            onClick={() => {
              // Conversion explicite en ISO avec fuseau du navigateur.
              const iso = new Date(value).toISOString();
              onConfirm(iso);
            }}
            className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold disabled:opacity-50"
          >
            {loading ? t("Envoi…") : t("Confirmer le créneau")}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-semibold"
          >
            {t("Annuler")}
          </button>
        </div>
      </div>
    </DetailDrawer>
  );
}

/* ── Éléments partagés ──────────────────────────────────────────────────── */

function Toolbar({ search, onSearch, count, onExport, extra, exporting }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative flex-1 min-w-[12rem]">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder={t("Rechercher un dossier, un enfant, un parent…")}
          aria-label={t("Rechercher")}
          className="w-full rounded-xl border border-slate-200 pl-9 pr-3 py-2 text-sm"
        />
      </div>
      {extra}
      <span className="text-xs text-slate-500">{count} {t("résultat(s)")}</span>
      <button
        type="button"
        onClick={onExport}
        disabled={count === 0 || exporting}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 text-sm font-semibold disabled:opacity-50"
      >
        {exporting
          ? <RefreshCw className="w-4 h-4 animate-spin" aria-hidden="true" />
          : <Download className="w-4 h-4" aria-hidden="true" />}
        {t("Exporter CSV")}
      </button>
    </div>
  );
}

function EmptyState({ label }) {
  return (
    <div className="card py-16 text-center text-slate-400">
      <ClipboardList className="w-12 h-12 mx-auto mb-3 opacity-30" aria-hidden="true" />
      {label}
    </div>
  );
}

function DetailDrawer({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden="true" />
      <div className="relative w-full max-w-2xl bg-white h-full overflow-y-auto overflow-x-hidden shadow-2xl">
        <header className="sticky top-0 bg-white border-b border-slate-100 px-5 py-4 flex items-center justify-between">
          <h2 className="font-bold text-slate-800">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t("Fermer")} className="p-1.5 rounded-lg hover:bg-slate-100">
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </header>
        <div className="p-5 min-w-0">{children}</div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">{title}</h3>
      <div className="space-y-1 min-w-0">{children}</div>
    </section>
  );
}

/**
 * P0 — `Row` est désormais un simple alias de `DetailField`.
 *
 * L'ancienne version (`flex justify-between` + `text-right`, sans aucune
 * règle de repli) est la cause exacte des six annotations « Les textes
 * longs ne sont pas bien cadrés » relevées sur ce panneau : adresse
 * complète, objectifs des parents, expérience antérieure, certifications,
 * précisions de disponibilité et précisions de matériel dépassaient tous
 * du cadre. Le composant partagé décide de la mise en forme d'après le
 * contenu et ne tronque jamais.
 */
function Row({ label, value }) {
  return <DetailField label={label} value={value} />;
}
