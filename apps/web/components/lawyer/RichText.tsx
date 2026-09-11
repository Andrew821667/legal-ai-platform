import { splitBlocks } from "@/lib/lawyer-text";

/**
 * Текст клиента с настоящими списками.
 *
 * Раньше описание выводилось одним блоком с сохранением переносов, и маркеры
 * «•», «o», «▪» оставались обычными символами в начале строк. Маркер — не
 * содержание: список рисуем списком, абзацы — абзацами.
 */
export default function RichText({ text, className = "" }: { text: string | null | undefined; className?: string }) {
  const blocks = splitBlocks(text);
  if (blocks.length === 0) return null;
  return (
    <div className={`space-y-2 text-lw-base leading-relaxed text-lw-ink ${className}`}>
      {blocks.map((block, index) =>
        block.type === "paragraph" ? (
          <p key={index} className="whitespace-pre-wrap">
            {block.text}
          </p>
        ) : block.ordered ? (
          <ol key={index} className="list-decimal space-y-1 pl-5">
            {block.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ol>
        ) : (
          <ul key={index} className="list-disc space-y-1 pl-5">
            {block.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        ),
      )}
    </div>
  );
}
