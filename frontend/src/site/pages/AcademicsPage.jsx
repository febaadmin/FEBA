/** Programmes académiques — niveaux, bilinguisme, matières et méthodes. */
import { Link } from "react-router-dom";
import { BookOpen, ArrowRight } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { LEVELS } from "../content";

const PILLARS = [
  { img: "/site/img/academique-classe-1600.webp", title: "Fondamentaux solides", desc: "Lecture, écriture, mathématiques : des bases solides construites pas à pas, en français et en anglais." },
  { img: "/site/img/academique-sciences-1600.webp", title: "Sciences & découverte", desc: "Expériences, observation et curiosité : les sciences s'apprennent en manipulant." },
  { img: "/site/img/academique-numerique-1600.webp", title: "Numérique & robotique", desc: "Premiers pas guidés avec l'ordinateur et la robotique éducative." },
  { img: "/site/img/academique-carte-1600.webp", title: "Ouverture sur le monde", desc: "Géographie, cultures et langues : comprendre le monde pour mieux y trouver sa place." },
];

export default function AcademicsPage() {
  return (
    <>
      <Seo title="Programmes académiques"
        description="Les programmes de FEBA de la garderie au CM2 : enseignement bilingue français-anglais, sciences, numérique et suivi personnalisé." />
      <PageBanner title="Programmes académiques"
        intro="Un parcours bilingue exigeant et bienveillant, de la garderie au CM2."
        image="/site/img/academique-classe-1600.webp" />

      {/* Bilinguisme */}
      <Section tone="white" id="bilinguisme">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <SectionHeading center={false} overline="Notre spécificité"
              title="Un enseignement réellement bilingue" />
            <p className="leading-relaxed">
              Le <strong className="text-feba-navy">français</strong> est la langue des apprentissages
              fondamentaux ; l'<strong className="text-feba-navy">anglais</strong> est pratiqué chaque
              jour — en classe, dans les activités et dans la vie de l'école.
              Les évaluations et les bulletins reflètent les deux parcours, avec
              une moyenne bilingue officielle.
            </p>
            <ul className="mt-5 space-y-3 text-sm">
              {["Immersion progressive dès le plus jeune âge",
                "Manuels et supports dans les deux langues",
                "Expression orale valorisée en français et en anglais",
                "Suivi individualisé des progrès dans chaque langue"].map((li) => (
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
            alt="Enseignante FEBA accompagnant deux élèves en classe"
            overlay="left-navy-md" sizes="(min-width:1024px) 50vw, 100vw"
            className="rounded-3xl shadow-xl h-80 sm:h-[28rem]"
            contentClass="p-6 sm:p-8 flex flex-col justify-end sm:justify-start items-start max-w-full sm:max-w-[46%]">
            <p className="text-feba-gold text-[11px] sm:text-xs font-bold uppercase tracking-[0.18em]">Français · English</p>
            <p className="text-white font-bold text-lg sm:text-2xl leading-snug mt-2 drop-shadow">
              Deux langues, un monde d'opportunités
            </p>
          </MediaFrame>
        </div>
      </Section>

      {/* Niveaux */}
      <Section>
        <SectionHeading overline="Le parcours" title="Nos niveaux, de la garderie au CM2"
          intro="Garderie, Maternelle 1 et 2, CI, CP, CE1, CE2, CM1 et CM2 : chaque étape prépare la suivante." />
        <div className="space-y-6">
          {LEVELS.map((lvl, i) => (
            <article key={lvl.name}
              className={`grid md:grid-cols-2 gap-6 items-center rounded-3xl bg-white shadow-md overflow-hidden ${i % 2 ? "md:[&>*:first-child]:order-2" : ""}`}>
              <div className="h-56 md:h-64">
                <SiteImage src={lvl.img} alt={`${lvl.name} à FEBA`} sizes="(min-width:768px) 50vw, 100vw"
                  className="w-full h-full object-cover" />
              </div>
              <div className="p-6 md:p-8">
                <h3 className="text-xl font-bold text-feba-navy">{lvl.name}</h3>
                <p className="mt-3 text-sm leading-relaxed">{lvl.desc}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>

      {/* Piliers pédagogiques */}
      <Section tone="white">
        <SectionHeading overline="Nos méthodes" title="Quatre piliers pédagogiques" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {PILLARS.map((p) => (
            <article key={p.title} className="rounded-2xl bg-feba-cream shadow-md overflow-hidden">
              <div className="h-40 overflow-hidden">
                <SiteImage src={p.img} alt={p.title} sizes="(min-width:1024px) 25vw, 50vw"
                  className="w-full h-full object-cover" />
              </div>
              <div className="p-4">
                <h3 className="font-bold text-feba-navy text-sm">{p.title}</h3>
                <p className="text-xs mt-1.5 leading-relaxed">{p.desc}</p>
              </div>
            </article>
          ))}
        </div>
        <div className="text-center mt-10">
          <Link to="/admissions"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-navy text-white font-bold text-sm hover:bg-feba-navy2 transition-colors">
            Inscrire mon enfant <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </Section>
    </>
  );
}
