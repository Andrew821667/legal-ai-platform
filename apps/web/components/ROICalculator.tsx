"use client";

import { useState, useEffect } from "react";
import { useScrollAnimation } from "@/lib/hooks/useScrollAnimation";

export default function ROICalculator() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation({ threshold: 0.1 });

  // Form state
  const [lawyers, setLawyers] = useState(5);
  const [salary, setSalary] = useState(150000);
  const [contractsPerMonth, setContractsPerMonth] = useState(50);
  const [hoursPerContract, setHoursPerContract] = useState(2);

  // Results state
  const [results, setResults] = useState({
    timeSaved: 0,
    moneySaved: 0,
    roiMonths: 0,
  });

  // Calculate ROI whenever inputs change
  useEffect(() => {
    calculateROI();
  }, [lawyers, salary, contractsPerMonth, hoursPerContract]);

  const calculateROI = () => {
    // Current time spent on contracts per month
    const totalHours = contractsPerMonth * hoursPerContract;

    // Time saved with 80% automation
    const timeSaved = Math.round(totalHours * 0.8);

    // Money saved per month
    // Assuming 160 work hours per month
    const hourlyRate = salary / 160;
    const moneySavedPerMonth = Math.round(timeSaved * hourlyRate);

    // Money saved per year
    const moneySavedPerYear = moneySavedPerMonth * 12;

    // ROI calculation
    // Average implementation cost: 400,000 RUB
    const implementationCost = 400000;
    const roiMonths = (implementationCost / moneySavedPerMonth).toFixed(1);

    setResults({
      timeSaved,
      moneySaved: moneySavedPerYear,
      roiMonths: parseFloat(roiMonths),
    });
  };

  return (
    <section id="calculator" className="py-20 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div ref={sectionRef} className={`text-center mb-12 scroll-reveal ${sectionVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Рассчитайте вашу экономию
          </h2>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            Узнайте сколько времени и денег сэкономит AI-автоматизация для вашего юротдела
          </p>
        </div>

        <div className={`grid grid-cols-1 lg:grid-cols-2 gap-12 items-start scroll-reveal ${sectionVisible ? 'visible' : ''}`}>
          {/* Input Form */}
          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/20">
            <h3 className="text-2xl font-bold text-white mb-6">
              Данные вашей компании
            </h3>

            <div className="space-y-6">
              {/* Lawyers count */}
              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Количество юристов в команде
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={lawyers}
                  onChange={(e) => setLawyers(parseInt(e.target.value) || 1)}
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>

              {/* Average salary */}
              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Средняя зарплата юриста (₽/мес)
                </label>
                <input
                  type="number"
                  min="50000"
                  max="500000"
                  step="10000"
                  value={salary}
                  onChange={(e) => setSalary(parseInt(e.target.value) || 50000)}
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>

              {/* Contracts per month */}
              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Договоров в месяц
                </label>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={contractsPerMonth}
                  onChange={(e) =>
                    setContractsPerMonth(parseInt(e.target.value) || 1)
                  }
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>

              {/* Hours per contract */}
              <div>
                <label className="block text-slate-300 mb-2 font-medium">
                  Часов на проверку 1 договора
                </label>
                <input
                  type="number"
                  min="0.5"
                  max="20"
                  step="0.5"
                  value={hoursPerContract}
                  onChange={(e) =>
                    setHoursPerContract(parseFloat(e.target.value) || 0.5)
                  }
                  className="w-full px-4 py-3 rounded-lg bg-white/20 border border-white/30 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* Results Display */}
          <div className="space-y-6">
            <div className="bg-amber-500/20 backdrop-blur-sm rounded-2xl p-8 border border-amber-500/50">
              <h3 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
                <span>📊</span> Ваша экономия
              </h3>

              <div className="space-y-6">
                {/* Time saved */}
                <div className="bg-white/10 rounded-xl p-6">
                  <div className="text-slate-300 mb-2">Сэкономите времени</div>
                  <div className="text-4xl font-bold text-amber-400">
                    {results.timeSaved} <span className="text-2xl">часов/мес</span>
                  </div>
                </div>

                {/* Money saved */}
                <div className="bg-white/10 rounded-xl p-6">
                  <div className="text-slate-300 mb-2">Экономия в деньгах</div>
                  <div className="text-4xl font-bold text-amber-400">
                    {results.moneySaved.toLocaleString("ru-RU")}{" "}
                    <span className="text-2xl">₽/год</span>
                  </div>
                </div>

                {/* ROI */}
                <div className="bg-white/10 rounded-xl p-6">
                  <div className="text-slate-300 mb-2">Окупаемость (ROI)</div>
                  <div className="text-4xl font-bold text-amber-400">
                    {results.roiMonths}{" "}
                    <span className="text-2xl">
                      {results.roiMonths === 1
                        ? "месяц"
                        : results.roiMonths < 5
                        ? "месяца"
                        : "месяцев"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* CTA */}
            <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 border border-white/20 text-center">
              <p className="text-slate-300 mb-4">
                Впечатляющие цифры? Давайте обсудим внедрение для вашей компании
              </p>
              <a
                href="https://t.me/legal_ai_helper_new_bot"
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full bg-amber-600 hover:bg-amber-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-lg"
              >
                Обсудить внедрение в Telegram →
              </a>
            </div>
          </div>
        </div>

        {/* Bottom note */}
        <div className="mt-12 text-center">
          <p className="text-slate-400 text-sm">
            * Расчет основан на 80% экономии времени при автоматизации договорной работы.
            <br />
            Средняя стоимость внедрения: 300-500 тыс. ₽
          </p>
        </div>
      </div>
    </section>
  );
}
