/** Admissions & inscriptions — parcours d'admission + formulaire de préinscription. */
import { CalendarCheck, ClipboardList, MessagesSquare, School } from "lucide-react";
import Seo from "../components/Seo";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { PreRegistrationForm } from "../components/PublicForms";
import { useSiteSettings } from "../SiteLayout";

const STEPS = [
  { icon: ClipboardList, title: "1. Préinscription", desc: "Remplissez le formulaire ci-dessous : il ne prend que quelques minutes." },
  { icon: MessagesSquare, title: "2. Échange avec l'équipe", desc: "Notre équipe vous contacte pour répondre à vos questions et préparer la visite." },
  { icon: School, title: "3. Visite de l'école", desc: "Venez découvrir le campus, rencontrer les enseignants et sentir l'esprit FEBA." },
  { icon: CalendarCheck, title: "4. Finalisation", desc: "Constitution du dossier et confirmation de l'inscription de votre enfant." },
];

export default function AdmissionsPage() {
  const settings = useSiteSettings();
  return (
    <>
      <Seo title="Admissions et inscriptions"
        description="Inscrivez votre enfant à FEBA : préinscription en ligne, visite de l'école et accompagnement de l'équipe. Garderie, maternelle et primaire à Cotonou." />
      <PageBanner title="Admissions & inscriptions"
        intro="Rejoindre FEBA est simple : préinscription en ligne, échange avec l'équipe, visite du campus."
        image="/site/img/hero-admissions-1600.webp" />

      <Section tone="white">
        <SectionHeading overline="Comment ça marche" title="Le parcours d'admission" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {STEPS.map((s) => (
            <div key={s.title} className="rounded-2xl bg-feba-cream border border-feba-gold/25 p-6">
              <div className="w-11 h-11 rounded-xl bg-feba-navy flex items-center justify-center mb-4">
                <s.icon className="w-5 h-5 text-feba-gold" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-feba-navy text-sm">{s.title}</h3>
              <p className="text-xs mt-2 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section>
        <div className="grid lg:grid-cols-5 gap-10 items-start">
          <div className="lg:col-span-2 space-y-5">
            <SectionHeading center={false} overline="Bienvenue"
              title="Une équipe à votre écoute"
              intro="Chaque famille est reçue personnellement : votre projet pour votre enfant est aussi le nôtre." />
            {/* V5 : la zone crème à gauche porte un dégradé marine + légende ;
                point focal sur la scène d'accueil (droite du visuel). */}
            <MediaFrame src="/site/img/admissions-accueil-1600.webp"
              alt="Famille reçue à l'accueil de FEBA"
              overlay="left-navy" sizes="(min-width:1024px) 40vw, 100vw"
              className="rounded-2xl shadow-lg h-56"
              contentClass="p-5 flex flex-col justify-center items-start max-w-[58%]">
              <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.18em]">Admissions</p>
              <p className="text-white font-bold text-lg leading-snug mt-1.5 drop-shadow">
                L'accueil des familles
              </p>
            </MediaFrame>
            <MediaFrame src="/site/img/admissions-famille-1600.webp"
              alt="Famille visitant l'école"
              overlay="bottom-navy" sizes="(min-width:1024px) 40vw, 100vw"
              className="rounded-2xl shadow-lg h-56"
              contentClass="p-5 flex flex-col justify-end">
              <p className="text-white/90 text-sm font-semibold drop-shadow">La visite du campus</p>
            </MediaFrame>
            {settings.phone && (
              <p className="text-sm">
                Vous préférez le téléphone ? Appelez-nous au{" "}
                <a href={`tel:${settings.phone.replace(/\s/g, "")}`} className="font-bold text-feba-navy hover:text-feba-gold">
                  {settings.phone}
                </a>.
              </p>
            )}
          </div>
          <div className="lg:col-span-3 rounded-3xl bg-white shadow-xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-feba-navy mb-1">Formulaire de préinscription</h2>
            <p className="text-sm text-feba-gray mb-6">
              Les champs marqués d'un astérisque (*) sont obligatoires.
            </p>
            <PreRegistrationForm />
          </div>
        </div>
      </Section>
    </>
  );
}
