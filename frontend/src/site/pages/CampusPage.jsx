/** Notre école / Campus — les espaces réels de FEBA à Akpakpa. */
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";

// V6 : chaque espace a une image DISTINCTE ; la bannière utilise
// campus-batiment (plus réutilisé en carte) — aucun doublon sur la page.
const SPACES = [
  {
    img: "/site/img/hero-campus-1600.webp",
    title: { fr: "Le bâtiment principal", en: "The main building" },
    desc: {
      fr: "Des salles de classe lumineuses et aérées, dans l'architecture crème et rouge caractéristique de FEBA.",
      en: "Bright, airy classrooms in FEBA's distinctive cream-and-red architecture.",
    },
  },
  {
    img: "/site/img/campus-garderie-maternelle-1600.webp",
    title: { fr: "Garderie & maternelle", en: "Nursery & kindergarten" },
    desc: {
      fr: "Un espace dédié aux plus petits, adapté à leur rythme et à leurs jeux.",
      en: "A dedicated space for the youngest children, suited to their pace and their games.",
    },
  },
  {
    img: "/site/img/campus-cour-1600.webp",
    title: { fr: "La cour de récréation", en: "The playground" },
    desc: {
      fr: "Un espace sécurisé pour jouer, courir et grandir ensemble.",
      en: "A safe space to play, run and grow up together.",
    },
  },
  {
    img: "/site/img/campus-facade-1600.webp",
    title: { fr: "L'entrée de l'école", en: "The school entrance" },
    desc: {
      fr: "Un accueil identifiable et sécurisé pour les familles, au cœur d'Akpakpa.",
      en: "A recognisable, secure welcome for families, in the heart of Akpakpa.",
    },
  },
  {
    img: "/site/img/academique-bibliotheque-1600.webp",
    title: { fr: "Le coin lecture", en: "The reading corner" },
    desc: {
      fr: "Livres en français et en anglais pour cultiver le plaisir de lire.",
      en: "Books in French and English to nurture a love of reading.",
    },
  },
];

export default function CampusPage() {
  const { lang, t } = useSiteLang();
  return (
    <>
      <Seo title={t("Notre campus", "Our campus")}
        description={t(
          "Découvrez le campus de FEBA à Akpakpa, Cotonou : salles de classe, espaces maternelle, cour de récréation et coin lecture.",
          "Discover FEBA's campus in Akpakpa, Cotonou: classrooms, kindergarten areas, playground and reading corner.",
        )} />
      <PageBanner title={t("Notre campus", "Our campus")}
        intro={t(
          "Des espaces pensés pour apprendre, jouer et s'épanouir en toute sécurité.",
          "Spaces designed for learning, playing and flourishing in complete safety.",
        )}
        image="/site/img/campus-batiment-1600.webp" />
      <Section tone="white">
        <SectionHeading
          overline={t("Le cadre", "The setting")}
          title={t("Une école vivante et accueillante", "A lively, welcoming school")} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {SPACES.map((s) => (
            <article key={s.title.fr} className="rounded-2xl bg-feba-cream shadow-md overflow-hidden">
              <div className="h-52 overflow-hidden">
                <SiteImage src={s.img} alt={tr(s.title, lang)} sizes="(min-width:1024px) 33vw, 100vw"
                  className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" />
              </div>
              <div className="p-5">
                <h3 className="font-bold text-feba-navy">{tr(s.title, lang)}</h3>
                <p className="text-sm mt-1.5 leading-relaxed">{tr(s.desc, lang)}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>
    </>
  );
}
