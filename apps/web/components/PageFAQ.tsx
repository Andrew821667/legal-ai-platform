interface PageFAQItem {
  question: string;
  answer: string;
}

interface PageFAQProps {
  items: PageFAQItem[];
  pageUrl: string;
  title?: string;
}

export default function PageFAQ({ items, pageUrl, title = "Частые вопросы" }: PageFAQProps) {
  const schema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "@id": `${pageUrl}#faq`,
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };

  return (
    <section className="border-t border-slate-800">
      <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }} />
        <h2 className="text-3xl font-semibold text-white">{title}</h2>
        <div className="mt-6 space-y-3">
          {items.map((item) => (
            <details
              key={item.question}
              className="group rounded-lg border border-slate-700 bg-slate-800/60 px-5 py-4"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-slate-100">
                {item.question}
                <span className="text-amber-400 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 leading-relaxed text-slate-300">{item.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
