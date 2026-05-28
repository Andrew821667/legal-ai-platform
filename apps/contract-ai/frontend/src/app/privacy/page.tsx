import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Политика конфиденциальности',
  description: 'Политика конфиденциальности Contract AI System: обработка данных, документы пользователей и меры защиты.',
  alternates: {
    canonical: '/privacy',
  },
}

const sections = [
  {
    title: '1. Какие данные обрабатываются',
    paragraphs: [
      'Contract AI System может обрабатывать регистрационные данные пользователя, контактные данные, загружаемые договоры, результаты анализа, технические журналы и сведения об использовании функций системы.',
      'Документы и результаты анализа используются для предоставления сервиса, контроля качества, диагностики ошибок и выполнения обязательств перед пользователем.',
    ],
  },
  {
    title: '2. Бесплатный режим и документы',
    paragraphs: [
      'В бесплатном режиме пользователю доступно 3 договора в месяц. Загружайте только документы, на обработку которых у вас есть право.',
      'Не загружайте документы, содержащие государственную тайну, банковскую тайну, врачебную тайну или иную информацию, для которой требуется отдельный защищенный контур.',
    ],
  },
  {
    title: '3. Цели обработки',
    paragraphs: [
      'Данные используются для регистрации и авторизации, анализа договоров, формирования отчетов, обеспечения безопасности, поддержки пользователя и улучшения качества сервиса.',
      'Обработка выполняется в объеме, необходимом для работы Contract AI System и связанных юридико-технических услуг AI Verdict.',
    ],
  },
  {
    title: '4. Передача и хранение',
    paragraphs: [
      'Доступ к данным ограничивается уполномоченными специалистами и техническими сервисами, необходимыми для работы системы.',
      'Срок хранения зависит от выбранного формата использования, требований безопасности и обязательств по договору или пользовательскому соглашению.',
    ],
  },
  {
    title: '5. Контакты',
    paragraphs: [
      'По вопросам обработки персональных данных и документов можно обратиться через основной сайт AI Verdict или по контактам, указанным на ai-verdict.ru.',
    ],
  },
]

export default function PrivacyPage() {
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
            Политика конфиденциальности
          </h1>
          <p className="text-gray-600 text-lg mb-8">
            Настоящая Политика описывает, как Contract AI System обрабатывает данные пользователей,
            загружаемые договоры и техническую информацию при использовании сервиса.
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
