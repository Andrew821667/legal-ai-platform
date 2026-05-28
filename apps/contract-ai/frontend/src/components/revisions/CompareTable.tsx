'use client'

/**
 * Side-by-side revision compare table — visually matches the xlsx/PDF
 * exporter (12 columns, dark-blue header #1F4E78, Arial-like font).
 *
 * The header uses the *same* hex (#1F4E78) and the same column titles
 * as `revision_xlsx_exporter.py` and `revision_pdf_exporter.py` so the
 * lawyer sees the same layout in-app and in the downloaded file.
 *
 * Assessment / Risk cells get colour-coding (per user request) — note
 * that the xlsx/PDF exports stay plain to match the original template,
 * but in the UI the colour helps scan the table.
 */

import type {
  RevisionAssessment,
  RevisionDiffRow,
  RevisionPerspective,
  RevisionRiskLevel,
} from '@/services/api'

const HEADER_BG = '#1F4E78'

const ASSESSMENT_LABEL: Record<RevisionAssessment, string> = {
  plus: 'Плюс',
  minus: 'Минус',
  neutral: 'Нейтрально',
  mixed: 'Смешанно',
}

const RISK_LABEL: Record<RevisionRiskLevel, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
}

const PERSPECTIVE_LABEL: Record<RevisionPerspective, string> = {
  supplier: 'Поставщик',
  buyer: 'Покупатель',
  neutral: 'Нейтральная позиция',
}

const ASSESSMENT_CELL_CLASS: Record<RevisionAssessment, string> = {
  plus: 'bg-green-100 text-green-900',
  minus: 'bg-red-100 text-red-900',
  neutral: 'bg-gray-100 text-gray-800',
  mixed: 'bg-yellow-100 text-yellow-900',
}

const RISK_CELL_CLASS: Record<RevisionRiskLevel, string> = {
  low: 'bg-green-50 text-green-900',
  medium: 'bg-yellow-100 text-yellow-900',
  high: 'bg-red-200 text-red-900',
}


interface Props {
  rows: RevisionDiffRow[]
  perspective: RevisionPerspective
  oldRevisionLabel: string
  newRevisionLabel: string
}

export default function CompareTable({
  rows,
  perspective,
  oldRevisionLabel,
  newRevisionLabel,
}: Props) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-600">
        Нет сравнимых пунктов между выбранными редакциями.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-300">
      <table className="min-w-full border-collapse text-[13px] leading-snug" style={{ fontFamily: 'Arial, Helvetica, sans-serif' }}>
        <thead>
          <tr style={{ backgroundColor: HEADER_BG }}>
            {[
              '№',
              'Пункт',
              'Блок',
              'Условие',
              oldRevisionLabel,
              newRevisionLabel,
              'Изменение / несоответствие',
              `Оценка для «${PERSPECTIVE_LABEL[perspective]}»`,
              'Риск',
              'Комплексное влияние на договор',
              'Рекомендация',
              'Источник',
            ].map((label, idx) => (
              <th
                key={idx}
                className="px-3 py-3 text-center align-top font-semibold text-white"
                scope="col"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.number} className="border-t border-gray-200 align-top">
              <td className="px-3 py-3 text-center font-medium">{row.number}</td>
              <td className="px-3 py-3 text-center whitespace-nowrap">{row.clause_pair_label}</td>
              <td className="px-3 py-3">{row.block}</td>
              <td className="px-3 py-3">{row.condition}</td>
              <td className="px-3 py-3 whitespace-pre-wrap text-gray-800">{row.old_text || '—'}</td>
              <td className="px-3 py-3 whitespace-pre-wrap text-gray-800">{row.new_text || '—'}</td>
              <td className="px-3 py-3">{row.change_summary}</td>
              <td className={`px-3 py-3 text-center font-medium ${ASSESSMENT_CELL_CLASS[row.assessment]}`}>
                {ASSESSMENT_LABEL[row.assessment]}
              </td>
              <td className={`px-3 py-3 text-center font-medium ${RISK_CELL_CLASS[row.risk_level]}`}>
                {RISK_LABEL[row.risk_level]}
              </td>
              <td className="px-3 py-3">{row.complex_impact}</td>
              <td className="px-3 py-3">{row.recommendation}</td>
              <td className="px-3 py-3 whitespace-nowrap text-xs text-gray-600">{row.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
