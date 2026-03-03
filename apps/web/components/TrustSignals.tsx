"use client";

import { CheckCircle2, Shield, FileCheck2, Workflow, Users } from "lucide-react";

const principles = [
  {
    icon: Workflow,
    title: "Начинаем с пилота",
    text: "Не продаем абстрактный AI. Сначала выбираем один процесс, ставим критерии эффекта и проверяем гипотезу на реальной работе.",
  },
  {
    icon: Shield,
    title: "Смотрим на данные и риски",
    text: "До внедрения разбираем, где персональные данные, коммерческая тайна, трансграничная передача и какие ограничения есть у инфраструктуры.",
  },
  {
    icon: FileCheck2,
    title: "Фиксируем роли и контуры ответственности",
    text: "Определяем, что остается у человека, где допустим AI-черновик, а где нужен обязательный ручной контроль и журналирование действий.",
  },
  {
    icon: Users,
    title: "Работаем под юридическую функцию",
    text: "Смотрим не только на модель, но и на маршрут заявки, договорный поток, комплаенс, сроки и то, как команда реально работает каждый день.",
  },
];

export default function TrustSignals() {
  return (
    <section id="trust" className="py-16 bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Как мы подходим к внедрению
          </h2>
          <p className="text-lg text-slate-300 max-w-3xl mx-auto">
            Для юридической функции важны не только скорость и удобство, но и контроль рисков, данных и ответственности.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {principles.map((item) => (
            <div
              key={item.title}
              className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-amber-500/40 transition-all"
            >
              <div className="flex items-start gap-4">
                <div className="rounded-xl bg-amber-500/10 p-3 border border-amber-500/20">
                  <item.icon className="w-6 h-6 text-amber-400" />
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-2">{item.title}</h3>
                  <p className="text-slate-300 leading-relaxed">{item.text}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
            <p className="text-slate-200">
              Если нужно, проект можно строить с учетом требований к локализации данных,
              контролю доступа, NDA, внутренним политикам и ограничению использования внешних моделей.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
