/**
 * Fiche de renseignements FEBA French Heritage Academy — formulaire public
 * en 12 étapes.
 *
 * DISTINCT du formulaire de préinscription FEBA (/admissions), qui reste
 * inchangé pour l'école présentielle de Cotonou.
 *
 * Caractéristiques :
 *  - multi-étapes avec barre de progression et validation par étape ;
 *  - bilingue FR/EN, mobile-first ;
 *  - brouillon enregistré localement : le parent peut reprendre plus tard ;
 *  - récapitulatif avant envoi ;
 *  - âge calculé automatiquement à partir de la date de naissance ;
 *  - fuseau horaire de la famille détecté puis modifiable.
 *
 * L'ENTITÉ N'EST PAS ENVOYÉE : le backend la déduit de la route
 * /api/website/fha/enroll/. Le brouillon local ne sert qu'au confort de
 * saisie — il n'a aucune valeur d'autorité.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Check, ChevronLeft, ChevronRight, Send, AlertCircle } from "lucide-react";
import Seo from "../components/Seo";
import { Section } from "../components/SiteSection";
import { siteAPI } from "../siteApi";
import { useSiteLang } from "../useSiteLang";
import { FHA_NAME, FHA_SHORT, FHA_TAGLINE } from "../fhaContent";

const DRAFT_KEY = "feba-fha-enroll-draft";

const FRENCH_LEVELS = [
  ["no_understanding", "Ne comprend pas le français", "Does not understand French"],
  ["few_words", "Comprend quelques mots", "Understands a few words"],
  ["understands_replies_english", "Comprend mais répond en anglais", "Understands but replies in English"],
  ["speaks_with_difficulty", "Parle difficilement", "Speaks with difficulty"],
  ["speaks_well", "Parle correctement", "Speaks well"],
  ["reads", "Lit le français", "Reads French"],
  ["writes", "Écrit le français", "Writes French"],
];

const PARENT_GOALS = [
  ["family_conversation", "Conversation familiale", "Family conversation"],
  ["grandparents", "Communication avec les grands-parents", "Talking with grandparents"],
  ["reading", "Lecture", "Reading"],
  ["writing", "Écriture", "Writing"],
  ["african_culture", "Culture africaine", "African culture"],
  ["travel", "Voyage", "Travel"],
  ["return_home", "Retour au pays", "Returning home"],
  ["studies", "Études", "Studies"],
  ["certification", "Certification", "Certification"],
  ["oral_confidence", "Confiance à l'oral", "Speaking confidence"],
  ["other", "Autre objectif", "Other goal"],
];

const DAYS = [
  [1, "Lundi", "Monday"], [2, "Mardi", "Tuesday"], [3, "Mercredi", "Wednesday"],
  [4, "Jeudi", "Thursday"], [5, "Vendredi", "Friday"], [6, "Samedi", "Saturday"],
  [7, "Dimanche", "Sunday"],
];

const STEP_TITLES = [
  ["L'enfant", "The child"],
  ["Origines et langues", "Origins and languages"],
  ["Niveau de français", "French level"],
  ["Expérience antérieure", "Previous experience"],
  ["Objectifs des parents", "Parents' goals"],
  ["Parent / responsable 1", "Parent / guardian 1"],
  ["Parent / responsable 2", "Parent / guardian 2"],
  ["Contact d'urgence", "Emergency contact"],
  ["Disponibilités", "Availability"],
  ["Équipement", "Equipment"],
  ["Besoins particuliers", "Special needs"],
  ["Consentements", "Consents"],
];

const EMPTY = {
  child_last_name: "", child_first_name: "", child_birth_date: "",
  child_city: "", child_state_province: "", child_country: "",
  child_current_school: "", child_grade: "",
  family_origin_country: "", home_main_language: "", other_languages: "",
  french_speakers_with_child: "", french_speakers_relation: "",
  french_levels: [], french_level_notes: "",
  previous_courses: false, bilingual_school: false,
  stay_in_francophone_country: false, certifications_obtained: "",
  experience_duration: "", experience_comments: "",
  parent_goals: [], parent_goals_other: "",
  parent1_last_name: "", parent1_first_name: "", parent1_relation: "",
  parent1_phone: "", parent1_whatsapp: "", parent1_email: "",
  parent1_address: "", parent1_city: "", parent1_state_province: "",
  parent1_country: "", parent1_postal_code: "",
  parent1_preferred_language: "en", parent1_timezone: "",
  parent2_last_name: "", parent2_first_name: "", parent2_relation: "",
  parent2_phone: "", parent2_whatsapp: "", parent2_email: "",
  parent2_address: "", parent2_city: "", parent2_state_province: "",
  parent2_country: "", parent2_postal_code: "",
  parent2_preferred_language: "", parent2_timezone: "",
  emergency_name: "", emergency_relation: "", emergency_phone: "",
  emergency_email: "", emergency_contact_authorized: false,
  available_days: [], available_time_slots: [], family_timezone: "",
  weekday_or_weekend: "", availability_notes: "",
  has_computer: false, has_tablet: false, has_camera: false,
  has_microphone: false, has_headset: false, has_internet: false,
  can_print: false, equipment_notes: "",
  special_needs: "",
  consent_rules: false, consent_zoom: false, consent_privacy: false,
  consent_data_processing: false, consent_photo_video: false,
  consent_communications: false, consent_payment_policy: false,
  consent_annual_commitment: false, consent_parental_authorization: false,
  website: "",
};

function computeAge(birthDate) {
  if (!birthDate) return null;
  const d = new Date(birthDate);
  if (Number.isNaN(d.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  const m = today.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < d.getDate())) age -= 1;
  return age;
}

/* ── Petits composants de formulaire ──────────────────────────────────── */

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

const inputClass =
  "w-full rounded-xl border border-feba-navy/20 px-3.5 py-2.5 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-feba-green/40 focus:border-feba-green";

function Text({ value, onChange, type = "text", ...rest }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={inputClass}
      {...rest}
    />
  );
}

function Check2({ checked, onChange, label }) {
  return (
    <label className="flex items-start gap-2.5 text-sm cursor-pointer py-1">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 w-4 h-4 rounded accent-feba-green shrink-0"
      />
      <span className="leading-snug">{label}</span>
    </label>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────── */

export default function FhaEnrollPage() {
  // P1 : langue issue du sélecteur GLOBAL du layout (plus de doublon).
  const { lang, t: tr2 } = useSiteLang();
  const t = tr2;

  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState({});
  const [done, setDone] = useState(null);

  // Brouillon repris automatiquement — confort de saisie uniquement.
  const [form, setForm] = useState(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      return raw ? { ...EMPTY, ...JSON.parse(raw) } : { ...EMPTY };
    } catch {
      return { ...EMPTY };
    }
  });

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  // Fuseau de la famille : proposé automatiquement, modifiable.
  useEffect(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) {
        setForm((f) => (f.family_timezone ? f : { ...f, family_timezone: tz }));
      }
    } catch {
      /* API indisponible : le parent saisira son fuseau */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
    } catch {
      /* quota dépassé : la saisie continue sans sauvegarde locale */
    }
  }, [form]);
  const toggleIn = (key, value) =>
    setForm((f) => ({
      ...f,
      [key]: f[key].includes(value)
        ? f[key].filter((v) => v !== value)
        : [...f[key], value],
    }));

  const age = useMemo(() => computeAge(form.child_birth_date), [form.child_birth_date]);

  const mutation = useMutation({
    mutationFn: (payload) => siteAPI.sendFhaEnrollment(payload),
    onSuccess: (resp) => {
      setDone(resp.data);
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {
        /* rien à nettoyer */
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => {
      const data = err?.response?.data || {};
      setErrors(data);
      const first =
        data.duplicate ||
        data.consents ||
        Object.values(data)[0] ||
        t("Une erreur est survenue.", "An error occurred.");
      toast.error(Array.isArray(first) ? first[0] : String(first));
    },
  });

  /* Validation par étape — miroir des règles serveur, qui restent la
     référence : le backend revalide tout. */
  function validateStep(index) {
    const e = {};
    if (index === 0) {
      if (!form.child_first_name.trim())
        e.child_first_name = t("Prénom obligatoire.", "First name is required.");
      if (!form.child_last_name.trim())
        e.child_last_name = t("Nom obligatoire.", "Last name is required.");
      if (!form.child_birth_date)
        e.child_birth_date = t("Date de naissance obligatoire.", "Date of birth is required.");
      else if (new Date(form.child_birth_date) > new Date())
        e.child_birth_date = t("Date dans le futur.", "Date is in the future.");
    }
    if (index === 5) {
      if (!form.parent1_first_name.trim())
        e.parent1_first_name = t("Prénom obligatoire.", "First name is required.");
      if (!form.parent1_last_name.trim())
        e.parent1_last_name = t("Nom obligatoire.", "Last name is required.");
      if (!/^\S+@\S+\.\S+$/.test(form.parent1_email))
        e.parent1_email = t("Adresse e-mail invalide.", "Invalid e-mail address.");
      if ((form.parent1_phone.match(/\d/g) || []).length < 7)
        e.parent1_phone = t("Numéro de téléphone invalide.", "Invalid phone number.");
    }
    if (index === 11) {
      const required = [
        ["consent_rules", t("le règlement", "the school rules")],
        ["consent_privacy", t("la confidentialité", "the privacy policy")],
        ["consent_data_processing", t("le traitement des données", "data processing")],
        ["consent_parental_authorization", t("l'autorisation parentale", "parental authorisation")],
      ];
      const missing = required.filter(([k]) => !form[k]).map(([, l]) => l);
      if (missing.length)
        e.consents = t(
          `Vous devez accepter : ${missing.join(", ")}.`,
          `You must accept: ${missing.join(", ")}.`,
        );
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  const next = () => {
    if (validateStep(step)) {
      setStep((s) => Math.min(s + 1, STEP_TITLES.length));
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };
  const back = () => {
    setErrors({});
    setStep((s) => Math.max(s - 1, 0));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  function submit() {
    if (!validateStep(11)) return;
    // `entity` n'est volontairement PAS transmis : le serveur l'impose.
    mutation.mutate(form);
  }

  /* ── Écran de confirmation ─────────────────────────────────────────── */
  if (done) {
    return (
      <>
        <Seo title={t("Fiche envoyée — FEBA FHA", "Form submitted — FEBA FHA")} />
        <Section tone="white">
          <div className="max-w-2xl mx-auto text-center">
            <div className="w-16 h-16 rounded-2xl bg-feba-green flex items-center justify-center mx-auto mb-6">
              <Check className="w-8 h-8 text-white" aria-hidden="true" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-feba-navy">
              {t("Merci !", "Thank you!")}
            </h1>
            <p className="mt-4 leading-relaxed">
              {lang === "fr" ? done.detail : done.detail_en || done.detail}
            </p>
            <div className="mt-6 rounded-2xl bg-feba-cream p-6">
              <p className="text-xs font-bold uppercase tracking-wide text-feba-navy">
                {t("Numéro de dossier", "File number")}
              </p>
              <p className="text-2xl font-bold text-feba-green mt-1">{done.reference}</p>
              {done.suggested_group && (
                <p className="text-xs mt-3">
                  {t("Groupe suggéré (selon l'âge)", "Suggested group (by age)")} :{" "}
                  <strong>{done.suggested_group.replace(/_/g, " ")}</strong>
                  {" — "}
                  {t(
                    "le placement définitif dépend du test de placement.",
                    "final placement depends on the placement assessment.",
                  )}
                </p>
              )}
            </div>
            <Link
              to="/feba-fha"
              className="mt-8 inline-block px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm"
            >
              {t("Retour au programme", "Back to the programme")}
            </Link>
          </div>
        </Section>
      </>
    );
  }

  const isReview = step === STEP_TITLES.length;
  const progress = Math.round(((step + (isReview ? 1 : 0)) / (STEP_TITLES.length + 1)) * 100);

  return (
    <>
      <Seo
        title={`${t("Inscription", "Enrollment")} — ${FHA_NAME}`}
        description={FHA_TAGLINE}
      />

      <div className="bg-feba-green">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
          <div className="flex justify-between items-start gap-4">
            <div>
              <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs">
                {FHA_SHORT}
              </p>
              <h1 className="text-white text-2xl sm:text-3xl font-bold mt-1">
                {t("Fiche de renseignements", "Enrollment form")}
              </h1>
            </div>
          </div>

          {/* Barre de progression */}
          <div className="mt-6">
            <div className="flex justify-between text-xs text-white/85 mb-2">
              <span>
                {isReview
                  ? t("Récapitulatif", "Summary")
                  : `${t("Étape", "Step")} ${step + 1}/${STEP_TITLES.length} — ${
                      STEP_TITLES[step][lang === "fr" ? 0 : 1]
                    }`}
              </span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 rounded-full bg-white/20 overflow-hidden">
              <div
                className="h-full bg-feba-gold transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          <p className="text-white/75 text-xs mt-3">
            {t(
              "Votre saisie est enregistrée sur cet appareil : vous pouvez reprendre plus tard.",
              "Your entries are saved on this device: you can come back later.",
            )}
          </p>
        </div>
      </div>

      <Section tone="white">
        <div className="max-w-3xl mx-auto">
          {/* Honeypot anti-robot — invisible pour les humains. */}
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            value={form.website}
            onChange={(e) => set("website", e.target.value)}
            className="absolute opacity-0 pointer-events-none h-0 w-0"
          />

          {/* ── Étape 1 : l'enfant ─────────────────────────────────── */}
          {step === 0 && (
            <div className="grid sm:grid-cols-2 gap-5">
              <Field label={t("Prénom", "First name")} required error={errors.child_first_name}>
                <Text value={form.child_first_name} onChange={(v) => set("child_first_name", v)} />
              </Field>
              <Field label={t("Nom", "Last name")} required error={errors.child_last_name}>
                <Text value={form.child_last_name} onChange={(v) => set("child_last_name", v)} />
              </Field>
              <Field
                label={t("Date de naissance", "Date of birth")}
                required
                error={errors.child_birth_date}
              >
                <Text
                  type="date"
                  value={form.child_birth_date}
                  onChange={(v) => set("child_birth_date", v)}
                />
              </Field>
              <Field label={t("Âge (calculé)", "Age (calculated)")}>
                <div className={`${inputClass} bg-feba-cream font-semibold`}>
                  {age === null ? "—" : `${age} ${t("ans", "years")}`}
                </div>
              </Field>
              <Field label={t("Ville", "City")}>
                <Text value={form.child_city} onChange={(v) => set("child_city", v)} />
              </Field>
              <Field label={t("État / province", "State / province")}>
                <Text
                  value={form.child_state_province}
                  onChange={(v) => set("child_state_province", v)}
                />
              </Field>
              <Field label={t("Pays", "Country")}>
                <Text value={form.child_country} onChange={(v) => set("child_country", v)} />
              </Field>
              <Field label={t("École actuelle", "Current school")}>
                <Text
                  value={form.child_current_school}
                  onChange={(v) => set("child_current_school", v)}
                />
              </Field>
              <Field label={t("Classe / grade actuel", "Current grade")}>
                <Text value={form.child_grade} onChange={(v) => set("child_grade", v)} />
              </Field>
            </div>
          )}

          {/* ── Étape 2 : origines et langues ──────────────────────── */}
          {step === 1 && (
            <div className="grid sm:grid-cols-2 gap-5">
              <Field label={t("Pays d'origine de la famille", "Family's country of origin")}>
                <Text
                  value={form.family_origin_country}
                  onChange={(v) => set("family_origin_country", v)}
                />
              </Field>
              <Field label={t("Langue principale à la maison", "Main language at home")}>
                <Text
                  value={form.home_main_language}
                  onChange={(v) => set("home_main_language", v)}
                />
              </Field>
              <Field label={t("Autres langues parlées", "Other languages spoken")}>
                <Text value={form.other_languages} onChange={(v) => set("other_languages", v)} />
              </Field>
              <Field
                label={t("Qui parle français avec l'enfant ?", "Who speaks French with the child?")}
              >
                <Text
                  value={form.french_speakers_with_child}
                  onChange={(v) => set("french_speakers_with_child", v)}
                />
              </Field>
              <div className="sm:col-span-2">
                <Field label={t("Relation avec ces personnes", "Relationship with these people")}>
                  <Text
                    value={form.french_speakers_relation}
                    onChange={(v) => set("french_speakers_relation", v)}
                  />
                </Field>
              </div>
            </div>
          )}

          {/* ── Étape 3 : niveau de français ───────────────────────── */}
          {step === 2 && (
            <div>
              <p className="text-sm mb-4">
                {t(
                  "Cochez tout ce qui correspond à votre enfant.",
                  "Tick everything that applies to your child.",
                )}
              </p>
              <div className="space-y-1 mb-5">
                {FRENCH_LEVELS.map(([key, fr, en]) => (
                  <Check2
                    key={key}
                    checked={form.french_levels.includes(key)}
                    onChange={() => toggleIn("french_levels", key)}
                    label={t(fr, en)}
                  />
                ))}
              </div>
              <Field label={t("Précisions (facultatif)", "Additional details (optional)")}>
                <textarea
                  rows={4}
                  value={form.french_level_notes}
                  onChange={(e) => set("french_level_notes", e.target.value)}
                  className={inputClass}
                />
              </Field>
            </div>
          )}

          {/* ── Étape 4 : expérience antérieure ────────────────────── */}
          {step === 3 && (
            <div className="space-y-4">
              <Check2
                checked={form.previous_courses}
                onChange={(v) => set("previous_courses", v)}
                label={t("A déjà suivi des cours de français", "Has already taken French lessons")}
              />
              <Check2
                checked={form.bilingual_school}
                onChange={(v) => set("bilingual_school", v)}
                label={t("A fréquenté une école bilingue", "Has attended a bilingual school")}
              />
              <Check2
                checked={form.stay_in_francophone_country}
                onChange={(v) => set("stay_in_francophone_country", v)}
                label={t(
                  "A séjourné dans un pays francophone",
                  "Has stayed in a French-speaking country",
                )}
              />
              <div className="grid sm:grid-cols-2 gap-5 pt-2">
                <Field label={t("Certifications obtenues", "Certifications obtained")}>
                  <Text
                    value={form.certifications_obtained}
                    onChange={(v) => set("certifications_obtained", v)}
                  />
                </Field>
                <Field label={t("Durée de l'expérience", "Length of experience")}>
                  <Text
                    value={form.experience_duration}
                    onChange={(v) => set("experience_duration", v)}
                  />
                </Field>
              </div>
              <Field label={t("Commentaires", "Comments")}>
                <textarea
                  rows={3}
                  value={form.experience_comments}
                  onChange={(e) => set("experience_comments", e.target.value)}
                  className={inputClass}
                />
              </Field>
            </div>
          )}

          {/* ── Étape 5 : objectifs des parents ────────────────────── */}
          {step === 4 && (
            <div>
              <p className="text-sm mb-4">
                {t(
                  "Que souhaitez-vous que votre enfant obtienne du programme ?",
                  "What do you want your child to gain from the programme?",
                )}
              </p>
              <div className="grid sm:grid-cols-2 gap-x-6">
                {PARENT_GOALS.map(([key, fr, en]) => (
                  <Check2
                    key={key}
                    checked={form.parent_goals.includes(key)}
                    onChange={() => toggleIn("parent_goals", key)}
                    label={t(fr, en)}
                  />
                ))}
              </div>
              {form.parent_goals.includes("other") && (
                <div className="mt-4">
                  <Field label={t("Précisez votre objectif", "Please specify your goal")}>
                    <Text
                      value={form.parent_goals_other}
                      onChange={(v) => set("parent_goals_other", v)}
                    />
                  </Field>
                </div>
              )}
            </div>
          )}

          {/* ── Étapes 6 et 7 : parents ────────────────────────────── */}
          {(step === 5 || step === 6) && (
            <ParentBlock
              index={step === 5 ? 1 : 2}
              form={form}
              set={set}
              errors={errors}
              t={t}
            />
          )}

          {/* ── Étape 8 : contact d'urgence ────────────────────────── */}
          {step === 7 && (
            <div className="grid sm:grid-cols-2 gap-5">
              <Field label={t("Nom complet", "Full name")}>
                <Text value={form.emergency_name} onChange={(v) => set("emergency_name", v)} />
              </Field>
              <Field label={t("Relation avec l'enfant", "Relationship to the child")}>
                <Text
                  value={form.emergency_relation}
                  onChange={(v) => set("emergency_relation", v)}
                />
              </Field>
              <Field label={t("Téléphone", "Phone")}>
                <Text value={form.emergency_phone} onChange={(v) => set("emergency_phone", v)} />
              </Field>
              <Field label={t("E-mail (facultatif)", "E-mail (optional)")}>
                <Text
                  type="email"
                  value={form.emergency_email}
                  onChange={(v) => set("emergency_email", v)}
                />
              </Field>
              <div className="sm:col-span-2">
                <Check2
                  checked={form.emergency_contact_authorized}
                  onChange={(v) => set("emergency_contact_authorized", v)}
                  label={t(
                    "J'autorise FEBA à contacter cette personne en cas d'urgence.",
                    "I authorise FEBA to contact this person in an emergency.",
                  )}
                />
              </div>
            </div>
          )}

          {/* ── Étape 9 : disponibilités ───────────────────────────── */}
          {step === 8 && (
            <div className="space-y-5">
              <div>
                <p className="text-xs font-semibold text-feba-navy mb-2">
                  {t("Jours disponibles", "Available days")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {DAYS.map(([value, fr, en]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleIn("available_days", value)}
                      aria-pressed={form.available_days.includes(value)}
                      className={`px-3.5 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                        form.available_days.includes(value)
                          ? "bg-feba-green text-white border-feba-green"
                          : "bg-white text-feba-navy border-feba-navy/20"
                      }`}
                    >
                      {t(fr, en)}
                    </button>
                  ))}
                </div>
              </div>

              <TimeSlots form={form} set={set} t={t} inputClass={inputClass} />

              <div className="grid sm:grid-cols-2 gap-5">
                <Field label={t("Fuseau horaire", "Time zone")}>
                  <Text
                    value={form.family_timezone}
                    onChange={(v) => set("family_timezone", v)}
                    placeholder="America/New_York"
                  />
                </Field>
                <Field label={t("Préférence", "Preference")}>
                  <select
                    value={form.weekday_or_weekend}
                    onChange={(e) => set("weekday_or_weekend", e.target.value)}
                    className={inputClass}
                  >
                    <option value="">—</option>
                    <option value="weekday">{t("Semaine", "Weekday")}</option>
                    <option value="weekend">{t("Week-end", "Weekend")}</option>
                    <option value="both">{t("Les deux", "Both")}</option>
                  </select>
                </Field>
              </div>

              <Field label={t("Disponibilités alternatives", "Alternative availability")}>
                <textarea
                  rows={3}
                  value={form.availability_notes}
                  onChange={(e) => set("availability_notes", e.target.value)}
                  className={inputClass}
                />
              </Field>
            </div>
          )}

          {/* ── Étape 10 : équipement ──────────────────────────────── */}
          {step === 9 && (
            <div>
              <div className="grid sm:grid-cols-2 gap-x-6">
                {[
                  ["has_computer", "Ordinateur", "Computer"],
                  ["has_tablet", "Tablette", "Tablet"],
                  ["has_camera", "Caméra", "Camera"],
                  ["has_microphone", "Microphone", "Microphone"],
                  ["has_headset", "Casque", "Headset"],
                  ["has_internet", "Connexion Internet", "Internet connection"],
                  ["can_print", "Possibilité d'imprimer", "Can print"],
                ].map(([key, fr, en]) => (
                  <Check2
                    key={key}
                    checked={form[key]}
                    onChange={(v) => set(key, v)}
                    label={t(fr, en)}
                  />
                ))}
              </div>
              <div className="mt-4">
                <Field label={t("Commentaires techniques", "Technical comments")}>
                  <textarea
                    rows={3}
                    value={form.equipment_notes}
                    onChange={(e) => set("equipment_notes", e.target.value)}
                    className={inputClass}
                  />
                </Field>
              </div>
            </div>
          )}

          {/* ── Étape 11 : besoins particuliers ────────────────────── */}
          {step === 10 && (
            <div>
              <div className="rounded-2xl bg-feba-cream p-5 mb-5 flex gap-3">
                <AlertCircle className="w-5 h-5 text-feba-green shrink-0 mt-0.5" aria-hidden="true" />
                <p className="text-sm leading-relaxed">
                  {t(
                    "Champ facultatif et confidentiel. Ces informations ne sont accessibles qu'aux personnes habilitées de l'administration et à l'enseignant concerné.",
                    "Optional and confidential. This information is only accessible to authorised administration staff and the child's teacher.",
                  )}
                </p>
              </div>
              <Field
                label={t(
                  "Adaptations pédagogiques, difficultés d'apprentissage, besoins de soutien",
                  "Learning adjustments, learning difficulties, support needs",
                )}
              >
                <textarea
                  rows={6}
                  value={form.special_needs}
                  onChange={(e) => set("special_needs", e.target.value)}
                  className={inputClass}
                />
              </Field>
            </div>
          )}

          {/* ── Étape 12 : consentements ───────────────────────────── */}
          {step === 11 && (
            <div>
              {errors.consents && (
                <div className="rounded-xl bg-red-50 border border-red-200 p-4 mb-5 text-sm text-red-700">
                  {errors.consents}
                </div>
              )}
              <div className="space-y-1">
                {[
                  ["consent_rules", "J'accepte le règlement intérieur.", "I accept the school rules.", true],
                  ["consent_privacy", "J'accepte la politique de confidentialité.", "I accept the privacy policy.", true],
                  ["consent_data_processing", "J'accepte le traitement des données de ma famille.", "I consent to the processing of my family's data.", true],
                  ["consent_parental_authorization", "Je suis le parent ou le responsable légal et j'autorise l'inscription.", "I am the parent or legal guardian and I authorise this enrollment.", true],
                  ["consent_zoom", "J'autorise la participation de mon enfant aux cours en visioconférence.", "I authorise my child to take part in video-conference classes.", false],
                  ["consent_photo_video", "J'autorise l'utilisation de photos ou vidéos de mon enfant (révocable).", "I authorise the use of photos or videos of my child (revocable).", false],
                  ["consent_communications", "J'accepte de recevoir les communications de FEBA FHA.", "I agree to receive communications from FEBA FHA.", false],
                  ["consent_payment_policy", "J'ai pris connaissance de la politique de paiement.", "I have read the payment policy.", false],
                  ["consent_annual_commitment", "Je comprends que l'inscription est un engagement annuel.", "I understand that enrollment is an annual commitment.", false],
                ].map(([key, fr, en, required]) => (
                  <Check2
                    key={key}
                    checked={form[key]}
                    onChange={(v) => set(key, v)}
                    label={
                      <>
                        {t(fr, en)}{" "}
                        {required && <span className="text-red-600 font-bold">*</span>}
                      </>
                    }
                  />
                ))}
              </div>
              <p className="text-xs text-feba-gray mt-5 leading-relaxed">
                {t(
                  "Chaque consentement est daté et enregistré avec sa version. L'autorisation photo/vidéo est distincte et peut être retirée.",
                  "Each consent is dated and stored with its version. The photo/video authorisation is separate and can be withdrawn.",
                )}
              </p>
            </div>
          )}

          {/* ── Récapitulatif ──────────────────────────────────────── */}
          {isReview && (
            <div>
              <h2 className="text-xl font-bold text-feba-navy mb-5">
                {t("Vérifiez vos informations", "Check your information")}
              </h2>
              {errors.duplicate && (
                <div className="rounded-xl bg-red-50 border border-red-200 p-4 mb-5 text-sm text-red-700">
                  {errors.duplicate}
                </div>
              )}
              <dl className="space-y-2.5 text-sm">
                {[
                  [t("Enfant", "Child"), `${form.child_first_name} ${form.child_last_name}`],
                  [t("Âge", "Age"), age === null ? "—" : `${age}`],
                  [t("Pays", "Country"), form.child_country || "—"],
                  [
                    t("Parent", "Parent"),
                    `${form.parent1_first_name} ${form.parent1_last_name}`,
                  ],
                  [t("E-mail", "E-mail"), form.parent1_email],
                  [t("Téléphone", "Phone"), form.parent1_phone],
                  [t("Fuseau horaire", "Time zone"), form.family_timezone || "—"],
                  [
                    t("Jours disponibles", "Available days"),
                    form.available_days.length
                      ? form.available_days
                          .map((d) => t(DAYS[d - 1][1], DAYS[d - 1][2]))
                          .join(", ")
                      : "—",
                  ],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="flex justify-between gap-4 border-b border-feba-navy/10 pb-2"
                  >
                    <dt className="font-semibold text-feba-navy">{label}</dt>
                    <dd className="text-right">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* ── Navigation ─────────────────────────────────────────── */}
          <div className="flex justify-between gap-3 mt-9 pt-6 border-t border-feba-navy/10">
            <button
              type="button"
              onClick={back}
              disabled={step === 0}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-feba-navy/20 text-sm font-semibold text-feba-navy disabled:opacity-40 hover:bg-feba-cream transition-colors"
            >
              <ChevronLeft className="w-4 h-4" aria-hidden="true" />
              {t("Précédent", "Back")}
            </button>

            {isReview ? (
              <button
                type="button"
                onClick={submit}
                disabled={mutation.isPending}
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-feba-green text-white text-sm font-bold hover:brightness-110 disabled:opacity-60 transition"
              >
                <Send className="w-4 h-4" aria-hidden="true" />
                {mutation.isPending
                  ? t("Envoi…", "Sending…")
                  : t("Envoyer ma fiche", "Submit my form")}
              </button>
            ) : (
              <button
                type="button"
                onClick={next}
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-feba-navy text-white text-sm font-bold hover:bg-feba-navy/90 transition-colors"
              >
                {step === STEP_TITLES.length - 1
                  ? t("Récapitulatif", "Summary")
                  : t("Suivant", "Next")}
                <ChevronRight className="w-4 h-4" aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </Section>
    </>
  );
}

/* ── Bloc parent réutilisé aux étapes 6 et 7 ──────────────────────────── */
function ParentBlock({ index, form, set, errors, t }) {
  const p = `parent${index}_`;
  const required = index === 1;
  return (
    <div>
      {index === 2 && (
        <p className="text-sm mb-5 rounded-xl bg-feba-cream p-4">
          {t(
            "Ce bloc est facultatif : renseignez-le selon votre situation familiale.",
            "This section is optional: fill it in according to your family situation.",
          )}
        </p>
      )}
      <div className="grid sm:grid-cols-2 gap-5">
        <Field
          label={t("Prénom", "First name")}
          required={required}
          error={errors[`${p}first_name`]}
        >
          <Text value={form[`${p}first_name`]} onChange={(v) => set(`${p}first_name`, v)} />
        </Field>
        <Field label={t("Nom", "Last name")} required={required} error={errors[`${p}last_name`]}>
          <Text value={form[`${p}last_name`]} onChange={(v) => set(`${p}last_name`, v)} />
        </Field>
        <Field label={t("Relation avec l'enfant", "Relationship to the child")}>
          <Text value={form[`${p}relation`]} onChange={(v) => set(`${p}relation`, v)} />
        </Field>
        <Field label={t("Téléphone", "Phone")} required={required} error={errors[`${p}phone`]}>
          <Text value={form[`${p}phone`]} onChange={(v) => set(`${p}phone`, v)} />
        </Field>
        <Field label="WhatsApp">
          <Text value={form[`${p}whatsapp`]} onChange={(v) => set(`${p}whatsapp`, v)} />
        </Field>
        <Field label={t("E-mail", "E-mail")} required={required} error={errors[`${p}email`]}>
          <Text type="email" value={form[`${p}email`]} onChange={(v) => set(`${p}email`, v)} />
        </Field>
        <div className="sm:col-span-2">
          <Field label={t("Adresse", "Address")}>
            <Text value={form[`${p}address`]} onChange={(v) => set(`${p}address`, v)} />
          </Field>
        </div>
        <Field label={t("Ville", "City")}>
          <Text value={form[`${p}city`]} onChange={(v) => set(`${p}city`, v)} />
        </Field>
        <Field label={t("État / province", "State / province")}>
          <Text
            value={form[`${p}state_province`]}
            onChange={(v) => set(`${p}state_province`, v)}
          />
        </Field>
        <Field label={t("Pays", "Country")}>
          <Text value={form[`${p}country`]} onChange={(v) => set(`${p}country`, v)} />
        </Field>
        <Field label={t("Code postal", "Postal code")}>
          <Text value={form[`${p}postal_code`]} onChange={(v) => set(`${p}postal_code`, v)} />
        </Field>
        <Field label={t("Langue préférée", "Preferred language")}>
          <select
            value={form[`${p}preferred_language`]}
            onChange={(e) => set(`${p}preferred_language`, e.target.value)}
            className={inputClass}
          >
            {index === 2 && <option value="">—</option>}
            <option value="en">English</option>
            <option value="fr">Français</option>
          </select>
        </Field>
        <Field label={t("Fuseau horaire", "Time zone")}>
          <Text
            value={form[`${p}timezone`]}
            onChange={(v) => set(`${p}timezone`, v)}
            placeholder="America/New_York"
          />
        </Field>
      </div>
    </div>
  );
}

/* ── Créneaux horaires (stockés au format normalisé HH:MM) ────────────── */
function TimeSlots({ form, set, t, inputClass: cls }) {
  const slots = form.available_time_slots;
  const update = (i, key, value) => {
    const next = slots.map((s, j) => (i === j ? { ...s, [key]: value } : s));
    set("available_time_slots", next);
  };
  return (
    <div>
      <p className="text-xs font-semibold text-feba-navy mb-2">
        {t("Plages horaires (heure locale)", "Time slots (your local time)")}
      </p>
      <div className="space-y-2">
        {slots.map((slot, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="time"
              value={slot.start || ""}
              onChange={(e) => update(i, "start", e.target.value)}
              className={cls}
            />
            <span className="text-sm shrink-0">→</span>
            <input
              type="time"
              value={slot.end || ""}
              onChange={(e) => update(i, "end", e.target.value)}
              className={cls}
            />
            <button
              type="button"
              onClick={() =>
                set(
                  "available_time_slots",
                  slots.filter((_, j) => j !== i),
                )
              }
              className="px-3 py-2 text-xs font-semibold text-red-600 shrink-0"
            >
              {t("Retirer", "Remove")}
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => set("available_time_slots", [...slots, { start: "", end: "" }])}
        className="mt-2 px-4 py-2 rounded-xl border border-feba-navy/20 text-xs font-semibold text-feba-navy hover:bg-feba-cream transition-colors"
      >
        + {t("Ajouter un créneau", "Add a time slot")}
      </button>
    </div>
  );
}
