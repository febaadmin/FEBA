/**
 * Formulaires publics du site vitrine : contact et préinscription.
 * Validation frontend (react-hook-form) doublée par la validation backend ;
 * honeypot anti-spam (champ « website » caché) ; messages de succès/erreur.
 */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { CheckCircle2, Loader2, Send } from "lucide-react";
import { siteAPI } from "../siteApi";

const LEVELS = [
  ["garderie", "Garderie"], ["maternelle1", "Maternelle 1"], ["maternelle2", "Maternelle 2"],
  ["ci", "CI"], ["cp", "CP"], ["ce1", "CE1"], ["ce2", "CE2"],
  ["cm1", "CM1"], ["cm2", "CM2"], ["feba_online", "FEBA Online"],
];

const inputCls = (err) =>
  `w-full px-4 py-2.5 rounded-xl border bg-white text-sm outline-none transition focus:ring-2 focus:ring-feba-gold/60 focus:border-feba-gold ${
    err ? "border-red-400" : "border-feba-navy/15"
  }`;

function FieldError({ error }) {
  if (!error) return null;
  return <p className="mt-1 text-xs text-red-600" role="alert">{error.message}</p>;
}

function extractErrors(e) {
  const data = e?.response?.data;
  if (!data) return ["Une erreur est survenue. Veuillez réessayer."];
  if (typeof data === "string") return [data];
  const msgs = [];
  Object.values(data).forEach((v) => {
    if (Array.isArray(v)) msgs.push(...v.map(String));
    else msgs.push(String(v));
  });
  return msgs.length ? msgs : ["Une erreur est survenue. Veuillez réessayer."];
}

/* Champ honeypot : invisible pour les humains, rempli par les robots. */
function Honeypot({ register }) {
  return (
    <div className="absolute -left-[9999px] top-auto" aria-hidden="true">
      <label htmlFor="hp-website">Ne pas remplir ce champ</label>
      <input id="hp-website" type="text" tabIndex={-1} autoComplete="off"
        {...register("website")} />
    </div>
  );
}

function SuccessBox({ message, onReset, resetLabel }) {
  return (
    <div className="rounded-2xl bg-feba-green/10 border border-feba-green/30 p-6 text-center">
      <CheckCircle2 className="w-10 h-10 text-feba-green mx-auto mb-3" />
      <p className="text-feba-navy font-semibold">{message}</p>
      <button onClick={onReset} className="mt-4 text-sm text-feba-green font-semibold hover:underline">
        {resetLabel}
      </button>
    </div>
  );
}

export function ContactForm() {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm();
  const [success, setSuccess] = useState("");
  const [apiErrors, setApiErrors] = useState([]);

  const onSubmit = async (d) => {
    setApiErrors([]);
    try {
      const resp = await siteAPI.sendContact(d);
      setSuccess(resp.data?.detail || "Message envoyé.");
      reset();
    } catch (e) {
      setApiErrors(extractErrors(e));
    }
  };

  if (success) {
    return <SuccessBox message={success} onReset={() => setSuccess("")}
      resetLabel="Envoyer un autre message" />;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="relative space-y-4" noValidate>
      <Honeypot register={register} />
      {apiErrors.length > 0 && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1" role="alert">
          {apiErrors.map((m, i) => <p key={i} className="text-sm text-red-700">{m}</p>)}
        </div>
      )}
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="ct-name" className="block text-sm font-semibold text-feba-navy mb-1.5">Nom complet *</label>
          <input id="ct-name" {...register("name", { required: "Votre nom est obligatoire." })}
            className={inputCls(errors.name)} autoComplete="name" />
          <FieldError error={errors.name} />
        </div>
        <div>
          <label htmlFor="ct-email" className="block text-sm font-semibold text-feba-navy mb-1.5">Email *</label>
          <input id="ct-email" type="email"
            {...register("email", {
              required: "Votre email est obligatoire.",
              pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: "Format d'email invalide." },
            })}
            className={inputCls(errors.email)} autoComplete="email" />
          <FieldError error={errors.email} />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="ct-phone" className="block text-sm font-semibold text-feba-navy mb-1.5">Téléphone</label>
          <input id="ct-phone" {...register("phone")} className={inputCls()} autoComplete="tel"
            placeholder="+229 ..." />
        </div>
        <div>
          <label htmlFor="ct-subject" className="block text-sm font-semibold text-feba-navy mb-1.5">Sujet *</label>
          <input id="ct-subject" {...register("subject", { required: "Le sujet est obligatoire." })}
            className={inputCls(errors.subject)} />
          <FieldError error={errors.subject} />
        </div>
      </div>
      <div>
        <label htmlFor="ct-message" className="block text-sm font-semibold text-feba-navy mb-1.5">Message *</label>
        <textarea id="ct-message" rows={5}
          {...register("message", { required: "Le message est obligatoire." })}
          className={inputCls(errors.message)} />
        <FieldError error={errors.message} />
      </div>
      <label className="flex items-start gap-2.5 text-xs text-feba-gray cursor-pointer">
        <input type="checkbox" {...register("consent", { required: "Votre consentement est requis." })}
          className="mt-0.5 rounded border-feba-navy/30" />
        <span>J'accepte que mes informations soient utilisées pour répondre à ma demande. *</span>
      </label>
      <FieldError error={errors.consent} />
      <button type="submit" disabled={isSubmitting}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy2 transition-colors disabled:opacity-60">
        {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        {isSubmitting ? "Envoi en cours…" : "Envoyer le message"}
      </button>
    </form>
  );
}

export function PreRegistrationForm() {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm();
  const [success, setSuccess] = useState("");
  const [apiErrors, setApiErrors] = useState([]);

  const onSubmit = async (d) => {
    setApiErrors([]);
    try {
      const payload = { ...d, child_age: d.child_age ? Number(d.child_age) : null };
      const resp = await siteAPI.sendPreRegistration(payload);
      setSuccess(resp.data?.detail || "Demande enregistrée.");
      reset();
    } catch (e) {
      setApiErrors(extractErrors(e));
    }
  };

  if (success) {
    return <SuccessBox message={success} onReset={() => setSuccess("")}
      resetLabel="Faire une autre demande" />;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="relative space-y-4" noValidate>
      <Honeypot register={register} />
      {apiErrors.length > 0 && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1" role="alert">
          {apiErrors.map((m, i) => <p key={i} className="text-sm text-red-700">{m}</p>)}
        </div>
      )}
      <p className="text-feba-navy font-bold text-sm uppercase tracking-wide">Le parent</p>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-parent" className="block text-sm font-semibold text-feba-navy mb-1.5">Nom du parent *</label>
          <input id="pr-parent" {...register("parent_name", { required: "Le nom du parent est obligatoire." })}
            className={inputCls(errors.parent_name)} autoComplete="name" />
          <FieldError error={errors.parent_name} />
        </div>
        <div>
          <label htmlFor="pr-phone" className="block text-sm font-semibold text-feba-navy mb-1.5">Téléphone *</label>
          <input id="pr-phone" {...register("phone", { required: "Le téléphone est obligatoire." })}
            className={inputCls(errors.phone)} autoComplete="tel" placeholder="+229 ..." />
          <FieldError error={errors.phone} />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-whatsapp" className="block text-sm font-semibold text-feba-navy mb-1.5">WhatsApp</label>
          <input id="pr-whatsapp" {...register("whatsapp")} className={inputCls()} placeholder="+229 ..." />
        </div>
        <div>
          <label htmlFor="pr-email" className="block text-sm font-semibold text-feba-navy mb-1.5">Email</label>
          <input id="pr-email" type="email" {...register("email")} className={inputCls()} autoComplete="email" />
        </div>
      </div>
      <p className="text-feba-navy font-bold text-sm uppercase tracking-wide pt-2">L'enfant</p>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-child" className="block text-sm font-semibold text-feba-navy mb-1.5">Nom de l'enfant *</label>
          <input id="pr-child" {...register("child_name", { required: "Le nom de l'enfant est obligatoire." })}
            className={inputCls(errors.child_name)} />
          <FieldError error={errors.child_name} />
        </div>
        <div>
          <label htmlFor="pr-age" className="block text-sm font-semibold text-feba-navy mb-1.5">Âge</label>
          <input id="pr-age" type="number" min="1" max="18"
            {...register("child_age", { min: { value: 1, message: "Âge invalide." }, max: { value: 18, message: "Âge invalide." } })}
            className={inputCls(errors.child_age)} />
          <FieldError error={errors.child_age} />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-level" className="block text-sm font-semibold text-feba-navy mb-1.5">Niveau souhaité *</label>
          <select id="pr-level" {...register("desired_level", { required: "Le niveau souhaité est obligatoire." })}
            className={inputCls(errors.desired_level)} defaultValue="">
            <option value="" disabled>— Choisir un niveau —</option>
            {LEVELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <FieldError error={errors.desired_level} />
        </div>
        <div>
          <label htmlFor="pr-year" className="block text-sm font-semibold text-feba-navy mb-1.5">Année scolaire</label>
          <input id="pr-year" {...register("school_year")} className={inputCls()} placeholder="2026-2027" />
        </div>
      </div>
      <div>
        <label htmlFor="pr-message" className="block text-sm font-semibold text-feba-navy mb-1.5">Message</label>
        <textarea id="pr-message" rows={4} {...register("message")} className={inputCls()} />
      </div>
      <button type="submit" disabled={isSubmitting}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:bg-feba-gold2 transition-colors disabled:opacity-60">
        {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        {isSubmitting ? "Envoi en cours…" : "Envoyer ma demande de préinscription"}
      </button>
    </form>
  );
}
