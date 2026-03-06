type MiniAppGuideCardProps = {
  title: string;
  description: string;
};

export default function MiniAppGuideCard({ title, description }: MiniAppGuideCardProps) {
  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-300">{title}</h2>
      <p className="mt-2 text-sm text-slate-300 leading-relaxed">{description}</p>
    </article>
  );
}
