'use client';

import { useState } from 'react';
import { Filter, X } from 'lucide-react';

interface FilterOptions {
  priority: 'all' | 'critical' | 'high' | 'medium';
  status: 'all' | 'open' | 'closed';
  dateRange: 'all' | 'week' | 'month' | '3months';
}

interface IssueFiltersProps {
  onFilterChange: (filters: FilterOptions) => void;
}

export default function IssueFilters({ onFilterChange }: IssueFiltersProps) {
  const [filters, setFilters] = useState<FilterOptions>({
    priority: 'all',
    status: 'all',
    dateRange: 'all'
  });
  const [isOpen, setIsOpen] = useState(false);

  const updateFilter = (key: keyof FilterOptions, value: any) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  const resetFilters = () => {
    const defaultFilters: FilterOptions = {
      priority: 'all',
      status: 'all',
      dateRange: 'all'
    };
    setFilters(defaultFilters);
    onFilterChange(defaultFilters);
  };

  const hasActiveFilters = filters.priority !== 'all' || filters.status !== 'all' || filters.dateRange !== 'all';

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
          hasActiveFilters
            ? 'bg-amber-600 text-white'
            : 'bg-slate-700 text-white hover:bg-slate-600'
        }`}
      >
        <Filter className="w-4 h-4" />
        Фильтры
        {hasActiveFilters && (
          <span className="ml-1 px-2 py-0.5 bg-white/20 rounded-full text-xs">
            активны
          </span>
        )}
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Filters Panel */}
          <div className="absolute right-0 mt-2 w-80 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 p-4">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold">Фильтры</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Priority Filter */}
            <div className="mb-4">
              <label className="block text-slate-300 text-sm font-medium mb-2">
                Приоритет
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: 'all', label: 'Все' },
                  { value: 'critical', label: 'Critical' },
                  { value: 'high', label: 'High' },
                  { value: 'medium', label: 'Medium' }
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => updateFilter('priority', option.value)}
                    className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                      filters.priority === option.value
                        ? 'bg-amber-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Status Filter */}
            <div className="mb-4">
              <label className="block text-slate-300 text-sm font-medium mb-2">
                Статус
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { value: 'all', label: 'Все' },
                  { value: 'open', label: 'Открытые' },
                  { value: 'closed', label: 'Закрытые' }
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => updateFilter('status', option.value)}
                    className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                      filters.status === option.value
                        ? 'bg-amber-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Date Range Filter */}
            <div className="mb-4">
              <label className="block text-slate-300 text-sm font-medium mb-2">
                Период
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: 'all', label: 'Все время' },
                  { value: 'week', label: 'Неделя' },
                  { value: 'month', label: 'Месяц' },
                  { value: '3months', label: '3 месяца' }
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => updateFilter('dateRange', option.value)}
                    className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                      filters.dateRange === option.value
                        ? 'bg-amber-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-3 border-t border-slate-700">
              <button
                onClick={resetFilters}
                disabled={!hasActiveFilters}
                className="flex-1 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Сбросить
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="flex-1 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
              >
                Применить
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
