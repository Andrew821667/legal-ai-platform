import Link from "next/link";
import { leadBotDeepLink } from "@/lib/links";

const sections = [
  "Сохраненное",
  "История чтения",
  "История анализов",
  "Интересы и тематики",
  "Настройки уведомлений",
];

export default function MiniAppProfilePage() {
  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <h2 className="text-base font-semibold text-white">Мой контур</h2>
        <p className="mt-2 text-sm text-slate-300">
          Единый профиль для reader-бота, mini-app и product-сценариев. Здесь будут персональные данные и история.
        </p>
      </article>

      <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <ul className="space-y-2 text-sm text-slate-200">
          {sections.map((section) => (
            <li key={section} className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2">
              {section}
            </li>
          ))}
        </ul>
      </article>

      <Link
        href={leadBotDeepLink("web_miniapp_profile")}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex rounded-lg border border-sky-500/60 px-4 py-2 text-sm font-semibold text-sky-200 hover:border-sky-300 transition-colors"
      >
        Связаться с Ассистентом Legal AI Pro
      </Link>
    </section>
  );
}
