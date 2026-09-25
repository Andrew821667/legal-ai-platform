import { fetchPublicReviews } from "@/lib/public-reviews";

/**
 * Отзывы клиентов. Пока одобренных нет — секции нет: пустой блок «Отзывы»
 * работает против, а не за.
 */
export default async function ClientReviews() {
  const reviews = await fetchPublicReviews();
  if (reviews.length === 0) return null;
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16" aria-labelledby="client-reviews-title">
      <h2 id="client-reviews-title" className="text-3xl font-semibold text-white">
        Отзывы клиентов
      </h2>
      <p className="mt-4 max-w-3xl text-slate-300">
        Публикуем с согласия клиентов — только имя, без фамилий и подробностей дела.
      </p>
      <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {reviews.map((review, index) => (
          <figure key={`${review.name}-${review.date}-${index}`} className="rounded-xl border border-slate-800 bg-slate-800/50 p-6">
            {review.score ? (
              <p className="text-amber-300" aria-label={`Оценка ${review.score} из 5`}>
                {"★".repeat(review.score)}
                <span className="text-slate-600">{"★".repeat(5 - review.score)}</span>
              </p>
            ) : null}
            <blockquote className="mt-3 text-slate-200 leading-relaxed">«{review.text}»</blockquote>
            <figcaption className="mt-4 text-sm text-slate-400">
              {review.name}
              {review.date ? ` · ${new Date(`${review.date}T12:00:00Z`).toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}` : ""}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
