/** À propos de FEBA — mission, vision, valeurs, équipe, campus. */
import { Link } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { VALUES, WHY_FEBA } from "../content";
import { tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";

/* V5 — section équipe harmonisée : même hauteur, point focal individuel et
   légende posée sur un voile marine identique sur les trois cartes.
   V6.1 — trois catégories RÉELLEMENT distinctes, aucune personne en double :
   « La direction » = portrait du directeur (une seule photo de lui, l'ancienne
   image « bureau » qui faisait doublon est retirée du site) ; « Les
   enseignants » = accompagnement en classe ; « L'encadrement » = vraie photo
   de l'équipe pédagogique fournie. */
const TEAM_CARDS = [
  // V6.2 — « La direction » : photo « Bonne image » demandée (directeur à son
  // bureau, vue large, mains visibles, logo FEBA en arrière-plan).
  {
    img: "/site/img/apropos-direction-2-1600.webp",
    alt: { fr: "Le directeur de FEBA à son bureau", en: "The head of FEBA at his desk" },
    label: { fr: "La direction", en: "Leadership" },
    desc: { fr: "Un cap clair : l'excellence pour chaque enfant.", en: "A clear course: excellence for every child." },
  },
  {
    img: "/site/img/accompagnement-duo-1600.webp",
    alt: { fr: "Enseignante accompagnant des élèves", en: "A teacher supporting pupils" },
    label: { fr: "Les enseignants", en: "Teachers" },
    desc: { fr: "Un accompagnement proche, en français et en anglais.", en: "Close support, in French and in English." },
  },
  {
    img: "/site/img/apropos-equipe-pedagogique-1600.webp",
    alt: { fr: "L'équipe pédagogique de FEBA", en: "The FEBA teaching team" },
    label: { fr: "L'encadrement", en: "Staff" },
    desc: { fr: "Une équipe engagée, à l'écoute des familles.", en: "A committed team that listens to families." },
  },
];

export default function AboutPage() {
  const { lang, t } = useSiteLang();
  return (
    <>
      <Seo title={t("À propos", "About")}
        description={t(
          "Faith & Excellence Bilingual Academy : notre mission, notre vision et nos valeurs. École bilingue français-anglais à Akpakpa, Cotonou.",
          "Faith & Excellence Bilingual Academy: our mission, vision and values. A French-English bilingual school in Akpakpa, Cotonou.",
        )} />
      <PageBanner title={t("À propos de FEBA", "About FEBA")}
        intro={t(
          "Une école bilingue, chaleureuse et exigeante, au cœur d'Akpakpa.",
          "A bilingual school — warm and demanding — in the heart of Akpakpa.",
        )}
        image="/site/img/campus-batiment-1600.webp" />

      <Section tone="white">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <SectionHeading center={false}
              overline={t("Qui sommes-nous ?", "Who we are")}
              title={t("Développer les talents, construire l'avenir", "Developing talent, building the future")} />
            <p className="leading-relaxed">
              {t(
                "Faith & Excellence Bilingual Academy (FEBA) accueille les enfants de la garderie au CM2 dans un cadre bilingue français-anglais. Notre projet éducatif associe l'exigence académique, l'éducation aux valeurs et l'épanouissement personnel de chaque enfant.",
                "Faith & Excellence Bilingual Academy (FEBA) welcomes children from nursery to Year 6 in a French-English bilingual setting. Our educational approach combines academic rigour, values-based education and the personal growth of every child.",
              )}
            </p>
            <p className="mt-3 leading-relaxed">
              <strong className="text-feba-navy">{t("Notre mission", "Our mission")}</strong>{" — "}
              {t(
                "révéler le potentiel de chaque élève et lui donner les outils pour réussir, en français comme en anglais.",
                "to reveal every pupil's potential and give them the tools to succeed, in French as well as in English.",
              )}
            </p>
            <p className="mt-3 leading-relaxed">
              <strong className="text-feba-navy">{t("Notre vision", "Our vision")}</strong>{" — "}
              {t(
                "une génération d'enfants enracinés dans leurs valeurs, fiers de leur culture et ouverts sur le monde.",
                "a generation of children rooted in their values, proud of their culture and open to the world.",
              )}
            </p>
          </div>
          <SiteImage src="/site/img/apropos-equipe-1600.webp" alt={t("L'équipe pédagogique de FEBA", "The FEBA teaching team")}
            sizes="(min-width:1024px) 50vw, 100vw" className="rounded-3xl shadow-xl object-cover w-full h-72 sm:h-96" />
        </div>
      </Section>

      <Section>
        <SectionHeading overline={t("Ce qui nous guide", "What guides us")} title={t("Nos valeurs", "Our values")} />
        <div className="grid sm:grid-cols-3 gap-6">
          {VALUES.map((v) => (
            <div key={v.title.fr} className="rounded-2xl bg-white shadow-md p-6 text-center">
              <div className="w-12 h-12 rounded-xl bg-feba-gold/15 flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-6 h-6 text-feba-gold" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-feba-navy text-lg">{tr(v.title, lang)}</h3>
              <p className="text-sm mt-2 leading-relaxed">{tr(v.desc, lang)}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-sm mt-8 max-w-2xl mx-auto">
          {t(
            "À ces trois piliers s'ajoutent la foi, la discipline, la bienveillance, l'ouverture culturelle et le goût de la réussite.",
            "These three pillars are joined by faith, discipline, kindness, cultural openness and a taste for achievement.",
          )}
        </p>
      </Section>

      <Section tone="white">
        <SectionHeading overline={t("L'encadrement", "Our staff")} title={t("Une équipe engagée", "A committed team")} />
        <div className="grid sm:grid-cols-3 gap-6">
          {TEAM_CARDS.map((card) => (
            <MediaFrame key={card.label.fr} src={card.img} alt={tr(card.alt, lang)}
              overlay="bottom-navy" sizes="(min-width:640px) 33vw, 100vw"
              className="h-72 rounded-2xl shadow-md"
              contentClass="p-5 flex flex-col justify-end">
              <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.18em]">{tr(card.label, lang)}</p>
              <p className="text-white/90 text-sm mt-1 leading-snug drop-shadow">{tr(card.desc, lang)}</p>
            </MediaFrame>
          ))}
        </div>
        <p className="text-center text-sm mt-6 max-w-2xl mx-auto">
          {t(
            "Direction, enseignants et personnel d'accueil travaillent main dans la main avec les familles, dans un esprit de proximité et d'écoute.",
            "Leadership, teachers and front-desk staff work hand in hand with families, in a spirit of closeness and attentiveness.",
          )}
        </p>
      </Section>

      <Section tone="navy">
        <SectionHeading light
          overline={t("Nos engagements", "Our commitments")}
          title={t("Ce que FEBA apporte à votre enfant", "What FEBA brings your child")} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {WHY_FEBA.map((item) => (
            <div key={item.title.fr} className="rounded-2xl bg-white/5 border border-white/10 p-6">
              <h3 className="font-bold text-white">{tr(item.title, lang)}</h3>
              <p className="text-sm text-white/75 mt-2 leading-relaxed">{tr(item.desc, lang)}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-10">
          <Link to="/campus" className="inline-flex items-center gap-2 text-feba-gold font-bold text-sm hover:text-white transition-colors">
            {t("Découvrir notre campus", "Discover our campus")} <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </Section>
    </>
  );
}
