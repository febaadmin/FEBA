/**
 * Page d'accueil du site vitrine FEBA — P4 v4.
 * Sections : hero carrousel administrable, présentation & valeurs, niveaux,
 * pourquoi FEBA, bilinguisme, vie à FEBA, FEBA French Heritage Academy (vert), chiffres
 * (uniquement si renseignés), actualités réelles, aperçu galerie, appel à
 * l'action final. Aucune donnée fictive : les blocs sans contenu sont masqués.
 */
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Award, BookOpen, Globe2, HeartHandshake, Languages, ShieldCheck,
  Sparkles, Users, ArrowRight, MessageCircle, CalendarDays,
} from "lucide-react";
import { siteAPI } from "../siteApi";
import { useSiteSettings } from "../SiteLayout";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import MediaFrame from "../components/MediaFrame";
import HeroCarousel from "../components/HeroCarousel";
import { Section, SectionHeading } from "../components/SiteSection";
import { DEFAULT_ALBUMS, pickLang } from "../siteDefaults";
import { LEVELS, WHY_FEBA, VALUES, ACTIVITIES, ONLINE_FEATURES } from "../content";
import { FHA_GROUPS, tr } from "../fhaContent";
import { useSiteLang } from "../useSiteLang";
import { HOME } from "../siteTranslations";

const WHY_ICONS = [Languages, Users, HeartHandshake, ShieldCheck, Award, Globe2];

export default function HomePage() {
  // P1 : la page d'accueil restait en français même en mode EN — le
  // sélecteur ne pilotait que la navigation et la page FEBA FHA.
  const { lang, t } = useSiteLang();
  const settings = useSiteSettings();
  const { data: slidesData } = useQuery({
    queryKey: ["site-hero"], queryFn: siteAPI.heroSlides, staleTime: 300000, retry: 1,
  });
  const { data: newsData } = useQuery({
    queryKey: ["site-news-home"], queryFn: () => siteAPI.news({ page_size: 3 }),
    staleTime: 300000, retry: 1,
  });
  const { data: galleryData } = useQuery({
    queryKey: ["site-gallery"], queryFn: siteAPI.gallery, staleTime: 300000, retry: 1,
  });

  const slides = slidesData?.data || [];
  const newsRaw = newsData?.data;
  const news = (newsRaw?.results || newsRaw || []).slice(0, 3);
  // V6 : aperçu galerie jamais vide — repli sur les albums packagés.
  const apiAlbums = (galleryData?.data || []).filter((a) => a.items?.length);
  const albums = apiAlbums.length ? apiAlbums : DEFAULT_ALBUMS;
  const galleryPreview = albums
    .flatMap((a) => a.items.filter((i) => i.kind === "image"))
    .slice(0, 8);

  const stats = [
    { value: settings.stat_students, label: t("Élèves épanouis", "Thriving students") },
    { value: settings.stat_teachers, label: t("Enseignants dévoués", "Dedicated teachers") },
    { value: settings.stat_years, label: t("Années d'expérience", "Years of experience") },
    { value: settings.stat_success_rate, label: t("% de réussite", "% success rate"), suffix: "%" },
  ].filter((s) => s.value != null && s.value !== "");

  return (
    <>
      <Seo
        description={pickLang(settings, "meta_description", lang) || t(
          "École bilingue français-anglais à Akpakpa, Cotonou : garderie, maternelle et primaire.",
          "French-English bilingual school in Akpakpa, Cotonou: nursery, kindergarten and primary.",
        )}
        image={settings.og_image || "/site/img/hero-campus-1600.webp"}
      />

      {/* 2. Hero / carrousel */}
      <HeroCarousel slides={slides} />

      {/* 3. Présentation de FEBA */}
      <Section tone="white">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">
              {tr(HOME.welcomeOverline, lang)}
            </p>
            <h2 className="text-2xl sm:text-4xl font-bold text-feba-navy leading-tight">
              Faith & Excellence Bilingual Academy
            </h2>
            <p className="mt-5 leading-relaxed">
              {tr(HOME.presentationBody, lang)}{" "}
              <strong className="text-feba-navy">{tr(HOME.presentationHighlight, lang)}</strong>{" "}
              {tr(HOME.presentationEnd, lang)}
            </p>
            <p className="mt-3 leading-relaxed">
              {t(
                "Notre vision : former des enfants épanouis, enracinés dans leurs valeurs et ouverts sur le monde — ",
                "Our vision: to raise fulfilled children, rooted in their values and open to the world — ",
              )}
              <em className="text-feba-navy">
                {t("l'école autrement, avec vous", "school done differently, with you")}
              </em>.
            </p>
            <div className="mt-7 grid sm:grid-cols-3 gap-4">
              {VALUES.map((v) => (
                <div key={v.title.fr} className="rounded-2xl border border-feba-gold/30 bg-feba-cream p-4">
                  <Sparkles className="w-5 h-5 text-feba-gold mb-2" aria-hidden="true" />
                  <p className="font-bold text-feba-navy text-sm">{tr(v.title, lang)}</p>
                  <p className="text-xs mt-1 leading-relaxed">{tr(v.desc, lang)}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {/* V6.2 : « Bonne image » demandée — façade FEBA avec logo, nom
                « Faith & Excellence » et fresques pédagogiques (composition
                verticale propre). Remplace l'ancienne vue drone non retenue. */}
            <SiteImage src="/site/img/campus-facade-logo-1600.webp"
              alt={t(
                "Façade de FEBA avec le logo, le nom Faith & Excellence Bilingual Academy et des fresques pédagogiques",
                "The FEBA frontage with its logo, the name Faith & Excellence Bilingual Academy and educational murals",
              )}
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg" />
            <SiteImage src="/site/img/valeurs-equipe-1600.webp"
              alt={t("Élèves de FEBA collaborant sur un projet", "FEBA pupils working together on a project")}
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg mt-8" />
            <SiteImage src="/site/img/accompagnement-individuel-1600.webp"
              alt={t("Enseignante accompagnant deux élèves", "A teacher supporting two pupils")}
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg" />
            {/* V6 : campus-cour (grand ciel/crème en haut) remplacé par une
                scène de classe qui remplit le cadre — pas de zone vide. */}
            <SiteImage src="/site/img/academique-lecture-1600.webp"
              alt={t("Deux élèves de FEBA lisant ensemble", "Two FEBA pupils reading together")}
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg mt-8" />
          </div>
        </div>
      </Section>

      {/* 4. Niveaux */}
      <Section>
        <SectionHeading
          overline={t("Notre offre", "What we offer")}
          title={tr(HOME.levelsTitle, lang)}
          intro={t(
            "Un parcours complet et cohérent, de la petite enfance à l'entrée au collège.",
            "A complete, coherent pathway from early childhood to secondary school.",
          )} />
        {/* V5 : cartes-compositions — l'image occupe toute la carte, le texte
            est posé sur un dégradé FEBA (en pied, ou dans la zone crème
            libre pour CM1·CM2 — plus aucune zone vide sans intention). */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-5">
          {LEVELS.map((lvl) => (
            <MediaFrame key={lvl.name.fr} src={lvl.img}
              alt={t(`${tr(lvl.name, lang)} à FEBA`, `${tr(lvl.name, lang)} at FEBA`)}
              overlay={lvl.overlay} sizes="(min-width:1024px) 20vw, 50vw"
              className="h-60 sm:h-64 rounded-2xl shadow-md hover:shadow-xl transition-shadow"
              contentClass={lvl.textSide === "left"
                ? "p-4 flex flex-col justify-center items-start max-w-[68%]"
                : "p-4 flex flex-col justify-end"}>
              <h3 className="font-bold text-white drop-shadow">{tr(lvl.name, lang)}</h3>
              <p className="text-xs mt-1.5 leading-relaxed text-white/85 drop-shadow">{tr(lvl.desc, lang)}</p>
            </MediaFrame>
          ))}
        </div>
      </Section>

      {/* 5. Pourquoi choisir FEBA */}
      <Section tone="navy">
        <SectionHeading light
          overline={t("Nos engagements", "Our commitments")}
          title={tr(HOME.whyTitle, lang)} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {WHY_FEBA.map((item, i) => {
            const Icon = WHY_ICONS[i % WHY_ICONS.length];
            return (
              <div key={item.title.fr}
                className="rounded-2xl bg-white/5 border border-white/10 p-6 hover:border-feba-gold/60 transition-colors">
                <div className="w-11 h-11 rounded-xl bg-feba-gold/15 flex items-center justify-center mb-4">
                  <Icon className="w-5 h-5 text-feba-gold" aria-hidden="true" />
                </div>
                <h3 className="font-bold text-white">{tr(item.title, lang)}</h3>
                <p className="text-sm text-white/75 mt-2 leading-relaxed">{tr(item.desc, lang)}</p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* 6. Enseignement bilingue */}
      <Section tone="white" id="bilinguisme">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <SiteImage src="/site/img/hero-bilingue-1600.webp"
            alt={t("Cours bilingue : manuels de français et d'anglais", "Bilingual lesson: French and English textbooks")}
            sizes="(min-width:1024px) 50vw, 100vw" className="rounded-3xl shadow-xl object-cover w-full h-72 sm:h-96" />
          <div>
            <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">
              {tr(HOME.bilingualOverline, lang)}
            </p>
            <h2 className="text-2xl sm:text-4xl font-bold text-feba-navy">
              {t("Le français et l'anglais, chaque jour", "French and English, every single day")}
            </h2>
            <p className="mt-5 leading-relaxed">
              {t(
                "À FEBA, le bilinguisme n'est pas une matière : c'est un mode de vie. Le français structure les apprentissages fondamentaux, et l'anglais est pratiqué quotidiennement en classe, dans les activités et dans les échanges.",
                "At FEBA, bilingualism is not a subject: it is a way of life. French structures the core learning, and English is used daily in class, in activities and in conversation.",
              )}
            </p>
            <ul className="mt-5 space-y-3 text-sm">
              {[
                t("Immersion progressive dès la garderie", "Gradual immersion from nursery onwards"),
                t("Enseignants qualifiés dans les deux langues", "Teachers qualified in both languages"),
                t("Évaluations et bulletins intégrant les deux parcours", "Assessments and report cards covering both pathways"),
                t("Une longueur d'avance pour le collège et au-delà", "A head start for secondary school and beyond"),
              ].map((li) => (
                <li key={li} className="flex gap-3">
                  <BookOpen className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />{li}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {/* 7. Vie à FEBA */}
      <Section>
        <SectionHeading
          overline={tr(HOME.activitiesOverline, lang)}
          title={t("Apprendre, grandir et s'épanouir", "Learn, grow and flourish")}
          intro={t(
            "Musique, arts, sport, sciences et jeux : l'épanouissement fait partie du programme.",
            "Music, arts, sport, science and games: personal growth is part of the curriculum.",
          )} />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {ACTIVITIES.slice(0, 8).map((act) => (
            <MediaFrame key={act.title.fr} src={act.img} alt={tr(act.title, lang)}
              overlay="bottom-navy" sizes="(min-width:1024px) 25vw, 50vw"
              className="h-56 rounded-2xl shadow-md"
              contentClass="p-4 flex flex-col justify-end">
              <h3 className="text-white font-bold">{tr(act.title, lang)}</h3>
              <p className="text-white/80 text-xs mt-1 leading-relaxed">{tr(act.desc, lang)}</p>
            </MediaFrame>
          ))}
        </div>
        <div className="text-center mt-8">
          <Link to="/vie-scolaire" className="inline-flex items-center gap-2 text-feba-navy font-bold text-sm hover:text-feba-gold transition-colors">
            {tr(HOME.discoverSchoolLife, lang)} <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </Section>

      {/* 8. FEBA French Heritage Academy (identité verte).
          Section développée : le programme est une entité à part entière,
          pas une simple carte. Le détail complet vit sur /feba-fha pour ne
          pas surcharger la page d'accueil de l'école de Cotonou. */}
      <Section tone="green">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <p className="text-white/90 font-bold uppercase tracking-[0.2em] text-xs mb-3">
              {t("Programme international · FEBA FHA", "International programme · FEBA FHA")}
            </p>
            <h2 className="text-2xl sm:text-4xl font-bold text-white">
              FEBA French Heritage Academy
            </h2>
            <p className="text-feba-gold mt-2 font-semibold italic text-sm sm:text-base">
              From English Speakers to Confident French Speakers
            </p>
            <p className="mt-5 text-white/90 leading-relaxed">
              {t(
                "Un programme d'apprentissage du français entièrement en ligne, destiné aux enfants de la diaspora africaine vivant aux États-Unis, au Canada et dans d'autres pays anglophones. Les cours sont dispensés depuis FEBA au Bénin par des enseignants formés à l'enseignement du français aux enfants anglophones.",
                "A fully online French-learning programme for children of the African diaspora living in the United States, Canada and other English-speaking countries. Lessons are delivered from FEBA in Benin by teachers trained to teach French to English-speaking children.",
              )}
            </p>

            {/* Les trois groupes de lancement. */}
            <div className="mt-6 grid sm:grid-cols-3 gap-3">
              {FHA_GROUPS.map((g) => (
                <div key={g.key} className="rounded-xl bg-white/10 p-3.5">
                  <p className="text-feba-gold text-[11px] font-bold uppercase tracking-wide">
                    {t(`${g.ages} ans`, `ages ${g.ages}`)}
                  </p>
                  <p className="text-white font-bold text-sm mt-0.5">{g.name}</p>
                </div>
              ))}
            </div>

            <ul className="mt-6 space-y-3 text-sm text-white/90">
              {ONLINE_FEATURES.map((f) => (
                <li key={f.fr} className="flex gap-3">
                  <Globe2 className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />
                  {tr(f, lang)}
                </li>
              ))}
            </ul>

            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/feba-fha"
                className="px-6 py-3 rounded-xl bg-white text-feba-green font-bold text-sm hover:bg-feba-cream transition-colors">
                {t("Découvrir FEBA FHA", "Discover FEBA FHA")}
              </Link>
              <Link to="/feba-fha/enroll"
                className="px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:brightness-110 transition">
                {t("Inscrire mon enfant", "Enrol my child")}
              </Link>
              <Link to="/feba-fha/placement-test"
                className="px-6 py-3 rounded-xl border border-white/50 text-white font-bold text-sm hover:bg-white/10 transition-colors">
                {t("Réserver un test de placement", "Book a placement test")}
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <SiteImage src="/site/img/online-visio-1600.webp"
              alt={t("Élève FEBA French Heritage Academy en visioconférence", "FEBA French Heritage Academy pupil in a video lesson")}
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-44 sm:h-56 shadow-lg" />
            <SiteImage src="/site/img/online-lecon-1600.webp" alt={t("Leçon de français en ligne", "Online French lesson")}
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-44 sm:h-56 shadow-lg mt-6" />
            <SiteImage src="/site/img/online-cours-francais-1600.webp"
              alt={t("Cours de français FEBA French Heritage Academy sur ordinateur", "FEBA French Heritage Academy French lesson on a computer")}
              sizes="(min-width:1024px) 50vw, 100vw" className="rounded-2xl object-cover w-full h-44 sm:h-56 shadow-lg col-span-2" />
          </div>
        </div>
      </Section>

      {/* 9. Chiffres — UNIQUEMENT si renseignés par l'administration */}
      {stats.length > 0 && (
        <Section tone="white">
          <div className={`grid gap-6 text-center grid-cols-2 ${
            { 1: "lg:grid-cols-1", 2: "lg:grid-cols-2", 3: "lg:grid-cols-3" }[stats.length] || "lg:grid-cols-4"
          }`}>
            {stats.map((s) => (
              <div key={s.label} className="rounded-2xl bg-feba-cream border border-feba-gold/25 py-8 px-4">
                <p className="text-3xl sm:text-4xl font-bold text-feba-navy">
                  {s.value}{s.suffix || ""}
                </p>
                <p className="text-xs sm:text-sm mt-2 text-feba-gray">{s.label}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* 10. Actualités & événements — contenus réels uniquement */}
      {news.length > 0 && (
        <Section>
          <SectionHeading
            overline={t("La vie de l'école", "School life")}
            title={t("Actualités et événements", "News and events")} />
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {news.map((post) => (
              <article key={post.id} className="rounded-2xl bg-white shadow-md overflow-hidden hover:shadow-xl transition-shadow">
                {post.image_src && (
                  <Link to={`/actualites/${post.slug}`} className="block h-44 overflow-hidden">
                    <SiteImage src={post.image_src} alt="" position={post.focal} sizes="(min-width:1024px) 33vw, 100vw"
                      className="w-full h-full object-cover" />
                  </Link>
                )}
                <div className="p-5">
                  <p className="flex items-center gap-2 text-xs text-feba-gold font-semibold uppercase tracking-wide">
                    <CalendarDays className="w-3.5 h-3.5" aria-hidden="true" />
                    {post.kind === "event" ? t("Événement", "Event") : t("Actualité", "News")}
                    {post.published_at && <span className="text-feba-gray font-normal normal-case">· {post.published_at.slice(0, 10)}</span>}
                  </p>
                  <h3 className="font-bold text-feba-navy mt-2 leading-snug">
                    <Link to={`/actualites/${post.slug}`} className="hover:text-feba-gold transition-colors">{pickLang(post, "title", lang)}</Link>
                  </h3>
                  {pickLang(post, "excerpt", lang) && (
                    <p className="text-sm mt-2 leading-relaxed">{pickLang(post, "excerpt", lang)}</p>
                  )}
                </div>
              </article>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link to="/actualites" className="inline-flex items-center gap-2 text-feba-navy font-bold text-sm hover:text-feba-gold transition-colors">
              {tr(HOME.allNews, lang)} <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Section>
      )}

      {/* 11. Aperçu galerie */}
      {galleryPreview.length >= 4 && (
        <Section tone="white">
          <SectionHeading
            overline={t("En images", "In pictures")}
            title={t("La galerie FEBA", "The FEBA gallery")} />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {galleryPreview.map((item, i) => (
              <Link key={item.id ?? i} to="/galerie" className="block rounded-xl overflow-hidden h-36 sm:h-44 group">
                <img src={item.image_src}
                  alt={pickLang(item, "alt_text", lang) || pickLang(item, "caption", lang) || t("Photo FEBA", "FEBA photo")}
                  loading="lazy"
                  style={{ objectPosition: item.focal || "50% 50%" }}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              </Link>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link to="/galerie" className="inline-flex items-center gap-2 text-feba-navy font-bold text-sm hover:text-feba-gold transition-colors">
              {t("Voir toute la galerie", "See the whole gallery")} <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Section>
      )}

      {/* 12. Appel à l'action final */}
      <Section tone="navy" className="!py-16">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-2xl sm:text-4xl font-bold text-white">
            {t("Prêts à rejoindre la famille FEBA ?", "Ready to join the FEBA family?")}
          </h2>
          <p className="text-white/80 mt-4">
            {t(
              "Inscrivez votre enfant ou venez nous rencontrer à Akpakpa : notre équipe vous accueille avec plaisir.",
              "Enrol your child or come and meet us in Akpakpa: our team will be glad to welcome you.",
            )}
          </p>
          <div className="flex flex-wrap justify-center gap-3 mt-8">
            <Link to="/admissions"
              className="px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:bg-feba-gold2 transition-colors">
              {t("Inscrire mon enfant", "Enrol my child")}
            </Link>
            <Link to="/contact"
              className="px-6 py-3 rounded-xl border border-white/40 text-white font-bold text-sm hover:bg-white/10 transition-colors">
              {t("Demander des informations", "Request information")}
            </Link>
            {settings.whatsapp && (
              <a href={`https://wa.me/${settings.whatsapp.replace(/[^0-9]/g, "")}`}
                target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-feba-green text-white font-bold text-sm hover:bg-feba-green2 transition-colors">
                <MessageCircle className="w-4 h-4" aria-hidden="true" /> WhatsApp
              </a>
            )}
          </div>
        </div>
      </Section>
    </>
  );
}
