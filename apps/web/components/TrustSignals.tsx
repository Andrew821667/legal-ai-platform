"use client";

import { ExternalLink, CheckCircle2, Calendar } from "lucide-react";
import { useMemo } from "react";

interface SourceItem {
  name: string;
  text: string;
  url?: string;
}

interface SourceCategory {
  category: string;
  items: SourceItem[];
}

// Move static data outside component for better performance
const SOURCES_DATA: SourceCategory[] = [
    {
      category: "Исследования и статистика",
      items: [
        { name: "McKinsey & Company", text: "Исследования по цифровой трансформации юридической отрасли", url: "https://www.mckinsey.com" },
        { name: "Gartner", text: "Прогнозы по внедрению AI в Legal Tech до 2026 года", url: "https://www.gartner.com" },
        { name: "Thomson Reuters", text: "Legal Tech Market Report 2025-2026", url: "https://www.thomsonreuters.com" },
      ],
    },
    {
      category: "Нормативные источники",
      items: [
        { name: "КонсультантПлюс", text: "Актуальная судебная практика и законодательство РФ", url: "http://www.consultant.ru" },
        { name: "Гарант", text: "Правовая информация и аналитика", url: "http://www.garant.ru" },
        { name: "Федеральный закон №152-ФЗ", text: "О персональных данных", url: "http://www.consultant.ru/document/cons_doc_LAW_61801/" },
      ],
    },
    {
      category: "Отраслевые стандарты",
      items: [
        { name: "Legal Tech Association", text: "Стандарты разработки и внедрения Legal Tech решений" },
        { name: "Ассоциация юристов России", text: "Этические нормы использования AI в юриспруденции" },
      ],
    },
  ];

// Move date formatting outside component
const UPDATE_INFO = {
  lastUpdated: new Date().toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' }),
  frequency: "Еженедельно",
  nextUpdate: "В течение 7 дней",
};

export default function TrustSignals() {
  // Use memoized data
  const sources = useMemo(() => SOURCES_DATA, []);
  const updateInfo = useMemo(() => UPDATE_INFO, []);

  return (
    <section id="sources" className="py-16 bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Источники и актуальность
          </h2>
          <p className="text-lg text-slate-300 max-w-3xl mx-auto">
            Используем актуальное законодательство и проверенные отраслевые источники.
          </p>
        </div>

        {/* Update Info */}
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-6 mb-8 flex items-start gap-4">
          <Calendar className="w-6 h-6 text-emerald-400 mt-1 flex-shrink-0" />
          <div>
            <h3 className="text-lg font-semibold text-emerald-400 mb-2">
              Информация актуальна
            </h3>
            <div className="text-slate-300 space-y-1">
              <p>
                <strong>Последнее обновление:</strong> {updateInfo.lastUpdated}
              </p>
              <p>
                <strong>Частота обновлений:</strong> {updateInfo.frequency}
              </p>
              <p className="text-sm text-slate-400 mt-2">
                Обновляем базы по изменениям в законодательстве и судебной практике.
              </p>
            </div>
          </div>
        </div>

        {/* Sources by Category */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {sources.map((category, catIndex) => (
            <div
              key={catIndex}
              className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-amber-500/50 transition-all"
            >
              <h3 className="text-xl font-bold text-amber-400 mb-4 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5" />
                {category.category}
              </h3>
              <ul className="space-y-4">
                {category.items.map((source, idx) => (
                  <li key={idx} className="text-sm">
                    <div className="font-semibold text-white mb-1">
                      {source.name}
                    </div>
                    <p className="text-slate-400 mb-2">{source.text}</p>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-amber-500 hover:text-amber-400 transition-colors text-xs"
                      >
                        Перейти
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Certification & Compliance */}
        <div className="mt-8 bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-blue-400 mb-3">
            Соответствие стандартам
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-300">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <span>152-ФЗ "О персональных данных" - полное соответствие</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <span>ГОСТ Р ИСО/МЭК 27001 - информационная безопасность</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <span>Использование российских AI-моделей (импортозамещение)</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <span>Этические нормы использования ИИ в юриспруденции</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
