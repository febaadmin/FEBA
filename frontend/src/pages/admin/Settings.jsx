/**
 * Admin Settings — v14
 *
 * FIX: Types de salles DYNAMIQUES
 *  - Nouveau CRUD complet : créer / modifier / supprimer des types personnalisés
 *  - Le dropdown "Type" lors de la création d'une salle affiche :
 *      • les types statiques par défaut
 *      • TOUS les types dynamiques créés par l'admin
 *  - Persistance en base via /api/schools/room_types/
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { schoolsAPI, subjectsAPI, classesAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import DataTable from "../../components/ui/DataTable";
import { Save, Plus, Trash2, Check, Calendar, DoorOpen, Pencil, Tag } from "lucide-react";
import { extractApiError } from "../../utils/errors";

/** Types statiques par défaut (toujours présents dans le dropdown). */
const STATIC_ROOM_TYPES = [
  { value: "classroom", label: "Salle de classe" },
  { value: "computer",  label: "Salle informatique" },
  { value: "canteen",   label: "Cantine" },
  { value: "library",   label: "Bibliothèque" },
  { value: "sports",    label: "Salle de sport" },
  { value: "dance",     label: "Salle de danse" },
  { value: "admin",     label: "Bureau administratif" },
  { value: "other",     label: "Autre" },
];

export default function AdminSettings() {
  const qc = useQueryClient();

  // ── Modal states ──────────────────────────────────────────────────────────
  const [subjectModal, setSubjectModal]       = useState(false);
  const [yearModal, setYearModal]             = useState(false);
  const [editYear, setEditYear]               = useState(null);
  const [deleteYear, setDeleteYear]           = useState(null);
  const [roomModal, setRoomModal]             = useState(false);
  const [editRoom, setEditRoom]               = useState(null);
  const [deleteSubject, setDeleteSubject]     = useState(null);
  const [editSubject, setEditSubject]         = useState(null);
  const [deleteRoom, setDeleteRoom]           = useState(null);
  // Room-type management
  const [roomTypeModal, setRoomTypeModal]     = useState(false);
  const [editRoomType, setEditRoomType]       = useState(null);
  const [deleteRoomType, setDeleteRoomType]   = useState(null);

  // ── Forms ─────────────────────────────────────────────────────────────────
  const { register, handleSubmit, reset }                                   = useForm();
  const { register: rs, handleSubmit: hss, reset: rss }                    = useForm();
  const { register: redit, handleSubmit: hsedit, reset: rsedit }           = useForm();
  const { register: ry, handleSubmit: hsy, reset: rsy }                    = useForm();
  const { register: rr, handleSubmit: hsr, reset: rsr, watch: wrr }        = useForm({
    defaultValues: { room_type: "classroom", capacity: 30 },
  });
  const { register: rrt, handleSubmit: hsrt, reset: rsrt }                 = useForm();

  const roomTypeValue = wrr("room_type");

  // ── Queries ───────────────────────────────────────────────────────────────
  const { data: schoolData }    = useQuery({ queryKey: ["school"],            queryFn: schoolsAPI.list });
  const { data: subjectsData }  = useQuery({ queryKey: ["subjects-settings"], queryFn: () => subjectsAPI.list() });
  const { data: yearsData }     = useQuery({ queryKey: ["years"],             queryFn: schoolsAPI.years });
  const { data: classData }     = useQuery({ queryKey: ["classes"],           queryFn: () => classesAPI.list() });
  const { data: roomsData }     = useQuery({ queryKey: ["rooms"],             queryFn: () => schoolsAPI.rooms() });
  const { data: roomTypesData } = useQuery({ queryKey: ["room-types"],        queryFn: () => schoolsAPI.roomTypes() });

  const school       = schoolData?.data?.results?.[0]  || schoolData?.data?.[0];
  const subjects     = subjectsData?.data?.results     || subjectsData?.data     || [];
  const years        = yearsData?.data?.results        || yearsData?.data        || [];
  const classes      = classData?.data?.results        || classData?.data        || [];
  const rooms        = roomsData?.data?.results        || roomsData?.data        || [];
  const dynamicTypes = roomTypesData?.data?.results    || roomTypesData?.data    || [];

  // Merge static + dynamic types for the room dropdown
  const allRoomTypeOptions = [
    ...STATIC_ROOM_TYPES,
    ...dynamicTypes.map(dt => ({ value: `dynamic_${dt.id}`, label: dt.name, isDynamic: true, id: dt.id })),
  ];

  // Combine rooms + class-based rooms
  const classRooms = classes.map(c => ({
    id: `class-${c.id}`, name: c.name, room_type: "classroom",
    display_type: "Salle de classe", capacity: c.max_students, is_active: true, isClass: true,
  }));
  const allRooms = [...rooms, ...classRooms.filter(cr => !rooms.find(r => r.name === cr.name))];

  useEffect(() => {
    if (school) reset({
      name: school.name, address: school.address, city: school.city,
      phone: school.phone, email: school.email, description: school.description,
    });
  }, [school, reset]);

  // ── Mutations : École ──────────────────────────────────────────────────────
  const updateMut = useMutation({
    mutationFn: d => schoolsAPI.update(school.id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["school"] }); toast.success("École mise à jour !"); },
  });

  // ── Mutations : Matières ───────────────────────────────────────────────────
  const createSubjectMut = useMutation({
    mutationFn: subjectsAPI.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subjects-settings"] }); toast.success("Matière créée !"); setSubjectModal(false); rss(); },
  });
  const updateSubjectMut = useMutation({
    mutationFn: ({ id, data }) => subjectsAPI.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subjects-settings"] }); toast.success("Matière modifiée !"); setEditSubject(null); rsedit(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteSubjectMut = useMutation({
    mutationFn: subjectsAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subjects-settings"] }); toast.success("Supprimée."); setDeleteSubject(null); },
  });

  // ── Mutations : Années ─────────────────────────────────────────────────────
  const createYearMut = useMutation({
    mutationFn: schoolsAPI.createYear,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["years"] }); toast.success("Année créée !"); setYearModal(false); rsy(); },
    onError: (e) => {
      const detail = e.response?.data?.detail || e.response?.data?.non_field_errors?.[0]
        || JSON.stringify(e.response?.data) || "Erreur lors de la création.";
      toast.error(detail);
    },
  });
  const activateYearMut = useMutation({
    mutationFn: schoolsAPI.activateYear,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["years"] }); toast.success("Année activée !"); },
  });
  // BUG N°5 — CRUD complet : modification et suppression d'une année
  const updateYearMut = useMutation({
    mutationFn: ({ id, data }) => schoolsAPI.updateYear(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["years"] });
      toast.success("Année scolaire modifiée !");
      setYearModal(false); setEditYear(null); rsy();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteYearMut = useMutation({
    mutationFn: schoolsAPI.deleteYear,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["years"] });
      toast.success(d.data?.detail || "Année scolaire supprimée.");
      setDeleteYear(null);
    },
    onError: (e) => {
      toast.error(extractApiError(e));
      setDeleteYear(null);
    },
  });
  const closeYearMut = useMutation({
    mutationFn: schoolsAPI.closeYear,
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["years"] }); toast.success(d.data?.detail || "Année clôturée."); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  // ── Mutations : Types de salles dynamiques ─────────────────────────────────
  const createRoomTypeMut = useMutation({
    mutationFn: schoolsAPI.createRoomType,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["room-types"] });
      toast.success("Type de salle créé !");
      setRoomTypeModal(false);
      rsrt();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateRoomTypeMut = useMutation({
    mutationFn: ({ id, data }) => schoolsAPI.updateRoomType(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["room-types"] });
      toast.success("Type modifié !");
      setEditRoomType(null);
      rsrt();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteRoomTypeMut = useMutation({
    mutationFn: schoolsAPI.deleteRoomType,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["room-types"] });
      qc.invalidateQueries({ queryKey: ["rooms"] });
      toast.success("Type supprimé.");
      setDeleteRoomType(null);
    },
  });

  // ── Mutations : Salles ─────────────────────────────────────────────────────
  const createRoomMut = useMutation({
    mutationFn: schoolsAPI.createRoom,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rooms"] }); toast.success("Salle créée !"); setRoomModal(false); setEditRoom(null); rsr({ room_type: "classroom", capacity: 30 }); },
  });
  const updateRoomMut = useMutation({
    mutationFn: ({ id, data }) => schoolsAPI.updateRoom(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rooms"] }); toast.success("Salle modifiée !"); setRoomModal(false); setEditRoom(null); rsr({ room_type: "classroom", capacity: 30 }); },
  });
  const deleteRoomMut = useMutation({
    mutationFn: schoolsAPI.deleteRoom,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rooms"] }); toast.success("Supprimée."); setDeleteRoom(null); },
  });

  // ── Helpers salles ─────────────────────────────────────────────────────────
  const openCreateRoom = () => {
    setEditRoom(null);
    rsr({ room_type: "classroom", capacity: 30, is_active: true });
    setRoomModal(true);
  };
  const openEditRoom = (r) => {
    setEditRoom(r);
    // Determine if room was created with a dynamic type
    const dynamicVal = r.room_type_obj ? `dynamic_${r.room_type_obj}` : null;
    rsr({
      name: r.name,
      room_type: dynamicVal || r.room_type || "classroom",
      capacity: r.capacity,
      description: r.description,
      is_active: r.is_active,
    });
    setRoomModal(true);
  };
  const submitRoom = (d) => {
    const { room_type, ...rest } = d;
    let payload = { ...rest, school: school?.id };

    // Check if it's a dynamic type (prefixed with "dynamic_")
    if (room_type && room_type.startsWith("dynamic_")) {
      const typeId = parseInt(room_type.replace("dynamic_", ""), 10);
      payload.room_type = "custom";
      payload.room_type_obj = typeId;
    } else {
      payload.room_type = room_type;
      payload.room_type_obj = null;
    }

    if (editRoom) updateRoomMut.mutate({ id: editRoom.id, data: payload });
    else createRoomMut.mutate(payload);
  };

  // ── Helpers types de salles ────────────────────────────────────────────────
  const openCreateRoomType = () => { setEditRoomType(null); rsrt(); setRoomTypeModal(true); };
  const openEditRoomType = (rt) => { setEditRoomType(rt); rsrt({ name: rt.name }); setRoomTypeModal(true); };
  const submitRoomType = (d) => {
    const payload = { ...d, school: school?.id };
    if (editRoomType) updateRoomTypeMut.mutate({ id: editRoomType.id, data: payload });
    else createRoomTypeMut.mutate(payload);
  };

  // ── Column defs ────────────────────────────────────────────────────────────
  const roomCols = [
    { key: "name",     label: "Nom",      accessor: "name" },
    { key: "type",     label: "Type",     render: r => r.display_type || r.room_type_label || r.room_type || "—" },
    { key: "capacity", label: "Capacité", accessor: "capacity" },
    {
      key: "status", label: "Statut",
      render: r => (
        <span className={`badge ${r.is_active ? "bg-success-50 text-success" : "bg-slate-100 text-slate-500"}`}>
          {r.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
  ];

  const roomTypeCols = [
    { key: "name", label: "Nom du type", accessor: "name" },
    {
      key: "rooms_count", label: "Salles associées",
      render: rt => {
        const count = rooms.filter(r => r.room_type_obj === rt.id).length;
        return <span className="text-slate-500 text-xs">{count} salle(s)</span>;
      },
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Paramètres" subtitle="Configuration de l'établissement" />

      {/* École */}
      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-4">Informations de l'École</h3>
        <form onSubmit={handleSubmit(d => updateMut.mutate(d))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Nom*</label><input {...register("name", { required: true })} className="input" /></div>
            <div><label className="label">Ville</label><input {...register("city")} className="input" /></div>
          </div>
          <div><label className="label">Adresse</label><textarea {...register("address")} className="input" rows={2} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Téléphone</label><input {...register("phone")} className="input" /></div>
            <div><label className="label">Email</label><input {...register("email")} type="email" className="input" /></div>
          </div>
          <div className="flex justify-end">
            <button type="submit" disabled={updateMut.isPending} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />Enregistrer
            </button>
          </div>
        </form>
      </div>

      {/* ── Types de salles personnalisés ─────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800 flex items-center gap-2">
            <Tag className="w-4 h-4 text-primary" />
            Types de salles personnalisés ({dynamicTypes.length})
          </h3>
          <button onClick={openCreateRoomType} className="btn-primary text-sm flex items-center gap-1">
            <Plus className="w-4 h-4" />Nouveau type
          </button>
        </div>
        {dynamicTypes.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">
            <Tag className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p>Aucun type personnalisé.</p>
            <p className="text-xs mt-1">Créez des types comme "Salle de jeux", "Salle de couture", "Laboratoire"…</p>
          </div>
        ) : (
          <DataTable
            columns={roomTypeCols}
            data={dynamicTypes}
            actions={rt => (
              <div className="flex items-center gap-1 justify-end">
                <button onClick={() => openEditRoomType(rt)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                  <Pencil className="w-4 h-4" />
                </button>
                <button onClick={() => setDeleteRoomType(rt)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
          />
        )}
      </div>

      {/* Salles */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800 flex items-center gap-2">
            <DoorOpen className="w-4 h-4 text-primary" />
            Salles physiques de l'École ({allRooms.length})
          </h3>
          <button onClick={openCreateRoom} className="btn-primary text-sm flex items-center gap-1">
            <Plus className="w-4 h-4" />Nouvelle salle
          </button>
        </div>
        <DataTable
          columns={roomCols}
          data={allRooms}
          actions={row => !row.isClass ? (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={() => openEditRoom(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                <Pencil className="w-4 h-4" />
              </button>
              <button onClick={() => setDeleteRoom(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ) : <span className="text-xs text-slate-400 italic">Salle de classe</span>}
        />
      </div>

      {/* Années scolaires */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800 flex items-center gap-2">
            <Calendar className="w-4 h-4" />Années Scolaires
          </h3>
          <button onClick={() => { setEditYear(null); rsy({ name: "", start_date: "", end_date: "" }); setYearModal(true); }}
            className="btn-primary text-sm flex items-center gap-1">
            <Plus className="w-4 h-4" />Nouvelle année
          </button>
        </div>
        <div className="space-y-2">
          {years.map(y => (
            <div key={y.id} className="flex items-center justify-between py-2 px-3 bg-slate-50 rounded-xl">
              <div>
                <p className="text-sm font-medium text-slate-800">{y.name}</p>
                <p className="text-xs text-slate-400">{y.start_date} → {y.end_date}</p>
              </div>
              <div className="flex items-center gap-2">
                {/* BUG N°5 — Modifier */}
                <button
                  onClick={() => {
                    setEditYear(y);
                    rsy({ name: y.name, start_date: y.start_date, end_date: y.end_date });
                    setYearModal(true);
                  }}
                  title="Modifier cette année"
                  className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                  <Pencil className="w-4 h-4" />
                </button>
                {/* BUG N°5 — Supprimer (interdit sur l'année active) */}
                <button
                  onClick={() => y.is_current
                    ? toast.error("L'année active ne peut pas être supprimée. Clôturez-la d'abord.")
                    : setDeleteYear(y)}
                  title={y.is_current ? "Année active : suppression impossible" : "Supprimer cette année"}
                  className={`p-1.5 rounded-lg ${y.is_current
                    ? "text-slate-200 cursor-not-allowed"
                    : "hover:bg-danger-50 text-slate-400 hover:text-danger"}`}>
                  <Trash2 className="w-4 h-4" />
                </button>
                {y.is_current ? (
                  <span className="flex items-center gap-2">
                    <span className="badge bg-success-50 text-success flex items-center gap-1">
                      <Check className="w-3 h-3" />En cours
                    </span>
                    <button onClick={() => closeYearMut.mutate(y.id)} title="Clôturer cette année"
                      className="btn-secondary text-xs py-1 px-2">Clôturer</button>
                  </span>
                ) : (
                  <button onClick={() => activateYearMut.mutate(y.id)} className="btn-secondary text-xs py-1 px-2">Activer</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Matières */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800">Matières ({subjects.length})</h3>
          <button onClick={() => setSubjectModal(true)} className="btn-primary text-sm flex items-center gap-1">
            <Plus className="w-4 h-4" />Ajouter
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {subjects.map(s => (
            <div key={s.id} className="flex items-center justify-between py-2 px-3 bg-slate-50 rounded-xl">
              <div>
                <p className="text-sm font-medium text-slate-800">{s.name}</p>
                <p className="text-xs text-slate-400">
                  Code: {s.code} | Coeff: {s.coefficient} |{" "}
                  <span className={`font-medium ${s.language === "fr" ? "text-blue-600" : s.language === "en" ? "text-green-600" : "text-purple-600"}`}>
                    {s.language === "fr" ? "🇫🇷 Français" : s.language === "en" ? "🇬🇧 Anglais" : "🌐 Bilingue"}
                  </span>
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => { setEditSubject(s); rsedit({ name: s.name, code: s.code, coefficient: s.coefficient, language: s.language || "fr" }); }} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => setDeleteSubject(s)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Modal : Type de salle ──────────────────────────────────────────── */}
      <Modal
        open={roomTypeModal}
        onClose={() => { setRoomTypeModal(false); setEditRoomType(null); rsrt(); }}
        title={editRoomType ? "Modifier le type de salle" : "Nouveau type de salle"}
        size="sm"
      >
        <form onSubmit={hsrt(submitRoomType)} className="space-y-4">
          <div>
            <label className="label">Nom du type *</label>
            <input
              {...rrt("name", { required: true })}
              className="input"
              placeholder="Ex: Salle de jeux, Salle de couture, Laboratoire…"
            />
            <p className="text-xs text-slate-400 mt-1">
              Ce type sera disponible dans le menu déroulant lors de la création de salles.
            </p>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => { setRoomTypeModal(false); setEditRoomType(null); rsrt(); }} className="btn-secondary">
              Annuler
            </button>
            <button
              type="submit"
              disabled={createRoomTypeMut.isPending || updateRoomTypeMut.isPending}
              className="btn-primary"
            >
              {editRoomType ? "Modifier" : "Créer"}
            </button>
          </div>
        </form>
      </Modal>

      {/* ── Modal : Salle ─────────────────────────────────────────────────── */}
      <Modal
        open={roomModal}
        onClose={() => { setRoomModal(false); setEditRoom(null); rsr({ room_type: "classroom", capacity: 30 }); }}
        title={editRoom ? "Modifier la salle" : "Nouvelle salle"}
      >
        <form onSubmit={hsr(submitRoom)} className="space-y-4">
          <div>
            <label className="label">Nom de la salle *</label>
            <input {...rr("name", { required: true })} placeholder="ex: Salle Informatique A" className="input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Type *</label>
              <select {...rr("room_type", { required: true })} className="input">
                <optgroup label="Types standards">
                  {STATIC_ROOM_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </optgroup>
                {dynamicTypes.length > 0 && (
                  <optgroup label="Types personnalisés">
                    {dynamicTypes.map(dt => (
                      <option key={`dynamic_${dt.id}`} value={`dynamic_${dt.id}`}>{dt.name}</option>
                    ))}
                  </optgroup>
                )}
              </select>
              {dynamicTypes.length === 0 && (
                <p className="text-xs text-slate-400 mt-1">
                  Aucun type personnalisé. Créez-en dans la section "Types de salles personnalisés" ci-dessus.
                </p>
              )}
            </div>
            <div>
              <label className="label">Capacité</label>
              <input {...rr("capacity")} type="number" min="1" className="input" />
            </div>
          </div>
          <div>
            <label className="label">Description</label>
            <textarea {...rr("description")} className="input" rows={2} />
          </div>
          <div className="flex items-center gap-2">
            <input {...rr("is_active")} type="checkbox" id="ra" className="w-4 h-4 accent-primary" defaultChecked />
            <label htmlFor="ra" className="text-sm font-medium text-slate-700">Salle active</label>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => { setRoomModal(false); setEditRoom(null); }} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createRoomMut.isPending || updateRoomMut.isPending} className="btn-primary">Enregistrer</button>
          </div>
        </form>
      </Modal>

      {/* ── Modal : Matière ───────────────────────────────────────────────── */}
      <Modal open={subjectModal} onClose={() => { setSubjectModal(false); rss(); }} title="Nouvelle matière">
        <form onSubmit={hss(d => createSubjectMut.mutate({ ...d, school: school?.id }))} className="space-y-4">
          <div><label className="label">Nom *</label><input {...rs("name", { required: true })} className="input" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Code *</label><input {...rs("code", { required: true })} className="input" /></div>
            <div><label className="label">Coefficient *</label><input {...rs("coefficient", { required: true })} type="number" min={1} max={10} className="input" /></div>
          </div>
          <div>
            <label className="label">Catégorie de matière *</label>
            <select {...rs("language", { required: true })} className="input">
              <option value="fr">🇫🇷 Française (Moyenne FR)</option>
              <option value="en">🇬🇧 Anglaise (Moyenne EN)</option>
              <option value="bilingual">🌐 Bilingue (FR + EN)</option>
            </select>
            <p className="text-xs text-slate-400 mt-1">Détermine dans quelle moyenne la matière est comptabilisée.</p>
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => { setSubjectModal(false); rss(); }} className="btn-secondary">Annuler</button>
            <button type="submit" className="btn-primary">Créer</button>
          </div>
        </form>
      </Modal>

      {/* ── Modal : Modifier matière ──────────────────────────────────────── */}
      <Modal open={!!editSubject} onClose={() => { setEditSubject(null); rsedit(); }} title="Modifier la matière">
        <form onSubmit={hsedit(d => updateSubjectMut.mutate({ id: editSubject.id, data: d }))} className="space-y-4">
          <div><label className="label">Nom *</label><input {...redit("name", { required: true })} className="input" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Code</label><input {...redit("code")} className="input" /></div>
            <div><label className="label">Coefficient</label><input {...redit("coefficient")} type="number" min="1" className="input" /></div>
          </div>
          <div>
            <label className="label">Catégorie de matière *</label>
            <select {...redit("language", { required: true })} className="input">
              <option value="fr">🇫🇷 Française (Moyenne FR)</option>
              <option value="en">🇬🇧 Anglaise (Moyenne EN)</option>
              <option value="bilingual">🌐 Bilingue (FR + EN)</option>
            </select>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => { setEditSubject(null); rsedit(); }} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={updateSubjectMut.isPending} className="btn-primary">Modifier</button>
          </div>
        </form>
      </Modal>

      {/* ── Modal : Année scolaire (création + modification — BUG N°5) ───── */}
      <Modal
        open={yearModal}
        onClose={() => { setYearModal(false); setEditYear(null); rsy(); }}
        title={editYear ? `Modifier l'année ${editYear.name}` : "Nouvelle année scolaire"}
      >
        <form
          onSubmit={hsy(d => editYear
            ? updateYearMut.mutate({ id: editYear.id, data: d })
            : createYearMut.mutate({ ...d, school: school?.id }))}
          className="space-y-4"
        >
          <div><label className="label">Nom *</label><input {...ry("name", { required: true })} placeholder="ex: 2025-2026" className="input" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Début *</label><input {...ry("start_date", { required: true })} type="date" className="input" /></div>
            <div><label className="label">Fin *</label><input {...ry("end_date", { required: true })} type="date" className="input" /></div>
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => { setYearModal(false); setEditYear(null); rsy(); }} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createYearMut.isPending || updateYearMut.isPending} className="btn-primary">
              {editYear
                ? (updateYearMut.isPending ? "Modification…" : "Modifier")
                : (createYearMut.isPending ? "Création…" : "Créer")}
            </button>
          </div>
        </form>
      </Modal>

      {/* ── Confirm dialogs ───────────────────────────────────────────────── */}
      <ConfirmDialog
        open={!!deleteRoomType}
        onClose={() => setDeleteRoomType(null)}
        onConfirm={() => deleteRoomTypeMut.mutate(deleteRoomType?.id)}
        loading={deleteRoomTypeMut.isPending}
        message={`Supprimer le type "${deleteRoomType?.name}" ? Les salles utilisant ce type seront mises à jour.`}
      />
      <ConfirmDialog
        open={!!deleteYear}
        onClose={() => setDeleteYear(null)}
        onConfirm={() => deleteYearMut.mutate(deleteYear?.id)}
        loading={deleteYearMut.isPending}
        message={`Supprimer définitivement l'année scolaire "${deleteYear?.name}" ? Cette action est impossible si l'année contient des inscriptions, classes, notes ou paiements.`}
      />
      <ConfirmDialog
        open={!!deleteSubject}
        onClose={() => setDeleteSubject(null)}
        onConfirm={() => deleteSubjectMut.mutate(deleteSubject?.id)}
        loading={deleteSubjectMut.isPending}
        message={`Supprimer "${deleteSubject?.name}" ?`}
      />
      <ConfirmDialog
        open={!!deleteRoom}
        onClose={() => setDeleteRoom(null)}
        onConfirm={() => deleteRoomMut.mutate(deleteRoom?.id)}
        loading={deleteRoomMut.isPending}
        message={`Supprimer la salle "${deleteRoom?.name}" ?`}
      />
    </div>
  );
}
