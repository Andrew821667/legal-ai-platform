import Link from "next/link";

import { ROUTES, contractAIEntryHref } from "@/lib/links";

const products = [
  {
    title: "Contract AI",
    description: "Публичный интерфейс системы анализа и проверки договоров с маршрутом от демо к пилоту.",
    image: "contract-ai-interface-v1",
    alt: "Публичный интерфейс Contract AI для анализа и проверки договоров",
    href: ROUTES.contractAI,
    cta: "Возможности Contract AI",
    productHref: contractAIEntryHref("demo"),
  },
  {
    title: "Telegram Mini App",
    description: "Единая точка входа в проверку договора, автоматизацию, юридическую и инженерную практики.",
    image: "miniapp-interface-v1",
    alt: "Интерфейс Mini App AI Verdict с маршрутами юридической и инженерной практик",
    href: ROUTES.miniApp,
    cta: "Открыть интерфейс",
    productHref: null,
  },
  {
    title: "Веб-ассистент",
    description: "Профильный диалоговый маршрут, который помогает выбрать нужную практику без передачи документов.",
    image: "web-assistant-interface-v1",
    alt: "Веб-ассистент AI Verdict с выбором автоматизации, юридической помощи или разработки",
    href: null,
    cta: null,
    productHref: null,
  },
];

export default function ProductProof() {
  return (
    <section className="border-y border-slate-800 bg-slate-800/40" aria-labelledby="product-proof-title">
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold text-amber-300">Создано в AI Verdict</p>
          <h2 id="product-proof-title" className="mt-2 text-3xl font-semibold text-white md:text-4xl">
            Работающие интерфейсы, а не концепты
          </h2>
          <p className="mt-4 text-slate-300">
            Эти публичные экраны относятся к действующим частям платформы. Они показывают, как юридическая логика,
            инженерная архитектура и удобный пользовательский маршрут соединяются в одном продукте.
          </p>
        </div>

        <div className="mt-9 grid gap-6 lg:grid-cols-3">
          {products.map((product) => (
            <article key={product.title} className="overflow-hidden rounded-2xl border border-slate-700 bg-white shadow-sm">
              <figure>
                <picture>
                  <source srcSet={`/images/visual-v2/${product.image}.avif`} type="image/avif" />
                  <img
                    alt={product.alt}
                    className="aspect-video w-full border-b border-slate-200 object-cover object-top"
                    decoding="async"
                    height="675"
                    loading="lazy"
                    src={`/images/visual-v2/${product.image}.webp`}
                    width="1200"
                  />
                </picture>
                <figcaption className="p-6">
                  <h3 className="text-xl font-semibold text-slate-950">{product.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-600">{product.description}</p>
                  {product.href ? (
                    <Link href={product.href} className="mt-5 inline-flex font-semibold text-amber-700 hover:text-amber-600">
                      {product.cta} →
                    </Link>
                  ) : (
                    <span className="mt-5 inline-flex text-sm font-semibold text-slate-500">
                      Доступен на публичных страницах сайта
                    </span>
                  )}
                  {product.productHref ? (
                    <a
                      href={product.productHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-0 mt-3 inline-flex text-sm font-semibold text-slate-600 hover:text-amber-700 sm:ml-4 sm:mt-5"
                    >
                      Перейти в сервис ↗
                    </a>
                  ) : null}
                </figcaption>
              </figure>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
