/**
 * FEBA French Heritage Academy (FEBA FHA) — page publique complète.
 *
 * Remplace l'ancienne page « FEBA Online ». Le menu principal affiche
 * l'abréviation « FEBA FHA » (le nom complet est trop long pour la barre de
 * navigation) ; les titres et contenus utilisent le nom complet.
 *
 * BILINGUE : le programme s'adresse d'abord à des familles anglophones.
 * La langue vient du sélecteur GLOBAL du layout public (`useSiteLang`), qui
 * couvre toutes les pages du site. Cette page n'a plus de sélecteur propre :
 * en avoir un ici afficherait deux contrôles concurrents.
 *
 * AUCUNE DONNÉE INVENTÉE : tarif, date de rentrée, horaires définitifs,
 * politique de remboursement, noms des enseignants et prestataire de
 * paiement proviennent de l'API et ne sont AFFICHÉS QUE s'ils ont été
 * renseignés par l'administration. Sinon le bloc indique explicitement que
 * l'information sera communiquée après validation.
 */
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Globe2, Laptop, Users2, BookHeart, GraduationCap, CalendarDays,
  ClipboardCheck, MessageCircle, ShieldCheck, Sparkles, AlertCircle, Check,
} from "lucide-react";
import Seo from "../components/Seo";
import { FHA_PLANS, FHA_FLYER_PATH } from "../fhaPlans";
import SiteImage from "../components/SiteImage";
import { Section, SectionHeading } from "../components/SiteSection";
import { siteAPI } from "../siteApi";
import { useSiteLang } from "../useSiteLang";
import {
  FHA_NAME, FHA_SHORT, FHA_TAGLINE, FHA_INTRO, FHA_PILLARS, FHA_PROBLEMS,
  FHA_SOLUTIONS, FHA_MISSION, FHA_VISION, FHA_AUDIENCE, FHA_GROUPS,
  FHA_YEAR_ORGANISATION, FHA_PROGRAMME, FHA_HERITAGE, FHA_CULTURAL_ACTIVITIES,
  FHA_PLACEMENT, FHA_ENROLLMENT_STEPS, FHA_CERTIFICATION_CONDITIONS,
  FHA_CERTIFICATION_NOTICE, FHA_FAQ, tr,
} from "../fhaContent";

const T = {
  navSections: {
    fr: [
      ["programme", "Le programme"], ["groupes", "Nos groupes"],
      ["annee", "L'année"], ["cinq-ans", "Programme 5 ans"],
      ["heritage", "African Heritage"], ["certification", "Certifications"],
      ["test", "Test de placement"], ["inscription", "Inscription"],
      ["tarifs", "Tarifs"], ["faq", "FAQ"], ["contact", "Contact"],
    ],
    en: [
      ["programme", "Programme"], ["groupes", "Our groups"],
      ["annee", "The year"], ["cinq-ans", "5-year path"],
      ["heritage", "African Heritage"], ["certification", "Certifications"],
      ["test", "Placement test"], ["inscription", "Enrollment"],
      ["tarifs", "Fees"], ["faq", "FAQ"], ["contact", "Contact"],
    ],
  },
  enroll: { fr: "Inscrire mon enfant", en: "Enroll my child" },
  bookTest: { fr: "Réserver un test de placement", en: "Book a placement test" },
  discover: { fr: "Découvrir FEBA FHA", en: "Discover FEBA FHA" },
  whatsapp: { fr: "Nous écrire sur WhatsApp", en: "Message us on WhatsApp" },
  problemTitle: { fr: "Le problème rencontré par les familles", en: "The challenge families face" },
  problemIntro: {
    fr: "De nombreux enfants nés ou élevés hors d'Afrique dans des familles francophones parlent principalement anglais.",
    en: "Many children born or raised outside Africa in French-speaking families mainly speak English.",
  },
  solutionTitle: { fr: "La solution FEBA FHA", en: "The FEBA FHA solution" },
  solutionIntro: {
    fr: "FEBA propose une véritable expérience scolaire en ligne, et non de simples cours occasionnels.",
    en: "FEBA offers a real online school experience, not occasional one-off lessons.",
  },
  missionTitle: { fr: "Mission", en: "Mission" },
  visionTitle: { fr: "Vision", en: "Vision" },
  audienceTitle: { fr: "Public cible", en: "Who it is for" },
  audienceCommunities: { fr: "Premières communautés concernées", en: "First communities concerned" },
  groupsTitle: { fr: "Nos trois groupes", en: "Our three groups" },
  groupSize: { fr: "Taille du groupe", en: "Group size" },
  groupDuration: { fr: "Durée d'une séance", en: "Session length" },
  groupMethod: { fr: "Méthode", en: "Method" },
  groupGoal: { fr: "Objectif", en: "Goal" },
  yearTitle: { fr: "Organisation de l'année", en: "How the year is organised" },
  yearVolume: { fr: "Sur une année, chaque élève reçoit environ", en: "Over a year, each student receives about" },
  programmeTitle: { fr: "Le programme sur cinq ans", en: "The five-year programme" },
  objectives: { fr: "Objectifs", en: "Objectives" },
  outcome: { fr: "Résultat attendu", en: "Expected outcome" },
  validation: { fr: "Validation", en: "Validation" },
  heritageTitle: { fr: "African Heritage", en: "African Heritage" },
  heritageIntro: {
    fr: "La culture africaine n'est pas séparée du français : elle sert de support à la conversation, à la lecture et à l'écriture.",
    en: "African culture is not separate from French: it is the medium for conversation, reading and writing.",
  },
  activitiesTitle: { fr: "Activités culturelles", en: "Cultural activities" },
  certificationTitle: { fr: "Progression et certifications", en: "Progress and certifications" },
  certificationIntro: {
    fr: "Le certificat n'est pas délivré simplement parce que l'enfant a passé plusieurs années dans le programme. L'élève doit notamment :",
    en: "A certificate is not awarded merely because a child has spent several years in the programme. The student must:",
  },
  testTitle: { fr: "Test de placement", en: "Placement assessment" },
  testDuration: { fr: "Durée", en: "Duration" },
  testSkills: { fr: "Compétences évaluées", en: "Skills assessed" },
  testLevels: { fr: "Niveaux", en: "Levels" },
  testResult: { fr: "Ce que vous recevez ensuite", en: "What you receive afterwards" },
  enrollTitle: { fr: "Déroulement de l'inscription", en: "How enrollment works" },
  calendarTitle: { fr: "Calendrier et horaires", en: "Calendar and schedule" },
  teachersTitle: { fr: "Enseignants", en: "Teachers" },
  teachersPending: {
    fr: "Les enseignants du programme seront présentés ici dès que la direction aura validé leur affectation.",
    en: "The programme's teachers will be introduced here as soon as the management has confirmed their assignment.",
  },
  feesTitle: { fr: "Tarifs et modalités", en: "Fees and payment terms" },
  feesPending: {
    fr: "Le tarif annuel n'est pas encore publié. Le programme sera vendu comme un forfait annuel correspondant à une année scolaire complète, avec possibilité de paiement en une, deux ou trois fois. Le montant définitif sera communiqué après validation par la direction de FEBA.",
    en: "The annual fee is not published yet. The programme will be sold as an annual package covering a full school year, with the option to pay in one, two or three instalments. The final amount will be communicated once approved by FEBA's management.",
  },
  calendarPending: {
    fr: "La date officielle de rentrée et les horaires définitifs des trois groupes seront publiés ici dès leur validation par la direction.",
    en: "The official start date and the final schedules for the three groups will be published here once approved by the management.",
  },
  faqTitle: { fr: "Questions fréquentes", en: "Frequently asked questions" },
  contactTitle: { fr: "Contacter FEBA FHA", en: "Contact FEBA FHA" },
  contactIntro: {
    fr: "Une question sur le programme, le test de placement ou l'inscription ? Notre équipe vous répond.",
    en: "A question about the programme, the placement assessment or enrollment? Our team will get back to you.",
  },
  contactForm: { fr: "Écrire à FEBA FHA", en: "Write to FEBA FHA" },
  ctaTitle: { fr: "Prêt à commencer ?", en: "Ready to get started?" },
  ctaText: {
    fr: "Remplissez la fiche de renseignements : nous vous proposerons ensuite un créneau pour le test de placement de votre enfant.",
    en: "Fill in the enrollment form: we will then offer you a slot for your child's placement assessment.",
  },
  pendingBadge: { fr: "À confirmer par la direction", en: "To be confirmed by management" },
};

const PILLAR_ICONS = [MessageCircle, Laptop, BookHeart, GraduationCap, ClipboardCheck, Users2, Globe2, Sparkles];

/** Encart réservé aux informations non encore validées par la direction. */
function PendingNotice({ children }) {
  return (
    <div className="rounded-2xl border border-feba-gold/40 bg-feba-gold/10 p-5 flex gap-3">
      <AlertCircle className="w-5 h-5 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />
      <p className="text-sm leading-relaxed">{children}</p>
    </div>
  );
}

export default function FhaPage() {
  // P1 : la langue vient du sélecteur GLOBAL du layout — plus de
  // sélecteur local ici, donc plus de doublon à l'écran.
  const { lang } = useSiteLang();
  const L = (entry) => tr(entry, lang);

  // Informations administrables du programme (tarif, rentrée, horaires...).
  const { data: programData } = useQuery({
    queryKey: ["fha-program"],
    queryFn: siteAPI.fhaProgram,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
  const program = programData?.data || {};

  const whatsapp = program.whatsapp || "";
  const whatsappHref = whatsapp
    ? `https://wa.me/${whatsapp.replace(/[^\d]/g, "")}`
    : null;

  return (
    <>
      <Seo
        title={`${FHA_NAME} — ${FHA_TAGLINE}`}
        description={
          lang === "fr"
            ? "FEBA French Heritage Academy : programme de français en ligne, culture et héritage africains pour les enfants de la diaspora aux États-Unis, au Canada et ailleurs."
            : "FEBA French Heritage Academy: online French programme, African culture and heritage for children of the diaspora in the United States, Canada and beyond."
        }
      />

      {/* ── 1. Hero ──────────────────────────────────────────────────── */}
      <div className="relative bg-feba-green">
        <SiteImage
          src="/site/img/online-visio-1600.webp"
          alt=""
          aria-hidden="true"
          eager
          className="absolute inset-0 w-full h-full object-cover opacity-20"
        />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-14 sm:py-24">
          <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">
            {FHA_SHORT}
          </p>
          <h1 className="text-white text-3xl sm:text-5xl font-bold max-w-4xl">
            {FHA_NAME}
          </h1>
          <p className="text-feba-gold mt-3 text-base sm:text-xl font-semibold italic">
            {FHA_TAGLINE}
          </p>
          <p className="text-white/90 mt-5 max-w-3xl text-sm sm:text-lg leading-relaxed">
            {L(FHA_INTRO)}
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/feba-fha/enroll"
              className="px-6 py-3 rounded-xl bg-white text-feba-green font-bold text-sm hover:bg-feba-cream transition-colors"
            >
              {L(T.enroll)}
            </Link>
            <Link
              to="/feba-fha/placement-test"
              className="px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:brightness-110 transition"
            >
              {L(T.bookTest)}
            </Link>
            <Link
              to="/feba-fha/contact"
              className="px-6 py-3 rounded-xl border border-white/50 text-white font-bold text-sm hover:bg-white/10 transition-colors"
            >
              {L(T.contactForm)}
            </Link>
            {/* Bouton WhatsApp affiché UNIQUEMENT si le numéro est validé. */}
            {whatsappHref && (
              <a
                href={whatsappHref}
                target="_blank"
                rel="noreferrer"
                className="px-6 py-3 rounded-xl bg-[#25D366] text-white font-bold text-sm hover:brightness-110 transition"
              >
                {L(T.whatsapp)}
              </a>
            )}
          </div>
        </div>

        {/* Navigation interne de la page. */}
        <nav
          aria-label={lang === "fr" ? "Sections de la page" : "Page sections"}
          className="relative border-t border-white/15 bg-feba-green/95"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 overflow-x-auto">
            <ul className="flex gap-1 py-2 min-w-max">
              {T.navSections[lang].map(([id, label]) => (
                <li key={id}>
                  <a
                    href={`#${id}`}
                    className="block px-3 py-2 text-xs font-semibold text-white/85 hover:text-white hover:bg-white/10 rounded-lg whitespace-nowrap transition-colors"
                  >
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </nav>
      </div>

      {/* ── 2. Le programme (piliers) ────────────────────────────────── */}
      <Section tone="white" id="programme">
        <SectionHeading
          overline={FHA_SHORT}
          title={lang === "fr" ? "Ce que le programme associe" : "What the programme brings together"}
        />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {FHA_PILLARS.map((pillar, i) => {
            const Icon = PILLAR_ICONS[i % PILLAR_ICONS.length];
            return (
              <div
                key={L(pillar)}
                className="rounded-2xl border border-feba-green/25 bg-feba-green/5 p-5"
              >
                <div className="w-10 h-10 rounded-xl bg-feba-green flex items-center justify-center mb-3">
                  <Icon className="w-5 h-5 text-white" aria-hidden="true" />
                </div>
                <p className="font-bold text-feba-navy text-sm">{L(pillar)}</p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── 3. Le problème rencontré par les familles ────────────────── */}
      <Section>
        <SectionHeading
          overline={lang === "fr" ? "Le constat" : "The situation"}
          title={L(T.problemTitle)}
        />
        <p className="max-w-3xl text-sm sm:text-base leading-relaxed mb-6">
          {L(T.problemIntro)}
        </p>
        <ul className="grid sm:grid-cols-2 gap-4">
          {FHA_PROBLEMS.map((p) => (
            <li
              key={L(p)}
              className="rounded-xl border border-feba-navy/10 bg-white p-4 text-sm leading-relaxed"
            >
              {L(p)}
            </li>
          ))}
        </ul>
      </Section>

      {/* ── 4. La solution FEBA FHA ──────────────────────────────────── */}
      <Section tone="white">
        <SectionHeading
          overline={FHA_SHORT}
          title={L(T.solutionTitle)}
        />
        <p className="max-w-3xl text-sm sm:text-base leading-relaxed mb-6">
          {L(T.solutionIntro)}
        </p>
        <ul className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FHA_SOLUTIONS.map((s) => (
            <li
              key={L(s)}
              className="rounded-xl bg-feba-green/5 border border-feba-green/20 p-4 text-sm font-medium text-feba-navy"
            >
              {L(s)}
            </li>
          ))}
        </ul>
      </Section>

      {/* ── 5. Mission et vision ─────────────────────────────────────── */}
      <Section>
        <div className="grid lg:grid-cols-2 gap-8">
          <div className="rounded-2xl bg-feba-navy text-white p-7">
            <h3 className="text-feba-gold font-bold uppercase tracking-[0.18em] text-xs mb-3">
              {L(T.missionTitle)}
            </h3>
            <p className="leading-relaxed text-sm sm:text-base">{L(FHA_MISSION)}</p>
          </div>
          <div className="rounded-2xl bg-feba-green text-white p-7">
            <h3 className="text-feba-gold font-bold uppercase tracking-[0.18em] text-xs mb-3">
              {L(T.visionTitle)}
            </h3>
            <p className="leading-relaxed text-sm sm:text-base">{L(FHA_VISION)}</p>
          </div>
        </div>
      </Section>

      {/* ── 6. Public cible ──────────────────────────────────────────── */}
      <Section tone="white">
        <SectionHeading overline={FHA_SHORT} title={L(T.audienceTitle)} />
        <ul className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {FHA_AUDIENCE.countries.map((c) => (
            <li
              key={L(c)}
              className="rounded-xl border border-feba-navy/10 p-4 text-sm font-semibold text-feba-navy"
            >
              {L(c)}
            </li>
          ))}
        </ul>
        <p className="font-bold text-feba-navy text-sm mb-3">
          {L(T.audienceCommunities)}
        </p>
        <div className="flex flex-wrap gap-2">
          {FHA_AUDIENCE.communities.map((c) => (
            <span
              key={c}
              className="px-3 py-1.5 rounded-lg bg-feba-cream text-feba-navy text-xs font-semibold"
            >
              {c}
            </span>
          ))}
        </div>
      </Section>

      {/* ── 7. Les trois groupes ─────────────────────────────────────── */}
      <Section id="groupes">
        <SectionHeading overline={FHA_SHORT} title={L(T.groupsTitle)} />
        <div className="grid lg:grid-cols-3 gap-6">
          {FHA_GROUPS.map((g) => (
            <article
              key={g.key}
              className="rounded-2xl bg-white border border-feba-navy/10 p-6 flex flex-col"
            >
              <p className="text-feba-green font-bold uppercase tracking-[0.15em] text-[11px]">
                {g.ages} {lang === "fr" ? "ans" : "years"}
              </p>
              <h3 className="text-xl font-bold text-feba-navy mt-1">{g.name}</h3>

              <dl className="mt-4 space-y-2 text-xs">
                <div className="flex gap-2">
                  <dt className="font-semibold text-feba-navy shrink-0">{L(T.groupSize)} :</dt>
                  <dd>{L(g.size)}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-semibold text-feba-navy shrink-0">{L(T.groupDuration)} :</dt>
                  <dd>{L(g.duration)}</dd>
                </div>
              </dl>

              <p className="font-semibold text-feba-navy text-xs mt-4 mb-2">
                {L(T.groupMethod)}
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {(lang === "fr" ? g.methods.fr : g.methods.en).map((m) => (
                  <li
                    key={m}
                    className="px-2 py-1 rounded-md bg-feba-green/10 text-feba-navy text-[11px] font-medium"
                  >
                    {m}
                  </li>
                ))}
              </ul>

              <p className="text-sm leading-relaxed mt-4 flex-1">
                <span className="font-semibold text-feba-navy">{L(T.groupGoal)} : </span>
                {L(g.goal)}
              </p>

              {g.note && (
                <p className="mt-4 text-[11px] leading-relaxed rounded-lg bg-feba-gold/10 border border-feba-gold/30 p-3">
                  {L(g.note)}
                </p>
              )}
            </article>
          ))}
        </div>
      </Section>

      {/* ── P4 : formules annuelles et flyer ─────────────────────────── */}
      <Section id="formules">
        <SectionHeading
          overline={FHA_SHORT}
          title={lang === "fr" ? "Nos formules annuelles" : "Our annual plans"}
          subtitle={
            lang === "fr"
              ? "Trois rythmes, un même programme d'héritage francophone. Tous les tarifs sont annuels et en dollars américains."
              : "Three rhythms, one same French heritage programme. All prices are annual and in US dollars."
          }
        />

        <div className="grid lg:grid-cols-3 gap-6">
          {FHA_PLANS.map((plan, index) => (
            <div
              key={plan.code}
              className={`rounded-2xl border p-6 flex flex-col ${
                index === 1
                  ? "border-feba-gold bg-white shadow-lg ring-2 ring-feba-gold/30"
                  : "border-slate-200 bg-white"
              }`}
            >
              <h3 className="text-feba-navy text-xl font-bold">
                {plan.name[lang === "fr" ? "fr" : "en"]}
              </h3>
              <p className="text-feba-gold text-2xl font-extrabold mt-1">
                {plan.price[lang === "fr" ? "fr" : "en"]}
              </p>

              <ul className="mt-4 space-y-1.5 text-sm text-slate-700 border-b border-slate-100 pb-4">
                {plan.rhythm[lang === "fr" ? "fr" : "en"].map((line) => (
                  <li key={line} className="flex gap-2">
                    <CalendarDays className="w-4 h-4 text-feba-navy/50 shrink-0 mt-0.5" aria-hidden="true" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>

              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mt-4 mb-2">
                {lang === "fr" ? "Inclus" : "Included"}
              </p>
              <ul className="space-y-1.5 text-sm text-slate-700 flex-1">
                {plan.includes[lang === "fr" ? "fr" : "en"].map((line) => (
                  <li key={line} className="flex gap-2">
                    <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" aria-hidden="true" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>

              <Link
                to="/feba-fha/enroll"
                className="mt-6 px-4 py-2.5 rounded-lg bg-feba-navy text-white text-sm font-bold text-center hover:bg-feba-navy/90 transition-colors"
              >
                {lang === "fr" ? "Choisir cette formule" : "Choose this plan"}
              </Link>
            </div>
          ))}
        </div>

        {/* Flyer officiel — consultable en grand et téléchargeable tel quel
            (le fichier servi est l'original, non recompressé). */}
        <div className="mt-10 grid md:grid-cols-[minmax(0,320px)_1fr] gap-6 items-start rounded-2xl bg-white border border-slate-200 p-6">
          <a
            href={FHA_FLYER_PATH}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-xl overflow-hidden border border-slate-200 hover:border-feba-gold transition-colors"
          >
            <img
              src={FHA_FLYER_PATH}
              alt={
                lang === "fr"
                  ? "Flyer FEBA French Heritage Academy — formules et informations pratiques"
                  : "FEBA French Heritage Academy flyer — plans and practical information"
              }
              className="w-full h-auto"
              loading="lazy"
            />
          </a>
          <div>
            <h3 className="text-feba-navy text-lg font-bold">
              {lang === "fr" ? "Le flyer officiel" : "The official flyer"}
            </h3>
            <p className="text-slate-600 text-sm mt-2">
              {lang === "fr"
                ? "Retrouvez l'essentiel du programme sur une page : formules, rythme et contacts. Idéal à partager avec votre entourage."
                : "The essentials of the programme on a single page: plans, rhythm and contacts. Easy to share with family and friends."}
            </p>
            <div className="flex flex-wrap gap-3 mt-5">
              <a
                href={FHA_FLYER_PATH}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2.5 rounded-lg border border-feba-navy text-feba-navy text-sm font-bold hover:bg-feba-navy hover:text-white transition-colors"
              >
                {lang === "fr" ? "Voir en grand" : "View full size"}
              </a>
              <a
                href={FHA_FLYER_PATH}
                download="feba-fha-flyer.jpeg"
                className="px-4 py-2.5 rounded-lg bg-feba-gold text-feba-navy text-sm font-bold hover:bg-feba-gold2 transition-colors"
              >
                {lang === "fr" ? "Télécharger le flyer" : "Download the flyer"}
              </a>
            </div>
          </div>
        </div>
      </Section>

      {/* ── 8. Organisation de l'année ───────────────────────────────── */}
      <Section tone="white" id="annee">
        <SectionHeading overline={FHA_SHORT} title={L(T.yearTitle)} />
        <div className="grid sm:grid-cols-3 gap-5 mb-8">
          {[FHA_YEAR_ORGANISATION.period, FHA_YEAR_ORGANISATION.weeks, FHA_YEAR_ORGANISATION.frequency].map((item) => (
            <div key={L(item)} className="rounded-2xl bg-feba-navy text-white p-6">
              <CalendarDays className="w-6 h-6 text-feba-gold mb-3" aria-hidden="true" />
              <p className="font-semibold text-sm">{L(item)}</p>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          <div>
            <ul className="space-y-2">
              {FHA_YEAR_ORGANISATION.extras.map((e) => (
                <li key={L(e)} className="flex gap-2.5 text-sm">
                  <Sparkles className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />
                  {L(e)}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl bg-feba-cream p-6">
            <p className="font-bold text-feba-navy text-sm mb-3">{L(T.yearVolume)}</p>
            <ul className="space-y-1.5 text-sm">
              {FHA_YEAR_ORGANISATION.volume.map((v) => (
                <li key={L(v)}>• {L(v)}</li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {/* ── 9. Programme sur cinq ans ────────────────────────────────── */}
      <Section id="cinq-ans">
        <SectionHeading overline={FHA_SHORT} title={L(T.programmeTitle)} />
        <div className="space-y-5">
          {FHA_PROGRAMME.map((y) => (
            <article
              key={y.year}
              className="rounded-2xl bg-white border border-feba-navy/10 p-6"
            >
              <div className="flex items-center gap-4 mb-4">
                <span className="w-11 h-11 rounded-xl bg-feba-green text-white font-bold flex items-center justify-center shrink-0">
                  {y.year}
                </span>
                <h3 className="text-lg font-bold text-feba-navy">
                  {lang === "fr" ? `Année ${y.year} — ` : `Year ${y.year} — `}
                  {L(y.title)}
                </h3>
              </div>
              <div className="grid md:grid-cols-3 gap-5 text-sm">
                <div>
                  <p className="font-semibold text-feba-navy text-xs uppercase tracking-wide mb-2">
                    {L(T.objectives)}
                  </p>
                  <ul className="space-y-1">
                    {(lang === "fr" ? y.objectives.fr : y.objectives.en).map((o) => (
                      <li key={o}>• {o}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="font-semibold text-feba-navy text-xs uppercase tracking-wide mb-2">
                    {L(T.outcome)}
                  </p>
                  <p className="leading-relaxed">{L(y.outcome)}</p>
                </div>
                <div>
                  <p className="font-semibold text-feba-navy text-xs uppercase tracking-wide mb-2">
                    {L(T.validation)}
                  </p>
                  <p className="leading-relaxed font-medium text-feba-green">
                    {L(y.validation)}
                  </p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Section>

      {/* ── 10. African Heritage ─────────────────────────────────────── */}
      <Section tone="white" id="heritage">
        <SectionHeading overline={FHA_SHORT} title={L(T.heritageTitle)} />
        <p className="max-w-3xl text-sm sm:text-base leading-relaxed mb-7">
          {L(T.heritageIntro)}
        </p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-10">
          {FHA_HERITAGE.map((h) => (
            <div key={h.year} className="rounded-2xl bg-feba-navy text-white p-5">
              <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.15em]">
                {lang === "fr" ? `Année ${h.year}` : `Year ${h.year}`}
              </p>
              <h3 className="font-bold text-sm mt-1 mb-3">{L(h.title)}</h3>
              <ul className="space-y-1 text-xs text-white/85">
                {(lang === "fr" ? h.items.fr : h.items.en).map((i) => (
                  <li key={i}>• {i}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <p className="font-bold text-feba-navy text-sm mb-3">{L(T.activitiesTitle)}</p>
        <div className="flex flex-wrap gap-2">
          {FHA_CULTURAL_ACTIVITIES.map((a, i) => (
            <span
              key={`${L(a)}-${i}`}
              className="px-3 py-1.5 rounded-lg bg-feba-green/10 text-feba-navy text-xs font-semibold"
            >
              {L(a)}
            </span>
          ))}
        </div>
      </Section>

      {/* ── 11. Progression et certifications ────────────────────────── */}
      <Section id="certification">
        <SectionHeading overline={FHA_SHORT} title={L(T.certificationTitle)} />
        <p className="max-w-3xl text-sm sm:text-base leading-relaxed mb-5">
          {L(T.certificationIntro)}
        </p>
        <ul className="grid sm:grid-cols-2 gap-3 mb-7">
          {FHA_CERTIFICATION_CONDITIONS.map((c) => (
            <li
              key={L(c)}
              className="flex gap-2.5 text-sm rounded-xl bg-white border border-feba-navy/10 p-4"
            >
              <ClipboardCheck className="w-4 h-4 text-feba-green shrink-0 mt-0.5" aria-hidden="true" />
              {L(c)}
            </li>
          ))}
        </ul>

        {/* Mention obligatoire sur la nature interne des certifications. */}
        <div className="rounded-2xl border-2 border-feba-gold bg-feba-gold/10 p-5 flex gap-3">
          <ShieldCheck className="w-5 h-5 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />
          <p className="text-sm leading-relaxed font-medium text-feba-navy">
            {L(FHA_CERTIFICATION_NOTICE)}
          </p>
        </div>
      </Section>

      {/* ── 12. Test de placement ────────────────────────────────────── */}
      <Section tone="white" id="test">
        <SectionHeading overline={FHA_SHORT} title={L(T.testTitle)} />
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="rounded-2xl bg-feba-green text-white p-6">
            <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.15em]">
              {L(T.testDuration)}
            </p>
            <p className="text-2xl font-bold mt-1">{L(FHA_PLACEMENT.duration)}</p>
            <p className="text-xs text-white/85 mt-4">
              {L(T.testLevels)} : {FHA_PLACEMENT.levels.map((l) => L(l)).join(" · ")}
            </p>
            <Link
              to="/feba-fha/placement-test"
              className="mt-5 inline-block px-5 py-2.5 rounded-xl bg-white text-feba-green font-bold text-xs hover:bg-feba-cream transition-colors"
            >
              {L(T.bookTest)}
            </Link>
          </div>
          <div>
            <p className="font-bold text-feba-navy text-sm mb-3">{L(T.testSkills)}</p>
            <ul className="space-y-1.5 text-sm">
              {FHA_PLACEMENT.skills.map((s) => (
                <li key={L(s)}>• {L(s)}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="font-bold text-feba-navy text-sm mb-3">{L(T.testResult)}</p>
            <ul className="space-y-1.5 text-sm">
              {FHA_PLACEMENT.result.map((r) => (
                <li key={L(r)}>• {L(r)}</li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {/* ── 13. Déroulement de l'inscription ─────────────────────────── */}
      <Section id="inscription">
        <SectionHeading overline={FHA_SHORT} title={L(T.enrollTitle)} />
        <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FHA_ENROLLMENT_STEPS.map((s, i) => (
            <li
              key={L(s)}
              className="rounded-2xl bg-white border border-feba-navy/10 p-5"
            >
              <span className="w-8 h-8 rounded-lg bg-feba-navy text-white text-sm font-bold flex items-center justify-center mb-3">
                {i + 1}
              </span>
              <p className="font-semibold text-feba-navy text-sm">{L(s)}</p>
            </li>
          ))}
        </ol>
      </Section>

      {/* ── 14. Calendrier · 15. Enseignants · 16. Tarifs ────────────── */}
      <Section tone="white" id="tarifs">
        <div className="grid lg:grid-cols-3 gap-6">
          <div>
            <h3 className="font-bold text-feba-navy mb-3">{L(T.calendarTitle)}</h3>
            {program.school_year_start_date || program.group_schedules ? (
              <ul className="text-sm space-y-1.5">
                {program.school_year_start_date && (
                  <li>• {program.school_year_start_date}</li>
                )}
                {program.group_schedules && <li>• {program.group_schedules}</li>}
              </ul>
            ) : (
              <PendingNotice>{L(T.calendarPending)}</PendingNotice>
            )}
          </div>

          <div>
            <h3 className="font-bold text-feba-navy mb-3">{L(T.teachersTitle)}</h3>
            {program.teacher_names ? (
              <p className="text-sm leading-relaxed">{program.teacher_names}</p>
            ) : (
              <PendingNotice>{L(T.teachersPending)}</PendingNotice>
            )}
          </div>

          <div>
            <h3 className="font-bold text-feba-navy mb-3">{L(T.feesTitle)}</h3>
            {program.annual_fee ? (
              <p className="text-sm leading-relaxed">
                {program.annual_fee} {program.currency}
                {program.installments_allowed
                  ? ` — ${program.installments_allowed}`
                  : ""}
              </p>
            ) : (
              /* Les trois formules annuelles sont désormais publiées plus
                 haut : afficher ici « tarif non communiqué » les
                 contredirait frontalement. On renvoie donc vers elles, tout
                 en gardant la réserve sur les modalités de paiement, qui
                 relèvent bien de la direction. */
              <div className="text-sm leading-relaxed space-y-2">
                <p>
                  {lang === "fr"
                    ? "Trois formules annuelles : Standard 699 $, Premium 999 $, Excellence 1 299 $."
                    : "Three annual plans: Standard $699, Premium $999, Excellence $1,299."}
                </p>
                <a href="#formules" className="text-feba-navy font-semibold underline">
                  {lang === "fr" ? "Voir le détail des formules" : "See full plan details"}
                </a>
                <p className="text-slate-500">
                  {lang === "fr"
                    ? "Les modalités de paiement (une, deux ou trois fois) sont précisées lors de l'entretien d'admission."
                    : "Payment terms (one, two or three instalments) are confirmed during the admission interview."}
                </p>
              </div>
            )}
          </div>
        </div>
      </Section>

      {/* ── 17. FAQ ──────────────────────────────────────────────────── */}
      <Section id="faq">
        <SectionHeading overline={FHA_SHORT} title={L(T.faqTitle)} />
        <div className="space-y-3 max-w-4xl">
          {FHA_FAQ.map((item) => (
            <details
              key={L(item.q)}
              className="group rounded-2xl bg-white border border-feba-navy/10 p-5"
            >
              <summary className="font-semibold text-feba-navy text-sm cursor-pointer list-none flex justify-between gap-4">
                {L(item.q)}
                <span className="text-feba-gold shrink-0 group-open:rotate-45 transition-transform">
                  +
                </span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed">{L(item.a)}</p>
            </details>
          ))}
        </div>
      </Section>

      {/* ── 18. Contact FEBA FHA ─────────────────────────────────────── */}
      <Section tone="white" id="contact">
        <SectionHeading overline={FHA_SHORT} title={L(T.contactTitle)} />
        <p className="max-w-3xl text-sm sm:text-base leading-relaxed mb-6">
          {L(T.contactIntro)}
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/feba-fha/contact"
            className="px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy/90 transition-colors"
          >
            {L(T.contactForm)}
          </Link>
          {whatsappHref && (
            <a
              href={whatsappHref}
              target="_blank"
              rel="noreferrer"
              className="px-6 py-3 rounded-xl bg-[#25D366] text-white font-bold text-sm hover:brightness-110 transition"
            >
              {L(T.whatsapp)} — {whatsapp}
            </a>
          )}
        </div>
      </Section>

      {/* ── 19. CTA final ────────────────────────────────────────────── */}
      <div className="bg-feba-green">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14 text-center">
          <h2 className="text-white text-2xl sm:text-3xl font-bold">
            {L(T.ctaTitle)}
          </h2>
          <p className="text-white/90 mt-3 max-w-2xl mx-auto text-sm sm:text-base">
            {L(T.ctaText)}
          </p>
          <div className="mt-7 flex flex-wrap gap-3 justify-center">
            <Link
              to="/feba-fha/enroll"
              className="px-7 py-3.5 rounded-xl bg-white text-feba-green font-bold text-sm hover:bg-feba-cream transition-colors"
            >
              {L(T.enroll)}
            </Link>
            <Link
              to="/feba-fha/placement-test"
              className="px-7 py-3.5 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:brightness-110 transition"
            >
              {L(T.bookTest)}
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
