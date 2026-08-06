import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, CalendarDays } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { scheduleAPI, classesAPI, schoolsAPI, subjectsAPI, teachersAPI } from "../../../api";
import Modal from "../../../components/ui/Modal";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import { clsx } from "clsx";
import SearchableSelect from "../../../components/ui/SearchableSelect";
import AcademyBadge from "../../../components/AcademyBadge";
import { useAcademy } from "../../../context/AcademyContext";
import { t } from "../../../i18n";

const DAYS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi"];
const COLORS = ["bg-primary-50 border-primary/20 text-primary","bg-emerald-50 border-emerald-200 text-emerald-700","bg-amber-50 border-amber-200 text-amber-700","bg-rose-50 border-rose-200 text-rose-700","bg-sky-50 border-sky-200 text-sky-700","bg-violet-50 border-violet-200 text-violet-700"];

export default function CampusSchedule() {
  const qc = useQueryClient();
  const { activeAcademy, isAllAcademies } = useAcademy();
  // Le nom de l'académie est rappelé sur le bouton de création : sans lui,
  // rien à l'écran ne dit dans quelle académie le créneau va être créé.
  const academyLabel = activeAcademy?.short_name || activeAcademy?.name || "";
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [classFilter, setClassFilter] = useState("");
  const [view, setView] = useState("grid"); // "grid" | "list"
  const { register, handleSubmit, reset, control } = useForm();

  const { data, isLoading } = useQuery({ queryKey: ["schedule", classFilter], queryFn: () => scheduleAPI.list(classFilter ? { cls: classFilter } : {}), retry: false });
  const { data: classData } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const { data: subjData } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const { data: teacherData } = useQuery({ queryKey: ["teachers-all"], queryFn: () => teachersAPI.list() });

  const { data: roomData } = useQuery({ queryKey: ["rooms"], queryFn: () => schoolsAPI.rooms() });
  const rooms = roomData?.data?.results || roomData?.data || [];
  const classes = classData?.data?.results || classData?.data || [];
  const subjects = subjData?.data?.results || subjData?.data || [];
  const years = yearsData?.data?.results || yearsData?.data || [];
  const teachers = teacherData?.data?.results || teacherData?.data || [];
  const schedules = data?.data?.results || data?.data || [];
  const currentYear = years.find(y => y.is_current);
  const classOptions = classes.map(c => ({ value: c.id, label: c.name }));
  const subjectOptions = subjects.map(s => ({ value: s.id, label: s.name }));
  const teacherOptions = teachers.map(tc => ({ value: tc.id, label: `${tc.user_first_name || ""} ${tc.user_last_name || ""}`.trim() }));
  const roomOptions = rooms.map(r => ({ value: r.name, label: `${r.name} (${r.room_type_label || r.room_type})` }));

  // P2 — Ces mutations n'affichaient AUCUN message d'erreur : une
  // modification ou une suppression refusée par le serveur (conflit
  // d'horaire, permission, etc.) échouait EN SILENCE. C'était exactement
  // le manque signalé côté FEBA, alors qu'OnlineSchedule (FEBA FHA)
  // affichait déjà le détail réel renvoyé par le serveur — l'écart de
  // qualité était ici, pas seulement dans la mise en page.
  const failure = (e) => {
    const detail = e?.response?.data;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.detail || Object.values(detail || {}).flat().join(" ") || t("Erreur serveur");
    toast.error(message);
  };

  const createMut = useMutation({ mutationFn: scheduleAPI.create, onSuccess: () => { qc.invalidateQueries({ queryKey: ["schedule"] }); toast.success(t("Créneau créé!")); closeModal(); }, onError: failure });
  const updateMut = useMutation({ mutationFn: ({ id, data }) => scheduleAPI.update(id, data), onSuccess: () => { qc.invalidateQueries({ queryKey: ["schedule"] }); toast.success(t("Modifié!")); closeModal(); }, onError: failure });
  const deleteMut = useMutation({ mutationFn: scheduleAPI.delete, onSuccess: () => { qc.invalidateQueries({ queryKey: ["schedule"] }); toast.success(t("Supprimé.")); setDeleteItem(null); }, onError: failure });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => { reset({ day_of_week: 0, school_year: currentYear?.id || "" }); setModalOpen(true); };
  const openEdit = (s) => { setEditItem(s); reset({ day_of_week: s.day_of_week, start_time: s.start_time?.slice(0,5), end_time: s.end_time?.slice(0,5), room: s.room }); setModalOpen(true); };
  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: d });
    else createMut.mutate(d);
  };

  // Build matrix: rows = unique time slots, cols = days
  const timeSlots = [...new Set(schedules.map(s => `${s.start_time?.slice(0,5)}-${s.end_time?.slice(0,5)}`))].sort();
  const daySchedules = DAYS.map((day, di) => ({
    day, idx: di,
    items: schedules.filter(s => s.day_of_week === di).sort((a,b) => a.start_time > b.start_time ? 1 : -1)
  }));

  const subjectMap = {};
  schedules.forEach((s, i) => { if (s.subject_name) subjectMap[s.subject_name] = i % COLORS.length; });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">{t("{n} créneau(x)", { n: schedules.length })}</p>
        <div className="flex gap-2">
          <div className="flex rounded-xl border border-slate-200 overflow-hidden">
            <button onClick={() => setView("grid")} className={clsx("px-3 py-1.5 text-xs font-medium", view === "grid" ? "bg-primary text-white" : "bg-white text-slate-600")}>{t("Grille")}</button>
            <button onClick={() => setView("list")} className={clsx("px-3 py-1.5 text-xs font-medium border-l", view === "list" ? "bg-primary text-white" : "bg-white text-slate-600")}>{t("Liste")}</button>
          </div>
          {/* En mode « Toutes les Académies », aucune académie n'est active :
              créer un créneau reviendrait à en choisir une au hasard. Le
              serveur refuse d'ailleurs la requête (403). */}
          {isAllAcademies ? (
            <span className="text-xs text-slate-500 self-center max-w-xs">
              {t("Sélectionnez une académie pour créer un créneau.")}
            </span>
          ) : (
            <button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />{t("Nouveau créneau")} — {academyLabel}</button>
          )}
        </div>
      </div>

      {/* Class filter */}
      <div className="card flex gap-2 items-center flex-wrap">
        <span className="text-sm font-medium text-slate-600">{t("Classe :")}</span>
        <button onClick={() => setClassFilter("")} className={clsx("px-3 py-1.5 rounded-xl text-xs font-medium", !classFilter ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>{t("Toutes")}</button>
        {classes.map(c => (
          <button key={c.id} onClick={() => setClassFilter(c.id.toString())}
            className={clsx("px-3 py-1.5 rounded-xl text-xs font-medium", classFilter === c.id.toString() ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>
            {c.name}
          </button>
        ))}
      </div>

      {/* GRID VIEW — days as columns */}
      {view === "grid" ? (
        isLoading ? <div className="skeleton h-64 rounded-2xl" /> : (
          <div className="card overflow-x-auto">
            <div className="min-w-[700px]">
              <div className={`grid grid-cols-${Math.min(daySchedules.filter(d => d.items.length).length + 1, 7)} gap-0`}
                style={{ gridTemplateColumns: `80px repeat(${DAYS.length}, 1fr)` }}>
                {/* Header row */}
                <div className="bg-slate-50 border border-slate-200 p-2 text-xs font-bold text-slate-500 text-center">{t("Horaire")}</div>
                {DAYS.map(day => (
                  <div key={day} className="bg-primary-50 border border-slate-200 p-2 text-xs font-bold text-primary text-center">{t(day)}</div>
                ))}
                {/* Rows by time */}
                {timeSlots.map(slot => {
                  const [start, end] = slot.split("-");
                  return [
                    <div key={`label-${slot}`} className="bg-slate-50 border border-slate-100 p-2 text-xs text-slate-500 text-center font-mono">{start}<br/>{end}</div>,
                    ...DAYS.map((_, di) => {
                      const items = schedules.filter(s => s.day_of_week === di && s.start_time?.slice(0,5) === start);
                      return (
                        <div key={`${slot}-${di}`} className="border border-slate-100 p-1 min-h-[60px]">
                          {items.map((item, ii) => {
                            const ci = subjectMap[item.subject_name] ?? ii;
                            return (
                              <div key={item.id} onClick={() => openEdit(item)}
                                className={clsx("rounded-lg px-2 py-1.5 text-xs cursor-pointer hover:opacity-80 mb-1 border", COLORS[ci % COLORS.length])}>
                                {isAllAcademies && (
                                  <p className="truncate font-semibold opacity-90">
                                    [{item.academy_short_name || item.academy_code}]
                                  </p>
                                )}
                                <p className="font-bold truncate">{item.subject_name}</p>
                                <p className="opacity-75 truncate">{item.class_name}</p>
                                {item.room && <p className="opacity-60 truncate">🚪 {item.room}</p>}
                                {item.teacher_name && <p className="opacity-60 truncate">👤 {item.teacher_name}</p>}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })
                  ];
                })}
              </div>
              {timeSlots.length === 0 && <div className="text-center py-12 text-slate-400"><CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" /><p>{t("Aucun créneau défini.")}</p></div>}
            </div>
          </div>
        )
      ) : (
        /* LIST VIEW */
        <div className="card">
          <div className="divide-y divide-slate-50">
            {schedules.length === 0 ? <div className="text-center py-12 text-slate-400">{t("Aucun créneau")}</div> :
              schedules.map(item => (
                <div key={item.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary-50 flex items-center justify-center text-primary text-xs font-bold">{item.day_label?.slice(0,2)}</div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                        {/* En mode consolidé, deux académies coexistent dans
                            la même liste : sans étiquette, rien ne dit à
                            laquelle une ligne appartient. */}
                        {isAllAcademies && (
                          <AcademyBadge code={item.academy_code} name={item.academy_name} />
                        )}
                        <span>{item.subject_name} — {item.class_name}</span>
                      </p>
                      <p className="text-xs text-slate-400">{item.start_time?.slice(0,5)}–{item.end_time?.slice(0,5)} {item.room ? `• 🚪 ${item.room}` : ""} {item.teacher_name ? `• 👤 ${item.teacher_name}` : ""}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => openEdit(item)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => setDeleteItem(item)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier le créneau") : t("Nouveau créneau")} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {!editItem && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="label">{t("Classe*")}</label>
                  <Controller name="cls" control={control} rules={{ required: true }}
                    render={({ field }) => <SearchableSelect options={classOptions} value={field.value} onChange={field.onChange} placeholder={t("Sélectionner une classe…")} />} />
                </div>
                <div><label className="label">{t("Matière*")}</label>
                  <Controller name="subject" control={control} rules={{ required: true }}
                    render={({ field }) => <SearchableSelect options={subjectOptions} value={field.value} onChange={field.onChange} placeholder={t("Sélectionner une matière…")} />} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="label">{t("Enseignant")}</label>
                  <Controller name="teacher" control={control}
                    render={({ field }) => <SearchableSelect options={teacherOptions} value={field.value} onChange={field.onChange} placeholder={t("Sélectionner un enseignant…")} />} />
                </div>
                <div><label className="label">{t("Année scolaire*")}</label>
                  <select {...register("school_year", { required: true })} className="input">
                    <option value="">-- Sélectionner --</option>
                    {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
                  </select>
                </div>
              </div>
            </>
          )}
          <div><label className="label">{t("Jour*")}</label>
            <select {...register("day_of_week", { required: true })} className="input">
              {DAYS.map((d,i) => <option key={i} value={i}>{d}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">{t("Heure début*")}</label><input {...register("start_time", { required: true })} type="time" className="input" /></div>
            <div><label className="label">{t("Heure fin*")}</label><input {...register("end_time", { required: true })} type="time" className="input" /></div>
          </div>
          <div>
            <label className="label">{t("Salle")}</label>
            <Controller name="room" control={control}
            render={({ field }) => <SearchableSelect options={roomOptions} value={field.value} onChange={field.onChange} placeholder={t("Sélectionner une salle…")} />} />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">{t("Enregistrer")}</button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)} onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending} message={t("Supprimer ce créneau ?")} />
    </div>
  );
}