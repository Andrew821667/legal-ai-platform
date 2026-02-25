"use client";

import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Quote, Star } from 'lucide-react';
import { useScrollAnimation } from '@/lib/hooks/useScrollAnimation';

interface Testimonial {
  name: string;
  position: string;
  company: string;
  content: string;
  rating: number;
  avatar: string;
}

export default function Testimonials() {
  const { ref, isVisible } = useScrollAnimation();
  const [currentIndex, setCurrentIndex] = useState(0);

  const testimonials: Testimonial[] = [
    {
      name: "Алексей Петров",
      position: "Генеральный директор",
      company: "АгроХолдинг \"Нива\"",
      content: "Автоматизация договорной работы сократила время на обработку документов на 85%. Система окупилась за 4 месяца. Теперь юристы занимаются действительно важными задачами, а не рутиной.",
      rating: 5,
      avatar: "AP"
    },
    {
      name: "Мария Соколова",
      position: "Руководитель юридического отдела",
      company: "Банк \"Столичный\"",
      content: "AI-система для судебной работы просто невероятна! Поиск прецедентов, который раньше занимал дни, теперь выполняется за минуты. Качество аналитики превосходит ожидания.",
      rating: 5,
      avatar: "МС"
    },
    {
      name: "Дмитрий Волков",
      position: "Юрисконсульт",
      company: "Холдинг \"Прогресс\"",
      content: "Due Diligence процесс ускорился в 10 раз. Система анализирует сотни документов за часы, выявляя риски, которые мы могли пропустить. Незаменимый инструмент для M&A сделок.",
      rating: 5,
      avatar: "ДВ"
    },
    {
      name: "Елена Кузнецова",
      position: "Директор по комплаенсу",
      company: "ТехноКорп",
      content: "Мониторинг законодательства 24/7 – это то, что нам было необходимо. Система моментально уведомляет об изменениях, релевантных для нашего бизнеса. Санкционный комплаенс на высшем уровне.",
      rating: 5,
      avatar: "ЕК"
    }
  ];

  const nextSlide = () => {
    setCurrentIndex((prev) => (prev + 1) % testimonials.length);
  };

  const prevSlide = () => {
    setCurrentIndex((prev) => (prev - 1 + testimonials.length) % testimonials.length);
  };

  useEffect(() => {
    const timer = setInterval(nextSlide, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="py-20 bg-gradient-to-br from-slate-900 to-slate-800 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-0 left-0 w-96 h-96 bg-amber-500 rounded-full filter blur-3xl"></div>
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-purple-500 rounded-full filter blur-3xl"></div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div ref={ref} className={`text-center mb-16 scroll-reveal ${isVisible ? 'visible' : ''}`}>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Что говорят наши клиенты
          </h2>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto">
            Реальные отзывы компаний, которые уже используют наши AI-решения
          </p>
        </div>

        <div className="relative">
          {/* Main testimonial card */}
          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 md:p-12 border border-white/20 shadow-2xl min-h-[400px] flex flex-col justify-between">
            <div>
              <Quote className="w-12 h-12 text-amber-400 mb-6" />

              <p className="text-xl md:text-2xl text-white leading-relaxed mb-8">
                "{testimonials[currentIndex].content}"
              </p>

              {/* Rating */}
              <div className="flex gap-1 mb-6">
                {[...Array(testimonials[currentIndex].rating)].map((_, i) => (
                  <Star key={i} className="w-5 h-5 fill-amber-400 text-amber-400" />
                ))}
              </div>
            </div>

            {/* Author info */}
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white font-bold text-xl">
                {testimonials[currentIndex].avatar}
              </div>
              <div>
                <div className="font-bold text-white text-lg">
                  {testimonials[currentIndex].name}
                </div>
                <div className="text-slate-300">
                  {testimonials[currentIndex].position}
                </div>
                <div className="text-amber-400 font-semibold">
                  {testimonials[currentIndex].company}
                </div>
              </div>
            </div>
          </div>

          {/* Navigation buttons */}
          <button
            onClick={prevSlide}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 md:-translate-x-16 bg-white/10 hover:bg-white/20 backdrop-blur-sm p-3 rounded-full border border-white/20 transition-all hover:scale-110"
            aria-label="Previous testimonial"
          >
            <ChevronLeft className="w-6 h-6 text-white" />
          </button>

          <button
            onClick={nextSlide}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 md:translate-x-16 bg-white/10 hover:bg-white/20 backdrop-blur-sm p-3 rounded-full border border-white/20 transition-all hover:scale-110"
            aria-label="Next testimonial"
          >
            <ChevronRight className="w-6 h-6 text-white" />
          </button>

          {/* Dots indicator */}
          <div className="flex justify-center gap-2 mt-8">
            {testimonials.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentIndex(index)}
                className={`w-3 h-3 rounded-full transition-all ${
                  index === currentIndex
                    ? 'bg-amber-400 w-8'
                    : 'bg-white/30 hover:bg-white/50'
                }`}
                aria-label={`Go to testimonial ${index + 1}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
