"use client";

import AnimatedStat from "./AnimatedStat";
import HeroIllustration from "./HeroIllustration";

export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      {/* Background decoration - Grid pattern */}
      <div className="absolute inset-0 opacity-[0.15]" style={{
        backgroundImage: `
          linear-gradient(to right, rgb(148 163 184 / 0.1) 1px, transparent 1px),
          linear-gradient(to bottom, rgb(148 163 184 / 0.1) 1px, transparent 1px)
        `,
        backgroundSize: '80px 80px'
      }}></div>

      {/* Animated gradient orbs */}
      <div className="absolute top-0 -left-4 w-96 h-96 bg-amber-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
      <div className="absolute top-0 -right-4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
      <div className="absolute -bottom-8 left-20 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-32">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          {/* Left side - Text content */}
          <div className="text-center lg:text-left">
            {/* Main heading */}
            <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 animate-fade-in">
              AI для юридического отдела <br />
              <span className="text-amber-400">меньше рутины, больше контроля</span>
            </h1>

            {/* Subtitle */}
            <h2 className="text-2xl md:text-3xl font-semibold text-slate-200 mb-6 animate-fade-in-delay-1">
              Помогаем юристам работать быстрее и спокойнее.
            </h2>

            <p className="text-base text-slate-400 mb-8 max-w-4xl mx-auto lg:mx-0 animate-fade-in-delay-1">
              Автоматизируем договоры, суды и комплаенс.
              В среднем сокращаем рутину до 80% и выходим на окупаемость за 4-6 месяцев.
            </p>
            
            {/* Stats - SIMPLIFIED for readability */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 animate-fade-in-delay-2">
              <AnimatedStat
                value={20}
                suffix="+"
                label="лет юридической практики"
              />
              <AnimatedStat
                value={80}
                suffix="%+"
                label="меньше рутины в типовых задачах"
              />
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20 hover:bg-white/15 hover:border-amber-400/50 hover:scale-105 transition-all duration-300">
                <div className="text-3xl font-bold text-amber-400 mb-1">4-6 мес</div>
                <div className="text-sm text-slate-300">средний срок окупаемости</div>
              </div>
            </div>

            {/* CTA Buttons - added more internal links */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start animate-fade-in-delay-3">
              <a
                href="#calculator"
                className="group relative bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-xl hover:shadow-2xl overflow-hidden animate-pulse-subtle"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-amber-400 to-orange-600 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="absolute inset-0 bg-amber-400 rounded-lg opacity-20 animate-ping"></div>
                <span className="relative z-10">Рассчитать экономию</span>
              </a>
              <a
                href="#services"
                className="group relative bg-blue-600/90 hover:bg-blue-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all backdrop-blur-sm border border-blue-500/50 hover:border-blue-400 transform hover:scale-105 shadow-lg"
              >
                <span className="relative z-10">Наши услуги</span>
              </a>
              <a
                href="#faq"
                className="group relative bg-white/10 hover:bg-white/20 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all backdrop-blur-sm border border-white/30 hover:border-white/60 transform hover:scale-105 shadow-lg"
              >
                <span className="relative z-10">FAQ</span>
              </a>
            </div>
          </div>

          {/* Right side - Illustration */}
          <div className="hidden lg:block animate-fade-in-delay-2">
            <HeroIllustration />
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
          <div className="text-white/50 text-sm mb-2 text-center">Листайте вниз</div>
          <svg className="w-6 h-6 text-white/50 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </div>
      </div>
    </section>
  );
}
