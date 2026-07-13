"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { contractAIEntryHref, contractAIEntryIsExternal } from "@/lib/links";
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
    { name: "Решения", href: "/solutions" },
    { name: "Contract_AI_System", href: contractAIEntryHref(), external: contractAIEntryIsExternal() },
    { name: "Контент / Кейсы", href: "/content-cases" },
    { name: "О платформе", href: "/about" },
  ];

  const secondaryNavigation = [
    { name: "Главная", href: "/" },
    { name: "Для юристов", href: "/for-lawyers" },
    { name: "Для бизнеса", href: "/for-business" },
    { name: "Другая автоматизация", href: "/services/custom-ai" },
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
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <div className="flex-shrink-0">
            <Link href="/" className="flex items-center gap-3 group">
              {/* AI Legal Scales Logo */}
              <svg width="40" height="40" viewBox="0 0 100 100" className="transition-transform group-hover:scale-110">
                {/* Весы - основа */}
                <g>
                  {/* Опора весов */}
                  <rect x="47" y="30" width="6" height="45" fill="#cbd5e1" rx="3"/>
                  <rect x="35" y="72" width="30" height="6" fill="#cbd5e1" rx="3"/>

                  {/* Горизонтальная перекладина */}
                  <rect x="20" y="28" width="60" height="4" fill="#f59e0b" className="fill-amber-500" rx="2"/>

                  {/* Левая чаша весов */}
                  <path d="M 15 32 L 25 32 L 27 42 L 13 42 Z" fill="#f59e0b" className="fill-amber-500" opacity="0.8"/>
                  <ellipse cx="20" cy="32" rx="5" ry="2" fill="#fbbf24" className="fill-amber-400"/>

                  {/* Правая чаша весов */}
                  <path d="M 75 32 L 85 32 L 87 42 L 73 42 Z" fill="#f59e0b" className="fill-amber-500" opacity="0.8"/>
                  <ellipse cx="80" cy="32" rx="5" ry="2" fill="#fbbf24" className="fill-amber-400"/>

                  {/* Цепочки */}
                  <line x1="20" y1="28" x2="20" y2="32" stroke="#94a3b8" strokeWidth="1.5"/>
                  <line x1="80" y1="28" x2="80" y2="32" stroke="#94a3b8" strokeWidth="1.5"/>
                </g>

                {/* AI элементы - нейронная сеть */}
                <g opacity="0.9">
                  {/* Центральный узел (AI чип) */}
                  <circle cx="50" cy="18" r="6" fill="#3b82f6" className="fill-blue-500"/>
                  <rect x="47" y="15" width="6" height="6" fill="#1e40af" className="fill-blue-700" opacity="0.6" rx="1"/>

                  {/* Узлы нейросети */}
                  <circle cx="35" cy="10" r="3" fill="#22d3ee" className="fill-cyan-400"/>
                  <circle cx="65" cy="10" r="3" fill="#22d3ee" className="fill-cyan-400"/>
                  <circle cx="30" cy="22" r="2.5" fill="#10b981" className="fill-emerald-500"/>
                  <circle cx="70" cy="22" r="2.5" fill="#10b981" className="fill-emerald-500"/>

                  {/* Связи нейросети */}
                  <line x1="50" y1="18" x2="35" y2="10" stroke="#22d3ee" strokeWidth="1.5" opacity="0.6"/>
                  <line x1="50" y1="18" x2="65" y2="10" stroke="#22d3ee" strokeWidth="1.5" opacity="0.6"/>
                  <line x1="50" y1="18" x2="30" y2="22" stroke="#10b981" strokeWidth="1.5" opacity="0.6"/>
                  <line x1="50" y1="18" x2="70" y2="22" stroke="#10b981" strokeWidth="1.5" opacity="0.6"/>

                  {/* Точки данных (анимированные) */}
                  <circle cx="42" cy="14" r="1.5" fill="#fbbf24" className="animate-pulse" style={{animationDuration: '2s'}}/>
                  <circle cx="58" cy="20" r="1.5" fill="#fbbf24" className="animate-pulse" style={{animationDuration: '2.5s', animationDelay: '0.3s'}}/>
                </g>
              </svg>
              <span className="text-xl font-bold text-white group-hover:text-amber-400 transition-colors">
                AI Verdict
              </span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8">
            {mainNavigation.map((item) => (
              item.external ? (
                <a
                  key={item.name}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-300 hover:text-amber-400 transition-colors font-medium whitespace-nowrap"
                >
                  {item.name}
                </a>
              ) : (
                <Link
                  key={item.name}
                  href={item.href}
                  className="text-slate-300 hover:text-amber-400 transition-colors font-medium whitespace-nowrap"
                >
                  {item.name}
                </Link>
              )
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
              <div className="more-menu-surface absolute right-0 mt-2 w-56 rounded-lg border border-slate-700 bg-slate-800 shadow-xl" role="menu">
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
          <div className="hidden md:block">
            {contractAIActionExternal ? (
              <a
                href={contractAIActionHref}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-amber-600 hover:bg-amber-700 text-white font-semibold px-6 py-3 rounded-lg transition-all transform hover:scale-105"
              >
                Открыть сервис проверки договоров →
              </a>
            ) : (
              <Link
                href={contractAIActionHref}
                className="bg-amber-600 hover:bg-amber-700 text-white font-semibold px-6 py-3 rounded-lg transition-all transform hover:scale-105"
              >
                Открыть сервис проверки договоров →
              </Link>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
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
          <div className="md:hidden bg-slate-800 rounded-lg mt-2 mb-4 overflow-hidden">
            <div className="px-4 py-2 space-y-1">
              {mainNavigation.map((item) => (
                item.external ? (
                  <a
                    key={item.name}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block px-4 py-3 text-slate-300 hover:text-amber-400 hover:bg-slate-700 rounded-lg transition-colors"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {item.name}
                  </a>
                ) : (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="block px-4 py-3 text-slate-300 hover:text-amber-400 hover:bg-slate-700 rounded-lg transition-colors"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    {item.name}
                  </Link>
                )
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
