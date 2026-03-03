"use client";

import { useState } from "react";
import { useScrollAnimation } from "@/lib/hooks/useScrollAnimation";
import { ChevronDown } from "lucide-react";
import { faqData } from "@/lib/faqData";

export default function FAQ() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation();
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const categories = [
    { id: "general", name: "Общие вопросы", emoji: "💡" },
    { id: "technical", name: "Технические", emoji: "⚙️" },
    { id: "pricing", name: "Стоимость и оценка", emoji: "💰" },
    { id: "implementation", name: "Внедрение", emoji: "🚀" }
  ];

  const toggleFAQ = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section id="faq" className="py-20 bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div ref={sectionRef} className={`text-center mb-16 scroll-reveal ${sectionVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
            Часто задаваемые вопросы
          </h2>
          <p className="text-xl text-slate-600 max-w-3xl mx-auto">
            Коротко отвечаем на главные вопросы по внедрению AI
          </p>
        </div>

        {/* FAQ by Categories */}
        <div className="space-y-12">
          {categories.map((category) => (
            <div key={category.id}>
              <h3 className="text-2xl font-bold text-slate-900 mb-6 flex items-center gap-3">
                <span className="text-3xl">{category.emoji}</span>
                {category.name}
              </h3>
              
              <div className="space-y-4">
                {faqData
                  .filter((item) => item.category === category.id)
                  .map((item, index) => {
                    const globalIndex = faqData.indexOf(item);
                    const isOpen = openIndex === globalIndex;
                    
                    return (
                      <div
                        key={globalIndex}
                        className="bg-white rounded-xl border border-slate-200 overflow-hidden transition-all duration-300 hover:shadow-lg"
                      >
                        <button
                          onClick={() => toggleFAQ(globalIndex)}
                          className="w-full px-6 py-5 text-left flex items-start justify-between gap-4 hover:bg-slate-50 transition-colors"
                        >
                          <span className="font-semibold text-slate-900 flex-1">
                            {item.question}
                          </span>
                          <ChevronDown
                            className={`w-5 h-5 text-amber-600 flex-shrink-0 transition-transform duration-300 ${
                              isOpen ? 'rotate-180' : ''
                            }`}
                          />
                        </button>
                        
                        <div
                          className={`transition-all duration-300 ease-in-out ${
                            isOpen ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
                          } overflow-hidden`}
                        >
                          <div className="px-6 pb-5 text-slate-600 leading-relaxed">
                            {item.answer}
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>

        {/* CTA after FAQ */}
        <div className="mt-16 bg-gradient-to-br from-amber-600 to-orange-600 rounded-2xl p-8 md:p-12 text-center text-white shadow-xl">
          <h3 className="text-3xl font-bold mb-4">
            Не нашли ответ на свой вопрос?
          </h3>
          <p className="text-xl text-white/90 mb-8 max-w-2xl mx-auto">
            Напишите нам, разберем вашу задачу на бесплатной консультации.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href="https://t.me/legal_ai_helper_new_bot?start=consultation"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center bg-white text-amber-700 font-semibold px-8 py-4 rounded-lg text-lg hover:bg-slate-100 transition-all transform hover:scale-105 shadow-lg"
            >
              Написать в Telegram
            </a>
            <a
              href="tel:+79092330909"
              className="inline-flex items-center justify-center bg-white/10 hover:bg-white/20 backdrop-blur-sm text-white font-semibold px-8 py-4 rounded-lg text-lg transition-all border border-white/30 hover:border-white/60"
            >
              Позвонить: +7 909 233-09-09
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
