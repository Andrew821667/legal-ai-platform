"use client";

import { useScrollAnimation } from '@/lib/hooks/useScrollAnimation';
import { Check, X } from 'lucide-react';

export default function ComparisonTable() {
  const { ref, isVisible } = useScrollAnimation();

  const comparisons = [
    {
      task: "Анализ договора (20 страниц)",
      withoutAI: "ручная проверка всего документа",
      withAI: "первичный AI-разбор и подсветка зон внимания",
      improvement: "быстрее первый проход"
    },
    {
      task: "Поиск судебной практики",
      withoutAI: "ручной поиск и сверка вручную",
      withAI: "быстрый shortlist релевантных материалов",
      improvement: "меньше рутины"
    },
    {
      task: "Due Diligence (100 документов)",
      withoutAI: "сплошной ручной просмотр",
      withAI: "первичная сортировка и кластеризация",
      improvement: "быстрее обзор массива"
    },
    {
      task: "Мониторинг законодательства",
      withoutAI: "вручную и нерегулярно",
      withAI: "по настроенному сценарию мониторинга",
      improvement: "лучше контроль"
    },
    {
      task: "Генерация типового договора",
      withoutAI: "с нуля или по старому шаблону",
      withAI: "черновик под проверку юриста",
      improvement: "быстрее старт"
    },
    {
      task: "Анализ рисков в документе",
      withoutAI: "целиком вручную",
      withAI: "автоподсветка спорных условий",
      improvement: "лучше приоритизация"
    }
  ];

  return (
    <section className="py-20 bg-gradient-to-br from-slate-900 to-slate-800 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-amber-500 rounded-full filter blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500 rounded-full filter blur-3xl animate-pulse" style={{animationDelay: '1s'}}></div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div ref={ref} className={`text-center mb-16 scroll-reveal ${isVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Работа с AI vs Без AI
          </h2>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            Сравниваем не “замену юриста”, а то, где AI ускоряет первый проход и снижает объем рутины.
          </p>
        </div>

        <div className="overflow-x-auto">
          <div className="inline-block min-w-full align-middle">
            <div className="overflow-hidden rounded-2xl shadow-2xl">
              <table className="min-w-full">
                <thead>
                  <tr className="bg-white/10 backdrop-blur-sm border-b border-white/20">
                    <th className="px-6 py-4 text-left text-lg font-bold text-white">
                      Задача
                    </th>
                    <th className="px-6 py-4 text-center text-lg font-bold text-red-400 flex items-center justify-center gap-2">
                      <X className="w-5 h-5" />
                      Без AI
                    </th>
                    <th className="px-6 py-4 text-center text-lg font-bold text-green-400">
                      <div className="flex items-center justify-center gap-2">
                        <Check className="w-5 h-5" />
                        С AI
                      </div>
                    </th>
                    <th className="px-6 py-4 text-center text-lg font-bold text-amber-400">
                      Экономия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white/5 backdrop-blur-sm">
                  {comparisons.map((item, index) => (
                    <tr
                      key={index}
                      className="border-b border-white/10 hover:bg-white/10 transition-colors duration-200"
                    >
                      <td className="px-6 py-4 text-white font-semibold">
                        {item.task}
                      </td>
                      <td className="px-6 py-4 text-center text-slate-300">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-red-400"></div>
                          {item.withoutAI}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center text-white font-semibold">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                          {item.withAI}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="inline-block px-4 py-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-white font-bold text-lg shadow-lg">
                          {item.improvement}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 text-center">
            <div className="text-4xl font-bold text-amber-400 mb-2">Пилот</div>
            <div className="text-slate-300">Сначала проверяем гипотезу на одном процессе</div>
          </div>
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 text-center">
            <div className="text-4xl font-bold text-green-400 mb-2">Контроль</div>
            <div className="text-slate-300">Финальное решение и проверка остаются у юриста</div>
          </div>
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20 text-center">
            <div className="text-4xl font-bold text-blue-400 mb-2">Оценка</div>
            <div className="text-slate-300">Считаем эффект только на ваших вводных и конкретном процессе</div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center mt-12">
          <p className="text-lg text-slate-300 mb-6">
            Разберем, где у вас есть смысл запускать пилот в первую очередь
          </p>
          <a
            href="#calculator"
            className="inline-block bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-xl"
          >
            Рассчитать экономию →
          </a>
        </div>
      </div>
    </section>
  );
}
