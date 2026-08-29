"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import BrandMark from "@/components/BrandMark";
import { ROUTES, contractAIEntryHref, contractAIEntryIsExternal } from "@/lib/links";
import { isLightOpsTheme } from "@/lib/visualTheme";

export default function Header() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement | null>(null);

  // Detect scroll to add background to header
  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!isMoreOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!moreMenuRef.current?.contains(event.target as Node)) {
        setIsMoreOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMoreOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isMoreOpen]);

  const mainNavigation = [
    { name: "Автоматизация", href: "/solutions" },
    { name: "Юридическая помощь", href: ROUTES.legalHelp },
    { name: "Разработка и AI", href: ROUTES.engineering },
    { name: "Услуги", href: "/services" },
    { name: "Материалы", href: "/guides" },
  ];

  const secondaryNavigation = [
    { name: "Главная", href: "/" },
    { name: "ИИ в юридической сфере", href: ROUTES.legalAi },
    { name: "Комментарии законодательства об ИИ", href: ROUTES.aiLaw },
    { name: "Для юристов", href: "/for-lawyers" },
    { name: "Для бизнеса", href: "/for-business" },
    { name: "О платформе", href: "/about" },
    { name: "Сценарии", href: "/cases" },
    { name: "Команда", href: "/team" },
  ];
  const contractAIActionHref = contractAIEntryHref("demo");
  const contractAIActionExternal = contractAIEntryIsExternal();

  return (
    <header
      className={`${isLightOpsTheme ? "site-header-light-ops" : ""} fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled
          ? "bg-slate-800/95 backdrop-blur-md shadow-lg"
          : "bg-transparent"
      }`}
    >
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-6 h-20">
          <div className="flex-shrink-0">
            <Link href="/" className="flex items-center gap-3 group">
              <BrandMark className="transition-transform duration-300 group-hover:scale-105" />
              <span className="text-xl font-bold text-white group-hover:text-amber-400 transition-colors">
                AI Verdict
              </span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden xl:flex items-center gap-6">
            {mainNavigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className="text-slate-300 hover:text-amber-400 transition-colors font-medium whitespace-nowrap"
              >
                {item.name}
              </Link>
            ))}
            <div className="relative" ref={moreMenuRef}>
              <button
                type="button"
                onClick={() => setIsMoreOpen((open) => !open)}
                className="cursor-pointer text-slate-300 hover:text-amber-400 transition-colors font-medium whitespace-nowrap"
                aria-expanded={isMoreOpen}
                aria-haspopup="menu"
              >
                Еще
              </button>
              {isMoreOpen && (
              <div className="more-menu-surface absolute right-0 mt-2 w-72 rounded-lg border border-slate-700 bg-slate-800 shadow-xl" role="menu">
                <div className="p-2">
                  {secondaryNavigation.map((item) => (
                    <Link
                      key={item.name}
                      href={item.href}
                      className="more-menu-item block rounded-md px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 hover:text-amber-300 transition-colors"
                      onClick={() => setIsMoreOpen(false)}
                      role="menuitem"
                    >
                      {item.name}
                    </Link>
                  ))}
                </div>
              </div>
              )}
            </div>
          </div>

          {/* Desktop CTA Button */}
          <div className="hidden xl:block">
            {contractAIActionExternal ? (
              <a
                href={contractAIActionHref}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center whitespace-nowrap bg-amber-600 hover:bg-amber-700 text-white font-semibold text-sm px-4 py-3 rounded-lg transition-all transform hover:scale-105"
              >
                Открыть сервис проверки договоров →
              </a>
            ) : (
              <Link
                href={contractAIActionHref}
                className="inline-flex items-center whitespace-nowrap bg-amber-600 hover:bg-amber-700 text-white font-semibold text-sm px-4 py-3 rounded-lg transition-all transform hover:scale-105"
              >
                Открыть сервис проверки договоров →
              </Link>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="xl:hidden">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="text-slate-300 hover:text-white p-2"
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? (
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              ) : (
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="xl:hidden bg-slate-800 rounded-lg mt-2 mb-4 overflow-hidden">
            <div className="px-4 py-2 space-y-1">
              {mainNavigation.map((item) => (
                <Link
                  key={item.name}
                  href={item.href}
                  className="block px-4 py-3 text-slate-300 hover:text-amber-400 hover:bg-slate-700 rounded-lg transition-colors"
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  {item.name}
                </Link>
              ))}
              {contractAIActionExternal ? (
                <a
                  href={contractAIActionHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block mt-4 bg-amber-600 hover:bg-amber-700 text-white font-semibold px-4 py-3 rounded-lg text-center transition-colors"
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Открыть сервис проверки договоров →
                </a>
              ) : (
                <Link
                  href={contractAIActionHref}
                  className="block mt-4 bg-amber-600 hover:bg-amber-700 text-white font-semibold px-4 py-3 rounded-lg text-center transition-colors"
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  Открыть сервис проверки договоров →
                </Link>
              )}
              <div className="mt-4 border-t border-slate-700 pt-3">
                <p className="px-4 pb-2 text-xs uppercase tracking-wide text-slate-400">Еще</p>
                {secondaryNavigation.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="block px-4 py-3 text-slate-300 hover:text-amber-400 hover:bg-slate-700 rounded-lg transition-colors"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
