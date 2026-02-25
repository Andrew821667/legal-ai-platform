"use client";

import { useScrollAnimation } from '@/lib/hooks/useScrollAnimation';
import { ClipboardCheck, MessageSquare, Code, Rocket, BarChart, HeadphonesIcon } from 'lucide-react';

export default function ProcessTimeline() {
  const { ref, isVisible } = useScrollAnimation();

  const steps = [
    {
      icon: MessageSquare,
      title: "Консультация",
      description: "Анализируем ваши бизнес-процессы и выявляем точки автоматизации",
      duration: "1-2 дня",
      color: "from-blue-500 to-cyan-500"
    },
    {
      icon: ClipboardCheck,
      title: "Аудит процессов",
      description: "Детально изучаем документооборот и юридические процедуры",
      duration: "3-5 дней",
      color: "from-purple-500 to-pink-500"
    },
    {
      icon: Code,
      title: "Разработка",
      description: "Создаем AI-решение под ваши задачи с учетом специфики бизнеса",
      duration: "2-4 недели",
      color: "from-amber-500 to-orange-500"
    },
    {
      icon: Rocket,
      title: "Внедрение",
      description: "Интегрируем систему в ваши процессы и обучаем сотрудников",
      duration: "1-2 недели",
      color: "from-green-500 to-emerald-500"
    },
    {
      icon: BarChart,
      title: "Оптимизация",
      description: "Настраиваем систему на основе реальных данных и обратной связи",
      duration: "2-3 недели",
      color: "from-indigo-500 to-purple-500"
    },
    {
      icon: HeadphonesIcon,
      title: "Поддержка",
      description: "Предоставляем техническую поддержку и развиваем функционал",
      duration: "постоянно",
      color: "from-red-500 to-pink-500"
    }
  ];

  return (
    <section className="py-20 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div ref={ref} className={`text-center mb-16 scroll-reveal ${isVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
            Как мы работаем
          </h2>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Прозрачный и понятный процесс от первой встречи до полноценной работы системы
          </p>
        </div>

        <div className="relative">
          {/* Timeline line */}
          <div className="hidden md:block absolute left-1/2 transform -translate-x-1/2 h-full w-1 bg-gradient-to-b from-blue-200 via-purple-200 to-pink-200"></div>

          {/* Steps */}
          <div className="space-y-12">
            {steps.map((step, index) => (
              <div
                key={index}
                className={`relative flex items-center ${
                  index % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'
                } flex-col gap-8`}
              >
                {/* Content card */}
                <div className="md:w-5/12 w-full">
                  <div className={`bg-white rounded-2xl p-6 shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 border-2 border-transparent hover:border-gradient-to-r ${step.color}`}>
                    <div className="flex items-start gap-4">
                      <div className={`p-3 rounded-xl bg-gradient-to-br ${step.color} shadow-lg`}>
                        <step.icon className="w-6 h-6 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="text-xl font-bold text-slate-900">
                            {step.title}
                          </h3>
                          <span className="text-sm font-semibold text-slate-500">
                            {step.duration}
                          </span>
                        </div>
                        <p className="text-slate-600 leading-relaxed">
                          {step.description}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Timeline dot */}
                <div className="hidden md:block absolute left-1/2 transform -translate-x-1/2">
                  <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${step.color} shadow-lg flex items-center justify-center text-white font-bold text-lg border-4 border-white`}>
                    {index + 1}
                  </div>
                </div>

                {/* Empty space for alternating layout */}
                <div className="hidden md:block md:w-5/12"></div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center mt-16">
          <p className="text-lg text-slate-700 mb-6">
            Готовы начать? Первая консультация бесплатно!
          </p>
          <a
            href="https://t.me/legal_ai_helper_new_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all transform hover:scale-105 shadow-lg"
          >
            Записаться на консультацию →
          </a>
        </div>
      </div>
    </section>
  );
}
