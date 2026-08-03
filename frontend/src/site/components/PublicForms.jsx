/**
 * Formulaires publics du site vitrine : contact et préinscription.
 * Validation frontend (react-hook-form) doublée par la validation backend ;
 * honeypot anti-spam (champ « website » caché) ; messages de succès/erreur.
 */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { CheckCircle2, Loader2, Send } from "lucide-react";
import { siteAPI } from "../siteApi";
import { tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";

//: Borne haute du sélecteur de date de naissance. Un navigateur refuse
//: alors une date future avant même l'envoi ; le serveur la refuse aussi,
//: parce qu'une validation qui n'existe que dans le navigateur n'existe pas.
const TODAY = new Date().toISOString().slice(0, 10);

const LEVELS = [
  ["garderie", { fr: "Garderie", en: "Nursery" }],
  ["maternelle1", { fr: "Maternelle 1", en: "Kindergarten 1" }],
  ["maternelle2", { fr: "Maternelle 2", en: "Kindergarten 2" }],
  ["ci", { fr: "CI", en: "CI" }], ["cp", { fr: "CP", en: "CP" }],
  ["ce1", { fr: "CE1", en: "CE1" }], ["ce2", { fr: "CE2", en: "CE2" }],
  ["cm1", { fr: "CM1", en: "CM1" }], ["cm2", { fr: "CM2", en: "CM2" }],
  ["feba_online", { fr: "FEBA French Heritage Academy", en: "FEBA French Heritage Academy" }],
];

const inputCls = (err) =>
  `w-full px-4 py-2.5 rounded-xl border bg-white text-sm outline-none transition focus:ring-2 focus:ring-feba-gold/60 focus:border-feba-gold ${
    err ? "border-red-400" : "border-feba-navy/15"
  }`;

function FieldError({ error }) {
  if (!error) return null;
  return <p className="mt-1 text-xs text-red-600" role="alert">{error.message}</p>;
}

function extractErrors(e, fallback) {
  const data = e?.response?.data;
  if (!data) return [fallback];
  if (typeof data === "string") return [data];
  const msgs = [];
  Object.values(data).forEach((v) => {
    if (Array.isArray(v)) msgs.push(...v.map(String));
    else msgs.push(String(v));
  });
  return msgs.length ? msgs : [fallback];
}

/* Champ honeypot : invisible pour les humains, rempli par les robots. */
function Honeypot({ register, label }) {
  return (
    <div className="absolute -left-[9999px] top-auto" aria-hidden="true">
      <label htmlFor="hp-website">{label}</label>
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
  // P1 : les libellés, les messages de validation et les erreurs API de ces
  // formulaires restaient en français quel que soit le choix de langue.
  const { lang, t } = useSiteLang();
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm();
  const [success, setSuccess] = useState("");
  const [apiErrors, setApiErrors] = useState([]);

  const onSubmit = async (d) => {
    setApiErrors([]);
    try {
      const resp = await siteAPI.sendContact(d);
      setSuccess(resp.data?.detail || t("Message envoyé.", "Message sent."));
      reset();
    } catch (e) {
      setApiErrors(extractErrors(e, t(
        "Une erreur est survenue. Veuillez réessayer.",
        "Something went wrong. Please try again.",
      )));
    }
  };

  if (success) {
    return <SuccessBox message={success} onReset={() => setSuccess("")}
      resetLabel={t("Envoyer un autre message", "Send another message")} />;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="relative space-y-4" noValidate>
      <Honeypot register={register} label={t("Ne pas remplir ce champ", "Do not fill in this field")} />
      {apiErrors.length > 0 && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1" role="alert">
          {apiErrors.map((m, i) => <p key={i} className="text-sm text-red-700">{m}</p>)}
        </div>
      )}
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="ct-name" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Nom complet *", "Full name *")}
          </label>
          <input id="ct-name" {...register("name", { required: t("Votre nom est obligatoire.", "Your name is required.") })}
            className={inputCls(errors.name)} autoComplete="name" />
          <FieldError error={errors.name} />
        </div>
        <div>
          <label htmlFor="ct-email" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Email *", "Email *")}
          </label>
          <input id="ct-email" type="email"
            {...register("email", {
              required: t("Votre email est obligatoire.", "Your email is required."),
              pattern: {
                value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                message: t("Format d'email invalide.", "Invalid email format."),
              },
            })}
            className={inputCls(errors.email)} autoComplete="email" />
          <FieldError error={errors.email} />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="ct-phone" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Téléphone", "Phone")}
          </label>
          <input id="ct-phone" {...register("phone")} className={inputCls()} autoComplete="tel"
            placeholder="+229 ..." />
        </div>
        {/* P5 — WhatsApp est le canal de rappel le plus utilisé ici. Le
            formulaire FEBA ne le demandait pas ; les familles le
            recopiaient dans le message, où personne ne le cherchait. */}
        <div>
          <label htmlFor="ct-whatsapp" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("WhatsApp", "WhatsApp")}
          </label>
          <input id="ct-whatsapp" {...register("whatsapp")} className={inputCls()}
            placeholder="+229 ..." />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="sm:col-span-2">
          <label htmlFor="ct-subject" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Sujet *", "Subject *")}
          </label>
          <input id="ct-subject" {...register("subject", { required: t("Le sujet est obligatoire.", "The subject is required.") })}
            className={inputCls(errors.subject)} />
          <FieldError error={errors.subject} />
        </div>
      </div>
      <div>
        <label htmlFor="ct-message" className="block text-sm font-semibold text-feba-navy mb-1.5">
          {t("Message *", "Message *")}
        </label>
        <textarea id="ct-message" rows={5}
          {...register("message", { required: t("Le message est obligatoire.", "The message is required.") })}
          className={inputCls(errors.message)} />
        <FieldError error={errors.message} />
      </div>
      <label className="flex items-start gap-2.5 text-xs text-feba-gray cursor-pointer">
        <input type="checkbox" {...register("consent", { required: t("Votre consentement est requis.", "Your consent is required.") })}
          className="mt-0.5 rounded border-feba-navy/30" />
        <span>
          {t(
            "J'accepte que mes informations soient utilisées pour répondre à ma demande. *",
            "I agree that my information may be used to answer my request. *",
          )}
        </span>
      </label>
      <FieldError error={errors.consent} />
      <button type="submit" disabled={isSubmitting}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy2 transition-colors disabled:opacity-60">
        {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        {isSubmitting ? t("Envoi en cours…", "Sending…") : t("Envoyer le message", "Send the message")}
      </button>
    </form>
  );
}

export function PreRegistrationForm() {
  const { lang, t } = useSiteLang();
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm();
  const [success, setSuccess] = useState("");
  const [apiErrors, setApiErrors] = useState([]);

  const onSubmit = async (d) => {
    setApiErrors([]);
    try {
      const payload = { ...d, child_age: d.child_age ? Number(d.child_age) : null };
      const resp = await siteAPI.sendPreRegistration(payload);
      setSuccess(resp.data?.detail || t("Demande enregistrée.", "Request recorded."));
      reset();
    } catch (e) {
      setApiErrors(extractErrors(e, t(
        "Une erreur est survenue. Veuillez réessayer.",
        "Something went wrong. Please try again.",
      )));
    }
  };

  if (success) {
    return <SuccessBox message={success} onReset={() => setSuccess("")}
      resetLabel={t("Faire une autre demande", "Make another request")} />;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="relative space-y-4" noValidate>
      <Honeypot register={register} label={t("Ne pas remplir ce champ", "Do not fill in this field")} />
      {apiErrors.length > 0 && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1" role="alert">
          {apiErrors.map((m, i) => <p key={i} className="text-sm text-red-700">{m}</p>)}
        </div>
      )}
      <p className="text-feba-navy font-bold text-sm uppercase tracking-wide">
        {t("Le parent", "The parent")}
      </p>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-parent" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Nom du parent *", "Parent's name *")}
          </label>
          <input id="pr-parent" {...register("parent_name", { required: t("Le nom du parent est obligatoire.", "The parent's name is required.") })}
            className={inputCls(errors.parent_name)} autoComplete="name" />
          <FieldError error={errors.parent_name} />
        </div>
        <div>
          <label htmlFor="pr-phone" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Téléphone *", "Phone *")}
          </label>
          <input id="pr-phone" {...register("phone", { required: t("Le téléphone est obligatoire.", "The phone number is required.") })}
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
          <label htmlFor="pr-phone2" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Téléphone secondaire", "Secondary phone")}
          </label>
          <input id="pr-phone2" {...register("phone_secondary")} className={inputCls()}
            autoComplete="tel" placeholder="+229 ..." />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-email" className="block text-sm font-semibold text-feba-navy mb-1.5">{t("Email", "Email")}</label>
          <input id="pr-email" type="email" {...register("email")} className={inputCls()} autoComplete="email" />
        </div>
        <div>
          <label htmlFor="pr-address" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Adresse du domicile", "Home address")}
          </label>
          {/* Zone de saisie multiligne : une adresse à Cotonou tient
              rarement sur une ligne, et la découper en champs séparés
              ferait perdre les repères que la famille donne d'elle-même
              (« carrefour … », « derrière … »). */}
          <textarea id="pr-address" rows={2} {...register("address")} className={inputCls()}
            autoComplete="street-address" />
        </div>
      </div>
      <p className="text-feba-navy font-bold text-sm uppercase tracking-wide pt-2">{t("L'enfant", "The child")}</p>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-child" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Nom de l'enfant *", "Child's name *")}
          </label>
          <input id="pr-child" {...register("child_name", { required: t("Le nom de l'enfant est obligatoire.", "The child's name is required.") })}
            className={inputCls(errors.child_name)} />
          <FieldError error={errors.child_name} />
        </div>
        <div>
          <label htmlFor="pr-birth" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Date de naissance", "Date of birth")}
          </label>
          {/* La date, pas seulement l'âge : un âge saisi en mars n'est
              plus vrai en septembre, et c'est la date qui décide de
              l'affectation au niveau réglementaire. */}
          <input id="pr-birth" type="date" {...register("child_birth_date")}
            className={inputCls(errors.child_birth_date)} max={TODAY} />
          <FieldError error={errors.child_birth_date} />
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-age" className="block text-sm font-semibold text-feba-navy mb-1.5">{t("Âge", "Age")}</label>
          <input id="pr-age" type="number" min="1" max="18"
            {...register("child_age", {
              min: { value: 1, message: t("Âge invalide.", "Invalid age.") },
              max: { value: 18, message: t("Âge invalide.", "Invalid age.") },
            })}
            className={inputCls(errors.child_age)} />
          <FieldError error={errors.child_age} />
        </div>
        <div />
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="pr-level" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Niveau souhaité *", "Desired year group *")}
          </label>
          <select id="pr-level" {...register("desired_level", { required: t("Le niveau souhaité est obligatoire.", "The desired year group is required.") })}
            className={inputCls(errors.desired_level)} defaultValue="">
            <option value="" disabled>{t("— Choisir un niveau —", "— Choose a year group —")}</option>
            {LEVELS.map(([v, l]) => <option key={v} value={v}>{tr(l, lang)}</option>)}
          </select>
          <FieldError error={errors.desired_level} />
        </div>
        <div>
          <label htmlFor="pr-year" className="block text-sm font-semibold text-feba-navy mb-1.5">
            {t("Année scolaire", "Academic year")}
          </label>
          <input id="pr-year" {...register("school_year")} className={inputCls()} placeholder="2026-2027" />
        </div>
      </div>
      <div>
        <label htmlFor="pr-message" className="block text-sm font-semibold text-feba-navy mb-1.5">{t("Message", "Message")}</label>
        <textarea id="pr-message" rows={4} {...register("message")} className={inputCls()} />
      </div>
      <button type="submit" disabled={isSubmitting}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:bg-feba-gold2 transition-colors disabled:opacity-60">
        {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        {isSubmitting
          ? t("Envoi en cours…", "Sending…")
          : t("Envoyer ma demande de préinscription", "Send my pre-registration request")}
      </button>
    </form>
  );
}
