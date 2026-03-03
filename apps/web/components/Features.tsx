"use client";

import { useScrollAnimation } from "@/lib/hooks/useScrollAnimation";
import { Briefcase, Bot, Flag, TrendingUp, Zap } from "lucide-react";
import Card3D from "./Card3D";

export default function Features() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation();
  const { ref: gridRef, isVisible: gridVisible } = useScrollAnimation({ threshold: 0.05 });

  const openLeadForm = () => {
    if (typeof window === "undefined") return;
    const target = document.getElementById("lead-form");
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const features = [
    {
      icon: Briefcase,
      title: "Юридическая практика",
      description: `Опираемся на практический опыт внутри юридической функции.
        Поэтому автоматизируем не “в целом AI”, а конкретные рабочие процессы.`,
    },
    {
      icon: Bot,
      title: "Собственная разработка",
      description: `Сами проектируем backend, ботов и контуры публикации.
        Это дает контроль над качеством, безопасностью и скоростью изменений.`,
    },
    {
      icon: Flag,
      title: "Гибкий стек моделей",
      description: `Подбираем модель и архитектуру под задачу: локальные ограничения,
        требования по данным, стоимость владения и ожидаемое качество.`,
    },
    {
      icon: TrendingUp,
      title: "Фокус на рутине и контроле",
      description: `Начинаем с процессов, где эффект измерим: заявки, договоры,
        маршрутизация задач, контроль сроков и подготовка типовых материалов.`,
    },
    {
      icon: Zap,
      title: "Пилот вместо абстракций",
      description: `Сначала проверяем гипотезу на реальном процессе, а затем
        масштабируем решение только там, где оно действительно работает.`,
    }
  ];

  return (
    <section id="features" className="py-20 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header - LSI keywords added */}
        <div ref={sectionRef} className={`text-center mb-16 scroll-reveal ${sectionVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
            Эксперты по автоматизации юридических функций
          </h2>
          <p className="text-xl text-slate-600 max-w-3xl mx-auto">
            Внедряем понятные Legal Tech решения для договоров, судебной работы и комплаенса.
            <a href="#services" className="text-amber-600 hover:text-amber-700 underline ml-1">Посмотреть услуги</a>.
          </p>
        </div>

        {/* Features Grid */}
        <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8">
          {features.map((feature, index) => (
            <Card3D
              key={index}
              className={`stagger-item ${gridVisible ? 'visible' : ''} group bg-white rounded-xl p-8 shadow-lg hover:shadow-2xl transition-all duration-500 border border-slate-200 hover:border-amber-300 relative overflow-hidden`}
            >
              {/* Glow effect on hover */}
              <div className="absolute inset-0 bg-gradient-to-br from-amber-400/0 to-amber-600/0 group-hover:from-amber-400/5 group-hover:to-amber-600/5 transition-all duration-500 rounded-xl"></div>

              <div className="relative z-10">
                {/* Icon */}
                <div className="mb-4 group-hover:scale-110 group-hover:rotate-6 transition-all duration-300">
                  <feature.icon className="w-12 h-12 text-amber-600 group-hover:text-amber-700" strokeWidth={1.5} />
                </div>

                {/* Title */}
                <h3 className="text-xl font-bold text-slate-900 mb-3 group-hover:text-amber-700 transition-colors">
                  {feature.title}
                </h3>

                {/* Description */}
                <p className="text-slate-600 leading-relaxed mb-3" style={{ whiteSpace: 'pre-line' }}>
                  {feature.description}
                </p>
                
              </div>
            </Card3D>
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="text-center mt-16">
          <p className="text-lg text-slate-700 mb-6">
            Хотите понять, что можно автоматизировать у вас?
          </p>
          <button
            type="button"
            onClick={openLeadForm}
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-lg"
          >
            Оставить заявку →
          </button>
        </div>
      </div>
    </section>
  );
}
