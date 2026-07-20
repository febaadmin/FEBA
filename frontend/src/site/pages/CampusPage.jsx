/** Notre école / Campus — les espaces réels de FEBA à Akpakpa. */
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";

// V6 : chaque espace a une image DISTINCTE ; la bannière utilise
// campus-batiment (plus réutilisé en carte) — aucun doublon sur la page.
const SPACES = [
  { img: "/site/img/hero-campus-1600.webp", title: "Le bâtiment principal", desc: "Des salles de classe lumineuses et aérées, dans l'architecture crème et rouge caractéristique de FEBA." },
  { img: "/site/img/campus-garderie-maternelle-1600.webp", title: "Garderie & maternelle", desc: "Un espace dédié aux plus petits, adapté à leur rythme et à leurs jeux." },
  { img: "/site/img/campus-cour-1600.webp", title: "La cour de récréation", desc: "Un espace sécurisé pour jouer, courir et grandir ensemble." },
  { img: "/site/img/campus-facade-1600.webp", title: "L'entrée de l'école", desc: "Un accueil identifiable et sécurisé pour les familles, au cœur d'Akpakpa." },
  { img: "/site/img/academique-bibliotheque-1600.webp", title: "Le coin lecture", desc: "Livres en français et en anglais pour cultiver le plaisir de lire." },
];

export default function CampusPage() {
  return (
    <>
      <Seo title="Notre campus"
        description="Découvrez le campus de FEBA à Akpakpa, Cotonou : salles de classe, espaces maternelle, cour de récréation et coin lecture." />
      <PageBanner title="Notre campus"
        intro="Des espaces pensés pour apprendre, jouer et s'épanouir en toute sécurité."
        image="/site/img/campus-batiment-1600.webp" />
      <Section tone="white">
        <SectionHeading overline="Le cadre" title="Une école vivante et accueillante" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {SPACES.map((s) => (
            <article key={s.title} className="rounded-2xl bg-feba-cream shadow-md overflow-hidden">
              <div className="h-52 overflow-hidden">
                <SiteImage src={s.img} alt={s.title} sizes="(min-width:1024px) 33vw, 100vw"
                  className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" />
              </div>
              <div className="p-5">
                <h3 className="font-bold text-feba-navy">{s.title}</h3>
                <p className="text-sm mt-1.5 leading-relaxed">{s.desc}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>
    </>
  );
}
