"use client";

import {
  FileText,
  Scale,
  Building2,
  Sprout,
  ShieldCheck,
  BarChart3,
  Settings,
  Briefcase,
  Coins,
} from "lucide-react";
import { useScrollAnimation } from "@/lib/hooks/useScrollAnimation";

export default function Services() {
  const { ref: headerRef, isVisible: headerVisible } = useScrollAnimation();
  const { ref: gridRef, isVisible: gridVisible } = useScrollAnimation({ threshold: 0.1 });

  const services = [
    {
      icon: FileText,
      title: "Договорная работа",
      description: "Проверяем и готовим договоры за минуты, подсвечиваем риски и спорные пункты.",
      price: "от 150 тыс. ₽",
      sources: ["Гражданский кодекс РФ", "Судебная практика Верховного Суда РФ", "Постановления Пленума ВС РФ"],
      features: [
        "AI-анализ рисков",
        "Конструктор документов",
        "Протоколы разногласий",
        "База знаний",
      ],
      pageHref: "/services/contracts-ai",
      gradient: "from-blue-500 to-indigo-600",
    },
    {
      icon: Scale,
      title: "Судебная работа",
      description: "Ищем релевантную практику, готовим процессуальные документы и следим за делами.",
      price: "от 200 тыс. ₽",
      sources: ["Картотека арбитражных дел (kad.arbitr.ru)", "ГАС Правосудие", "КонсультантПлюс"],
      features: [
        "Поиск прецедентов",
        "Генерация исков",
        "Мониторинг дел",
        "Предиктивная аналитика",
      ],
      pageHref: "/services/litigation-ai",
      gradient: "from-amber-500 to-orange-600",
    },
    {
      icon: Building2,
      title: "Корпоративное право и M&A",
      description: "Ускоряем Due Diligence и анализ корпоративных документов для сделок M&A.",
      price: "от 300 тыс. ₽",
      sources: ["ФЗ об ООО", "ФЗ об Акционерных обществах", "Реестр ЕГРЮЛ"],
      features: [
        "Due Diligence за часы",
        "Анализ уставов",
        "Сделки M&A",
        "Реестр акционеров",
      ],
      pageHref: "/services/corporate-ma-ai",
      gradient: "from-emerald-500 to-teal-600",
    },
    {
      icon: Sprout,
      title: "Земельное право",
      description: "Анализируем документы, работаем с кадастром и сопровождаем земельные сделки.",
      price: "от 250 тыс. ₽",
      sources: ["Земельный кодекс РФ", "Публичная кадастровая карта", "Росреестр"],
      features: [
        "Кадастровый анализ",
        "Сделки с землей",
        "Оспаривание стоимости",
        "Арендные отношения",
      ],
      pageHref: "/services/land-law-ai",
      gradient: "from-lime-500 to-green-600",
    },
    {
      icon: ShieldCheck,
      title: "Комплаенс",
      description: "Мониторим изменения закона и помогаем выстроить санкционный и антикоррупционный контроль.",
      price: "от 200 тыс. ₽",
      sources: ["КоАП РФ", "Методические рекомендации ЦБ РФ", "ФЗ о противодействии коррупции"],
      features: [
        "Мониторинг 24/7",
        "Антикоррупция",
        "Санкционный контроль",
        "Внутренний аудит",
      ],
      pageHref: "/services/compliance-ai",
      gradient: "from-red-500 to-rose-600",
    },
    {
      icon: BarChart3,
      title: "Аналитика",
      description: "Строим дашборды рисков и KPI юридической функции на данных компании.",
      price: "от 150 тыс. ₽",
      sources: ["Внутренняя статистика компании", "Отраслевые бенчмарки", "Данные судебного департамента"],
      features: [
        "Анализ портфеля",
        "Риск-дашборды",
        "KPI отдела",
        "Прогнозирование",
      ],
      pageHref: "/services/legal-analytics-ai",
      gradient: "from-violet-500 to-purple-600",
    },
    {
      icon: Settings,
      title: "Кастомные решения",
      description: "Делаем AI-решения под вашу отрасль и интегрируем с 1С, CRM и внутренними системами.",
      price: "от 300 тыс. ₽",
      sources: ["Техническая документация API", "Best Practices разработки", "GDPR/152-ФЗ"],
      features: [
        "Под вашу отрасль",
        "Интеграция с 1С/CRM",
        "Обучение на данных",
        "On-premise / Cloud",
      ],
      pageHref: "/services/custom-ai",
      gradient: "from-cyan-500 to-blue-600",
    },
    {
      icon: Briefcase,
      title: "Аутсорсинг + AI",
      description: "Комбинируем работу юриста и AI: закрываем рутину и усиливаем команду без лишнего найма.",
      price: "от 100 тыс. ₽/мес",
      sources: ["Стандарты оказания юридических услуг", "Кодекс профессиональной этики адвоката"],
      features: [
        "Юрист + AI",
        "Договорная работа",
        "Суды и арбитраж",
        "Консультации",
      ],
      pageHref: "/services/outsourcing-ai",
      gradient: "from-fuchsia-500 to-pink-600",
    },
    {
      icon: Coins,
      title: "Налоговый комплаенс с AI-аналитикой",
      description: "Следим за изменениями в налогах, оцениваем риски и автоматизируем регулярную отчетность.",
      price: "от 200 тыс. ₽",
      sources: ["Налоговый кодекс РФ", "Письма Минфина и ФНС", "Арбитражная практика по налоговым спорам"],
      features: [
        "Мониторинг изменений 24/7",
        "Проверка контрагентов",
        "Анализ налоговых рисков",
        "Автоматизация отчетности",
      ],
      pageHref: "/services/tax-compliance-ai",
      gradient: "from-yellow-500 to-amber-600",
    },
  ];

  return (
    <section id="services" className="py-20 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div ref={headerRef} className={`text-center mb-16 scroll-reveal ${headerVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
            Наши услуги
          </h2>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Готовые и кастомные AI-решения для юридического отдела.
          </p>
        </div>

        {/* Services Grid */}
        <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map((service, index) => (
            <div
              key={index}
              className={`stagger-item ${gridVisible ? 'visible' : ''} group bg-white rounded-xl p-6 shadow-lg hover:shadow-2xl transition-all duration-500 border border-slate-200 hover:border-amber-300 flex flex-col relative overflow-hidden transform hover:-translate-y-2`}
            >
              {/* Glow effect on hover */}
              <div className="absolute inset-0 bg-gradient-to-br from-amber-400/0 to-amber-600/0 group-hover:from-amber-400/5 group-hover:to-amber-600/5 transition-all duration-500 rounded-xl"></div>

              <div className="relative z-10 flex flex-col h-full">
                {/* Icon with gradient background */}
                <div className="mb-4 group-hover:scale-110 group-hover:rotate-3 transition-all duration-300">
                  <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${service.gradient} shadow-lg`}>
                    <service.icon className="w-10 h-10 text-white" strokeWidth={1.5} />
                  </div>
                </div>

                {/* Title */}
                <h3 className="text-xl font-bold text-slate-900 mb-3 group-hover:text-amber-700 transition-colors">
                  {service.title}
                </h3>

                {/* Description */}
                <p className="text-slate-600 text-sm mb-4 leading-relaxed flex-grow">
                  {service.description}
                </p>

                {/* Features */}
                <ul className="space-y-2 mb-4">
                  {service.features.map((feature, idx) => (
                    <li key={idx} className="text-sm text-slate-700 flex items-start">
                      <span className={`mr-2 mt-1 w-1.5 h-1.5 rounded-full bg-gradient-to-br ${service.gradient}`}></span>
                      {feature}
                    </li>
                  ))}
                </ul>

                {/* Sources (for SEO schema, hidden visually but useful for data) */}
                <div className="hidden">
                  {service.sources?.join(", ")}
                </div>

                {/* Price */}
                <div className="text-lg font-bold text-amber-600 mb-4">
                  {service.price}
                </div>

                {/* CTA Button */}
                {service.pageHref ? (
                  <a
                    href={service.pageHref}
                    className="w-full block text-center py-3 rounded-lg border border-slate-200 text-slate-600 font-medium hover:bg-slate-50 hover:text-amber-600 transition-colors"
                  >
                    Подробнее
                  </a>
                ) : (
                  <a
                    href="https://t.me/legal_ai_helper_new_bot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full block text-center py-3 rounded-lg border border-slate-200 text-slate-600 font-medium hover:bg-slate-50 hover:text-amber-600 transition-colors"
                  >
                    Подробнее
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="mt-16 text-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700 rounded-2xl p-12">
          <h3 className="text-3xl font-bold text-white mb-4">
            Не нашли нужную услугу?
          </h3>
          <p className="text-xl text-slate-300 mb-6 max-w-2xl mx-auto">
            Подберем формат под ваши задачи и бюджет.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href="/services"
              className="inline-block bg-white text-slate-800 font-bold py-3 px-8 rounded-lg text-lg transition-transform hover:scale-105 shadow-lg"
            >
              Все услуги подробно
            </a>
            <a
              href="https://t.me/legal_ai_helper_new_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-bold py-3 px-8 rounded-lg text-lg transition-transform hover:scale-105 shadow-lg"
            >
              Связаться с нами
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
