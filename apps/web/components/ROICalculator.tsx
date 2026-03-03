"use client";

import { useEffect, useState } from "react";
import { useScrollAnimation } from "@/lib/hooks/useScrollAnimation";

export default function ROICalculator() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation({ threshold: 0.1 });

  const [contractsPerMonth, setContractsPerMonth] = useState(50);
  const [hoursPerContract, setHoursPerContract] = useState(2);
  const [teamRate, setTeamRate] = useState(1800);
  const [pilotShare, setPilotShare] = useState(35);

  const [results, setResults] = useState({
    currentHours: 0,
    pilotHours: 0,
    pilotValue: 0,
  });

  useEffect(() => {
    const currentHours = Math.round(contractsPerMonth * hoursPerContract);
    const pilotHours = Math.round(currentHours * (pilotShare / 100));
    const pilotValue = Math.round(pilotHours * teamRate * 12);

    setResults({
      currentHours,
      pilotHours,
      pilotValue,
    });
  }, [contractsPerMonth, hoursPerContract, teamRate, pilotShare]);

  return (
    <section id="calculator" className="py-20 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div ref={sectionRef} className={`text-center mb-12 scroll-reveal ${sectionVisible ? "visible" : ""}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Предварительная оценка эффекта
          </h2>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto">
            Это не обещание ROI, а быстрый способ понять масштаб задачи и потенциал пилота на одном процессе.
          </p>
        </div>

        <div className={`grid grid-cols-1 lg:grid-cols-2 gap-12 items-start scroll-reveal ${sectionVisible ? "visible" : ""}`}>
          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/20">
            <h3 className="text-2xl font-bold text-white mb-6">
              Вводные по процессу
            </h3>

            <div className="space-y-6">
              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Документов или задач в месяц
                </label>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={contractsPerMonth}
                  onChange={(e) => setContractsPerMonth(parseInt(e.target.value, 10) || 1)}
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Часов на одну задачу сейчас
                </label>
                <input
                  type="number"
                  min="0.25"
                  max="24"
                  step="0.25"
                  value={hoursPerContract}
                  onChange={(e) => setHoursPerContract(parseFloat(e.target.value) || 0.25)}
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Внутренняя стоимость часа команды (₽)
                </label>
                <input
                  type="number"
                  min="500"
                  max="20000"
                  step="100"
                  value={teamRate}
                  onChange={(e) => setTeamRate(parseInt(e.target.value, 10) || 500)}
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Какую долю процесса вы готовы дать в пилот (%)
                </label>
                <input
                  type="number"
                  min="5"
                  max="100"
                  step="5"
                  value={pilotShare}
                  onChange={(e) => setPilotShare(parseInt(e.target.value, 10) || 5)}
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-amber-500/20 backdrop-blur-sm rounded-2xl p-8 border border-amber-500/50">
              <h3 className="text-2xl font-bold text-white mb-6">
                Что это показывает
              </h3>

              <div className="space-y-6">
                <div className="bg-white/10 rounded-xl p-6">
                  <div className="text-slate-300 mb-2">Текущий объем ручной работы</div>
                  <div className="text-4xl font-bold text-amber-400">
                    {results.currentHours} <span className="text-2xl">часов/мес</span>
                  </div>
                </div>

                <div className="bg-white/10 rounded-xl p-6">
                  <div className="text-slate-300 mb-2">Объем пилотного контура</div>
                  <div className="text-4xl font-bold text-amber-400">
                    {results.pilotHours} <span className="text-2xl">часов/мес</span>
                  </div>
                </div>

                <div className="bg-white/10 rounded-xl p-6">
                  <div className="text-slate-300 mb-2">Годовой объем работы внутри пилота</div>
                  <div className="text-4xl font-bold text-amber-400">
                    {results.pilotValue.toLocaleString("ru-RU")} <span className="text-2xl">₽/год</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center">
              <p className="text-slate-300 mb-4">
                По этим вводным можно обсудить, какой пилот имеет смысл запускать первым.
              </p>
              <a
                href="https://t.me/legal_ai_helper_new_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-lg"
              >
                Обсудить пилот в Telegram →
              </a>
            </div>
          </div>
        </div>

        <div className="mt-12 text-center">
          <p className="text-slate-400 text-sm max-w-3xl mx-auto">
            Расчет ориентировочный. Он не подменяет полноценную оценку проекта и не является обещанием экономического эффекта.
            Реальный результат зависит от процесса, качества исходных данных, объема ручной проверки и выбранной архитектуры.
          </p>
        </div>
      </div>
    </section>
  );
}
