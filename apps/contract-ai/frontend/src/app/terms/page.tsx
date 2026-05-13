import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Условия использования | Contract AI System',
  description: 'Условия использования Contract AI System: бесплатный режим, ограничения, ответственность и правила работы с договорами.',
}

const sections = [
  {
    title: '1. Назначение сервиса',
    paragraphs: [
      'Contract AI System помогает загружать, анализировать и готовить договорные документы с использованием автоматизированных инструментов и AI-моделей.',
      'Результаты анализа носят информационный и вспомогательный характер. Они не заменяют индивидуальную юридическую консультацию по конкретной ситуации.',
    ],
  },
  {
    title: '2. Бесплатный доступ',
    paragraphs: [
      'На бесплатном этапе пользователю доступно 3 договора в месяц. Этот лимит предназначен для первичной проверки интерфейса, качества отчета и применимости сервиса к вашему процессу.',
      'После использования бесплатного лимита дальнейшая работа обсуждается в формате пилота, рабочего контура или отдельного проектного соглашения.',
    ],
  },
  {
    title: '3. Правила загрузки документов',
    paragraphs: [
      'Пользователь отвечает за законность загрузки документов и наличие необходимых прав на их обработку.',
      'Запрещается загружать вредоносные файлы, документы с незаконным содержанием или материалы, обработка которых требует специального режима защиты без отдельного согласования.',
    ],
  },
  {
    title: '4. Ограничение ответственности',
    paragraphs: [
      'Сервис не гарантирует выявление всех юридических, финансовых, налоговых или коммерческих рисков в договоре.',
      'Окончательное решение по подписанию, изменению или отклонению договора принимает пользователь или его уполномоченный специалист.',
    ],
  },
  {
    title: '5. Изменение условий',
    paragraphs: [
      'Условия могут обновляться при развитии продукта, изменении лимитов, появлении новых функций или изменении правовых требований.',
      'Актуальная версия условий публикуется на этой странице и применяется с момента размещения, если не указано иное.',
    ],
  },
]

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 px-4 py-12">
      <div className="max-w-4xl mx-auto">
        <Link href="/" className="inline-flex items-center text-primary-700 hover:text-primary-900 font-semibold mb-8">
          ← На главную Contract AI
        </Link>
        <article className="bg-white rounded-2xl shadow-card border border-gray-100 p-6 md:p-10">
          <p className="text-sm font-semibold uppercase tracking-wide text-primary-600 mb-3">
            Legal
          </p>
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-5">
            Условия использования
          </h1>
          <p className="text-gray-600 text-lg mb-8">
            Настоящие Условия регулируют использование Contract AI System, включая бесплатный режим,
            загрузку документов, получение отчетов и переход к пилоту или рабочему контуру.
          </p>
          <div className="space-y-8">
            {sections.map((section) => (
              <section key={section.title}>
                <h2 className="text-2xl font-bold text-gray-900 mb-3">{section.title}</h2>
                <div className="space-y-3 text-gray-700 leading-relaxed">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </section>
            ))}
          </div>
          <div className="mt-10 pt-6 border-t border-gray-200 text-sm text-gray-500">
            Актуальная редакция: 13 мая 2026 года.
          </div>
        </article>
      </div>
    </main>
  )
}
