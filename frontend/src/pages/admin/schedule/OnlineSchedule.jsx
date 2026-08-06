/**
 * OnlineSchedule — emploi du temps FEBA French Heritage Academy.
 *
 * MÉTIER DIFFÉRENT DE CELUI DE FEBA (P3)
 * --------------------------------------
 * Une séance FEBA FHA n'a pas de salle physique à réserver : elle a un
 * groupe en ligne, une salle virtuelle et — surtout — des participants
 * répartis sur plusieurs fuseaux horaires. L'heure de référence est donc
 * stockée en UTC : « 17 h » n'est pas une information suffisante quand une
 * famille est à Philadelphie, une autre à Vancouver et l'enseignant à
 * Cotonou.
 *
 * L'écran affiche systématiquement les DEUX heures — UTC et heure locale de
 * référence — parce qu'afficher l'une sans l'autre a produit exactement le
 * malentendu que ce module corrige. Le jour local est affiché quand il
 * diffère du jour UTC : une séance à 00 h 30 UTC le mardi a lieu le lundi
 * soir aux États-Unis.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { Bell, BellOff, CalendarDays, Globe2, Pencil, Plus, Trash2, Video } from "lucide-react";
import {
  onlineSessionsAPI, classesAPI, schoolsAPI, subjectsAPI, teachersAPI, virtualAPI,
} from "../../../api";
import Modal from "../../../components/ui/Modal";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import SearchableSelect from "../../../components/ui/SearchableSelect";
import AcademyBadge from "../../../components/AcademyBadge";
import { useAcademy } from "../../../context/AcademyContext";
import { t } from "../../../i18n";
import { clsx } from "clsx";

/* FEBA FHA planifie aussi le week-end : les familles de la diaspora sont
   disponibles le samedi et le dimanche, contrairement au campus. */
const DAYS = [
  "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
];

/** Fuseaux proposés : ceux des familles cibles, plus celui des enseignants. */
const TIMEZONES = [
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Toronto", "America/Vancouver", "Europe/Paris", "Africa/Porto-Novo", "UTC",
];

/* Même palette que CampusSchedule — parité visuelle, pas seulement fonctionnelle. */
const COLORS = ["bg-primary-50 border-primary/20 text-primary","bg-emerald-50 border-emerald-200 text-emerald-700","bg-amber-50 border-amber-200 text-amber-700","bg-rose-50 border-rose-200 text-rose-700","bg-sky-50 border-sky-200 text-sky-700","bg-violet-50 border-violet-200 text-violet-700"];

function unwrap(response) {
  return response?.data?.results || response?.data || [];
}

export default function OnlineSchedule() {
  const qc = useQueryClient();
  const { activeAcademy, isAllAcademies } = useAcademy();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [groupFilter, setGroupFilter] = useState("");
  // P2 — Parité avec CampusSchedule : même bascule Grille/Liste, même
  // valeur par défaut. FEBA FHA n'avait qu'un tableau — une capacité en
  // moins par rapport à FEBA, ce que la demande interdit explicitement.
  const [view, setView] = useState("grid"); // "grid" | "list"
  const { register, handleSubmit, reset, control, watch } = useForm();

  const { data, isLoading, error } = useQuery({
    queryKey: ["online-sessions", groupFilter],
    queryFn: () => onlineSessionsAPI.list(groupFilter ? { group: groupFilter } : {}),
    retry: false,
  });
  const { data: groupData } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const { data: subjectData } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: yearData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const { data: teacherData } = useQuery({ queryKey: ["teachers-all"], queryFn: () => teachersAPI.list() });
  const { data: roomData } = useQuery({ queryKey: ["virtual-rooms"], queryFn: () => virtualAPI.list(), retry: false });

  const sessions = unwrap(data);
  const groups = unwrap(groupData);
  const subjects = unwrap(subjectData);
  const years = unwrap(yearData);
  const teachers = unwrap(teacherData);
  const rooms = unwrap(roomData);
  const currentYear = years.find((y) => y.is_current);

  const groupOptions = groups.map((g) => ({ value: g.id, label: g.name }));
  const subjectOptions = subjects.map((s) => ({ value: s.id, label: s.name }));
  const teacherOptions = teachers.map((tc) => ({
    value: tc.id,
    label: `${tc.user_first_name || ""} ${tc.user_last_name || ""}`.trim() || tc.user_email,
  }));
  const roomOptions = rooms.map((r) => ({ value: r.id, label: r.name }));

  const invalidate = () => qc.invalidateQueries({ queryKey: ["online-sessions"] });
  const failure = (e) => {
    // Le serveur explique POURQUOI (relation inter-académies, conflit
    // d'enseignant, académie non active) : afficher « Erreur serveur »
    // priverait l'utilisateur de la seule information utile.
    const detail = e?.response?.data;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.detail || Object.values(detail || {}).flat().join(" ") || t("Erreur serveur");
    toast.error(message);
  };

  const createMut = useMutation({
    mutationFn: onlineSessionsAPI.create,
    onSuccess: () => { invalidate(); toast.success(t("Séance planifiée.")); closeModal(); },
    onError: failure,
  });
  const updateMut = useMutation({
    mutationFn: ({ id, payload }) => onlineSessionsAPI.update(id, payload),
    onSuccess: () => { invalidate(); toast.success(t("Séance modifiée.")); closeModal(); },
    onError: failure,
  });
  const deleteMut = useMutation({
    mutationFn: onlineSessionsAPI.delete,
    onSuccess: () => { invalidate(); toast.success(t("Séance supprimée.")); setDeleteItem(null); },
    onError: failure,
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => {
    reset({
      day_of_week: 0,
      duration_minutes: 60,
      display_timezone: activeAcademy?.timezone || "America/New_York",
      school_year: currentYear?.id || "",
      reminders_enabled: true,
      reminder_minutes_before: 30,
      is_active: true,
    });
    setModalOpen(true);
  };
  const openEdit = (session) => {
    setEditItem(session);
    reset({
      group: session.group, subject: session.subject, teacher: session.teacher || "",
      school_year: session.school_year, virtual_room: session.virtual_room || "",
      day_of_week: session.day_of_week,
      start_time_utc: session.start_time_utc?.slice(0, 5),
      duration_minutes: session.duration_minutes,
      display_timezone: session.display_timezone,
      reminders_enabled: session.reminders_enabled,
      reminder_minutes_before: session.reminder_minutes_before,
      is_active: session.is_active,
      notes: session.notes || "",
    });
    setModalOpen(true);
  };

  const onSubmit = (values) => {
    const payload = {
      ...values,
      teacher: values.teacher || null,
      virtual_room: values.virtual_room || null,
      duration_minutes: Number(values.duration_minutes),
      reminder_minutes_before: Number(values.reminder_minutes_before),
      day_of_week: Number(values.day_of_week),
    };
    if (editItem) updateMut.mutate({ id: editItem.id, payload });
    else createMut.mutate(payload);
  };

  const remindersOn = watch("reminders_enabled");

  // ── Vue grille : mêmes principes que CampusSchedule ──────────────────
  // Axes en UTC (jour, heure) : c'est la référence sans ambiguïté d'une
  // séance. L'heure locale reste visible dans chaque case, pas dans l'axe
  // — un axe en heure locale déplacerait les séances de colonne selon le
  // fuseau choisi, ce qui rendrait la grille instable à l'affichage.
  const gridTimeSlots = [...new Set(
    sessions.map((s) => `${s.start_time_utc?.slice(0, 5)}-${s.end_time_utc}`),
  )].sort();
  const groupColorMap = {};
  sessions.forEach((s, i) => { if (s.group_name) groupColorMap[s.group_name] = i % COLORS.length; });

  // Le serveur refuse cet endpoint aux académies présentielles (403). Le
  // dire clairement vaut mieux qu'un tableau vide qui laisse croire à une
  // absence de données.
  if (error?.response?.status === 403) {
    return (
      <div className="card text-sm text-slate-600">
        <p className="font-semibold text-slate-800">
          {t("Les séances en ligne n'existent pas pour cette académie.")}
        </p>
        <p className="mt-1">
          {t(
            "FEBA Cotonou est une école présentielle : ses cours se planifient dans l'onglet FEBA, avec une classe et une salle physique.",
          )}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">{t("{n} séance(s) en direct", { n: sessions.length })}</p>
        <div className="flex gap-2">
          {/* P2 — Parité avec CampusSchedule : même bascule, même styles. */}
          <div className="flex rounded-xl border border-slate-200 overflow-hidden">
            <button onClick={() => setView("grid")}
              className={clsx("px-3 py-1.5 text-xs font-medium", view === "grid" ? "bg-primary text-white" : "bg-white text-slate-600")}>
              {t("Grille")}
            </button>
            <button onClick={() => setView("list")}
              className={clsx("px-3 py-1.5 text-xs font-medium border-l", view === "list" ? "bg-primary text-white" : "bg-white text-slate-600")}>
              {t("Liste")}
            </button>
          </div>
          {isAllAcademies ? (
            <span className="text-xs text-slate-500 self-center max-w-xs">
              {t("Sélectionnez FEBA FHA pour planifier une séance.")}
            </span>
          ) : (
            <button onClick={openCreate} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />{t("Nouvelle séance")} — {activeAcademy?.short_name || "FEBA FHA"}
            </button>
          )}
        </div>
      </div>

      {/* Filtre par groupe en ligne */}
      <div className="card flex gap-2 items-center flex-wrap">
        <span className="text-sm font-medium text-slate-600">{t("Groupe :")}</span>
        <button onClick={() => setGroupFilter("")}
          className={clsx("px-3 py-1.5 rounded-xl text-xs font-medium", !groupFilter ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>
          {t("Tous")}
        </button>
        {groups.map((g) => (
          <button key={g.id} onClick={() => setGroupFilter(String(g.id))}
            className={clsx("px-3 py-1.5 rounded-xl text-xs font-medium", groupFilter === String(g.id) ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>
            {g.name}
          </button>
        ))}
      </div>

      {view === "grid" ? (
        /* VUE GRILLE — mêmes principes visuels que CampusSchedule : jours en
           colonnes, créneaux horaires en lignes. FEBA FHA planifie aussi le
           week-end (voir DAYS ci-dessus), donc la grille compte 7 colonnes
           au lieu des 6 de FEBA — la seule différence structurelle, dictée
           par le métier, pas par un oubli d'implémentation. */
        isLoading ? <div className="skeleton h-64 rounded-2xl" /> : (
          <div className="card overflow-x-auto">
            <div className="min-w-[900px]">
              <div className="grid gap-0" style={{ gridTemplateColumns: `90px repeat(${DAYS.length}, 1fr)` }}>
                <div className="bg-slate-50 border border-slate-200 p-2 text-xs font-bold text-slate-500 text-center">
                  {t("Horaire (UTC)")}
                </div>
                {DAYS.map((day) => (
                  <div key={day} className="bg-primary-50 border border-slate-200 p-2 text-xs font-bold text-primary text-center">
                    {t(day)}
                  </div>
                ))}
                {gridTimeSlots.map((slot) => {
                  const [start] = slot.split("-");
                  return [
                    <div key={`label-${slot}`} className="bg-slate-50 border border-slate-100 p-2 text-xs text-slate-500 text-center font-mono">
                      {start}
                    </div>,
                    ...DAYS.map((_, di) => {
                      const items = sessions.filter(
                        (s) => s.day_of_week === di && s.start_time_utc?.slice(0, 5) === start,
                      );
                      return (
                        <div key={`${slot}-${di}`} className="border border-slate-100 p-1 min-h-[64px]">
                          {items.map((item) => {
                            const ci = groupColorMap[item.group_name] ?? 0;
                            return (
                              <div key={item.id} onClick={() => openEdit(item)}
                                className={clsx("rounded-lg px-2 py-1.5 text-xs cursor-pointer hover:opacity-80 mb-1 border", COLORS[ci % COLORS.length], !item.is_active && "opacity-40")}>
                                {isAllAcademies && (
                                  <p className="truncate font-semibold opacity-90">
                                    [{item.academy_code}]
                                  </p>
                                )}
                                <p className="font-bold truncate">{item.group_name}</p>
                                <p className="opacity-75 truncate">{item.subject_name}</p>
                                <p className="opacity-60 truncate">🌐 {item.local_start_label} ({item.display_timezone})</p>
                                {item.teacher_name && <p className="opacity-60 truncate">👤 {item.teacher_name}</p>}
                              </div>
                            );
                          })}
                        </div>
                      );
                    }),
                  ];
                })}
              </div>
              {gridTimeSlots.length === 0 && (
                <div className="text-center py-12 text-slate-400">
                  <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>{t("Aucune séance en direct planifiée.")}</p>
                </div>
              )}
            </div>
          </div>
        )
      ) : isLoading ? (
        <div className="skeleton h-64 rounded-2xl" />
      ) : sessions.length === 0 ? (
        <div className="card text-center py-12 text-slate-400">
          <Globe2 className="w-12 h-12 mx-auto mb-3 opacity-30" aria-hidden="true" />
          <p>{t("Aucune séance en direct planifiée.")}</p>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                {isAllAcademies && <th className="py-2 pr-3">{t("Académie")}</th>}
                <th className="py-2 pr-3">{t("Groupe")}</th>
                <th className="py-2 pr-3">{t("Matière")}</th>
                <th className="py-2 pr-3">{t("Jour (UTC)")}</th>
                <th className="py-2 pr-3">{t("Heure UTC")}</th>
                <th className="py-2 pr-3">{t("Heure locale")}</th>
                <th className="py-2 pr-3">{t("Enseignant")}</th>
                <th className="py-2 pr-3">{t("Salle virtuelle")}</th>
                <th className="py-2 pr-3">{t("Rappel")}</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {sessions.map((s) => (
                <tr key={s.id} className={clsx(!s.is_active && "opacity-50")}>
                  {isAllAcademies && (
                    <td className="py-3 pr-3">
                      <AcademyBadge code={s.academy_code} name={s.academy_name} />
                    </td>
                  )}
                  <td className="py-3 pr-3 font-semibold text-slate-800">{s.group_name}</td>
                  <td className="py-3 pr-3 text-slate-600">{s.subject_name}</td>
                  <td className="py-3 pr-3 text-slate-600">{s.day_label}</td>
                  <td className="py-3 pr-3 font-mono text-xs text-slate-700">
                    {s.start_time_utc?.slice(0, 5)}–{s.end_time_utc}
                  </td>
                  <td className="py-3 pr-3 text-slate-600">
                    <span className="font-mono text-xs">{s.local_start_label}</span>
                    <span className="block text-[11px] text-slate-400">
                      {s.display_timezone}
                      {/* Le jour local n'est signalé QUE s'il diffère : le
                          répéter partout noierait l'information utile. */}
                      {s.local_day_label && s.local_day_label !== s.day_label && (
                        <strong className="ml-1 text-amber-600">{s.local_day_label}</strong>
                      )}
                    </span>
                  </td>
                  <td className="py-3 pr-3 text-slate-600">{s.teacher_name || "—"}</td>
                  <td className="py-3 pr-3 text-slate-600">
                    {s.virtual_room_name ? (
                      <span className="inline-flex items-center gap-1">
                        <Video className="w-3.5 h-3.5 text-primary" aria-hidden="true" />
                        {s.virtual_room_name}
                      </span>
                    ) : (
                      <span className="text-amber-600 text-xs">{t("À rattacher")}</span>
                    )}
                  </td>
                  <td className="py-3 pr-3 text-slate-600">
                    {s.reminders_enabled ? (
                      <span className="inline-flex items-center gap-1 text-xs">
                        <Bell className="w-3.5 h-3.5" aria-hidden="true" />
                        {t("{n} min avant", { n: s.reminder_minutes_before })}
                      </span>
                    ) : (
                      <BellOff className="w-3.5 h-3.5 text-slate-300" aria-hidden="true" />
                    )}
                  </td>
                  <td className="py-3 text-right whitespace-nowrap">
                    <button onClick={() => openEdit(s)} aria-label={t("Modifier")}
                      className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => setDeleteItem(s)} aria-label={t("Supprimer")}
                      className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={modalOpen} onClose={closeModal} size="lg"
        title={editItem ? t("Modifier la séance en direct") : t("Nouvelle séance en direct")}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Groupe en ligne*")}</label>
              <Controller name="group" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect options={groupOptions} value={field.value} onChange={field.onChange}
                    placeholder={t("Sélectionner un groupe…")} />
                )} />
            </div>
            <div>
              <label className="label">{t("Matière*")}</label>
              <Controller name="subject" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect options={subjectOptions} value={field.value} onChange={field.onChange}
                    placeholder={t("Sélectionner une matière…")} />
                )} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Enseignant")}</label>
              <Controller name="teacher" control={control}
                render={({ field }) => (
                  <SearchableSelect options={teacherOptions} value={field.value} onChange={field.onChange}
                    placeholder={t("Sélectionner un enseignant…")} />
                )} />
            </div>
            <div>
              <label className="label">{t("Année scolaire*")}</label>
              <select {...register("school_year", { required: true })} className="input">
                <option value="">{t("-- Sélectionner --")}</option>
                {years.map((y) => (
                  <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 space-y-3">
            <p className="text-xs text-sky-900">
              {t(
                "L'heure est enregistrée en UTC. C'est la seule référence commune à des familles réparties entre les États-Unis, le Canada et le Bénin — et la seule qui reste juste au changement d'heure.",
              )}
            </p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="label">{t("Jour (UTC)*")}</label>
                <select {...register("day_of_week", { required: true })} className="input">
                  {DAYS.map((d, i) => <option key={d} value={i}>{t(d)}</option>)}
                </select>
              </div>
              <div>
                <label className="label">{t("Début (UTC)*")}</label>
                <input {...register("start_time_utc", { required: true })} type="time" className="input" />
              </div>
              <div>
                <label className="label">{t("Durée (min)*")}</label>
                <input {...register("duration_minutes", { required: true, min: 1, max: 480 })}
                  type="number" min="1" max="480" className="input" />
              </div>
            </div>
            <div>
              <label className="label">{t("Fuseau d'affichage de référence")}</label>
              <select {...register("display_timezone")} className="input">
                {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
              </select>
              <p className="mt-1 text-[11px] text-slate-500">
                {t("Sert uniquement à l'affichage : ne modifie pas l'heure réelle de la séance.")}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Salle virtuelle")}</label>
              <Controller name="virtual_room" control={control}
                render={({ field }) => (
                  <SearchableSelect options={roomOptions} value={field.value} onChange={field.onChange}
                    placeholder={t("Sélectionner une salle virtuelle…")} />
                )} />
              <p className="mt-1 text-[11px] text-slate-500">
                {t("Le lien de connexion est généré à la demande, pour chaque participant : aucun lien permanent n'est publié.")}
              </p>
            </div>
            <div className="space-y-2">
              <label className="label">{t("Rappel avant la séance")}</label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" {...register("reminders_enabled")} className="rounded" />
                {t("Envoyer un rappel aux familles")}
              </label>
              <input {...register("reminder_minutes_before", { min: 0, max: 1440 })}
                type="number" min="0" max="1440" disabled={!remindersOn}
                className="input disabled:bg-slate-100" placeholder="30" />
              <p className="text-[11px] text-slate-500">{t("Minutes avant le début (maximum 24 h).")}</p>
            </div>
          </div>

          <div>
            <label className="label">{t("Notes internes")}</label>
            <textarea {...register("notes")} rows="2" className="input" />
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" {...register("is_active")} className="rounded" />
            {t("Séance active")}
          </label>

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!deleteItem}
        onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)}
        loading={deleteMut.isPending}
        /* L'académie est nommée dans la confirmation : en mode consolidé,
           deux séances de deux académies peuvent porter le même libellé. */
        message={t(
          "Supprimer la séance « {subject} » du groupe {group} ({academy}) ?",
          {
            subject: deleteItem?.subject_name || "",
            group: deleteItem?.group_name || "",
            academy: deleteItem?.academy_short_name || deleteItem?.academy_name || "",
          },
        )}
      />
    </div>
  );
}
