/**
 * Formulaire de contact FEBA French Heritage Academy.
 *
 * DISTINCT du formulaire de contact FEBA (/contact), qui reste réservé à
 * l'école présentielle de Cotonou. Les messages déposés ici sont rattachés
 * à l'entité FEBA_FHA par le backend (route /api/website/fha/contact/) et
 * n'apparaissent que dans la boîte de réception des administrateurs FHA.
 *
 * Champs adaptés à des familles internationales : pays, État/province,
 * fuseau horaire, langue préférée, WhatsApp, et catégories propres au
 * programme en ligne.
 */
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Check, Send } from "lucide-react";
import Seo from "../components/Seo";
import { Section } from "../components/SiteSection";
import { siteAPI } from "../siteApi";
import { useSiteLang } from "../useSiteLang";
import { FHA_NAME, FHA_SHORT } from "../fhaContent";


const CATEGORIES = [
  ["general", "Informations générales", "General information"],
  ["enrollment", "Inscription", "Enrollment"],
  ["placement_test", "Test de placement", "Placement test"],
  ["payment", "Paiement", "Payment"],
  ["zoom", "Cours en direct", "Live classes"],
  ["technical", "Support technique", "Technical support"],
  ["pedagogical", "Question pédagogique", "Teaching question"],
  ["absence", "Absence", "Absence"],
  ["document", "Document", "Document"],
  ["other", "Autre", "Other"],
];

const EMPTY = {
  name: "", email: "", phone: "", whatsapp: "", country: "",
  state_province: "", timezone: "", preferred_language: "en",
  subject: "", category: "general", message: "", consent: false,
  website: "",
};

const inputClass =
  "w-full rounded-xl border border-feba-navy/20 px-3.5 py-2.5 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-feba-green/40 focus:border-feba-green";

export default function FhaContactPage() {
  // P1 : langue issue du sélecteur GLOBAL du layout (plus de doublon).
  const { lang, t: tr2 } = useSiteLang();
  const t = tr2;

  const [form, setForm] = useState({ ...EMPTY });
  const [errors, setErrors] = useState({});
  const [sent, setSent] = useState(false);

  // Fuseau proposé automatiquement, modifiable par la famille.
  useEffect(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) setForm((f) => (f.timezone ? f : { ...f, timezone: tz }));
    } catch {
      /* API indisponible : champ laissé libre */
    }
  }, []);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const mutation = useMutation({
    mutationFn: (payload) => siteAPI.sendFhaContact(payload),
    onSuccess: () => {
      setSent(true);
      setForm({ ...EMPTY });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => {
      const data = err?.response?.data || {};
      setErrors(data);
      const first = Object.values(data)[0];
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
    if (!form.name.trim()) errs.name = t("Nom obligatoire.", "Name is required.");
    if (!/^\S+@\S+\.\S+$/.test(form.email))
      errs.email = t("Adresse e-mail invalide.", "Invalid e-mail address.");
    if (!form.subject.trim()) errs.subject = t("Sujet obligatoire.", "Subject is required.");
    if (!form.message.trim()) errs.message = t("Message obligatoire.", "Message is required.");
    if (!form.consent)
      errs.consent = t("Le consentement est obligatoire.", "Consent is required.");
    setErrors(errs);
    if (Object.keys(errs).length) return;
    // Aucune entité transmise : le backend l'impose depuis la route.
    mutation.mutate(form);
  }

  return (
    <>
      <Seo
        title={`${t("Contact", "Contact")} — ${FHA_NAME}`}
        description={t(
          "Contactez l'équipe de FEBA French Heritage Academy.",
          "Get in touch with the FEBA French Heritage Academy team.",
        )}
      />

      <div className="bg-feba-green">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
          <div className="flex justify-between items-start gap-4">
            <div>
              <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs">
                {FHA_SHORT}
              </p>
              <h1 className="text-white text-2xl sm:text-4xl font-bold mt-1">
                {t("Contacter FEBA FHA", "Contact FEBA FHA")}
              </h1>
              <p className="text-white/85 mt-3 text-sm">
                {t(
                  "Une question sur le programme, le test de placement ou l'inscription ?",
                  "A question about the programme, the placement test or enrollment?",
                )}
              </p>
            </div>
          </div>
        </div>
      </div>

      <Section tone="white">
        <div className="max-w-3xl mx-auto">
          {sent && (
            <div className="rounded-2xl bg-feba-green/10 border border-feba-green/30 p-5 mb-7 flex gap-3">
              <Check className="w-5 h-5 text-feba-green shrink-0 mt-0.5" aria-hidden="true" />
              <p className="text-sm leading-relaxed">
                {t(
                  "Merci ! Votre message a bien été envoyé à FEBA French Heritage Academy. Notre équipe vous répondra rapidement.",
                  "Thank you! Your message has been sent to FEBA French Heritage Academy. Our team will reply shortly.",
                )}
              </p>
            </div>
          )}

          <form onSubmit={submit} noValidate className="grid sm:grid-cols-2 gap-5">
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

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Nom complet", "Full name")} <span className="text-red-600">*</span>
              </span>
              <input
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                className={inputClass}
              />
              {errors.name && <span className="text-xs text-red-600">{errors.name}</span>}
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("E-mail", "E-mail")} <span className="text-red-600">*</span>
              </span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                className={inputClass}
              />
              {errors.email && <span className="text-xs text-red-600">{errors.email}</span>}
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Téléphone", "Phone")}
              </span>
              <input
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">WhatsApp</span>
              <input
                value={form.whatsapp}
                onChange={(e) => set("whatsapp", e.target.value)}
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Pays", "Country")}
              </span>
              <input
                value={form.country}
                onChange={(e) => set("country", e.target.value)}
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("État / province", "State / province")}
              </span>
              <input
                value={form.state_province}
                onChange={(e) => set("state_province", e.target.value)}
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Fuseau horaire", "Time zone")}
              </span>
              <input
                value={form.timezone}
                onChange={(e) => set("timezone", e.target.value)}
                placeholder="America/New_York"
                className={inputClass}
              />
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Langue préférée", "Preferred language")}
              </span>
              <select
                value={form.preferred_language}
                onChange={(e) => set("preferred_language", e.target.value)}
                className={inputClass}
              >
                <option value="en">English</option>
                <option value="fr">Français</option>
              </select>
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Catégorie", "Category")}
              </span>
              <select
                value={form.category}
                onChange={(e) => set("category", e.target.value)}
                className={inputClass}
              >
                {CATEGORIES.map(([value, fr, en]) => (
                  <option key={value} value={value}>
                    {t(fr, en)}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                {t("Sujet", "Subject")} <span className="text-red-600">*</span>
              </span>
              <input
                value={form.subject}
                onChange={(e) => set("subject", e.target.value)}
                className={inputClass}
              />
              {errors.subject && <span className="text-xs text-red-600">{errors.subject}</span>}
            </label>

            <div className="sm:col-span-2">
              <label className="block">
                <span className="block text-xs font-semibold text-feba-navy mb-1.5">
                  {t("Message", "Message")} <span className="text-red-600">*</span>
                </span>
                <textarea
                  rows={6}
                  value={form.message}
                  onChange={(e) => set("message", e.target.value)}
                  className={inputClass}
                />
                {errors.message && <span className="text-xs text-red-600">{errors.message}</span>}
              </label>
            </div>

            <div className="sm:col-span-2">
              <label className="flex items-start gap-2.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.consent}
                  onChange={(e) => set("consent", e.target.checked)}
                  className="mt-0.5 w-4 h-4 rounded accent-feba-green shrink-0"
                />
                <span className="leading-snug">
                  {t(
                    "J'accepte que mes informations soient utilisées pour répondre à ma demande.",
                    "I agree that my information may be used to respond to my request.",
                  )}{" "}
                  <span className="text-red-600 font-bold">*</span>
                </span>
              </label>
              {errors.consent && (
                <span className="block text-xs text-red-600 mt-1">{errors.consent}</span>
              )}
            </div>

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={mutation.isPending}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-navy text-white text-sm font-bold hover:bg-feba-navy/90 disabled:opacity-60 transition-colors"
              >
                <Send className="w-4 h-4" aria-hidden="true" />
                {mutation.isPending
                  ? t("Envoi…", "Sending…")
                  : t("Envoyer le message", "Send message")}
              </button>
            </div>
          </form>
        </div>
      </Section>
    </>
  );
}
