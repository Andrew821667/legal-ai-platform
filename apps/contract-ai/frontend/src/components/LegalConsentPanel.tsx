'use client'

import Link from 'next/link'
import { CheckIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'

interface LegalConsentPanelProps {
  accepted: boolean
  onChange: (accepted: boolean) => void
  disabled?: boolean
  documentUpload?: boolean
  tone?: 'light' | 'dark'
}

export default function LegalConsentPanel({
  accepted,
  onChange,
  disabled = false,
  documentUpload = false,
  tone = 'light',
}: LegalConsentPanelProps) {
  const dark = tone === 'dark'

  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition ${
        accepted
          ? dark
            ? 'border-emerald-400 bg-emerald-400/10'
            : 'border-emerald-500 bg-emerald-50'
          : dark
            ? 'border-amber-300/70 bg-amber-300/10 hover:border-amber-300'
            : 'border-amber-400 bg-amber-50 hover:border-amber-500'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <input
        type="checkbox"
        checked={accepted}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
        className="sr-only"
      />
      <span
        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded border ${
          accepted
            ? 'border-emerald-500 bg-emerald-500 text-white'
            : dark
              ? 'border-amber-300 bg-slate-950 text-transparent'
              : 'border-amber-500 bg-white text-transparent'
        }`}
      >
        <CheckIcon className="h-4 w-4 stroke-[3]" aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className={`flex items-center gap-2 text-sm font-bold ${dark ? 'text-white' : 'text-slate-950'}`}>
          <ShieldCheckIcon className="h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
          {accepted ? 'Согласие принято' : 'Требуется согласие'}
        </span>
        <span className={`mt-1 block text-xs leading-5 ${dark ? 'text-slate-300' : 'text-slate-600'}`}>
          Принимаю{' '}
          <Link href="/terms" target="_blank" className="font-semibold underline">
            пользовательское соглашение
          </Link>
          {' '}и{' '}
          <Link href="/privacy" target="_blank" className="font-semibold underline">
            политику конфиденциальности
          </Link>
          {documentUpload ? ', включая обработку загружаемого документа для анализа.' : '.'}
        </span>
      </span>
    </label>
  )
}
