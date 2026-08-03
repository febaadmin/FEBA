/** Programmes académiques — niveaux, bilinguisme, matières et méthodes. */
import { Link } from "react-router-dom";
import { BookOpen, ArrowRight } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { LEVELS } from "../content";
import { tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";

const PILLARS = [
  {
    img: "/site/img/academique-classe-1600.webp",
    title: { fr: "Fondamentaux solides", en: "Solid fundamentals" },
    desc: {
      fr: "Lecture, écriture, mathématiques : des bases solides construites pas à pas, en français et en anglais.",
      en: "Reading, writing, mathematics: firm foundations built step by step, in French and in English.",
    },
  },
  {
    img: "/site/img/academique-sciences-1600.webp",
    title: { fr: "Sciences & découverte", en: "Science & discovery" },
    desc: {
      fr: "Expériences, observation et curiosité : les sciences s'apprennent en manipulant.",
      en: "Experiments, observation and curiosity: science is learnt by doing.",
    },
  },
  {
    img: "/site/img/academique-numerique-1600.webp",
    title: { fr: "Numérique & robotique", en: "Digital & robotics" },
    desc: {
      fr: "Premiers pas guidés avec l'ordinateur et la robotique éducative.",
      en: "Guided first steps with computers and educational robotics.",
    },
  },
  {
    img: "/site/img/academique-carte-1600.webp",
    title: { fr: "Ouverture sur le monde", en: "Openness to the world" },
    desc: {
      fr: "Géographie, cultures et langues : comprendre le monde pour mieux y trouver sa place.",
      en: "Geography, cultures and languages: understanding the world to find one's place in it.",
    },
  },
];

export default function AcademicsPage() {
  const { lang, t } = useSiteLang();
  return (
    <>
      <Seo title={t("Programmes académiques", "Academic programmes")}
        description={t(
          "Les programmes de FEBA de la garderie au CM2 : enseignement bilingue français-anglais, sciences, numérique et suivi personnalisé.",
          "FEBA's programmes from nursery to Year 6: French-English bilingual teaching, science, digital skills and personalised follow-up.",
        )} />
      <PageBanner title={t("Programmes académiques", "Academic programmes")}
        intro={t(
          "Un parcours bilingue exigeant et bienveillant, de la garderie au CM2.",
          "A demanding, caring bilingual pathway from nursery to Year 6.",
        )}
        image="/site/img/academique-classe-1600.webp" />

      {/* Bilinguisme */}
      <Section tone="white" id="bilinguisme">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <SectionHeading center={false}
              overline={t("Notre spécificité", "What sets us apart")}
              title={t("Un enseignement réellement bilingue", "Genuinely bilingual teaching")} />
            <p className="leading-relaxed">
              {t(
                "Le français est la langue des apprentissages fondamentaux ; l'anglais est pratiqué chaque jour — en classe, dans les activités et dans la vie de l'école. Les évaluations et les bulletins reflètent les deux parcours, avec une moyenne bilingue officielle.",
                "French is the language of core learning; English is used every day — in class, in activities and in school life. Assessments and report cards reflect both pathways, with an official bilingual average.",
              )}
            </p>
            <ul className="mt-5 space-y-3 text-sm">
              {[
                t("Immersion progressive dès le plus jeune âge", "Gradual immersion from the earliest age"),
                t("Manuels et supports dans les deux langues", "Textbooks and materials in both languages"),
                t("Expression orale valorisée en français et en anglais", "Speaking skills valued in French and in English"),
                t("Suivi individualisé des progrès dans chaque langue", "Individual tracking of progress in each language"),
              ].map((li) => (
                <li key={li} className="flex gap-3">
                  <BookOpen className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />{li}
                </li>
              ))}
            </ul>
          </div>
          {/* V5 : la zone crème à gauche du visuel devient une composition
              intentionnelle — dégradé marine + message bilinguisme. */}
          {/* V6.2 — cadrage corrigé : conteneur plus haut + point focal descendu
              (mediaMeta 50/66) pour montrer la tête entière de l'enseignante, son
              buste et les têtes/bustes des enfants (fini les têtes coupées) ; le
              texte est resserré pour ne pas masquer la scène pédagogique. */}
          <MediaFrame src="/site/img/bilingue-accompagnement-1600.webp"
            alt={t("Enseignante FEBA accompagnant deux élèves en classe", "A FEBA teacher supporting two pupils in class")}
            overlay="left-navy-md" sizes="(min-width:1024px) 50vw, 100vw"
            className="rounded-3xl shadow-xl h-80 sm:h-[28rem]"
            contentClass="p-6 sm:p-8 flex flex-col justify-end sm:justify-start items-start max-w-full sm:max-w-[46%]">
            <p className="text-feba-gold text-[11px] sm:text-xs font-bold uppercase tracking-[0.18em]">Français · English</p>
            <p className="text-white font-bold text-lg sm:text-2xl leading-snug mt-2 drop-shadow">
              {t("Deux langues, un monde d'opportunités", "Two languages, a world of opportunity")}
            </p>
          </MediaFrame>
        </div>
      </Section>

      {/* Niveaux */}
      <Section>
        <SectionHeading
          overline={t("Le parcours", "The pathway")}
          title={t("Nos niveaux, de la garderie au CM2", "Our year groups, from nursery to Year 6")}
          intro={t(
            "Garderie, Maternelle 1 et 2, CI, CP, CE1, CE2, CM1 et CM2 : chaque étape prépare la suivante.",
            "Nursery, Kindergarten 1 and 2, CI, CP, CE1, CE2, CM1 and CM2: each stage prepares the next.",
          )} />
        <div className="space-y-6">
          {LEVELS.map((lvl, i) => (
            <article key={lvl.name.fr}
              className={`grid md:grid-cols-2 gap-6 items-center rounded-3xl bg-white shadow-md overflow-hidden ${i % 2 ? "md:[&>*:first-child]:order-2" : ""}`}>
              <div className="h-56 md:h-64">
                <SiteImage src={lvl.img}
                  alt={t(`${tr(lvl.name, lang)} à FEBA`, `${tr(lvl.name, lang)} at FEBA`)}
                  sizes="(min-width:768px) 50vw, 100vw"
                  className="w-full h-full object-cover" />
              </div>
              <div className="p-6 md:p-8">
                <h3 className="text-xl font-bold text-feba-navy">{tr(lvl.name, lang)}</h3>
                <p className="mt-3 text-sm leading-relaxed">{tr(lvl.desc, lang)}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>

      {/* Piliers pédagogiques */}
      <Section tone="white">
        <SectionHeading
          overline={t("Nos méthodes", "Our methods")}
          title={t("Quatre piliers pédagogiques", "Four teaching pillars")} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {PILLARS.map((p) => (
            <article key={p.title.fr} className="rounded-2xl bg-feba-cream shadow-md overflow-hidden">
              <div className="h-40 overflow-hidden">
                <SiteImage src={p.img} alt={tr(p.title, lang)} sizes="(min-width:1024px) 25vw, 50vw"
                  className="w-full h-full object-cover" />
              </div>
              <div className="p-4">
                <h3 className="font-bold text-feba-navy text-sm">{tr(p.title, lang)}</h3>
                <p className="text-xs mt-1.5 leading-relaxed">{tr(p.desc, lang)}</p>
              </div>
            </article>
          ))}
        </div>
        <div className="text-center mt-10">
          <Link to="/admissions"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy2 transition-colors">
            {t("Inscrire mon enfant", "Enrol my child")} <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </Section>
    </>
  );
}
