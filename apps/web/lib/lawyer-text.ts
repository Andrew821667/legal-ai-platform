/**
 * Текст клиента — абзацами и списками, а не сплошной строкой.
 *
 * Клиент пишет обращение как умеет: перечни через «•», «-», «▪» или «o» —
 * последнее Word ставит вместо маркера, и в сплошном тексте оно читается как
 * опечатка. Здесь маркер отделяется от пункта, и список рисуется списком.
 * Никакой разметки не разбираем — только начало строки.
 */

export type TextBlock =
  | { type: "paragraph"; text: string }
  | { type: "list"; ordered: boolean; items: string[] };

const BULLET = /^\s*(?:[•●◦▪■□‣⁃·\-–—*]|o)\s+(.+)$/;
const NUMBERED = /^\s*\d{1,2}[.)]\s+(.+)$/;

function bulletItem(line: string): { text: string; ordered: boolean } | null {
  const numbered = NUMBERED.exec(line);
  if (numbered) return { text: numbered[1].trim(), ordered: true };
  const bullet = BULLET.exec(line);
  if (bullet) return { text: bullet[1].trim(), ordered: false };
  return null;
}

export function splitBlocks(text: string | null | undefined): TextBlock[] {
  const blocks: TextBlock[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", text: paragraph.join("\n") });
      paragraph = [];
    }
  };

  for (const rawLine of (text || "").split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    const item = bulletItem(line);
    if (item) {
      flush();
      const last = blocks[blocks.length - 1];
      if (last && last.type === "list" && last.ordered === item.ordered) {
        last.items.push(item.text);
      } else {
        blocks.push({ type: "list", ordered: item.ordered, items: [item.text] });
      }
      continue;
    }
    if (!line.trim()) {
      flush();
      continue;
    }
    paragraph.push(line.trim());
  }
  flush();
  return blocks;
}
