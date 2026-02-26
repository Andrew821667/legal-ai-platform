'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, RefreshCw, Search, ShieldOff, ShieldCheck } from 'lucide-react';

type ScopeType = 'bot' | 'news' | 'worker' | 'admin' | 'global';

interface AutomationControl {
  key: string;
  scope: ScopeType | null;
  title: string;
  description: string | null;
  enabled: boolean;
  config: Record<string, unknown>;
  updated_at: string;
  updated_by: string | null;
}

export default function AutomationControlsPanel() {
  const [items, setItems] = useState<AutomationControl[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState<Record<string, boolean>>({});
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [scopeFilter, setScopeFilter] = useState<'all' | ScopeType>('all');

  const loadControls = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch('/api/admin/automation-controls');
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Failed to load controls');
      }
      setItems(Array.isArray(data.controls) ? data.controls : []);
    } catch (e: any) {
      setError(e?.message || 'Failed to load controls');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadControls();
  }, []);

  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (scopeFilter !== 'all' && (item.scope || 'global') !== scopeFilter) {
        return false;
      }
      if (!search.trim()) {
        return true;
      }
      const hay = `${item.key} ${item.title} ${item.description || ''}`.toLowerCase();
      return hay.includes(search.toLowerCase());
    });
  }, [items, search, scopeFilter]);

  const updateControl = async (key: string, payload: Record<string, unknown>) => {
    setIsSaving((prev) => ({ ...prev, [key]: true }));
    setError('');
    try {
      const response = await fetch('/api/admin/automation-controls', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, ...payload }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Failed to update control');
      }
      setItems((prev) => prev.map((item) => (item.key === key ? data.control : item)));
    } catch (e: any) {
      setError(e?.message || 'Failed to update control');
    } finally {
      setIsSaving((prev) => ({ ...prev, [key]: false }));
    }
  };

  const toggleScope = async (scope: ScopeType, enabled: boolean) => {
    const targets = items.filter((item) => (item.scope || 'global') === scope);
    for (const item of targets) {
      // eslint-disable-next-line no-await-in-loop
      await updateControl(item.key, { enabled });
    }
  };

  return (
    <div className="space-y-5">
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск автоматизаций..."
              className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/40"
            />
          </div>
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value as any)}
            className="px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200"
          >
            <option value="all">Все scope</option>
            <option value="news">news</option>
            <option value="bot">bot</option>
            <option value="worker">worker</option>
            <option value="admin">admin</option>
            <option value="global">global</option>
          </select>
          <button
            onClick={loadControls}
            className="inline-flex items-center gap-2 px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => toggleScope('news', false)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-red-900/30 border border-red-700/50 text-red-300 hover:bg-red-900/50"
          >
            <ShieldOff className="w-4 h-4" />
            Отключить все news
          </button>
          <button
            onClick={() => toggleScope('news', true)}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs bg-green-900/30 border border-green-700/50 text-green-300 hover:bg-green-900/50"
          >
            <ShieldCheck className="w-4 h-4" />
            Включить все news
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-300 bg-red-900/30 border border-red-700/40 rounded-lg p-3">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {filtered.map((item) => {
          const scopeLabel = item.scope || 'global';
          const configText = JSON.stringify(item.config || {}, null, 2);
          return (
            <div key={item.key} className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="text-sm font-semibold text-slate-100">{item.title}</h4>
                    <span className="text-[11px] px-2 py-0.5 rounded-full border border-slate-600 text-slate-300">
                      {scopeLabel}
                    </span>
                    <span className="text-[11px] px-2 py-0.5 rounded-full border border-slate-600 text-slate-300">
                      {item.key}
                    </span>
                  </div>
                  {item.description && <p className="text-sm text-slate-400">{item.description}</p>}
                  <p className="text-xs text-slate-500">
                    Обновлено: {new Date(item.updated_at).toLocaleString()} {item.updated_by ? `· ${item.updated_by}` : ''}
                  </p>
                </div>
                <button
                  onClick={() => updateControl(item.key, { enabled: !item.enabled })}
                  disabled={Boolean(isSaving[item.key])}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    item.enabled
                      ? 'bg-green-900/30 border border-green-700/50 text-green-300 hover:bg-green-900/50'
                      : 'bg-slate-900 border border-slate-600 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  {isSaving[item.key] ? 'Сохраняю...' : item.enabled ? 'Включено' : 'Выключено'}
                </button>
              </div>

              <details className="mt-3">
                <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-200">
                  JSON config
                </summary>
                <ConfigEditor
                  value={configText}
                  onSave={(nextConfig) => updateControl(item.key, { config: nextConfig })}
                />
              </details>
            </div>
          );
        })}
      </div>

      {!isLoading && filtered.length === 0 && (
        <div className="text-sm text-slate-400 bg-slate-800/40 border border-slate-700 rounded-lg p-4">
          Ничего не найдено по текущим фильтрам.
        </div>
      )}

      {!isLoading && items.length > 0 && (
        <div className="text-xs text-slate-500 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-400" />
          Control plane активен: можно централизованно отключать автоматизации без деплоя.
        </div>
      )}
    </div>
  );
}

function ConfigEditor({
  value,
  onSave,
}: {
  value: string;
  onSave: (nextConfig: Record<string, unknown>) => Promise<void>;
}) {
  const [text, setText] = useState(value);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setText(value);
  }, [value]);

  const handleSave = async () => {
    setError('');
    setIsSaving(true);
    try {
      const parsed = JSON.parse(text);
      await onSave(parsed);
    } catch (e: any) {
      setError(e?.message || 'Некорректный JSON');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="mt-2 space-y-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full min-h-[120px] bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-200 font-mono"
      />
      {error && <div className="text-xs text-red-300">{error}</div>}
      <button
        onClick={handleSave}
        disabled={isSaving}
        className="px-3 py-1.5 rounded-lg text-xs bg-amber-700/80 text-white hover:bg-amber-700 disabled:opacity-50"
      >
        {isSaving ? 'Сохраняю...' : 'Сохранить config'}
      </button>
    </div>
  );
}
