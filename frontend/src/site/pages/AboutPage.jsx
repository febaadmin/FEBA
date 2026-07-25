/** À propos de FEBA — mission, vision, valeurs, équipe, campus. */
import { Link } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { VALUES, WHY_FEBA } from "../content";

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
  { img: "/site/img/apropos-direction-2-1600.webp", alt: "Le directeur de FEBA à son bureau", label: "La direction", desc: "Un cap clair : l'excellence pour chaque enfant." },
  { img: "/site/img/accompagnement-duo-1600.webp", alt: "Enseignante accompagnant des élèves", label: "Les enseignants", desc: "Un accompagnement proche, en français et en anglais." },
  { img: "/site/img/apropos-equipe-pedagogique-1600.webp", alt: "L'équipe pédagogique de FEBA", label: "L'encadrement", desc: "Une équipe engagée, à l'écoute des familles." },
];

export default function AboutPage() {
  return (
    <>
      <Seo title="À propos"
        description="Faith & Excellence Bilingual Academy : notre mission, notre vision et nos valeurs. École bilingue français-anglais à Akpakpa, Cotonou." />
      <PageBanner title="À propos de FEBA"
        intro="Une école bilingue, chaleureuse et exigeante, au cœur d'Akpakpa."
        image="/site/img/campus-batiment-1600.webp" />

      <Section tone="white">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <SectionHeading center={false} overline="Qui sommes-nous ?"
              title="Développer les talents, construire l'avenir" />
            <p className="leading-relaxed">
              Faith & Excellence Bilingual Academy (FEBA) accueille les enfants de
              la garderie au CM2 dans un cadre bilingue français-anglais. Notre
              projet éducatif associe l'exigence académique, l'éducation aux
              valeurs et l'épanouissement personnel de chaque enfant.
            </p>
            <p className="mt-3 leading-relaxed">
              <strong className="text-feba-navy">Notre mission</strong> — révéler le potentiel de
              chaque élève et lui donner les outils pour réussir, en français
              comme en anglais.
            </p>
            <p className="mt-3 leading-relaxed">
              <strong className="text-feba-navy">Notre vision</strong> — une génération d'enfants
              enracinés dans leurs valeurs, fiers de leur culture et ouverts sur
              le monde.
            </p>
          </div>
          <SiteImage src="/site/img/apropos-equipe-1600.webp" alt="L'équipe pédagogique de FEBA"
            sizes="(min-width:1024px) 50vw, 100vw" className="rounded-3xl shadow-xl object-cover w-full h-72 sm:h-96" />
        </div>
      </Section>

      <Section>
        <SectionHeading overline="Ce qui nous guide" title="Nos valeurs" />
        <div className="grid sm:grid-cols-3 gap-6">
          {VALUES.map((v) => (
            <div key={v.title} className="rounded-2xl bg-white shadow-md p-6 text-center">
              <div className="w-12 h-12 rounded-xl bg-feba-gold/15 flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-6 h-6 text-feba-gold" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-feba-navy text-lg">{v.title}</h3>
              <p className="text-sm mt-2 leading-relaxed">{v.desc}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-sm mt-8 max-w-2xl mx-auto">
          À ces trois piliers s'ajoutent la foi, la discipline, la bienveillance,
          l'ouverture culturelle et le goût de la réussite.
        </p>
      </Section>

      <Section tone="white">
        <SectionHeading overline="L'encadrement" title="Une équipe engagée" />
        <div className="grid sm:grid-cols-3 gap-6">
          {TEAM_CARDS.map((card) => (
            <MediaFrame key={card.label} src={card.img} alt={card.alt}
              overlay="bottom-navy" sizes="(min-width:640px) 33vw, 100vw"
              className="h-72 rounded-2xl shadow-md"
              contentClass="p-5 flex flex-col justify-end">
              <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.18em]">{card.label}</p>
              <p className="text-white/90 text-sm mt-1 leading-snug drop-shadow">{card.desc}</p>
            </MediaFrame>
          ))}
        </div>
        <p className="text-center text-sm mt-6 max-w-2xl mx-auto">
          Direction, enseignants et personnel d'accueil travaillent main dans la
          main avec les familles, dans un esprit de proximité et d'écoute.
        </p>
      </Section>

      <Section tone="navy">
        <SectionHeading light overline="Nos engagements" title="Ce que FEBA apporte à votre enfant" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {WHY_FEBA.map((item) => (
            <div key={item.title} className="rounded-2xl bg-white/5 border border-white/10 p-6">
              <h3 className="font-bold text-white">{item.title}</h3>
              <p className="text-sm text-white/75 mt-2 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-10">
          <Link to="/campus" className="inline-flex items-center gap-2 text-feba-gold font-bold text-sm hover:text-white transition-colors">
            Découvrir notre campus <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </Section>
    </>
  );
}
