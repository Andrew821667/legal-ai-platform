'use client'

/**
 * Summary card mirroring the «Краткие выводы» sheet of the xlsx export.
 * Same dark-blue title bar, same light-blue label fill (#D9EAF7).
 */

import type { RevisionCompareReport } from '@/services/api'

const HEADER_BG = '#1F4E78'
const LABEL_BG = '#D9EAF7'

const PERSPECTIVE_LABEL: Record<string, string> = {
  supplier: 'Поставщик',
  buyer: 'Покупатель',
  neutral: 'Нейтральная позиция',
}

interface Props {
  report: RevisionCompareReport
}

export default function CompareSummaryCard({ report }: Props) {
  const { summary, perspective } = report
  const prepared = new Date(summary.prepared_at).toLocaleString('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  })

  const rows: Array<{ label: string; value: React.ReactNode }> = [
    { label: 'Дата подготовки', value: prepared },
    { label: 'Точка зрения', value: PERSPECTIVE_LABEL[perspective] ?? perspective },
    { label: 'Сравниваемые документы', value: summary.documents_compared },
    { label: 'Общий вывод', value: summary.overall_verdict },
    { label: 'Ключевые плюсы', value: <BulletList items={summary.key_pros} /> },
    { label: 'Ключевые риски', value: <BulletList items={summary.key_risks} /> },
    { label: 'Что править перед подписанием', value: <BulletList items={summary.pre_signature_edits} /> },
  ]

  for (const [key, value] of Object.entries(summary.source_files)) {
    if (value) rows.push({ label: key, value })
  }

  return (
    <div
      className="rounded-lg border border-gray-300 bg-white overflow-hidden"
      style={{ fontFamily: 'Arial, Helvetica, sans-serif' }}
    >
      <div
        className="px-4 py-3 text-center font-semibold text-white"
        style={{ backgroundColor: HEADER_BG }}
      >
        {summary.title}
      </div>
      <table className="w-full text-[13px] leading-snug">
        <tbody>
          {rows.map(({ label, value }, idx) => (
            <tr key={idx} className="align-top border-t border-gray-200">
              <th
                className="w-64 px-4 py-3 text-left font-semibold"
                style={{ backgroundColor: LABEL_BG }}
                scope="row"
              >
                {label}
              </th>
              <td className="px-4 py-3 whitespace-pre-wrap text-gray-800">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <span className="text-gray-500">—</span>
  return (
    <ul className="list-disc pl-5 space-y-1">
      {items.map((it, idx) => (
        <li key={idx}>{it}</li>
      ))}
    </ul>
  )
}
