import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Video, Users, CalendarClock, StopCircle } from "lucide-react";
import { useForm } from "react-hook-form";
import { format } from "date-fns";
import { fr, enGB } from "date-fns/locale";
import toast from "react-hot-toast";
import { virtualAPI, classesAPI, subjectsAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import JitsiMeeting from "../../components/JitsiMeeting";
import { extractApiError } from "../../utils/errors";
import { t, getLang } from "../../i18n";
import JitsiInfrastructureBanner from "../../components/JitsiInfrastructureBanner";

const STATUS_STYLE = {
  scheduled: "bg-blue-50 text-blue-600",
  live: "bg-emerald-50 text-emerald-600",
  ended: "bg-slate-100 text-slate-500",
  cancelled: "bg-red-50 text-red-500",
};
const STATUS_LABEL = {
  scheduled: "Planifiée",
  live: "En cours",
  ended: "Terminée",
  cancelled: "Annulée",
};

/**
 * Page « Salles virtuelles » partagée par tous les rôles.
 * Les enseignants et administrateurs peuvent créer / modifier / clôturer ;
 * élèves et parents voient uniquement les salles de leur périmètre et
 * peuvent les rejoindre.
 */
export default function VirtualRooms() {
  const qc = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const canManage = ["superadmin", "admin", "teacher"].includes(user?.role);

  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [activeMeeting, setActiveMeeting] = useState(null); // {room_code, join_domain, name}

  const { register, handleSubmit, reset, formState: { errors } } = useForm();

  const { data: roomsData, isLoading } = useQuery({
    queryKey: ["virtual-rooms"],
    queryFn: () => virtualAPI.list(),
    refetchInterval: 30000,
  });
  const { data: classesData } = useQuery({
    queryKey: ["classes"],
    queryFn: () => classesAPI.list(),
    enabled: canManage,
  });
  const { data: subjectsData } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => subjectsAPI.list(),
    enabled: canManage,
  });

  const rooms = roomsData?.data?.results || roomsData?.data || [];
  const classes = classesData?.data?.results || classesData?.data || [];
  const subjects = subjectsData?.data?.results || subjectsData?.data || [];

  const sortedRooms = useMemo(() => {
    const rank = { live: 0, scheduled: 1, ended: 2, cancelled: 3 };
    return [...rooms].sort((a, b) => (rank[a.status] ?? 9) - (rank[b.status] ?? 9));
  }, [rooms]);

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => { reset({ duration_minutes: 60 }); setModalOpen(true); };
  const openEdit = (r) => {
    setEditItem(r);
    reset({
      name: r.name,
      description: r.description,
      class_obj: r.class_obj || "",
      subject: r.subject || "",
      scheduled_at: r.scheduled_at ? r.scheduled_at.slice(0, 16) : "",
      duration_minutes: r.duration_minutes,
    });
    setModalOpen(true);
  };

  const normalize = (d) => ({
    ...d,
    class_obj: d.class_obj || null,
    subject: d.subject || null,
    scheduled_at: d.scheduled_at || null,
  });

  const createMut = useMutation({
    mutationFn: (d) => virtualAPI.create(normalize(d)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["virtual-rooms"] }); toast.success(t("Salle créée !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => virtualAPI.update(id, normalize(data)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["virtual-rooms"] }); toast.success(t("Salle modifiée !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: virtualAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["virtual-rooms"] }); toast.success(t("Salle supprimée.")); setDeleteItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const joinMut = useMutation({
    mutationFn: virtualAPI.join,
    onSuccess: ({ data }) => {
      qc.invalidateQueries({ queryKey: ["virtual-rooms"] });
      setActiveMeeting(data);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const endMut = useMutation({
    mutationFn: virtualAPI.end,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["virtual-rooms"] }); toast.success(t("Réunion clôturée.")); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: d });
    else createMut.mutate(d);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Salles virtuelles")}
        subtitle={t("Visioconférence intégrée (Jitsi Meet) — cours en ligne, réunions parents-professeurs…")}
        action={canManage && (
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />{t("Nouvelle salle")}</button>
        )}
      />

      {/* État réel de l'infrastructure de visioconférence auto-hébergée.
          Remplace l'ancienne bannière « mode démonstration » : il n'existe
          plus d'instance publique de repli, donc plus rien à signaler
          lorsque tout fonctionne. */}
      <JitsiInfrastructureBanner />

      <div className="card">
        {isLoading ? (
          <div className="py-12 text-center text-slate-400">{t("Chargement…")}</div>
        ) : sortedRooms.length === 0 ? (
          <div className="py-16 text-center text-slate-400">
            <Video className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">{t("Aucune salle virtuelle")}</p>
            <p className="text-sm mt-1">
              {canManage
                ? t("Créez une salle pour organiser un cours en ligne ou une réunion.") : t("Aucune réunion n'est planifiée pour le moment.")}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Salle")}</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Classe / Matière")}</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Planification")}</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Statut")}</th>
                  <th className="py-3 px-4 w-48" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {sortedRooms.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-800">{r.name}</div>
                      {r.description && <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">{r.description}</div>}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      <div>{r.class_name || "Toute l'école"}</div>
                      {r.subject_name && <div className="text-xs text-slate-400">{r.subject_name}</div>}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {r.scheduled_at ? (
                        <span className="inline-flex items-center gap-1.5">
                          <CalendarClock className="w-3.5 h-3.5 text-slate-400" />
                          {format(new Date(r.scheduled_at), "dd MMM yyyy HH:mm", { locale: getLang() === "en" ? enGB : fr })}
                          <span className="text-xs text-slate-400">· {r.duration_minutes} min</span>
                        </span>
                      ) : (
                        <span className="text-slate-400">{t("Permanente")}</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[r.status] || ""}`}>
                        {STATUS_LABEL[r.status] || r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1 justify-end">
                        {r.status !== "ended" && r.status !== "cancelled" && (
                          <button
                            onClick={() => joinMut.mutate(r.id)}
                            disabled={joinMut.isPending}
                            className="btn-primary flex items-center gap-1.5 !py-1.5 !px-3 text-xs"
                          >
                            <Video className="w-3.5 h-3.5" />{t("Rejoindre")}</button>
                        )}
                        {canManage && r.status === "live" && (
                          <button
                            onClick={() => endMut.mutate(r.id)}
                            title={t("Clôturer la réunion")}
                            className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-400 hover:text-amber-600"
                          >
                            <StopCircle className="w-4 h-4" />
                          </button>
                        )}
                        {canManage && (
                          <>
                            <button onClick={() => openEdit(r)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                              <Pencil className="w-4 h-4" />
                            </button>
                            <button onClick={() => setDeleteItem(r)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                      {canManage && r.participants_count > 0 && (
                        <div className="flex items-center gap-1 justify-end mt-1 text-xs text-slate-400">
                          <Users className="w-3 h-3" />{r.participants_count} participant(s)
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {canManage && (
        <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier la salle") : t("Nouvelle salle virtuelle")}>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="label">{t("Nom de la salle*")}</label>
              <input {...register("name", { required: true })} placeholder={t("ex: Cours de Mathématiques — 6ème A")} className="input" />
              {errors.name && <p className="text-danger text-xs mt-1">{t("Requis")}</p>}
            </div>
            <div>
              <label className="label">{t("Description")}</label>
              <textarea {...register("description")} rows={2} className="input" placeholder={t("Ordre du jour, consignes…")} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">{t("Classe")}</label>
                <select {...register("class_obj")} className="input">
                  <option value="">{t("Toute l'école")}</option>
                  {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">{t("Matière")}</label>
                <select {...register("subject")} className="input">
                  <option value="">—</option>
                  {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">{t("Date / heure (vide = permanente)")}</label>
                <input {...register("scheduled_at")} type="datetime-local" className="input" />
              </div>
              <div>
                <label className="label">{t("Durée (minutes)")}</label>
                <input {...register("duration_minutes", { valueAsNumber: true })} type="number" min="5" className="input" />
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
      )}

      <ConfirmDialog
        open={!!deleteItem}
        onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)}
        loading={deleteMut.isPending}
        message={`Supprimer la salle "${deleteItem?.name}" ? L'historique des participations sera perdu.`}
      />

      {activeMeeting && (
        <JitsiMeeting
          roomName={activeMeeting.room_code}
          domain={activeMeeting.join_domain}
          displayName={user ? `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.username : ""}
          subject={activeMeeting.name}
          jwt={activeMeeting.jwt || null}
          onClose={() => {
            // FIX v35 : clôture de la participation (left_at + durée)
            virtualAPI.leave(activeMeeting.id).catch(() => {});
            setActiveMeeting(null);
          }}
        />
      )}
    </div>
  );
}
