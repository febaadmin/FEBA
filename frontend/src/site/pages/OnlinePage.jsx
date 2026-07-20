/** FEBA Online — programme international pour la diaspora (identité verte). */
import { Link } from "react-router-dom";
import { Globe2, Laptop, Users2, BookHeart } from "lucide-react";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading } from "../components/SiteSection";
import { ONLINE_FEATURES } from "../content";

const CARDS = [
  { icon: Laptop, title: "Cours en ligne vivants", desc: "Des séances interactives en visioconférence, pensées pour les enfants." },
  { icon: Users2, title: "Petits groupes", desc: "Des effectifs réduits pour que chaque enfant participe et progresse." },
  { icon: BookHeart, title: "Français vivant", desc: "Lire, parler et écrire en français avec des enseignants qualifiés." },
  { icon: Globe2, title: "Culture & héritage", desc: "Contes, musique et patrimoine africains au cœur du programme." },
];

export default function OnlinePage() {
  return (
    <>
      <Seo title="FEBA Online — Programme international"
        description="FEBA Online : cours de français en ligne, culture et patrimoine africains pour les enfants de la diaspora, en petits groupes." />

      {/* Bannière verte spécifique FEBA Online */}
      <div className="relative bg-feba-green">
        <SiteImage src="/site/img/online-visio-1600.webp" alt="" aria-hidden="true" eager
          className="absolute inset-0 w-full h-full object-cover opacity-20" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
          <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">
            Programme international
          </p>
          <h1 className="text-white text-3xl sm:text-5xl font-bold">FEBA Online</h1>
          <p className="text-white/90 mt-4 max-w-2xl text-sm sm:text-lg">
            Le français, la culture et le patrimoine africains, transmis en
            ligne aux enfants de la diaspora — où que vous soyez dans le monde.
          </p>
          <div className="w-16 h-1 bg-feba-gold rounded mt-6" />
        </div>
      </div>

      <Section tone="white">
        <SectionHeading overline="Le programme" title="Ce que votre enfant y trouvera" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {CARDS.map((c) => (
            <div key={c.title} className="rounded-2xl border border-feba-green/25 bg-feba-green/5 p-6">
              <div className="w-11 h-11 rounded-xl bg-feba-green flex items-center justify-center mb-4">
                <c.icon className="w-5 h-5 text-white" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-feba-navy text-sm">{c.title}</h3>
              <p className="text-xs mt-2 leading-relaxed">{c.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section>
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div className="grid grid-cols-2 gap-4">
            {/* V5 : zone crème gauche → dégradé vert FEBA Online + légende. */}
            <MediaFrame src="/site/img/online-cours-francais-1600.webp"
              alt="Cours de français en ligne FEBA"
              overlay="left-green" sizes="(min-width:1024px) 50vw, 100vw"
              className="rounded-2xl shadow-lg h-48 col-span-2"
              contentClass="p-5 flex flex-col justify-center items-start max-w-[55%]">
              <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.18em]">FEBA Online</p>
              <p className="text-white font-bold text-lg leading-snug mt-1.5 drop-shadow">
                Le français en direct, où que vous soyez
              </p>
            </MediaFrame>
            <SiteImage src="/site/img/online-lecon-1600.webp" alt="Enfant suivant une leçon FEBA Online"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl shadow-lg object-cover w-full h-44" />
            <SiteImage src="/site/img/activite-percussions-1600.webp" alt="Percussions et culture africaine"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl shadow-lg object-cover w-full h-44" />
          </div>
          <div>
            <SectionHeading center={false} overline="Pour qui ?"
              title="Un pont entre vos enfants et leurs racines" />
            <ul className="space-y-3 text-sm">
              {ONLINE_FEATURES.map((f) => (
                <li key={f} className="flex gap-3">
                  <Globe2 className="w-4 h-4 text-feba-green shrink-0 mt-0.5" aria-hidden="true" />{f}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-3 mt-7">
              <Link to="/admissions"
                className="px-6 py-3 rounded-xl bg-feba-green text-white font-bold text-sm hover:bg-feba-green2 transition-colors">
                Préinscrire mon enfant
              </Link>
              <Link to="/contact"
                className="px-6 py-3 rounded-xl border border-feba-green text-feba-green font-bold text-sm hover:bg-feba-green/10 transition-colors">
                Poser une question
              </Link>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
