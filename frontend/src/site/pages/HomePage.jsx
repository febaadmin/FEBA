/**
 * Page d'accueil du site vitrine FEBA — P4 v4.
 * Sections : hero carrousel administrable, présentation & valeurs, niveaux,
 * pourquoi FEBA, bilinguisme, vie à FEBA, FEBA Online (vert), chiffres
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
import { DEFAULT_ALBUMS } from "../siteDefaults";
import { LEVELS, WHY_FEBA, VALUES, ACTIVITIES, ONLINE_FEATURES } from "../content";

const WHY_ICONS = [Languages, Users, HeartHandshake, ShieldCheck, Award, Globe2];

export default function HomePage() {
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
    { value: settings.stat_students, label: "Élèves épanouis" },
    { value: settings.stat_teachers, label: "Enseignants dévoués" },
    { value: settings.stat_years, label: "Années d'expérience" },
    { value: settings.stat_success_rate, label: "% de réussite", suffix: "%" },
  ].filter((s) => s.value != null && s.value !== "");

  return (
    <>
      <Seo
        description={settings.meta_description ||
          "École bilingue français-anglais à Akpakpa, Cotonou : garderie, maternelle et primaire."}
        image={settings.og_image || "/site/img/hero-campus-1600.webp"}
      />

      {/* 2. Hero / carrousel */}
      <HeroCarousel slides={slides} />

      {/* 3. Présentation de FEBA */}
      <Section tone="white">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">
              Bienvenue à FEBA
            </p>
            <h2 className="text-2xl sm:text-4xl font-bold text-feba-navy leading-tight">
              Faith & Excellence Bilingual Academy
            </h2>
            <p className="mt-5 leading-relaxed">
              Située à Akpakpa (Cotonou, Bénin), FEBA est une école bilingue
              français-anglais qui accueille les enfants de la garderie au CM2.
              Notre mission : <strong className="text-feba-navy">développer les talents et
              construire l'avenir</strong> de chaque enfant, dans un cadre chaleureux,
              sécurisé et exigeant.
            </p>
            <p className="mt-3 leading-relaxed">
              Notre vision : former des enfants épanouis, enracinés dans leurs
              valeurs et ouverts sur le monde — <em className="text-feba-navy">l'école
              autrement, avec vous</em>.
            </p>
            <div className="mt-7 grid sm:grid-cols-3 gap-4">
              {VALUES.map((v) => (
                <div key={v.title} className="rounded-2xl border border-feba-gold/30 bg-feba-cream p-4">
                  <Sparkles className="w-5 h-5 text-feba-gold mb-2" aria-hidden="true" />
                  <p className="font-bold text-feba-navy text-sm">{v.title}</p>
                  <p className="text-xs mt-1 leading-relaxed">{v.desc}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {/* V6.2 : « Bonne image » demandée — façade FEBA avec logo, nom
                « Faith & Excellence » et fresques pédagogiques (composition
                verticale propre). Remplace l'ancienne vue drone non retenue. */}
            <SiteImage src="/site/img/campus-facade-logo-1600.webp" alt="Façade de FEBA avec le logo, le nom Faith & Excellence Bilingual Academy et des fresques pédagogiques"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg" />
            <SiteImage src="/site/img/valeurs-equipe-1600.webp" alt="Élèves de FEBA collaborant sur un projet"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg mt-8" />
            <SiteImage src="/site/img/accompagnement-individuel-1600.webp" alt="Enseignante accompagnant deux élèves"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg" />
            {/* V6 : campus-cour (grand ciel/crème en haut) remplacé par une
                scène de classe qui remplit le cadre — pas de zone vide. */}
            <SiteImage src="/site/img/academique-lecture-1600.webp" alt="Deux élèves de FEBA lisant ensemble"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-52 sm:h-64 shadow-lg mt-8" />
          </div>
        </div>
      </Section>

      {/* 4. Niveaux */}
      <Section>
        <SectionHeading overline="Notre offre" title="De la garderie au CM2"
          intro="Un parcours complet et cohérent, de la petite enfance à l'entrée au collège." />
        {/* V5 : cartes-compositions — l'image occupe toute la carte, le texte
            est posé sur un dégradé FEBA (en pied, ou dans la zone crème
            libre pour CM1·CM2 — plus aucune zone vide sans intention). */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-5">
          {LEVELS.map((lvl) => (
            <MediaFrame key={lvl.name} src={lvl.img} alt={`${lvl.name} à FEBA`}
              overlay={lvl.overlay} sizes="(min-width:1024px) 20vw, 50vw"
              className="h-60 sm:h-64 rounded-2xl shadow-md hover:shadow-xl transition-shadow"
              contentClass={lvl.textSide === "left"
                ? "p-4 flex flex-col justify-center items-start max-w-[68%]"
                : "p-4 flex flex-col justify-end"}>
              <h3 className="font-bold text-white drop-shadow">{lvl.name}</h3>
              <p className="text-xs mt-1.5 leading-relaxed text-white/85 drop-shadow">{lvl.desc}</p>
            </MediaFrame>
          ))}
        </div>
      </Section>

      {/* 5. Pourquoi choisir FEBA */}
      <Section tone="navy">
        <SectionHeading light overline="Nos engagements" title="Pourquoi choisir FEBA ?" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {WHY_FEBA.map((item, i) => {
            const Icon = WHY_ICONS[i % WHY_ICONS.length];
            return (
              <div key={item.title}
                className="rounded-2xl bg-white/5 border border-white/10 p-6 hover:border-feba-gold/60 transition-colors">
                <div className="w-11 h-11 rounded-xl bg-feba-gold/15 flex items-center justify-center mb-4">
                  <Icon className="w-5 h-5 text-feba-gold" aria-hidden="true" />
                </div>
                <h3 className="font-bold text-white">{item.title}</h3>
                <p className="text-sm text-white/75 mt-2 leading-relaxed">{item.desc}</p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* 6. Enseignement bilingue */}
      <Section tone="white" id="bilinguisme">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <SiteImage src="/site/img/hero-bilingue-1600.webp" alt="Cours bilingue : manuels de français et d'anglais"
            sizes="(min-width:1024px) 50vw, 100vw" className="rounded-3xl shadow-xl object-cover w-full h-72 sm:h-96" />
          <div>
            <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">Bilinguisme</p>
            <h2 className="text-2xl sm:text-4xl font-bold text-feba-navy">
              Le français et l'anglais, chaque jour
            </h2>
            <p className="mt-5 leading-relaxed">
              À FEBA, le bilinguisme n'est pas une matière : c'est un mode de vie.
              Le <strong className="text-feba-navy">français</strong> structure les apprentissages
              fondamentaux, et l'<strong className="text-feba-navy">anglais</strong> est pratiqué
              quotidiennement en classe, dans les activités et dans les échanges.
            </p>
            <ul className="mt-5 space-y-3 text-sm">
              {["Immersion progressive dès la garderie",
                "Enseignants qualifiés dans les deux langues",
                "Évaluations et bulletins intégrant les deux parcours",
                "Une longueur d'avance pour le collège et au-delà"].map((li) => (
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
        <SectionHeading overline="Vie scolaire" title="Apprendre, grandir et s'épanouir"
          intro="Musique, arts, sport, sciences et jeux : l'épanouissement fait partie du programme." />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {ACTIVITIES.slice(0, 8).map((act) => (
            <MediaFrame key={act.title} src={act.img} alt={act.title}
              overlay="bottom-navy" sizes="(min-width:1024px) 25vw, 50vw"
              className="h-56 rounded-2xl shadow-md"
              contentClass="p-4 flex flex-col justify-end">
              <h3 className="text-white font-bold">{act.title}</h3>
              <p className="text-white/80 text-xs mt-1 leading-relaxed">{act.desc}</p>
            </MediaFrame>
          ))}
        </div>
        <div className="text-center mt-8">
          <Link to="/vie-scolaire" className="inline-flex items-center gap-2 text-feba-navy font-bold text-sm hover:text-feba-gold transition-colors">
            Découvrir la vie à FEBA <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </Section>

      {/* 8. FEBA Online (identité verte) */}
      <Section tone="green">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <p className="text-white/90 font-bold uppercase tracking-[0.2em] text-xs mb-3">
              Programme international
            </p>
            <h2 className="text-2xl sm:text-4xl font-bold text-white">FEBA Online</h2>
            <p className="mt-5 text-white/90 leading-relaxed">
              Pour les enfants de la diaspora et les familles du monde entier :
              FEBA Online transmet la langue française, la culture et le
              patrimoine africains à travers des cours en ligne vivants,
              en petits groupes.
            </p>
            <ul className="mt-5 space-y-3 text-sm text-white/90">
              {ONLINE_FEATURES.map((f) => (
                <li key={f} className="flex gap-3">
                  <Globe2 className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />{f}
                </li>
              ))}
            </ul>
            <Link to="/feba-online"
              className="mt-7 inline-block px-6 py-3 rounded-xl bg-white text-feba-green font-bold text-sm hover:bg-feba-cream transition-colors">
              Découvrir FEBA Online
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <SiteImage src="/site/img/online-visio-1600.webp" alt="Élève FEBA Online en visioconférence"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-44 sm:h-56 shadow-lg" />
            <SiteImage src="/site/img/online-lecon-1600.webp" alt="Leçon de français en ligne"
              sizes="(min-width:1024px) 25vw, 50vw" className="rounded-2xl object-cover w-full h-44 sm:h-56 shadow-lg mt-6" />
            <SiteImage src="/site/img/online-cours-francais-1600.webp" alt="Cours de français FEBA Online sur ordinateur"
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
          <SectionHeading overline="La vie de l'école" title="Actualités et événements" />
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
                    {post.kind === "event" ? "Événement" : "Actualité"}
                    {post.published_at && <span className="text-feba-gray font-normal normal-case">· {post.published_at.slice(0, 10)}</span>}
                  </p>
                  <h3 className="font-bold text-feba-navy mt-2 leading-snug">
                    <Link to={`/actualites/${post.slug}`} className="hover:text-feba-gold transition-colors">{post.title}</Link>
                  </h3>
                  {post.excerpt && <p className="text-sm mt-2 leading-relaxed">{post.excerpt}</p>}
                </div>
              </article>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link to="/actualites" className="inline-flex items-center gap-2 text-feba-navy font-bold text-sm hover:text-feba-gold transition-colors">
              Toutes les actualités <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Section>
      )}

      {/* 11. Aperçu galerie */}
      {galleryPreview.length >= 4 && (
        <Section tone="white">
          <SectionHeading overline="En images" title="La galerie FEBA" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {galleryPreview.map((item, i) => (
              <Link key={item.id ?? i} to="/galerie" className="block rounded-xl overflow-hidden h-36 sm:h-44 group">
                <img src={item.image_src} alt={item.alt_text || item.caption || "Photo FEBA"} loading="lazy"
                  style={{ objectPosition: item.focal || "50% 50%" }}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              </Link>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link to="/galerie" className="inline-flex items-center gap-2 text-feba-navy font-bold text-sm hover:text-feba-gold transition-colors">
              Voir toute la galerie <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Section>
      )}

      {/* 12. Appel à l'action final */}
      <Section tone="navy" className="!py-16">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-2xl sm:text-4xl font-bold text-white">
            Prêts à rejoindre la famille FEBA ?
          </h2>
          <p className="text-white/80 mt-4">
            Inscrivez votre enfant ou venez nous rencontrer à Akpakpa :
            notre équipe vous accueille avec plaisir.
          </p>
          <div className="flex flex-wrap justify-center gap-3 mt-8">
            <Link to="/admissions"
              className="px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm hover:bg-feba-gold2 transition-colors">
              Inscrire mon enfant
            </Link>
            <Link to="/contact"
              className="px-6 py-3 rounded-xl border border-white/40 text-white font-bold text-sm hover:bg-white/10 transition-colors">
              Demander des informations
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
