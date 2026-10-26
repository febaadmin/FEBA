/**
 * Académies — création et configuration par le super administrateur.
 *
 * Le TYPE choisi à la création (en ligne, physique primaire, physique
 * secondaire) fixe les niveaux initiaux, leurs cycles (donc le barème /10
 * ou /20 des bulletins) et les fonctionnalités. Tout est initialisé par le
 * serveur (apps/schools/academy_setup.py) : cet écran n'invente rien et
 * n'affiche un succès qu'après la réponse du serveur.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, Pencil, Plus, Power, ListChecks, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

export const ACADEMY_TYPES = [
  {
    value: "online",
    label: "Académie en ligne",
    detail: "Cours à distance (comme FEBA FHA) : tests de placement, cours et devoirs en ligne. "
      + "Les groupes sont à créer selon le programme.",
    timezone: "America/New_York", currency: "USD", language: "en",
  },
  {
    value: "physical_primary",
    label: "Académie physique — primaire",
    detail: "Maternelle 1 et 2, CI, CP, CE1, CE2, CM1, CM2 créés. Bulletins sur 10.",
    timezone: "Africa/Porto-Novo", currency: "XOF", language: "fr",
  },
  {
    value: "physical_secondary",
    label: "Académie physique — secondaire (collège et lycée)",
    detail: "6ème à 3ème (collège) et Seconde à Terminale (lycée) créés. Bulletins sur 20.",
    timezone: "Africa/Porto-Novo", currency: "XOF", language: "fr",
  },
];
const typeLabel = (value) => ACADEMY_TYPES.find((x) => x.value === value)?.label;

const EMPTY = {
  academy_type: "", name: "", legal_name: "", code: "", address: "", city: "", country: "",
  phone: "", email: "", timezone: "Africa/Porto-Novo", currency_code: "XOF",
  default_language: "fr", school_year_name: "", school_year_start: "", school_year_end: "",
};

function suggestCode(name) {
  return name.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 32);
}

function fieldErrors(error) {
  const data = error?.response?.data;
  return data && typeof data === "object" ? data : {};
}

function Field({ label, error, children }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {error && <span className="block text-danger text-xs mt-1">{Array.isArray(error) ? error[0] : String(error)}</span>}
    </label>
  );
}

function SetupChecklist({ status }) {
  if (!status) return null;
  return (
    <ul className="space-y-2" data-testid="setup-checklist">
      {status.checks.map((c) => (
        <li key={c.key} className="flex items-start gap-2 text-sm">
          {c.done
            ? <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
            : <Circle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />}
          <span>
            <span className={c.done ? "text-slate-700" : "text-slate-900 font-medium"}>{t(c.label)}</span>
            {!c.done && c.action && <span className="block text-xs text-slate-500">{t(c.action)}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function SuperAdminAcademies() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [codeTouched, setCodeTouched] = useState(false);
  const [created, setCreated] = useState(null);
  const [editItem, setEditItem] = useState(null);
  const [statusFor, setStatusFor] = useState(null);
  const [toggleItem, setToggleItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);

  const { data, isLoading, isError } = useQuery({ queryKey: ["academies"], queryFn: schoolsAPI.list });
  const academies = data?.data?.results || data?.data || [];

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["academies"] });
    qc.invalidateQueries({ queryKey: ["schools"] });
    qc.invalidateQueries({ queryKey: ["entity-context"] });
  };

  const createMut = useMutation({
    mutationFn: (payload) => schoolsAPI.createAcademy(payload),
    onSuccess: (resp) => {
      refresh();
      setCreated(resp.data);
      toast.success(t("Académie créée et initialisée."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data: payload }) => schoolsAPI.update(id, payload),
    onSuccess: () => { refresh(); setEditItem(null); setToggleItem(null); toast.success(t("Académie mise à jour.")); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: (id) => schoolsAPI.deleteAcademy(id),
    onSuccess: () => { refresh(); setDeleteItem(null); toast.success(t("Académie supprimée.")); },
    onError: (e) => { setDeleteItem(null); toast.error(extractApiError(e)); },
  });
  const statusQuery = useQuery({
    queryKey: ["academy-setup", statusFor?.id],
    queryFn: () => schoolsAPI.setupStatus(statusFor.id),
    enabled: Boolean(statusFor),
  });

  const set = (key, value) => setForm((f) => {
    const next = { ...f, [key]: value };
    if (key === "name" && !codeTouched) next.code = suggestCode(value);
    return next;
  });
  const chooseType = (type) => setForm((f) => ({
    ...f, academy_type: type.value, timezone: type.timezone,
    currency_code: type.currency, default_language: type.language,
  }));
  const openCreate = () => {
    setForm(EMPTY); setCodeTouched(false); setCreated(null); createMut.reset(); setCreateOpen(true);
  };
  const submitCreate = (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ""));
    createMut.mutate(payload);
  };
  const errors = fieldErrors(createMut.error);
  const editErrors = fieldErrors(updateMut.error);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Académies")}
        subtitle={t("Créez et configurez les académies de la plateforme. Chaque académie est isolée des autres.")}
        action={
          <button onClick={openCreate} className="btn-primary flex items-center gap-2" data-testid="academy-create">
            <Plus className="w-4 h-4" />{t("Nouvelle académie")}
          </button>
        }
      />

      <div className="card overflow-x-auto">
        {isLoading ? (
          <div className="py-12 text-center text-slate-400">{t("Chargement…")}</div>
        ) : isError ? (
          <div className="py-12 text-center text-danger">{t("Impossible de charger les académies.")}</div>
        ) : (
          <table className="w-full text-sm" data-testid="academies-table">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="py-3 px-4">{t("Académie")}</th>
                <th className="py-3 px-4">{t("Code")}</th>
                <th className="py-3 px-4">{t("Type")}</th>
                <th className="py-3 px-4">{t("Élèves")}</th>
                <th className="py-3 px-4">{t("Statut")}</th>
                <th className="py-3 px-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {academies.map((a) => (
                <tr key={a.id} data-testid={`academy-row-${a.code}`}>
                  <td className="py-3 px-4">
                    <div className="font-semibold text-slate-800">{a.name}</div>
                    <div className="text-xs text-slate-500">{[a.city, a.country].filter(Boolean).join(", ")}</div>
                  </td>
                  <td className="py-3 px-4 font-mono text-xs">{a.code || "—"}</td>
                  <td className="py-3 px-4">
                    {a.academy_type ? (
                      <span>{t(typeLabel(a.academy_type))}</span>
                    ) : (
                      <span className="text-amber-700" title={a.classification?.reason || ""}>
                        {t("Non classée")}
                        {a.classification?.reason && (
                          <span className="block text-xs text-slate-500 max-w-xs">{a.classification.reason}</span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4">{a.students_count ?? "—"}</td>
                  <td className="py-3 px-4">
                    <span className={a.is_active ? "text-emerald-700" : "text-slate-500"}>
                      {a.is_active ? t("Active") : t("Désactivée")}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => setStatusFor(a)} title={t("Configuration restante")}
                              className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-500"><ListChecks className="w-4 h-4" /></button>
                      <button onClick={() => { updateMut.reset(); setEditItem({ ...a }); }} title={t("Modifier")}
                              className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-500"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => setToggleItem(a)} title={a.is_active ? t("Désactiver") : t("Réactiver")}
                              className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-500"><Power className="w-4 h-4" /></button>
                      <button onClick={() => setDeleteItem(a)} title={t("Supprimer")}
                              className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-500"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Création ───────────────────────────────────────────────── */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} size="lg"
             title={created ? t("Académie créée") : t("Nouvelle académie")}>
        {created ? (
          <div className="space-y-4" data-testid="academy-created">
            <p className="text-sm">
              <strong>{created.name}</strong> ({created.code}) — {t(typeLabel(created.academy_type))}.
            </p>
            <p className="text-sm text-slate-600">
              {t("Sélectionnez cette académie dans le sélecteur d'académie pour terminer sa configuration :")}
            </p>
            <SetupChecklist status={created.setup_status} />
            <div className="flex justify-end">
              <button className="btn-primary" onClick={() => setCreateOpen(false)}>{t("Fermer")}</button>
            </div>
          </div>
        ) : (
          <form onSubmit={submitCreate} className="space-y-5">
            <fieldset>
              <legend className="label">{t("Type d'académie*")}</legend>
              <div className="grid sm:grid-cols-3 gap-3">
                {ACADEMY_TYPES.map((type) => (
                  <button type="button" key={type.value} onClick={() => chooseType(type)}
                          data-testid={`academy-type-${type.value}`}
                          className={`text-left rounded-xl border p-3 transition ${form.academy_type === type.value
                            ? "border-primary bg-primary-50 ring-2 ring-primary/30" : "border-slate-200 hover:border-primary/40"}`}>
                    <span className="block font-semibold text-sm text-slate-800">{t(type.label)}</span>
                    <span className="block text-xs text-slate-500 mt-1">{t(type.detail)}</span>
                  </button>
                ))}
              </div>
              {errors.academy_type && <p className="text-danger text-xs mt-1">{String(errors.academy_type)}</p>}
            </fieldset>

            <div className="grid sm:grid-cols-2 gap-4">
              <Field label={t("Nom de l'académie*")} error={errors.name}>
                <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} data-testid="academy-name" />
              </Field>
              <Field label={t("Code interne* (définitif)")} error={errors.code}>
                <input className="input font-mono" value={form.code} data-testid="academy-code"
                       onChange={(e) => { setCodeTouched(true); set("code", e.target.value.toUpperCase()); }} />
              </Field>
              <Field label={t("Dénomination légale")} error={errors.legal_name}>
                <input className="input" value={form.legal_name} onChange={(e) => set("legal_name", e.target.value)} />
              </Field>
              <Field label={t("Adresse*")} error={errors.address}>
                <input className="input" value={form.address} onChange={(e) => set("address", e.target.value)} data-testid="academy-address" />
              </Field>
              <Field label={t("Ville")} error={errors.city}>
                <input className="input" value={form.city} onChange={(e) => set("city", e.target.value)} />
              </Field>
              <Field label={t("Pays")} error={errors.country}>
                <input className="input" value={form.country} onChange={(e) => set("country", e.target.value)} />
              </Field>
              <Field label={t("Téléphone")} error={errors.phone}>
                <input className="input" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
              </Field>
              <Field label={t("E-mail")} error={errors.email}>
                <input className="input" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
              </Field>
              <Field label={t("Fuseau horaire")} error={errors.timezone}>
                <input className="input" value={form.timezone} onChange={(e) => set("timezone", e.target.value)} />
              </Field>
              <Field label={t("Devise")} error={errors.currency_code}>
                <select className="input" value={form.currency_code} onChange={(e) => set("currency_code", e.target.value)}>
                  <option value="XOF">XOF — Franc CFA</option>
                  <option value="USD">USD — Dollar</option>
                </select>
              </Field>
              <Field label={t("Langue des documents")} error={errors.default_language}>
                <select className="input" value={form.default_language} onChange={(e) => set("default_language", e.target.value)}>
                  <option value="fr">Français</option>
                  <option value="en">English</option>
                </select>
              </Field>
            </div>

            <fieldset className="rounded-xl border border-slate-200 p-4">
              <legend className="px-1 text-sm font-semibold text-slate-700">{t("Première année scolaire (facultatif)")}</legend>
              <div className="grid sm:grid-cols-3 gap-3">
                <Field label={t("Nom (ex. 2026-2027)")} error={errors.school_year_name || errors.school_year}>
                  <input className="input" value={form.school_year_name} onChange={(e) => set("school_year_name", e.target.value)} />
                </Field>
                <Field label={t("Début")} error={errors.school_year_start}>
                  <input className="input" type="date" value={form.school_year_start} onChange={(e) => set("school_year_start", e.target.value)} />
                </Field>
                <Field label={t("Fin")} error={errors.school_year_end}>
                  <input className="input" type="date" value={form.school_year_end} onChange={(e) => set("school_year_end", e.target.value)} />
                </Field>
              </div>
            </fieldset>

            <p className="text-xs text-slate-500">
              {t("Aucune donnée d'une autre académie n'est copiée : ni élèves, ni notes, ni paiements, ni logo.")}
            </p>
            <div className="flex justify-end gap-3">
              <button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>{t("Annuler")}</button>
              <button type="submit" className="btn-primary" disabled={createMut.isPending || !form.academy_type}
                      data-testid="academy-submit">
                {createMut.isPending ? t("Création…") : t("Créer l'académie")}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Modification ───────────────────────────────────────────── */}
      <Modal open={Boolean(editItem)} onClose={() => setEditItem(null)} size="lg" title={t("Modifier l'académie")}>
        {editItem && (
          <form className="space-y-4" onSubmit={(e) => {
            e.preventDefault();
            const payload = {};
            for (const key of ["name", "legal_name", "address", "city", "country", "phone", "email",
              "timezone", "currency_code", "default_language"]) payload[key] = editItem[key] ?? "";
            if (editItem.academy_type) payload.academy_type = editItem.academy_type;
            updateMut.mutate({ id: editItem.id, data: payload });
          }}>
            <p className="text-sm text-slate-600">{t("Code interne")} : <span className="font-mono">{editItem.code}</span> {t("(non modifiable)")}</p>
            <Field label={t("Type d'académie")} error={editErrors.academy_type}>
              <select className="input" value={editItem.academy_type || ""} data-testid="academy-edit-type"
                      onChange={(e) => setEditItem({ ...editItem, academy_type: e.target.value || null })}>
                {!editItem.academy_type && <option value="">{t("Non classée")}</option>}
                {ACADEMY_TYPES.map((type) => <option key={type.value} value={type.value}>{t(type.label)}</option>)}
              </select>
            </Field>
            <div className="grid sm:grid-cols-2 gap-4">
              {[["name", "Nom de l'académie*"], ["legal_name", "Dénomination légale"], ["address", "Adresse*"],
                ["city", "Ville"], ["country", "Pays"], ["phone", "Téléphone"], ["email", "E-mail"],
                ["timezone", "Fuseau horaire"]].map(([key, label]) => (
                <Field key={key} label={t(label)} error={editErrors[key]}>
                  <input className="input" value={editItem[key] || ""} onChange={(e) => setEditItem({ ...editItem, [key]: e.target.value })} />
                </Field>
              ))}
            </div>
            <div className="flex justify-end gap-3">
              <button type="button" className="btn-secondary" onClick={() => setEditItem(null)}>{t("Annuler")}</button>
              <button type="submit" className="btn-primary" disabled={updateMut.isPending}>
                {updateMut.isPending ? t("Enregistrement…") : t("Enregistrer")}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Configuration restante ─────────────────────────────────── */}
      <Modal open={Boolean(statusFor)} onClose={() => setStatusFor(null)} title={statusFor ? statusFor.name : ""}>
        {statusQuery.isLoading ? <p className="text-sm text-slate-400">{t("Chargement…")}</p>
          : statusQuery.isError ? <p className="text-sm text-danger">{extractApiError(statusQuery.error)}</p>
            : <SetupChecklist status={statusQuery.data?.data} />}
      </Modal>

      <ConfirmDialog
        open={Boolean(toggleItem)}
        onClose={() => setToggleItem(null)}
        loading={updateMut.isPending}
        onConfirm={() => updateMut.mutate({ id: toggleItem.id, data: { is_active: !toggleItem.is_active } })}
        message={toggleItem?.is_active
          ? t("Désactiver cette académie ? Ses utilisateurs ne pourront plus se connecter ; aucune donnée n'est supprimée.")
          : t("Réactiver cette académie ?")}
      />
      <ConfirmDialog
        open={Boolean(deleteItem)}
        onClose={() => setDeleteItem(null)}
        loading={deleteMut.isPending}
        onConfirm={() => deleteMut.mutate(deleteItem.id)}
        message={t("Supprimer définitivement cette académie ? Seule une académie vide (créée par erreur) peut l'être ; sinon, désactivez-la.")}
      />
    </div>
  );
}

