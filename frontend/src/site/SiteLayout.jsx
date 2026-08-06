/**
 * SiteLayout — enveloppe du site vitrine public FEBA (P4 v4).
 *
 * Header sticky (navigation complète + menu mobile accessible) et footer.
 * Visuellement DISTINCT de l'ERP : palette officielle FEBA (bleu marine,
 * or, crème). Le bouton « Connexion » mène à /login ; un utilisateur déjà
 * authentifié voit « Mon espace » à la place.
 */
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Menu, X, Phone, Mail, MapPin, Clock, Facebook, Instagram, Youtube, ArrowRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { siteAPI } from "./siteApi";
import { useAuthStore } from "../store/authStore";
import { useBranding } from "../hooks/useBranding";
import SiteLangSwitcher from "./components/SiteLangSwitcher";
import { useSiteLang } from "./useSiteLang";
import { NAV, UI } from "./siteTranslations";
import { tr } from "./fhaContent";

/** Libellés du menu, traduits selon la langue active (P1). */
function buildNavLinks(lang) {
  const L = (entry) => tr(entry, lang);
  return [
  { to: "/", label: L(NAV.home), end: true },
  { to: "/a-propos", label: L(NAV.about) },
  { to: "/academique", label: L(NAV.academics) },
  { to: "/admissions", label: L(NAV.admissions) },
  { to: "/vie-scolaire", label: L(NAV.schoolLife) },
  // Nom complet « FEBA French Heritage Academy » trop long pour la barre
  // de navigation : le menu principal affiche l'abréviation officielle.
  { to: "/feba-fha", label: L(NAV.fha) },
  { to: "/actualites", label: L(NAV.news) },
  { to: "/galerie", label: L(NAV.gallery) },
  { to: "/contact", label: L(NAV.contact) },
  ];
}

export function useSiteSettings() {
  const { data } = useQuery({
    queryKey: ["site-settings"],
    queryFn: siteAPI.settings,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
  return data?.data || {};
}

export default function SiteLayout() {
  // P1 : la langue pilote désormais TOUT le site, pas seulement /feba-fha.
  const { lang } = useSiteLang();
  const L = (entry) => tr(entry, lang);
  const NAV_LINKS = buildNavLinks(lang);

  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { accessToken, user } = useAuthStore();
  const { logoSrc } = useBranding();
  const settings = useSiteSettings();

  // Fermer le menu mobile et remonter en haut à chaque navigation.
  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  const goToSpace = () => {
    const role = user?.role;
    if (role === "superadmin") navigate("/superadmin/dashboard");
    else if (role === "admin") navigate("/admin/dashboard");
    else if (role === "teacher") navigate("/teacher/dashboard");
    else if (role === "parent") navigate("/parent/home");
    else if (role === "student") navigate("/student/home");
    else navigate("/login");
  };

  const authButton = accessToken ? (
    <button onClick={goToSpace}
      className="px-4 py-2 rounded-lg border border-feba-gold/70 text-feba-gold text-sm font-semibold hover:bg-feba-gold hover:text-feba-navy transition-colors">
      {L(UI.mySpace)}
    </button>
  ) : (
    <Link to="/login"
      className="px-4 py-2 rounded-lg border border-feba-gold/70 text-feba-gold text-sm font-semibold hover:bg-feba-gold hover:text-feba-navy transition-colors">
      {L(UI.login)}
    </Link>
  );

  return (
    <div className="min-h-screen flex flex-col bg-feba-cream text-feba-gray font-sans">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-feba-navy shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          {/* V6 : header sur UNE seule ligne aux grands écrans. Les liens ne
              se coupent jamais (whitespace-nowrap) ; le sous-titre du logo ne
              s'affiche qu'en très large pour libérer de la place ; la nav
              horizontale apparaît dès qu'elle tient (≥1200px), sinon menu
              hamburger propre. */}
          <div className="flex items-center justify-between h-16 lg:h-[72px] gap-3 flex-nowrap">
            <Link to="/" className="flex items-center gap-2.5 shrink-0" aria-label="FEBA — Accueil">
              <img src={logoSrc} alt="Logo FEBA"
                className="w-10 h-10 lg:w-11 lg:h-11 rounded-full bg-white object-contain border-2 border-feba-gold" />
              <span className="leading-tight">
                <span className="block text-white font-bold text-sm lg:text-base tracking-wide">FEBA</span>
                <span className="hidden 2xl:block text-feba-gold text-[11px] whitespace-nowrap">
                  Faith & Excellence Bilingual Academy
                </span>
              </span>
            </Link>

            {/* Navigation desktop */}
            <nav className="hidden min-[1200px]:flex items-center gap-0.5" aria-label={L(UI.mainNav)}>
              {NAV_LINKS.map((l) => (
                <NavLink key={l.to} to={l.to} end={l.end}
                  className={({ isActive }) =>
                    `px-2 py-2 rounded-lg text-[13px] font-medium whitespace-nowrap transition-colors ${
                      isActive ? "text-feba-gold" : "text-white/85 hover:text-feba-gold"
                    }`}>
                  {l.label}
                </NavLink>
              ))}
            </nav>

            <div className="hidden min-[1200px]:flex items-center gap-2 shrink-0">
              {/* P1 : sélecteur FR/EN GLOBAL — monté dans le layout, donc
                  présent sur TOUTES les pages publiques et plus seulement
                  sur /feba-fha. */}
              <SiteLangSwitcher tone="dark" />
              {authButton}
              <Link to="/admissions"
                className="px-3.5 py-2 rounded-lg bg-feba-gold text-feba-navy text-sm font-bold whitespace-nowrap hover:bg-feba-gold2 transition-colors">
                {L(UI.enrollChild)}
              </Link>
            </div>

            {/* P9 — Sélecteur FR/EN VISIBLE SUR PETIT ÉCRAN.
                Il n'existait qu'au-delà de 1200px et dans le menu déroulant :
                sur mobile, changer de langue imposait d'ouvrir le hamburger,
                donc de deviner qu'il s'y trouvait. Il est désormais dans la
                barre elle-même — disposition « Logo | FEBA | EN/FR | Menu ».
                C'est le MÊME composant que sur desktop : une seule source de
                vérité pour la langue, aucun risque de désynchronisation. */}
            <div className="flex items-center gap-1.5 min-[1200px]:hidden shrink-0">
              <SiteLangSwitcher tone="dark" />

              {/* Bouton menu mobile / tablette */}
              <button
                className="p-2 rounded-lg text-white hover:bg-white/10"
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
                aria-controls="site-mobile-menu"
                aria-label={menuOpen ? L(UI.closeMenu) : L(UI.openMenu)}>
                {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>
        </div>

        {/* Menu mobile */}
        {menuOpen && (
          <nav id="site-mobile-menu" aria-label={L(UI.mobileNav)}
            className="min-[1200px]:hidden bg-feba-navy border-t border-white/10 px-4 pb-5 pt-2 space-y-1">
            {NAV_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end}
                className={({ isActive }) =>
                  `block px-3 py-2.5 rounded-lg text-sm font-medium ${
                    isActive ? "bg-white/10 text-feba-gold" : "text-white/90 hover:bg-white/5"
                  }`}>
                {l.label}
              </NavLink>
            ))}
            {/* Le sélecteur n'est plus dupliqué ici : il est désormais
                toujours visible dans la barre d'en-tête, y compris menu
                fermé. En laisser un second afficherait deux sélecteurs
                simultanés dès l'ouverture du menu. */}
            <div className="flex flex-col gap-2 pt-3">
              {authButton}
              <Link to="/admissions"
                className="px-4 py-2.5 rounded-lg bg-feba-gold text-feba-navy text-sm font-bold text-center hover:bg-feba-gold2">
                {L(UI.enrollChild)}
              </Link>
            </div>
          </nav>
        )}
      </header>

      {/* ── Contenu ────────────────────────────────────────────────────── */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="bg-feba-navy text-white/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <img src={logoSrc} alt="" className="w-10 h-10 rounded-full bg-white object-contain border-2 border-feba-gold" />
              <p className="font-bold text-white leading-tight">
                FEBA<br />
                <span className="text-[11px] font-normal text-feba-gold">Faith & Excellence Bilingual Academy</span>
              </p>
            </div>
            <p className="text-sm leading-relaxed">
              {settings.tagline || "Développer les talents, construire l'avenir."}
            </p>
            <p className="text-feba-gold text-sm italic mt-2">
              {settings.signature || "FEBA, l'école autrement avec vous."}
            </p>
          </div>

          <div>
            <h3 className="text-white font-semibold mb-4">{L(UI.quickLinks)}</h3>
            <ul className="space-y-2 text-sm">
              {[["/a-propos", L(UI.aboutFeba)], ["/academique", L(UI.academicPrograms)],
                ["/admissions", L(NAV.admissions)], ["/feba-fha", "FEBA French Heritage Academy"],
                ["/galerie", L(UI.photoGallery)], ["/login", L(UI.userArea)]].map(([to, label]) => (
                <li key={to}>
                  <Link to={to} className="hover:text-feba-gold transition-colors inline-flex items-center gap-1.5">
                    <ArrowRight className="w-3 h-3 text-feba-gold" /> {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-white font-semibold mb-4">Contact</h3>
            <ul className="space-y-3 text-sm">
              {settings.address && (
                <li className="flex gap-2.5"><MapPin className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" />{settings.address}</li>
              )}
              {settings.phone && (
                <li className="flex gap-2.5"><Phone className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" />
                  <a href={`tel:${settings.phone.replace(/\s/g, "")}`} className="hover:text-feba-gold">{settings.phone}</a></li>
              )}
              {settings.email && (
                <li className="flex gap-2.5"><Mail className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" />
                  <a href={`mailto:${settings.email}`} className="hover:text-feba-gold">{settings.email}</a></li>
              )}
              {settings.opening_hours && (
                <li className="flex gap-2.5"><Clock className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" />{settings.opening_hours}</li>
              )}
            </ul>
            {(settings.facebook_url || settings.instagram_url || settings.youtube_url) && (
              <div className="flex gap-3 mt-4">
                {settings.facebook_url && (
                  <a href={settings.facebook_url} target="_blank" rel="noreferrer" aria-label="Facebook"
                    className="p-2 rounded-lg bg-white/10 hover:bg-feba-gold hover:text-feba-navy transition-colors"><Facebook className="w-4 h-4" /></a>
                )}
                {settings.instagram_url && (
                  <a href={settings.instagram_url} target="_blank" rel="noreferrer" aria-label="Instagram"
                    className="p-2 rounded-lg bg-white/10 hover:bg-feba-gold hover:text-feba-navy transition-colors"><Instagram className="w-4 h-4" /></a>
                )}
                {settings.youtube_url && (
                  <a href={settings.youtube_url} target="_blank" rel="noreferrer" aria-label="YouTube"
                    className="p-2 rounded-lg bg-white/10 hover:bg-feba-gold hover:text-feba-navy transition-colors"><Youtube className="w-4 h-4" /></a>
                )}
              </div>
            )}
          </div>

          <div>
            <h3 className="text-white font-semibold mb-4">{L(UI.ourLevels)}</h3>
            <ul className="grid grid-cols-2 gap-x-2 gap-y-2 text-sm">
              {["Garderie", "Maternelle 1", "Maternelle 2", "CI", "CP", "CE1", "CE2", "CM1", "CM2"].map((n) => (
                <li key={n} className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-feba-gold inline-block" />{n}
                </li>
              ))}
            </ul>
            <Link to="/feba-fha"
              className="mt-4 inline-block px-3 py-1.5 rounded-lg bg-feba-green text-white text-xs font-semibold hover:bg-feba-green2 transition-colors">
              {L(UI.fhaDiaspora)}
            </Link>
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-white/60">
            <p>© {new Date().getFullYear()} Faith & Excellence Bilingual Academy — Akpakpa, Cotonou, Bénin</p>
            <p className="flex gap-4">
              <Link to="/mentions-legales" className="hover:text-feba-gold">{L(UI.legalNotice)}</Link>
              <Link to="/confidentialite" className="hover:text-feba-gold">{L(UI.privacy)}</Link>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
