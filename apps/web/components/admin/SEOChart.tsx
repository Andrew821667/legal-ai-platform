'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

interface SEOHistoryItem {
  date: string;
  score: number | null;
  url?: string;
}

interface SEOChartProps {
  data: SEOHistoryItem[];
}

export default function SEOChart({ data }: SEOChartProps) {
  // Преобразуем данные для графика
  const chartData = data
    .filter(item => item.score !== null)
    .map(item => ({
      date: item.date,
      score: item.score,
      formattedDate: format(new Date(item.date), 'd MMM', { locale: ru })
    }))
    .reverse(); // От старых к новым

  if (chartData.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-8 border border-slate-700/50 text-center">
        <p className="text-slate-400">Недостаточно данных для построения графика</p>
      </div>
    );
  }

  // Кастомный tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-900 border border-amber-500/50 rounded-lg p-3 shadow-xl">
          <p className="text-white font-semibold">{data.date}</p>
          <p className={`text-lg font-bold ${
            data.score >= 80 ? 'text-green-400' :
            data.score >= 60 ? 'text-yellow-400' :
            'text-red-400'
          }`}>
            Score: {data.score}/100
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
      <h3 className="text-white font-semibold mb-4">Динамика SEO Score</h3>

      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />

          <XAxis
            dataKey="formattedDate"
            stroke="#94a3b8"
            style={{ fontSize: '12px' }}
          />

          <YAxis
            domain={[0, 100]}
            stroke="#94a3b8"
            style={{ fontSize: '12px' }}
            ticks={[0, 20, 40, 60, 80, 100]}
          />

          <Tooltip content={<CustomTooltip />} />

          <Area
            type="monotone"
            dataKey="score"
            stroke="#f59e0b"
            strokeWidth={3}
            fill="url(#scoreGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Легенда */}
      <div className="flex items-center justify-center gap-6 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-400" />
          <span className="text-slate-400">Отлично (80+)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-yellow-400" />
          <span className="text-slate-400">Хорошо (60-79)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-400" />
          <span className="text-slate-400">Требует улучшений (&lt;60)</span>
        </div>
      </div>

      {/* Статистика */}
      <div className="grid grid-cols-3 gap-4 mt-6">
        <div className="bg-slate-900/50 p-3 rounded-lg text-center">
          <div className="text-slate-400 text-xs mb-1">Средний</div>
          <div className="text-white font-bold text-lg">
            {Math.round(chartData.reduce((sum, item) => sum + (item.score || 0), 0) / chartData.length)}
          </div>
        </div>
        <div className="bg-slate-900/50 p-3 rounded-lg text-center">
          <div className="text-slate-400 text-xs mb-1">Максимум</div>
          <div className="text-green-400 font-bold text-lg">
            {Math.max(...chartData.map(item => item.score || 0))}
          </div>
        </div>
        <div className="bg-slate-900/50 p-3 rounded-lg text-center">
          <div className="text-slate-400 text-xs mb-1">Минимум</div>
          <div className="text-red-400 font-bold text-lg">
            {Math.min(...chartData.map(item => item.score || 0))}
          </div>
        </div>
      </div>
    </div>
  );
}
