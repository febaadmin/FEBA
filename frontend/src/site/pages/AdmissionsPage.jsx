/** Admissions & inscriptions — parcours d'admission + formulaire de préinscription. */
import { CalendarCheck, ClipboardList, MessagesSquare, School } from "lucide-react";
import Seo from "../components/Seo";
import MediaFrame from "../components/MediaFrame";
import { Section, SectionHeading, PageBanner } from "../components/SiteSection";
import { PreRegistrationForm } from "../components/PublicForms";
import { useSiteSettings } from "../SiteLayout";
import { tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";

const STEPS = [
  {
    icon: ClipboardList,
    title: { fr: "1. Préinscription", en: "1. Pre-registration" },
    desc: {
      fr: "Remplissez le formulaire ci-dessous : il ne prend que quelques minutes.",
      en: "Fill in the form below: it only takes a few minutes.",
    },
  },
  {
    icon: MessagesSquare,
    title: { fr: "2. Échange avec l'équipe", en: "2. Conversation with the team" },
    desc: {
      fr: "Notre équipe vous contacte pour répondre à vos questions et préparer la visite.",
      en: "Our team contacts you to answer your questions and arrange the visit.",
    },
  },
  {
    icon: School,
    title: { fr: "3. Visite de l'école", en: "3. School visit" },
    desc: {
      fr: "Venez découvrir le campus, rencontrer les enseignants et sentir l'esprit FEBA.",
      en: "Come and see the campus, meet the teachers and get a feel for the FEBA spirit.",
    },
  },
  {
    icon: CalendarCheck,
    title: { fr: "4. Finalisation", en: "4. Completion" },
    desc: {
      fr: "Constitution du dossier et confirmation de l'inscription de votre enfant.",
      en: "Putting the file together and confirming your child's enrolment.",
    },
  },
];

export default function AdmissionsPage() {
  const { lang, t } = useSiteLang();
  const settings = useSiteSettings();
  return (
    <>
      <Seo title={t("Admissions et inscriptions", "Admissions and enrolment")}
        description={t(
          "Inscrivez votre enfant à FEBA : préinscription en ligne, visite de l'école et accompagnement de l'équipe. Garderie, maternelle et primaire à Cotonou.",
          "Enrol your child at FEBA: online pre-registration, a school visit and support from our team. Nursery, kindergarten and primary in Cotonou.",
        )} />
      <PageBanner title={t("Admissions & inscriptions", "Admissions & enrolment")}
        intro={t(
          "Rejoindre FEBA est simple : préinscription en ligne, échange avec l'équipe, visite du campus.",
          "Joining FEBA is simple: online pre-registration, a conversation with the team, a campus visit.",
        )}
        image="/site/img/hero-admissions-1600.webp" />

      <Section tone="white">
        <SectionHeading
          overline={t("Comment ça marche", "How it works")}
          title={t("Le parcours d'admission", "The admissions journey")} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {STEPS.map((s) => (
            <div key={s.title.fr} className="rounded-2xl bg-feba-cream border border-feba-gold/25 p-6">
              <div className="w-11 h-11 rounded-xl bg-feba-navy flex items-center justify-center mb-4">
                <s.icon className="w-5 h-5 text-feba-gold" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-feba-navy text-sm">{tr(s.title, lang)}</h3>
              <p className="text-xs mt-2 leading-relaxed">{tr(s.desc, lang)}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section>
        <div className="grid lg:grid-cols-5 gap-10 items-start">
          <div className="lg:col-span-2 space-y-5">
            <SectionHeading center={false}
              overline={t("Bienvenue", "Welcome")}
              title={t("Une équipe à votre écoute", "A team that listens")}
              intro={t(
                "Chaque famille est reçue personnellement : votre projet pour votre enfant est aussi le nôtre.",
                "Every family is received personally: your plans for your child are ours too.",
              )} />
            {/* V5 : la zone crème à gauche porte un dégradé marine + légende ;
                point focal sur la scène d'accueil (droite du visuel). */}
            <MediaFrame src="/site/img/admissions-accueil-1600.webp"
              alt={t("Famille reçue à l'accueil de FEBA", "A family welcomed at the FEBA reception")}
              overlay="left-navy" sizes="(min-width:1024px) 40vw, 100vw"
              className="rounded-2xl shadow-lg h-56"
              contentClass="p-5 flex flex-col justify-center items-start max-w-[58%]">
              <p className="text-feba-gold text-[11px] font-bold uppercase tracking-[0.18em]">Admissions</p>
              <p className="text-white font-bold text-lg leading-snug mt-1.5 drop-shadow">
                {t("L'accueil des familles", "Welcoming families")}
              </p>
            </MediaFrame>
            {/* V7 : conteneur plus haut + point focal descendu (mediaMeta 50/60)
                pour montrer le corps entier des enfants et des parents, pas
                seulement leurs têtes. */}
            <MediaFrame src="/site/img/admissions-famille-1600.webp"
              alt={t("Famille visitant le campus de FEBA", "A family visiting the FEBA campus")}
              overlay="bottom-navy" sizes="(min-width:1024px) 40vw, 100vw"
              className="rounded-2xl shadow-lg h-72 sm:h-80"
              contentClass="p-5 flex flex-col justify-end">
              <p className="text-white/90 text-sm font-semibold drop-shadow">{t("La visite du campus", "The campus visit")}</p>
            </MediaFrame>
            {settings.phone && (
              <p className="text-sm">
                {t("Vous préférez le téléphone ? Appelez-nous au", "Prefer the phone? Call us on")}{" "}
                <a href={`tel:${settings.phone.replace(/\s/g, "")}`} className="font-bold text-feba-navy hover:text-feba-gold">
                  {settings.phone}
                </a>.
              </p>
            )}
          </div>
          <div className="lg:col-span-3 rounded-3xl bg-white shadow-xl p-6 sm:p-8">
            <h2 className="text-xl font-bold text-feba-navy mb-1">
              {t("Formulaire de préinscription", "Pre-registration form")}
            </h2>
            <p className="text-sm text-feba-gray mb-6">
              {t(
                "Les champs marqués d'un astérisque (*) sont obligatoires.",
                "Fields marked with an asterisk (*) are required.",
              )}
            </p>
            <PreRegistrationForm />
          </div>
        </div>
      </Section>
    </>
  );
}
