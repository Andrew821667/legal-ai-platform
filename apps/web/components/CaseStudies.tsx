"use client";

import { useScrollAnimation } from "@/lib/hooks/useScrollAnimation";
import { useScrollAnimationMultiple } from "@/lib/hooks/useScrollAnimationMultiple";

// SVG Icons Components
const AgroIcon = () => (
  <svg viewBox="0 0 100 100" className="w-20 h-20">
    {/* Wheat stalks */}
    <g fill="#fbbf24">
      <ellipse cx="35" cy="30" rx="3" ry="5" />
      <ellipse cx="30" cy="38" rx="3" ry="5" />
      <ellipse cx="40" cy="38" rx="3" ry="5" />
      <ellipse cx="35" cy="46" rx="3" ry="5" />
      <rect x="34" y="50" width="2" height="40" fill="#92400e" />

      <ellipse cx="55" cy="25" rx="3" ry="5" />
      <ellipse cx="50" cy="33" rx="3" ry="5" />
      <ellipse cx="60" cy="33" rx="3" ry="5" />
      <ellipse cx="55" cy="41" rx="3" ry="5" />
      <rect x="54" y="45" width="2" height="45" fill="#92400e" />
    </g>
    {/* Document */}
    <rect x="60" y="60" width="30" height="35" rx="2" fill="#fff" stroke="#3b82f6" strokeWidth="2" />
    <line x1="65" y1="68" x2="85" y2="68" stroke="#1e293b" strokeWidth="1.5" />
    <line x1="65" y1="75" x2="85" y2="75" stroke="#1e293b" strokeWidth="1.5" opacity="0.6" />
    <line x1="65" y1="82" x2="80" y2="82" stroke="#1e293b" strokeWidth="1.5" opacity="0.6" />
    {/* AI badge */}
    <circle cx="82" cy="88" r="6" fill="#10b981" />
    <text x="82" y="91" fontSize="6" fill="#fff" textAnchor="middle" fontWeight="bold">AI</text>
  </svg>
);

const BankIcon = () => (
  <svg viewBox="0 0 100 100" className="w-20 h-20">
    {/* Bank building */}
    <polygon points="50,20 20,35 20,40 80,40 80,35" fill="#3b82f6" />
    <rect x="25" y="42" width="8" height="40" fill="#1e40af" />
    <rect x="37" y="42" width="8" height="40" fill="#1e40af" />
    <rect x="49" y="42" width="8" height="40" fill="#1e40af" />
    <rect x="61" y="42" width="8" height="40" fill="#1e40af" />
    <rect x="20" y="82" width="60" height="6" fill="#1e3a8a" />
    {/* Digital elements */}
    <circle cx="70" cy="60" r="12" fill="#10b981" opacity="0.9" />
    <path d="M 65 60 L 68 63 L 75 55" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" />
    {/* Circuit lines */}
    <line x1="70" y1="45" x2="70" y2="48" stroke="#fbbf24" strokeWidth="2" />
    <line x1="85" y1="60" x2="82" y2="60" stroke="#fbbf24" strokeWidth="2" />
  </svg>
);

const HoldingIcon = () => (
  <svg viewBox="0 0 100 100" className="w-20 h-20">
    {/* Office building */}
    <rect x="25" y="25" width="50" height="60" fill="#6366f1" />
    <rect x="20" y="82" width="60" height="5" fill="#4338ca" />
    {/* Windows */}
    {[0, 1, 2, 3].map(row =>
      [0, 1, 2, 3].map(col => (
        <rect
          key={`${row}-${col}`}
          x={30 + col * 10}
          y={32 + row * 12}
          width="6"
          height="8"
          fill="#a5b4fc"
          opacity="0.8"
        />
      ))
    )}
    {/* M&A arrows */}
    <g opacity="0.9">
      <circle cx="78" cy="35" r="10" fill="#10b981" />
      <path d="M 73 35 L 78 30 L 83 35" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M 73 35 L 78 40 L 83 35" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </g>
  </svg>
);

export default function CaseStudies() {
  const { ref: headerRef, isVisible: headerVisible } = useScrollAnimation();

  const cases = [
    {
      industry: "Агрохолдинг",
      IconComponent: AgroIcon,
      gradient: "from-amber-500 to-orange-500",
      problem: {
        title: "Проблема",
        points: [
          "50+ договоров в месяц требуют проверки",
          "2 юриста не успевают проверять все документы",
          "Пропуск критически важных условий",
          "2-4 часа на проверку одного договора",
        ],
      },
      solution: {
        title: "Решение",
        points: [
          "Разработка AI-системы для анализа договоров",
          "Обучение системы на внутренних шаблонах компании",
          "Интеграция с 1C и корпоративной почтой",
          "Автоматическое выявление рисков в договорах",
        ],
      },
      results: {
        title: "Результаты",
        metrics: [
          { label: "Время проверки", value: "2-4 ч → 30 мин", highlight: "8x быстрее" },
          { label: "Выявление рисков", value: "95%+", highlight: "автоматически" },
          { label: "Экономия времени", value: "80 часов/мес", highlight: "2 ставки юриста" },
          { label: "ROI", value: "4 месяца", highlight: "окупаемость" },
        ],
      },
      testimonial:
        "После внедрения AI рутинная проверка ушла в автомат, команда сосредоточилась на сложных задачах.",
      role: "Главный юрист",
    },
    {
      industry: "Банк",
      IconComponent: BankIcon,
      gradient: "from-blue-500 to-indigo-600",
      problem: {
        title: "Проблема",
        points: [
          "200+ процедур банкротства одновременно",
          "Ручной мониторинг КАД по всем делам",
          "Пропуск сроков из-за человеческого фактора",
          "Огромный объем процессуальных документов",
        ],
      },
      solution: {
        title: "Решение",
        points: [
          "Автоматизация мониторинга картотеки арбитражных дел",
          "AI-генерация процессуальных документов",
          "Уведомления о критических сроках",
          "Анализ судебной практики по аналогичным делам",
        ],
      },
      results: {
        title: "Результаты",
        metrics: [
          { label: "Мониторинг дел", value: "24/7", highlight: "автоматически" },
          { label: "Пропущенных сроков", value: "0", highlight: "за 6 месяцев" },
          { label: "Генерация документов", value: "15 мин", highlight: "вместо 3 часов" },
          { label: "Экономия", value: "3 млн ₽/год", highlight: "на ФОТ" },
        ],
      },
      testimonial:
        "Система сама мониторит дела и сроки, а юристы занимаются аналитикой и стратегией.",
      role: "Начальник юридического управления",
    },
    {
      industry: "Холдинг",
      IconComponent: HoldingIcon,
      gradient: "from-indigo-500 to-purple-600",
      problem: {
        title: "Проблема",
        points: [
          "Due Diligence занимала 2-3 недели",
          "Анализ сотен документов вручную",
          "Высокий риск пропустить важные детали",
          "Задержки в закрытии сделок M&A",
        ],
      },
      solution: {
        title: "Решение",
        points: [
          "AI-система для автоматизированного Due Diligence",
          "Анализ правоустанавливающих документов",
          "Выявление юридических рисков и обременений",
          "Структурированные отчеты для руководства",
        ],
      },
      results: {
        title: "Результаты",
        metrics: [
          { label: "Время DD", value: "2-3 недели → 2 дня", highlight: "10x быстрее" },
          { label: "Анализ документов", value: "500+ за день", highlight: "автоматически" },
          { label: "Выявленные риски", value: "85%+", highlight: "точность" },
          { label: "Ускорение сделок", value: "в 5 раз", highlight: "быстрее" },
        ],
      },
      testimonial:
        "Due Diligence перестал тормозить сделки: решения принимаем быстрее и увереннее.",
      role: "Директор по правовым вопросам",
    },
  ];

  const { setRef, visibleItems } = useScrollAnimationMultiple(cases.length, {
    threshold: 0.15,
    rootMargin: "0px 0px -100px 0px",
  });

  return (
    <section id="cases" className="py-20 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div ref={headerRef} className={`text-center mb-16 scroll-reveal ${headerVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Кейсы и результаты
          </h2>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            Реальные примеры внедрения AI в юридических командах.
          </p>
        </div>

        {/* Cases */}
        <div className="space-y-12">
          {cases.map((caseStudy, index) => (
            <div
              key={index}
              ref={setRef(index)}
              className={`scroll-reveal ${visibleItems[index] ? 'visible' : ''} bg-white/10 backdrop-blur-sm rounded-2xl p-8 md:p-12 border border-white/20 hover:border-white/40 transition-all duration-500`}
              style={{ transitionDelay: `${index * 0.2}s` }}
            >
              {/* Header */}
              <div className="flex items-center gap-4 mb-8">
                <div className={`p-4 rounded-2xl bg-gradient-to-br ${caseStudy.gradient} shadow-xl`}>
                  <caseStudy.IconComponent />
                </div>
                <h3 className="text-3xl font-bold text-white">
                  {caseStudy.industry}
                </h3>
              </div>

              {/* Problem, Solution, Results Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
                {/* Problem */}
                <div>
                  <h4 className="text-xl font-bold text-red-400 mb-4 flex items-center gap-2">
                    <span>❌</span> {caseStudy.problem.title}
                  </h4>
                  <ul className="space-y-2">
                    {caseStudy.problem.points.map((point, idx) => (
                      <li key={idx} className="text-slate-300 text-sm">
                        • {point}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Solution */}
                <div>
                  <h4 className="text-xl font-bold text-blue-400 mb-4 flex items-center gap-2">
                    <span>🔧</span> {caseStudy.solution.title}
                  </h4>
                  <ul className="space-y-2">
                    {caseStudy.solution.points.map((point, idx) => (
                      <li key={idx} className="text-slate-300 text-sm">
                        • {point}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Results */}
                <div>
                  <h4 className="text-xl font-bold text-green-400 mb-4 flex items-center gap-2">
                    <span>✅</span> {caseStudy.results.title}
                  </h4>
                  <div className="space-y-3">
                    {caseStudy.results.metrics.map((metric, idx) => (
                      <div key={idx} className="bg-white/10 rounded-lg p-3">
                        <div className="text-xs text-slate-400 mb-1">
                          {metric.label}
                        </div>
                        <div className="text-amber-400 font-bold">
                          {metric.value}
                        </div>
                        <div className="text-xs text-green-400">
                          {metric.highlight}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Testimonial */}
              <div className="bg-amber-500/20 border border-amber-500/50 rounded-xl p-6">
                <div className="flex gap-4">
                  <div className="text-3xl">💬</div>
                  <div>
                    <p className="text-slate-200 italic mb-3">
                      "{caseStudy.testimonial}"
                    </p>
                    <p className="text-slate-400 text-sm">
                      — {caseStudy.role}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="mt-16 text-center">
          <h3 className="text-3xl font-bold text-white mb-4">
            Хотите такие же результаты?
          </h3>
          <p className="text-xl text-slate-300 mb-6 max-w-2xl mx-auto">
            Обсудим ваш процесс и покажем, где AI даст быстрый эффект.
          </p>
          <a
            href="https://t.me/legal_ai_helper_new_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-lg"
          >
            Обсудить ваш проект в Telegram →
          </a>
        </div>
      </div>
    </section>
  );
}
