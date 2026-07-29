export default function LegalHelpCommercialFacts() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 lg:px-8">
      <h2 className="text-3xl font-semibold text-white">Формат, сроки и стоимость</h2>
      <div className="mt-7 grid gap-5 md:grid-cols-3">
        <article className="rounded-xl border border-slate-700 bg-slate-800/60 p-6">
          <h3 className="text-xl font-semibold text-white">Дистанционно по России</h3>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Консультации, анализ и подготовка документов доступны онлайн. Необходимость очного участия
            проверяется применительно к задаче, органу или суду.
          </p>
        </article>
        <article className="rounded-xl border border-slate-700 bg-slate-800/60 p-6">
          <h3 className="text-xl font-semibold text-white">Согласованный объём</h3>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            До начала работы фиксируем вопросы, ожидаемый результат и состав документов. Дополнительные
            действия не включаются автоматически.
          </p>
        </article>
        <article className="rounded-xl border border-slate-700 bg-slate-800/60 p-6">
          <h3 className="text-xl font-semibold text-white">Условия до старта</h3>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Срок и стоимость зависят от сложности, объёма материалов и срочности. Конкретные условия
            сообщаются после первичной оценки и согласуются до выполнения поручения.
          </p>
        </article>
      </div>
    </section>
  );
}
