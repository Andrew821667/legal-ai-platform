'use client';

import { useState } from 'react';
import { Download, FileText, FileSpreadsheet } from 'lucide-react';
import { format } from 'date-fns';

interface ExportButtonProps {
  data: any;
  filename?: string;
}

export default function ExportButton({ data, filename = 'admin-data' }: ExportButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Экспорт в CSV
  const exportToCSV = () => {
    try {
      let csvContent = '';

      // SEO Report
      if (data.seo_report) {
        csvContent += 'SEO Report\n';
        csvContent += `Date,${data.seo_report.report_date || 'N/A'}\n`;
        csvContent += `Score,${data.seo_report.score || 'N/A'}\n`;
        csvContent += `Predicted Position,${data.seo_report.predicted_position || 'N/A'}\n`;
        csvContent += `Readability,${data.seo_report.readability || 'N/A'}\n`;
        csvContent += `E-E-A-T Score,${data.seo_report.eeat_score || 'N/A'}\n`;
        csvContent += '\n';
      }

      // Issues Stats
      if (data.issues) {
        csvContent += 'Issues Statistics\n';
        csvContent += `Total,${data.issues.total || 0}\n`;
        csvContent += `Open,${data.issues.open || 0}\n`;
        csvContent += `Closed,${data.issues.closed || 0}\n`;
        csvContent += `SEO Critical,${data.issues.seo_critical || 0}\n`;
        csvContent += `SEO High,${data.issues.seo_high || 0}\n`;
        csvContent += `SEO Medium,${data.issues.seo_medium || 0}\n`;
        csvContent += '\n';
      }

      // SEO History
      if (data.seo_history && data.seo_history.length > 0) {
        csvContent += 'SEO History\n';
        csvContent += 'Date,Score\n';
        data.seo_history.forEach((item: any) => {
          csvContent += `${item.date},${item.score || 'N/A'}\n`;
        });
        csvContent += '\n';
      }

      // Top SEO Tasks
      if (data.top_seo_tasks && data.top_seo_tasks.length > 0) {
        csvContent += 'Top SEO Tasks\n';
        csvContent += 'Number,Title,Priority\n';
        data.top_seo_tasks.forEach((task: any) => {
          csvContent += `#${task.number},"${task.title.replace(/"/g, '""')}",${task.priority}\n`;
        });
      }

      // Создаем blob и скачиваем
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);

      link.setAttribute('href', url);
      link.setAttribute('download', `${filename}-${format(new Date(), 'yyyy-MM-dd')}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setIsOpen(false);
    } catch (error) {
      console.error('Export error:', error);
      alert('Ошибка при экспорте данных');
    }
  };

  // Экспорт в JSON
  const exportToJSON = () => {
    try {
      const jsonString = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);

      link.setAttribute('href', url);
      link.setAttribute('download', `${filename}-${format(new Date(), 'yyyy-MM-dd')}.json`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setIsOpen(false);
    } catch (error) {
      console.error('Export error:', error);
      alert('Ошибка при экспорте данных');
    }
  };

  // Печать отчета
  const printReport = () => {
    const printWindow = window.open('', '', 'width=800,height=600');
    if (!printWindow) return;

    const htmlContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>Admin Report - ${format(new Date(), 'dd.MM.yyyy')}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { color: #1e293b; }
            h2 { color: #475569; margin-top: 30px; }
            table { width: 100%; border-collapse: collapse; margin: 10px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f59e0b; color: white; }
            .score-good { color: #22c55e; font-weight: bold; }
            .score-medium { color: #eab308; font-weight: bold; }
            .score-bad { color: #ef4444; font-weight: bold; }
          </style>
        </head>
        <body>
          <h1>Admin Panel Report</h1>
          <p>Дата: ${format(new Date(), 'dd MMMM yyyy, HH:mm', { locale: require('date-fns/locale/ru') })}</p>

          ${data.seo_report ? `
            <h2>SEO Отчет</h2>
            <table>
              <tr><th>Метрика</th><th>Значение</th></tr>
              <tr><td>SEO Score</td><td class="${
                (data.seo_report.score || 0) >= 80 ? 'score-good' :
                (data.seo_report.score || 0) >= 60 ? 'score-medium' : 'score-bad'
              }">${data.seo_report.score || 'N/A'}/100</td></tr>
              <tr><td>Predicted Position</td><td>${data.seo_report.predicted_position || 'N/A'}</td></tr>
              <tr><td>Readability</td><td>${data.seo_report.readability || 'N/A'}</td></tr>
              <tr><td>E-E-A-T Score</td><td>${data.seo_report.eeat_score || 'N/A'}</td></tr>
            </table>
          ` : ''}

          ${data.issues ? `
            <h2>Статистика Issues</h2>
            <table>
              <tr><th>Тип</th><th>Количество</th></tr>
              <tr><td>Всего</td><td>${data.issues.total || 0}</td></tr>
              <tr><td>Открыто</td><td>${data.issues.open || 0}</td></tr>
              <tr><td>Закрыто</td><td>${data.issues.closed || 0}</td></tr>
              <tr><td>SEO Critical</td><td class="score-bad">${data.issues.seo_critical || 0}</td></tr>
              <tr><td>SEO High</td><td class="score-medium">${data.issues.seo_high || 0}</td></tr>
              <tr><td>SEO Medium</td><td>${data.issues.seo_medium || 0}</td></tr>
            </table>
          ` : ''}

          ${data.top_seo_tasks && data.top_seo_tasks.length > 0 ? `
            <h2>Приоритетные задачи</h2>
            <table>
              <tr><th>#</th><th>Задача</th><th>Приоритет</th></tr>
              ${data.top_seo_tasks.map((task: any) => `
                <tr>
                  <td>${task.number}</td>
                  <td>${task.title}</td>
                  <td>${task.priority.toUpperCase()}</td>
                </tr>
              `).join('')}
            </table>
          ` : ''}
        </body>
      </html>
    `;

    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);

    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
      >
        <Download className="w-4 h-4" />
        Экспорт
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown menu */}
          <div className="absolute right-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50">
            <button
              onClick={exportToCSV}
              className="w-full flex items-center gap-3 px-4 py-3 text-left text-white hover:bg-slate-700 transition-colors rounded-t-lg"
            >
              <FileSpreadsheet className="w-4 h-4 text-green-400" />
              <span>Экспорт в CSV</span>
            </button>

            <button
              onClick={exportToJSON}
              className="w-full flex items-center gap-3 px-4 py-3 text-left text-white hover:bg-slate-700 transition-colors"
            >
              <FileText className="w-4 h-4 text-blue-400" />
              <span>Экспорт в JSON</span>
            </button>

            <button
              onClick={printReport}
              className="w-full flex items-center gap-3 px-4 py-3 text-left text-white hover:bg-slate-700 transition-colors rounded-b-lg"
            >
              <FileText className="w-4 h-4 text-amber-400" />
              <span>Печать отчета</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
