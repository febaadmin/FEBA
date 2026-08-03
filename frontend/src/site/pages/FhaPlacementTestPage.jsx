/**
 * Réservation d'un test de placement FEBA French Heritage Academy.
 *
 * PARCOURS DISTINCT DE L'INSCRIPTION (P3)
 * ---------------------------------------
 * « Inscrire mon enfant » et « Réserver un test de placement » ouvraient
 * auparavant le MÊME formulaire en 12 étapes. C'était une confusion de
 * parcours : réserver un test précède l'admission et ne l'engage pas.
 *
 * Ce formulaire est donc volontairement COURT — une page, les informations
 * strictement nécessaires pour proposer un créneau. La fiche complète
 * n'est demandée qu'au moment de l'inscription.
 *
 * Le backend enregistre la demande dans un modèle SÉPARÉ
 * (`FHAPlacementTestRequest`), avec sa propre numérotation
 * « FHA-TEST-AAAA-NNNN » et sa propre boîte de réception.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { CalendarClock, Check, Send } from "lucide-react";
import Seo from "../components/Seo";
import { Section } from "../components/SiteSection";
import { siteAPI } from "../siteApi";
import { FHA_NAME, FHA_SHORT, FHA_PLACEMENT, tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";

const ESTIMATED_LEVELS = [
  ["none", "Ne comprend pas le français", "Does not understand French"],
  ["few_words", "Comprend quelques mots", "Understands a few words"],
  ["understands", "Comprend mais répond en anglais", "Understands but replies in English"],
  ["speaks_a_little", "Parle un peu", "Speaks a little"],
  ["speaks_well", "Parle bien", "Speaks well"],
  ["unknown", "Je ne sais pas", "I am not sure"],
];

const EMPTY = {
  child_first_name: "", child_last_name: "", child_birth_date: "",
  child_country: "", child_state_province: "",
  parent_first_name: "", parent_last_name: "", parent_email: "",
  parent_phone: "", parent_whatsapp: "", parent_timezone: "",
  preferred_language: "en", estimated_level: "unknown", previous_experience: "",
  preferred_date: "", preferred_time: "", alternate_date: "", alternate_time: "",
  special_needs: "", consent_video: false, comment: "",
  website: "",
};

const inputClass =
  "w-full rounded-xl border border-feba-navy/20 px-3.5 py-2.5 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-feba-green/40 focus:border-feba-green";

function Field({ label, required, error, children }) {
  return (
    <label className="block">
      <span className="block text-xs font-semibold text-feba-navy mb-1.5">
        {label} {required && <span className="text-red-600">*</span>}
      </span>
      {children}
      {error && <span className="block text-xs text-red-600 mt-1">{error}</span>}
    </label>
  );
}

export default function FhaPlacementTestPage() {
  const { lang } = useSiteLang();
  const t = (fr, en) => (lang === "fr" ? fr : en);
  const L = (entry) => tr(entry, lang);

  const [form, setForm] = useState({ ...EMPTY });
  const [errors, setErrors] = useState({});
  const [done, setDone] = useState(null);

  // Fuseau de la famille : proposé automatiquement, modifiable. Les
  // créneaux lui seront ensuite présentés dans cette heure locale.
  useEffect(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) setForm((f) => (f.parent_timezone ? f : { ...f, parent_timezone: tz }));
    } catch {
      /* API indisponible : le parent saisira son fuseau */
    }
  }, []);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const mutation = useMutation({
    mutationFn: (payload) => siteAPI.sendFhaPlacementTest(payload),
    onSuccess: (resp) => {
      setDone(resp.data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => {
      const data = err?.response?.data || {};
      setErrors(data);
      const first = data.duplicate || Object.values(data)[0];
      toast.error(
        Array.isArray(first)
          ? first[0]
          : String(first || t("Une erreur est survenue.", "An error occurred.")),
      );
    },
  });

  function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!form.child_first_name.trim())
      errs.child_first_name = t("Prénom obligatoire.", "First name is required.");
    if (!form.child_last_name.trim())
      errs.child_last_name = t("Nom obligatoire.", "Last name is required.");
    if (!form.child_birth_date)
      errs.child_birth_date = t("Date de naissance obligatoire.", "Date of birth is required.");
    if (!form.parent_first_name.trim())
      errs.parent_first_name = t("Prénom obligatoire.", "First name is required.");
    if (!form.parent_last_name.trim())
      errs.parent_last_name = t("Nom obligatoire.", "Last name is required.");
    if (!/^\S+@\S+\.\S+$/.test(form.parent_email))
      errs.parent_email = t("Adresse e-mail invalide.", "Invalid e-mail address.");
    if ((form.parent_phone.match(/\d/g) || []).length < 7)
      errs.parent_phone = t("Numéro de téléphone invalide.", "Invalid phone number.");
    if (!form.consent_video)
      errs.consent_video = t(
        "Le consentement à la visioconférence est obligatoire.",
        "Consent to the video session is required.",
      );
    setErrors(errs);
    if (Object.keys(errs).length) return;
    // Aucune entité transmise : le backend l'impose depuis la route.
    mutation.mutate(form);
  }

  /* ── Confirmation ──────────────────────────────────────────────────── */
  if (done) {
    return (
      <>
        <Seo title={t("Demande enregistrée — FEBA FHA", "Request received — FEBA FHA")} />
        <Section tone="white">
          <div className="max-w-2xl mx-auto text-center">
            <div className="w-16 h-16 rounded-2xl bg-feba-green flex items-center justify-center mx-auto mb-6">
              <Check className="w-8 h-8 text-white" aria-hidden="true" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-feba-navy">
              {t("Demande enregistrée", "Request received")}
            </h1>
            <p className="mt-4 leading-relaxed">
              {lang === "fr" ? done.detail : done.detail_en || done.detail}
            </p>
            <div className="mt-6 rounded-2xl bg-feba-cream p-6">
              <p className="text-xs font-bold uppercase tracking-wide text-feba-navy">
                {t("Numéro de dossier", "File number")}
              </p>
              <p className="text-2xl font-bold text-feba-green mt-1">{done.reference}</p>
            </div>
            <p className="mt-6 text-sm">
              {t(
                "Souhaitez-vous aussi compléter la fiche d'inscription ? Ce n'est pas obligatoire avant le test.",
                "Would you also like to complete the enrollment form? It is not required before the assessment.",
              )}
            </p>
            <div className="mt-4 flex flex-wrap gap-3 justify-center">
              <Link
                to="/feba-fha/enroll"
                className="px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm"
              >
                {t("Compléter la fiche d'inscription", "Complete the enrollment form")}
              </Link>
              <Link
                to="/feba-fha"
                className="px-6 py-3 rounded-xl border border-feba-navy/20 text-feba-navy font-bold text-sm"
              >
                {t("Retour au programme", "Back to the programme")}
              </Link>
            </div>
          </div>
        </Section>
      </>
    );
  }

  return (
    <>
      <Seo
        title={`${t("Test de placement", "Placement assessment")} — ${FHA_NAME}`}
        description={t(
          "Réservez le test de placement en français de votre enfant (15 à 20 minutes).",
          "Book your child's French placement assessment (15 to 20 minutes).",
        )}
      />

      <div className="bg-feba-green">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
          <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs">
            {FHA_SHORT}
          </p>
          <h1 className="text-white text-2xl sm:text-4xl font-bold mt-1">
            {t("Réserver un test de placement", "Book a placement assessment")}
          </h1>
          <p className="text-white/85 mt-3 text-sm sm:text-base leading-relaxed">
            {t(
              "Le test dure 15 à 20 minutes et se déroule en visioconférence. Il permet de déterminer le groupe et le niveau de départ de votre enfant.",
              "The assessment takes 15 to 20 minutes and is held by video conference. It determines your child's group and starting level.",
            )}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {FHA_PLACEMENT.skills.map((s) => (
              <span
                key={L(s)}
                className="px-3 py-1.5 rounded-lg bg-white/15 text-white text-xs font-semibold"
              >
                {L(s)}
              </span>
            ))}
          </div>
          <p className="text-white/70 text-xs mt-5">
            {t(
              "Réserver un test n'engage pas une inscription.",
              "Booking an assessment does not commit you to enrolling.",
            )}
          </p>
        </div>
      </div>

      <Section tone="white">
        <form onSubmit={submit} noValidate className="max-w-3xl mx-auto">
          {/* Honeypot anti-robot */}
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            value={form.website}
            onChange={(e) => set("website", e.target.value)}
            className="absolute opacity-0 pointer-events-none h-0 w-0"
          />

          {errors.duplicate && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-4 mb-6 text-sm text-red-700">
              {errors.duplicate}
            </div>
          )}

          <h2 className="text-lg font-bold text-feba-navy mb-4">
            {t("L'enfant", "The child")}
          </h2>
          <div className="grid sm:grid-cols-2 gap-5 mb-8">
            <Field label={t("Prénom", "First name")} required error={errors.child_first_name}>
              <input
                value={form.child_first_name}
                onChange={(e) => set("child_first_name", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Nom", "Last name")} required error={errors.child_last_name}>
              <input
                value={form.child_last_name}
                onChange={(e) => set("child_last_name", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field
              label={t("Date de naissance", "Date of birth")}
              required
              error={errors.child_birth_date}
            >
              <input
                type="date"
                value={form.child_birth_date}
                onChange={(e) => set("child_birth_date", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Pays", "Country")}>
              <input
                value={form.child_country}
                onChange={(e) => set("child_country", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("État / province", "State / province")}>
              <input
                value={form.child_state_province}
                onChange={(e) => set("child_state_province", e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>

          <h2 className="text-lg font-bold text-feba-navy mb-4">
            {t("Parent ou responsable", "Parent or guardian")}
          </h2>
          <div className="grid sm:grid-cols-2 gap-5 mb-8">
            <Field label={t("Prénom", "First name")} required error={errors.parent_first_name}>
              <input
                value={form.parent_first_name}
                onChange={(e) => set("parent_first_name", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Nom", "Last name")} required error={errors.parent_last_name}>
              <input
                value={form.parent_last_name}
                onChange={(e) => set("parent_last_name", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("E-mail", "E-mail")} required error={errors.parent_email}>
              <input
                type="email"
                value={form.parent_email}
                onChange={(e) => set("parent_email", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Téléphone", "Phone")} required error={errors.parent_phone}>
              <input
                value={form.parent_phone}
                onChange={(e) => set("parent_phone", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="WhatsApp">
              <input
                value={form.parent_whatsapp}
                onChange={(e) => set("parent_whatsapp", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Fuseau horaire", "Time zone")}>
              <input
                value={form.parent_timezone}
                onChange={(e) => set("parent_timezone", e.target.value)}
                placeholder="America/New_York"
                className={inputClass}
              />
            </Field>
            <Field label={t("Langue préférée", "Preferred language")}>
              <select
                value={form.preferred_language}
                onChange={(e) => set("preferred_language", e.target.value)}
                className={inputClass}
              >
                <option value="en">English</option>
                <option value="fr">Français</option>
              </select>
            </Field>
          </div>

          <h2 className="text-lg font-bold text-feba-navy mb-4">
            {t("Niveau estimé", "Estimated level")}
          </h2>
          <div className="grid sm:grid-cols-2 gap-5 mb-8">
            <Field label={t("Niveau de français de l'enfant", "Child's level of French")}>
              <select
                value={form.estimated_level}
                onChange={(e) => set("estimated_level", e.target.value)}
                className={inputClass}
              >
                {ESTIMATED_LEVELS.map(([value, fr, en]) => (
                  <option key={value} value={value}>
                    {t(fr, en)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("Expérience antérieure", "Previous experience")}>
              <input
                value={form.previous_experience}
                onChange={(e) => set("previous_experience", e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>

          <h2 className="text-lg font-bold text-feba-navy mb-2 flex items-center gap-2">
            <CalendarClock className="w-5 h-5 text-feba-green" aria-hidden="true" />
            {t("Créneau souhaité", "Preferred time slot")}
          </h2>
          <p className="text-xs text-feba-gray mb-4">
            {t(
              "Indiquez vos heures locales : nous confirmerons le créneau dans votre fuseau horaire.",
              "Give your local times: we will confirm the slot in your own time zone.",
            )}
          </p>
          <div className="grid sm:grid-cols-2 gap-5 mb-8">
            <Field label={t("Date souhaitée", "Preferred date")}>
              <input
                type="date"
                value={form.preferred_date}
                onChange={(e) => set("preferred_date", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Heure souhaitée", "Preferred time")}>
              <input
                type="time"
                value={form.preferred_time}
                onChange={(e) => set("preferred_time", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Date alternative", "Alternative date")}>
              <input
                type="date"
                value={form.alternate_date}
                onChange={(e) => set("alternate_date", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Heure alternative", "Alternative time")}>
              <input
                type="time"
                value={form.alternate_time}
                onChange={(e) => set("alternate_time", e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>

          <div className="space-y-5 mb-8">
            <Field
              label={t(
                "Besoin particulier (facultatif et confidentiel)",
                "Special need (optional and confidential)",
              )}
            >
              <textarea
                rows={3}
                value={form.special_needs}
                onChange={(e) => set("special_needs", e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label={t("Commentaire", "Comment")}>
              <textarea
                rows={3}
                value={form.comment}
                onChange={(e) => set("comment", e.target.value)}
                className={inputClass}
              />
            </Field>

            <div>
              <label className="flex items-start gap-2.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.consent_video}
                  onChange={(e) => set("consent_video", e.target.checked)}
                  className="mt-0.5 w-4 h-4 rounded accent-feba-green shrink-0"
                />
                <span className="leading-snug">
                  {t(
                    "J'autorise la participation de mon enfant à une session de visioconférence encadrée par FEBA.",
                    "I authorise my child to take part in a video session supervised by FEBA.",
                  )}{" "}
                  <span className="text-red-600 font-bold">*</span>
                </span>
              </label>
              {errors.consent_video && (
                <span className="block text-xs text-red-600 mt-1">{errors.consent_video}</span>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-green text-white text-sm font-bold hover:brightness-110 disabled:opacity-60 transition"
          >
            <Send className="w-4 h-4" aria-hidden="true" />
            {mutation.isPending
              ? t("Envoi…", "Sending…")
              : t("Réserver le test", "Book the assessment")}
          </button>
        </form>
      </Section>
    </>
  );
}
