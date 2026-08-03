import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Download, Eye, FileSpreadsheet } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { studentsAPI, classesAPI, schoolsAPI, authAPI, parentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import StatusBadge from "../../components/ui/StatusBadge";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";
import { useSchoolYearScope } from "../../hooks/useSchoolYearScope";

function exportCSV(rows, filename) {
  if (!rows.length) { toast.error(t("Aucune donnée à exporter.")); return; }
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(";"),
    ...rows.map(r => headers.map(h => `"${String(r[h] ?? "").replace(/"/g, '""')}"`).join(";")),
  ];
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

export default function AdminStudents() {
  const qc = useQueryClient();
  const [enrollModal, setEnrollModal] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [viewItem, setViewItem] = useState(null);
  const [photoFile, setPhotoFile] = useState(null);
  const photoRef = useRef();
  const { register, handleSubmit, reset, control, watch, setValue, formState: { errors } } = useForm();
  const selectedUserId  = watch("user");
  const selectedLevelId = watch("level_filter");
  const selectedYearId  = watch("school_year");

  const [yearFilter, setYearFilter] = useState(null);
  const { data: classData }        = useQuery({ queryKey: ["classes-all-years"], queryFn: () => classesAPI.list({ all_years: "1" }) });
  const { data: yearsData }        = useQuery({ queryKey: ["years"],         queryFn: schoolsAPI.years });
  const { data: levelsData }       = useQuery({ queryKey: ["levels"],        queryFn: schoolsAPI.levels });
  // FIX v37 : seuls les comptes élève SANS profil sont proposés — un compte
  // déjà lié (ex: Estelle/0005) provoquait une erreur d'intégrité au lieu
  // d'orienter vers la réinscription annuelle.
  const { data: studentUsersData } = useQuery({ queryKey: ["student-users-unlinked"], queryFn: () => authAPI.listUsers({ role: "student", unlinked: 1 }) });

  const classes      = classData?.data?.results      || classData?.data      || [];
  const years        = yearsData?.data?.results      || yearsData?.data      || [];
  const levels       = levelsData?.data?.results     || levelsData?.data     || [];
  const studentUsers = studentUsersData?.data?.results || studentUsersData?.data || [];
  // P2 : en mode « Toutes les Académies », aucune année ne peut représenter
  // les deux académies — voir useSchoolYearScope.
  const { currentYear, yearLabel, isAllAcademies } = useSchoolYearScope(years);

  useEffect(() => {
    if (yearFilter !== null) return;
    // Mode consolidé : on n'impose AUCUNE année. Filtrer sur l'année
    // courante d'une seule académie masquerait l'autre sans le dire.
    if (isAllAcademies) { setYearFilter("all"); return; }
    if (currentYear) setYearFilter(currentYear.id);
  }, [currentYear, isAllAcademies, yearFilter]);

  const { data, isLoading } = useQuery({
    queryKey: ["students", yearFilter],
    queryFn: () => yearFilter === "all" ? studentsAPI.list() : studentsAPI.list({ school_year: yearFilter }),
    enabled: yearFilter !== null,
  });

  const students         = data?.data?.results || data?.data || [];
  const studentUserOpts  = studentUsers.map(u => ({ value: u.id, label: `${u.first_name} ${u.last_name} (${u.email})` }));
  const selectedUser     = studentUsers.find(u => u.id === selectedUserId);
  const levelOpts        = levels.map(l => ({ value: l.id, label: l.name }));

  // FIX v34 (cause racine des doublons CP1/CP1/CP1) : les classes existent
  // PAR ANNÉE. La liste est d'abord filtrée par l'année scolaire sélectionnée
  // dans le formulaire (cascade année → classes), puis par le niveau.
  // Sans année sélectionnée, chaque classe est étiquetée par son année.
  const classesOfYear = selectedYearId
    ? classes.filter(c => String(c.school_year) === String(selectedYearId))
    : classes;
  const filteredClassOpts = (selectedLevelId
    ? classesOfYear.filter(c => String(c.level) === String(selectedLevelId))
    : classesOfYear
  ).map(c => ({
    value: c.id,
    label: selectedYearId
      ? `${c.name}${c.level_name ? ` (${c.level_name})` : ""}`
      : `${c.name} — ${c.school_year_name || "?"}${c.level_name ? ` (${c.level_name})` : ""}`,
  }));

  // Changer d'année invalide la classe choisie si elle n'appartient plus à l'année
  useEffect(() => {
    const current = watch("current_class");
    if (current && selectedYearId) {
      const stillValid = classesOfYear.some(c => String(c.id) === String(current));
      if (!stillValid) setValue("current_class", "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedYearId]);

  useEffect(() => {
    if (selectedUserId && !editItem) {
      const found = studentUsers.find(u => String(u.id) === String(selectedUserId));
      if (found) { setValue("first_name", found.first_name || ""); setValue("last_name", found.last_name || ""); }
    }
  }, [selectedUserId, studentUsers, editItem, setValue]);

  const buildPayload = (d, isEdit = false) => {
    const fd = new FormData();
    if (d.user) fd.append("user", d.user);
    if (d.first_name) fd.append("first_name", d.first_name);
    if (d.last_name)  fd.append("last_name",  d.last_name);
    if (d.gender)     fd.append("gender",     d.gender);
    if (d.date_of_birth) fd.append("date_of_birth", d.date_of_birth);
    if (d.current_class) fd.append("current_class", d.current_class);
    if (d.school_year)   fd.append("school_year",   d.school_year);
    if (d.address)       fd.append("address",       d.address);
    if (!isEdit) fd.append("is_active", "true");
    if (photoFile) fd.append("photo", photoFile);
    return fd;
  };

  const createMut = useMutation({
    mutationFn: (d) => studentsAPI.create(buildPayload(d, false)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success(t("Élève créé !")); closeModal(); },
    onError: (e) => {
      const err = e.response?.data;
      toast.error(err?.detail || err?.first_name?.[0] || err?.last_name?.[0] || Object.values(err || {})?.[0]?.[0] || "Erreur");
    },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => studentsAPI.update(id, buildPayload(data, true)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success(t("Modifié !")); closeModal(); },
    onError: (e) => { const err = e.response?.data; toast.error(err?.detail || Object.values(err || {})?.[0]?.[0] || "Erreur"); },
  });
  // FIX v34 — trois niveaux de suppression, l'historique multi-années
  // n'est JAMAIS détruit par défaut :
  const removeYearMut = useMutation({
    mutationFn: ({ id, yearId }) => studentsAPI.removeFromYear(id, yearId),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success(r.data?.detail || "Retiré de l'année."); setDeleteItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: studentsAPI.delete,   // backend = DÉSACTIVATION (soft)
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success(r.data?.detail || "Élève désactivé — historique conservé."); setDeleteItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const hardDeleteMut = useMutation({
    mutationFn: studentsAPI.hardDelete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success(t("Suppression définitive effectuée.")); setDeleteItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  // FIX v35 (vidéos) : la suppression EN MASSE depuis une année précise ne
  // retire que les inscriptions de CETTE année ; les autres années restent
  // intactes. Depuis « Toutes » : désactivation (soft), jamais destructive.
  const yearScoped = yearFilter && yearFilter !== "all";
  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => yearScoped
      ? studentsAPI.bulkRemoveFromYear(ids, yearFilter)
      : studentsAPI.bulkDelete(ids),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(d?.data?.detail || `${d?.data?.removed ?? d?.data?.deleted ?? ""} élève(s) traité(s).`);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const selectedYearName = years.find(y => String(y.id) === String(yearFilter))?.name;
  const bulkConfirmMessage = (n) => yearScoped
    ? `Retirer ${n} élève(s) de l'année ${selectedYearName} ?\n\nSeules leurs inscriptions ${selectedYearName} seront supprimées — leurs autres années restent intactes.`
    : `Désactiver ${n} élève(s) (toutes années) ?\n\nIls disparaîtront des listes actives mais tout leur historique est conservé (réactivation possible).`;

  const closeModal = () => { setModalOpen(false); setEditItem(null); setPhotoFile(null); reset(); };

  const openCreate = () => {
    reset({ gender: "M", school_year: currentYear?.id || "", level_filter: "" });
    setPhotoFile(null); setModalOpen(true);
  };

  const openEdit = (s) => {
    setEditItem(s);
    const cls = classes.find(c => c.id === s.current_class);
    reset({
      user: s.user || null, gender: s.gender, date_of_birth: s.date_of_birth,
      current_class: s.current_class, school_year: s.school_year,
      first_name: s.first_name, last_name: s.last_name, address: s.address,
      level_filter: cls?.level || "",
    });
    setPhotoFile(null); setModalOpen(true);
  };

  const onSubmit = (d) => {
    if (editItem) {
      updateMut.mutate({ id: editItem.id, data: d });
    } else {
      if (selectedUser && !d.first_name) d.first_name = selectedUser.first_name;
      if (selectedUser && !d.last_name)  d.last_name  = selectedUser.last_name;
      createMut.mutate(d);
    }
  };

  const exportStudents = () => {
    const yearName = years.find(y => y.id === yearFilter)?.name || "toutes";
    const rows = students.map(s => ({
      // P2 : l'export doit rester exploitable hors de l'application, où
      // rien ne rappelle quelle académie était affichée au moment du clic.
      "Académie": s.academy_short_name || s.academy_name || "Sans académie",
      "Matricule": s.matricule || "", "Prénom": s.first_name || "", "Nom": s.last_name || "",
      "Genre": s.gender === "M" ? t("Masculin") : t("Féminin"),
      "Date de naissance": s.date_of_birth || "", "Niveau": s.class_level || "",
      "Classe": s.class_name || "", "Année scolaire": s.school_year_name || "",
      "Adresse": s.address || "", "Statut": s.is_active ? t("Actif") : t("Inactif"),
      "Date inscription": s.enrollment_date || "",
    }));
    exportCSV(rows, `eleves_${yearName}_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const cols = [
    { key: "photo", label: "", sortable: false, render: r => r.photo
      ? <img src={r.photo} className="w-8 h-8 rounded-lg object-cover" alt="" />
      : <div className="w-8 h-8 rounded-lg bg-primary-50 flex items-center justify-center text-primary text-xs font-bold">{r.first_name?.[0]}{r.last_name?.[0]}</div> },
    { key: "matricule", label: t("Matricule"), accessor: "matricule" },
    { key: "name",    label: t("Nom complet"),    accessor: "full_name" },
    { key: "class",   label: t("Classe"),         accessor: "class_name" },
    { key: "year",    label: t("Année"),          accessor: "school_year_name" },
    { key: "gender",  label: t("Genre"),          render: r => r.gender === "M" ? t("Masculin") : t("Féminin") },
    { key: "status",  label: t("Statut"),         sortable: false, render: r => <StatusBadge status={r.is_active ? "active" : "inactive"} /> },
  ];

  const { register: re, handleSubmit: he, reset: resetEnroll, watch: watchEnroll } = useForm();
  // FIX v44 : la classe cible du ré-inscription suit l'ANNÉE cible choisie —
  // sinon la liste affichait « 3ème-A — 3ème » une fois par année (triplons).
  const enrollTargetYear = watchEnroll ? watchEnroll("school_year") : "";
  const addEnrollMut = useMutation({
    mutationFn: (d) => {
      if (d._bulk === "class") return studentsAPI.enrollClass({ class_id: d.class_id, target_year_id: d.target_year_id, new_class_id: d.new_class_id });
      if (d._bulk === "all")   return studentsAPI.enrollAllFromYear({ source_year_id: d.source_year_id, target_year_id: d.target_year_id });
      return studentsAPI.enroll(d.student, { school_year: d.school_year, class_obj: d.class_obj || null });
    },
    onSuccess: (res) => {
      const data = res?.data;
      if (data?.enrolled !== undefined) {
        toast.success(t("{n} élève(s) inscrit(s)", { n: data.enrolled }) + (data.skipped ? t(", {n} déjà inscrit(s)", { n: data.skipped }) : "") + ".");
      } else {
        toast.success(t("Élève inscrit pour la nouvelle année !"));
      }
      setEnrollModal(null); resetEnroll(); qc.invalidateQueries({ queryKey: ["students"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Élèves")}
        subtitle={t("{n} élève(s)", { n: students.length }) + " — " + (years.find(y => y.id === yearFilter)?.name || (yearFilter === "all" ? t("Toutes les années") : ""))}
        action={
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <button onClick={exportStudents} className="btn-secondary flex items-center gap-2 text-sm">
              <FileSpreadsheet className="w-4 h-4" />{t("Export Excel")}</button>
            <button onClick={() => setEnrollModal({ _mode: "all", full_name: "Tous les élèves" })}
              className="btn-secondary flex items-center gap-2 text-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>{t("Inscrire tous")}</button>
            <button onClick={openCreate} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />{t("Ajouter un élève")}</button>
          </div>
        }
      />

      {years.length > 0 && (
        <div className="card flex gap-2 flex-wrap items-center">
          <span className="text-xs text-slate-500 font-medium mr-1">{t("Année :")}</span>
          {years.map(y => (
            <button key={y.id} onClick={() => setYearFilter(y.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${yearFilter === y.id ? "bg-primary text-white shadow" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {yearLabel(y)}{y.is_current ? " ✓" : ""}
            </button>
          ))}
          <button onClick={() => setYearFilter("all")}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${yearFilter === "all" ? "bg-slate-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{t("Toutes")}</button>
        </div>
      )}

      <div className="card overflow-x-auto">
        <DataTable
          emptyMessage={yearFilter && yearFilter !== "all"
            ? `Aucun élève inscrit en ${years.find(y => String(y.id) === String(yearFilter))?.name || "cette année"}.\nInscrivez des élèves via « Ajouter un élève », « Inscrire tous » ou l'onglet Inscriptions.\nBase vide ? Générez les données de démonstration : make seed`
            : "Aucun élève actif.\nBase vide ? Générez les données de démonstration : make seed"}
          columns={cols}
          data={students}
          loading={isLoading}
          onRowClick={(row) => setViewItem(row)}
          selectable
          onBulkDelete={ids => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          bulkDeleteLabel={yearScoped ? `Retirer de ${selectedYearName || "l'année"}` : "Désactiver la sélection"}
          bulkConfirmMessage={bulkConfirmMessage}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={(e) => { e.stopPropagation(); setViewItem(row); }}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600" title={t("Voir")}>
                <Eye className="w-4 h-4" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); openEdit(row); }}
                className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                <Pencil className="w-4 h-4" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); setDeleteItem(row); }}
                className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}
        />
      </div>

      {/* Detail modal */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto z-10">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">{t("Fiche Élève")}</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="flex items-center gap-4">
              {viewItem.photo
                ? <img src={viewItem.photo} className="w-20 h-20 rounded-xl object-cover border border-slate-100" alt={t("Photo")} />
                : <div className="w-20 h-20 rounded-xl bg-primary-50 flex items-center justify-center text-primary text-2xl font-bold">{viewItem.first_name?.[0]}{viewItem.last_name?.[0]}</div>}
              <div>
                <p className="font-bold text-slate-800 text-xl">{viewItem.full_name}</p>
                <p className="text-sm text-slate-500 font-mono">{viewItem.matricule}</p>
                <StatusBadge status={viewItem.is_active ? "active" : "inactive"} />
              </div>
            </div>
            <div className="space-y-0 text-sm divide-y divide-slate-100">
              {[
                ["Genre",          viewItem.gender === "M" ? t("Masculin") : t("Féminin")],
                ["Date naissance", viewItem.date_of_birth || "—"],
                ["Niveau",         viewItem.class_level || "—"],
                ["Classe",         viewItem.class_name || "—"],
                ["Année scolaire", viewItem.school_year_name || "—"],
                ["Adresse",        viewItem.address || "—"],
                ["Inscription",    viewItem.enrollment_date || "—"],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between py-2">
                  <span className="text-slate-500">{label}</span>
                  <span className="font-medium text-right max-w-[60%]">{val}</span>
                </div>
              ))}
            </div>
            {viewItem.photo && (
              <a href={viewItem.photo} download target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 btn-secondary text-sm">
                <Download className="w-4 h-4" />{t("Télécharger la photo")}</a>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEnrollModal(viewItem)}
                className="btn-secondary text-sm flex items-center gap-1">
                <Plus className="w-4 h-4" />{t("Nouvelle année")}</button>
              <button onClick={() => { setViewItem(null); openEdit(viewItem); }} className="btn-primary text-sm">
                <Pencil className="w-4 h-4 inline mr-1" />{t("Modifier")}</button>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier l'élève") : t("Nouvel élève")} size="lg">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

          <div>
            <label className="label">{t("Compte utilisateur élève")}{!editItem && " *"}</label>
            <Controller name="user" control={control} rules={!editItem ? { required: true } : {}}
              render={({ field }) => (
                <SearchableSelect options={studentUserOpts} value={field.value} onChange={field.onChange}
                  placeholder={t("Rechercher un utilisateur (rôle élève)…")} />
              )} />
            {errors.user && <p className="text-danger text-xs mt-1">{t("Requis")}</p>}
            {selectedUser && <p className="text-xs text-slate-400 mt-1">{t("Auto-rempli")} : {selectedUser.first_name} {selectedUser.last_name}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Prénom")} {!selectedUser && !editItem && "*"}</label>
              <input {...register("first_name", { required: !selectedUser && !editItem })} className="input"
                placeholder={selectedUser?.first_name || ""} readOnly={!!selectedUser} />
            </div>
            <div>
              <label className="label">{t("Nom")} {!selectedUser && !editItem && "*"}</label>
              <input {...register("last_name", { required: !selectedUser && !editItem })} className="input"
                placeholder={selectedUser?.last_name || ""} readOnly={!!selectedUser} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Genre")}</label>
              <select {...register("gender")} className="input">
                <option value="M">{t("Masculin")}</option><option value="F">{t("Féminin")}</option>
              </select>
            </div>
            <div>
              <label className="label">{t("Date de naissance")}</label>
              <input {...register("date_of_birth")} type="date" className="input" />
            </div>
          </div>

          {/* FIX v34 : workflow exigé — 1. année scolaire, 2. classes de
              CETTE année chargées dynamiquement, 3. classe. */}
          <div>
            <label className="label">{t("Année scolaire *")}</label>
            <Controller name="school_year" control={control}
              render={({ field }) => (
                <SearchableSelect
                  options={years.map(y => ({ value: y.id, label: `${y.name}${y.is_current ? " ✓ Active" : ""}` }))}
                  value={field.value} onChange={field.onChange} placeholder={t("Sélectionner une année…")}
                />
              )} />
            <p className="text-xs text-slate-400 mt-1">{t("Détermine les classes proposées ci-dessous")}</p>
          </div>

          {/* Niveau → filtre les classes */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Niveau académique")}</label>
              <Controller name="level_filter" control={control}
                render={({ field }) => (
                  <SearchableSelect
                    options={[{ value: "", label: "— Tous les niveaux —" }, ...levelOpts]}
                    value={field.value}
                    onChange={(val) => { field.onChange(val); setValue("current_class", ""); }}
                    placeholder={t("Filtrer par niveau…")}
                  />
                )} />
              <p className="text-xs text-slate-400 mt-1">{t("Filtre les classes disponibles")}</p>
            </div>
            <div>
              <label className="label">{t("Classe")}</label>
              <Controller name="current_class" control={control}
                render={({ field }) => (
                  <SearchableSelect
                    options={filteredClassOpts}
                    value={field.value}
                    onChange={field.onChange}
                    placeholder={selectedLevelId ? t("Choisir une classe…") : t("Toutes les classes…")}
                  />
                )} />
            </div>
          </div>

          <div>
            <label className="label">{t("Adresse")}</label>
            <textarea {...register("address")} className="input" rows={2} />
          </div>

          <div>
            <label className="label">{t("Photo (optionnel)")}</label>
            <input ref={photoRef} type="file" accept="image/*" className="hidden"
              onChange={e => setPhotoFile(e.target.files[0] || null)} />
            <div className="flex items-center gap-3">
              <button type="button" onClick={() => photoRef.current?.click()} className="btn-secondary text-sm">
                {photoFile ? photoFile.name : "Choisir une photo"}
              </button>
              {photoFile && <button type="button" onClick={() => setPhotoFile(null)} className="text-danger text-sm">{t("Retirer")}</button>}
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? t("Enregistrement…") : t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={!!deleteItem} onClose={() => setDeleteItem(null)} title={`Supprimer ${deleteItem?.full_name || ""} ?`} size="md">
        <div className="space-y-3">
          <p className="text-sm text-slate-600">{t("Choisissez la portée de la suppression. L'historique des autres années n'est")} <strong>jamais</strong> {t("affecté par les deux premières options.")}</p>
          {yearFilter && yearFilter !== "all" && (
            <button
              onClick={() => removeYearMut.mutate({ id: deleteItem.id, yearId: yearFilter })}
              disabled={removeYearMut.isPending}
              className="w-full text-left rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100 p-3 transition"
            >
              <p className="font-semibold text-amber-800 text-sm">
                Retirer de l'année {years.find(y => String(y.id) === String(yearFilter))?.name}
              </p>
              <p className="text-xs text-amber-700 mt-0.5">
                Supprime uniquement son inscription {years.find(y => String(y.id) === String(yearFilter))?.name}.
                Toutes ses autres années restent intactes.
              </p>
            </button>
          )}
          <button
            onClick={() => deleteMut.mutate(deleteItem.id)}
            disabled={deleteMut.isPending}
            className="w-full text-left rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 p-3 transition"
          >
            <p className="font-semibold text-slate-800 text-sm">{t("Désactiver l'élève (toutes années)")}</p>
            <p className="text-xs text-slate-500 mt-0.5">{t("L'élève disparaît des listes actives ; tout son historique est conservé et il peut être réactivé.")}</p>
          </button>
          <button
            onClick={() => {
              if (window.confirm("SUPPRESSION DÉFINITIVE : cette action est irréversible. Confirmer ?")) {
                hardDeleteMut.mutate(deleteItem.id);
              }
            }}
            disabled={hardDeleteMut.isPending}
            className="w-full text-left rounded-xl border border-red-200 bg-red-50 hover:bg-red-100 p-3 transition"
          >
            <p className="font-semibold text-red-700 text-sm">{t("Suppression définitive")}</p>
            <p className="text-xs text-red-600 mt-0.5">{t("Refusée automatiquement si des notes, paiements ou inscriptions existent encore.")}</p>
          </button>
          <div className="flex justify-end pt-1">
            <button onClick={() => setDeleteItem(null)} className="btn-secondary">{t("Annuler")}</button>
          </div>
        </div>
      </Modal>

      {/* Enrollment modal */}
      {enrollModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setEnrollModal(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto z-10">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">{t("Inscrire — nouvelle année")}</h2>
              <button onClick={() => setEnrollModal(null)} className="text-slate-400 hover:text-slate-600 text-2xl">×</button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[{ key: "single", label: t("Un élève") }, { key: "class", label: t("Une classe") }, { key: "all", label: t("Toute l'année") }].map(m => (
                <button key={m.key} onClick={() => setEnrollModal(p => ({ ...p, _mode: m.key }))}
                  className={`py-2 px-3 rounded-xl border text-sm font-medium transition ${(enrollModal._mode || "single") === m.key ? "bg-blue-600 text-white border-blue-600" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
                  {m.label}
                </button>
              ))}
            </div>
            <form onSubmit={he(d => {
              const mode = enrollModal._mode || "single";
              if (mode === "single") addEnrollMut.mutate({ student: enrollModal.id, school_year: d.school_year, class_obj: d.class_obj || null });
              else if (mode === "class") addEnrollMut.mutate({ _bulk: "class", class_id: d.class_id, target_year_id: d.school_year, new_class_id: d.class_obj || null });
              else addEnrollMut.mutate({ _bulk: "all", source_year_id: d.source_year, target_year_id: d.school_year });
            })} className="space-y-4">
              {(enrollModal._mode || "single") === "single" && (
                <div className="bg-blue-50 rounded-xl px-4 py-3 text-sm text-blue-800">{t("Élève :")} <span className="font-semibold">{enrollModal.full_name}</span>
                </div>
              )}
              {enrollModal._mode === "class" && (
                <div>
                  <label className="label">{t("Classe source *")}</label>
                  <select {...re("class_id", { required: true })} className="input" style={{ minHeight: "2.5rem" }}>
                    <option value="">{t("Choisir une classe...")}</option>
                    {classes.map(c => <option key={c.id} value={c.id}>{c.name}{c.level_name ? ` — ${c.level_name}` : ""}</option>)}
                  </select>
                </div>
              )}
              {enrollModal._mode === "all" && (
                <div>
                  <label className="label">{t("Année source *")}</label>
                  <select {...re("source_year", { required: true })} className="input" style={{ minHeight: "2.5rem" }}>
                    <option value="">{t("Choisir l'année source...")}</option>
                    {years.map(y => <option key={y.id} value={y.id}>{y.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="label">{t("Année cible *")}</label>
                <select {...re("school_year", { required: true })} className="input" style={{ minHeight: "2.5rem" }}>
                  <option value="">{t("Choisir une année...")}</option>
                  {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
                </select>
              </div>
              <div>
                <label className="label">{t("Nouvelle classe (optionnel)")}</label>
                <select {...re("class_obj")} className="input" style={{ minHeight: "2.5rem" }}>
                  <option value="">— Pas encore affecté —</option>
                  {(enrollTargetYear
                    ? classes.filter(c => String(c.school_year) === String(enrollTargetYear))
                    : classes
                  ).map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name}{enrollTargetYear ? "" : ` — ${c.school_year_name || "?"}`}{c.level_name ? ` (${c.level_name})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 justify-end pt-2">
                <button type="button" onClick={() => setEnrollModal(null)} className="btn-secondary">{t("Annuler")}</button>
                <button type="submit" disabled={addEnrollMut.isPending} className="btn-primary">
                  {addEnrollMut.isPending ? t("Inscription…") : t("Inscrire")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
