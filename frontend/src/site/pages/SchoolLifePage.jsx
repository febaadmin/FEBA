/** Vie scolaire & activités parascolaires — uniquement les activités réellement illustrées. */
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { ACTIVITIES } from "../content";

export default function SchoolLifePage() {
  return (
    <>
      <Seo title="Vie scolaire et activités"
        description="La vie à FEBA : musique, percussions, arts plastiques, sport, sciences, expression orale et jeux éducatifs." />
      <PageBanner title="La vie à FEBA"
        intro="Apprendre, oui — mais aussi jouer, créer, chanter et grandir ensemble."
        image="/site/img/activite-musique-groupe-1600.webp" />

      <Section tone="white">
        <SectionHeading overline="Épanouissement" title="Nos activités"
          intro="Chaque activité développe une compétence : créativité, confiance, esprit d'équipe et curiosité." />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {ACTIVITIES.map((act) => (
            <article key={act.title} className="rounded-2xl bg-feba-cream shadow-md overflow-hidden group">
              <div className="h-52 overflow-hidden">
                <SiteImage src={act.img} alt={act.title} sizes="(min-width:1024px) 33vw, 100vw"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              </div>
              <div className="p-5">
                <h3 className="font-bold text-feba-navy">{act.title}</h3>
                <p className="text-sm mt-1.5 leading-relaxed">{act.desc}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>

      <Section tone="navy">
        <div className="grid lg:grid-cols-2 gap-10 items-center">
          {/* V6 : conteneur plus haut (4:3) → object-cover recadre les côtés et
              élimine la bande crème à gauche ; focal poussé sur la ronde à
              droite ; léger dégradé gauche pour fondre tout résidu crème. */}
          <MediaFrame src="/site/img/activite-ronde-1600.webp"
            alt="Ronde d'enfants dans la cour de FEBA"
            overlay="left-navy" sizes="(min-width:1024px) 50vw, 100vw"
            position="74% 60%" mobilePosition="76% 62%"
            className="rounded-3xl shadow-xl aspect-[5/4] sm:aspect-[16/11]" />
          <div>
            <SectionHeading center={false} light overline="Développement personnel"
              title="Grandir en confiance" />
            <p className="text-white/85 leading-relaxed">
              Prendre la parole devant la classe, chanter dans l'orchestre de
              l'école, défendre les couleurs de son équipe : à FEBA, chaque
              enfant trouve un espace pour s'exprimer et prendre confiance en
              lui — dans le respect des autres et la joie de faire ensemble.
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
