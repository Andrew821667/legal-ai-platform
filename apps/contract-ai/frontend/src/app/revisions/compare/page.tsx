'use client'

/**
 * Раздел «Сравнение редакций» — выбираешь два revision одного контракта,
 * получаешь side-by-side таблицу (та же 12-колонная разметка что в
 * xlsx/PDF), скачиваешь экспорт в xlsx или PDF.
 *
 * Все три поверхности (UI / xlsx / PDF) используют один и тот же endpoint
 * /api/v1/revisions/compare и одну и ту же data-модель, поэтому что
 * лежит в таблице — то и в файле.
 */

import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'

import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import CompareSummaryCard from '@/components/revisions/CompareSummaryCard'
import CompareTable from '@/components/revisions/CompareTable'
import api, {
  CompareRevisionsRequest,
  RevisionCompareReport,
  RevisionListItem,
  RevisionPerspective,
} from '@/services/api'

interface ContractOption {
  id: string
  name: string
}

const PERSPECTIVES: { value: RevisionPerspective; label: string }[] = [
  { value: 'supplier', label: 'Поставщик' },
  { value: 'buyer', label: 'Покупатель' },
  { value: 'neutral', label: 'Нейтральная позиция' },
]


export default function RevisionsComparePage() {
  const [contracts, setContracts] = useState<ContractOption[]>([])
  const [contractsLoading, setContractsLoading] = useState(false)
  const [contractId, setContractId] = useState<string>('')

  const [revisions, setRevisions] = useState<RevisionListItem[]>([])
  const [revisionsLoading, setRevisionsLoading] = useState(false)
  const [oldRevisionId, setOldRevisionId] = useState<string>('')
  const [newRevisionId, setNewRevisionId] = useState<string>('')
  const [perspective, setPerspective] = useState<RevisionPerspective>('neutral')

  const [report, setReport] = useState<RevisionCompareReport | null>(null)
  const [comparing, setComparing] = useState(false)
  const [downloading, setDownloading] = useState<'xlsx' | 'pdf' | null>(null)

  // Load contracts list once on mount
  useEffect(() => {
    let cancelled = false
    setContractsLoading(true)
    api
      .listContracts({ limit: 200 })
      .then((data) => {
        if (cancelled) return
        // listContracts returns either {items: [...]} or a raw array depending
        // on backend revision — handle both.
        const items: any[] = Array.isArray(data) ? data : data?.items ?? []
        setContracts(items.map((c) => ({ id: String(c.id), name: c.name ?? c.title ?? c.id })))
      })
      .catch((err) => {
        console.error(err)
        toast.error('Не удалось загрузить список договоров')
      })
      .finally(() => !cancelled && setContractsLoading(false))
    return () => { cancelled = true }
  }, [])

  // Whenever the user picks a contract, reload its revisions and clear
  // the previous selection / report.
  useEffect(() => {
    setRevisions([])
    setOldRevisionId('')
    setNewRevisionId('')
    setReport(null)
    if (!contractId) return

    let cancelled = false
    setRevisionsLoading(true)
    api
      .listRevisions(contractId)
      .then((data) => {
        if (cancelled) return
        setRevisions(data)
        // Auto-pick the two most recent so the user can hit «Сравнить» without
        // extra clicks — this is by far the most common case.
        if (data.length >= 2) {
          const sorted = [...data].sort((a, b) => a.version_number - b.version_number)
          setOldRevisionId(String(sorted[sorted.length - 2].id))
          setNewRevisionId(String(sorted[sorted.length - 1].id))
        }
      })
      .catch((err) => {
        console.error(err)
        toast.error('Не удалось загрузить редакции договора')
      })
      .finally(() => !cancelled && setRevisionsLoading(false))
    return () => { cancelled = true }
  }, [contractId])

  const buildRequest = (): CompareRevisionsRequest | null => {
    if (!oldRevisionId || !newRevisionId) {
      toast.error('Выберите обе редакции для сравнения')
      return null
    }
    if (oldRevisionId === newRevisionId) {
      toast.error('Старая и новая редакции должны различаться')
      return null
    }
    return {
      old_revision_id: Number(oldRevisionId),
      new_revision_id: Number(newRevisionId),
      perspective,
    }
  }

  const handleCompare = async () => {
    const req = buildRequest()
    if (!req) return
    setComparing(true)
    setReport(null)
    try {
      const r = await api.compareRevisions(req)
      setReport(r)
    } catch (err: any) {
      console.error(err)
      const detail = err?.response?.data?.detail ?? 'Не удалось сравнить редакции'
      toast.error(typeof detail === 'string' ? detail : 'Не удалось сравнить редакции')
    } finally {
      setComparing(false)
    }
  }

  const handleDownload = async (format: 'xlsx' | 'pdf') => {
    const req = buildRequest()
    if (!req) return
    setDownloading(format)
    try {
      const blob = await api.downloadRevisionsCompare(req, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `revision_compare_v${req.old_revision_id}_v${req.new_revision_id}.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error(err)
      toast.error(`Не удалось скачать ${format.toUpperCase()}`)
    } finally {
      setDownloading(null)
    }
  }

  const oldLabel = revisions.find((r) => String(r.id) === oldRevisionId)
    ? `Редакция №${revisions.find((r) => String(r.id) === oldRevisionId)!.version_number}`
    : 'Старая редакция'
  const newLabel = revisions.find((r) => String(r.id) === newRevisionId)
    ? `Редакция №${revisions.find((r) => String(r.id) === newRevisionId)!.version_number}`
    : 'Новая редакция'

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-gray-900">Сравнение редакций договоров</h1>
        <p className="mt-1 text-sm text-gray-600">
          Выберите договор и две его редакции — система покажет построчное сравнение пунктов
          с оценкой влияния и подскажет, что править перед подписанием.
        </p>
      </header>

      <Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Field label="Договор">
            <select
              className="block w-full rounded-lg border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
              value={contractId}
              onChange={(e) => setContractId(e.target.value)}
              disabled={contractsLoading}
            >
              <option value="">
                {contractsLoading ? 'Загрузка…' : '— выберите договор —'}
              </option>
              {contracts.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </Field>

          <Field label="Старая редакция">
            <RevisionSelect
              value={oldRevisionId}
              onChange={setOldRevisionId}
              revisions={revisions}
              loading={revisionsLoading}
              placeholder={contractId ? '— выберите редакцию —' : 'сначала выберите договор'}
            />
          </Field>

          <Field label="Новая редакция">
            <RevisionSelect
              value={newRevisionId}
              onChange={setNewRevisionId}
              revisions={revisions}
              loading={revisionsLoading}
              placeholder={contractId ? '— выберите редакцию —' : 'сначала выберите договор'}
            />
          </Field>

          <Field label="Точка зрения">
            <select
              className="block w-full rounded-lg border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
              value={perspective}
              onChange={(e) => setPerspective(e.target.value as RevisionPerspective)}
            >
              {PERSPECTIVES.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <Button
            onClick={handleCompare}
            loading={comparing}
            disabled={!oldRevisionId || !newRevisionId || comparing}
          >
            Сравнить
          </Button>
          <Button
            variant="outline"
            onClick={() => handleDownload('xlsx')}
            loading={downloading === 'xlsx'}
            disabled={!oldRevisionId || !newRevisionId || downloading !== null}
          >
            Скачать xlsx
          </Button>
          <Button
            variant="outline"
            onClick={() => handleDownload('pdf')}
            loading={downloading === 'pdf'}
            disabled={!oldRevisionId || !newRevisionId || downloading !== null}
          >
            Скачать PDF
          </Button>
        </div>
      </Card>

      {report && (
        <>
          <CompareSummaryCard report={report} />
          <CompareTable
            rows={report.rows}
            perspective={report.perspective}
            oldRevisionLabel={oldLabel}
            newRevisionLabel={newLabel}
          />
        </>
      )}
    </div>
  )
}


function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-600">
        {label}
      </span>
      {children}
    </label>
  )
}

function RevisionSelect({
  value,
  onChange,
  revisions,
  loading,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  revisions: RevisionListItem[]
  loading: boolean
  placeholder: string
}) {
  return (
    <select
      className="block w-full rounded-lg border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading || revisions.length === 0}
    >
      <option value="">{loading ? 'Загрузка…' : placeholder}</option>
      {revisions.map((r) => (
        <option key={r.id} value={r.id}>
          v{r.version_number} — {r.file_name}
          {r.is_current ? ' (текущая)' : ''}
        </option>
      ))}
    </select>
  )
}
