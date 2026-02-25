import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Условия использования",
  description: "Условия использования сайта legalaipro.ru. Правила предоставления услуг по разработке AI-решений для автоматизации юридической работы.",
  alternates: {
    canonical: "/terms",
  },
  openGraph: {
    title: "Условия использования | Legal AI PRO",
    description:
      "Правила использования сайта и оказания услуг Legal AI PRO.",
    url: "/terms",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Условия использования | Legal AI PRO",
    description: "Правила использования сайта и оказания услуг Legal AI PRO.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function TermsOfService() {
  return (
    <main className="min-h-screen bg-slate-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
            Условия использования
          </h1>
          <p className="text-lg text-slate-600">
            Настоящие Условия использования регулируют порядок использования сайта legalaipro.ru 
            и получения услуг по автоматизации юридической работы
          </p>
          <p className="text-sm text-slate-500 mt-4">
            Последнее обновление: 13 января 2026 года
          </p>
        </div>

        {/* Content */}
        <div className="prose prose-slate max-w-none">
          
          {/* 1. Общие положения */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">1. Общие положения</h2>
            
            <p className="text-slate-700 mb-4">
              1.1. Настоящие Условия использования (далее — «Условия») регулируют отношения между 
              <strong> Попов Андрей</strong> (самозанятый), действующим под брендом <strong>Legal AI PRO</strong> 
              (далее — «мы», «Исполнитель», «Оператор»), и любым лицом, использующим сайт 
              <strong> legalaipro.ru</strong> (далее — «Сайт», «вы», «Пользователь», «Клиент»).
            </p>
            
            <p className="text-slate-700 mb-4">
              1.2. Используя Сайт, отправляя запросы, заполняя формы или связываясь с нами любым способом, 
              вы подтверждаете, что:
            </p>
            
            <ul className="list-disc pl-6 text-slate-700 space-y-2">
              <li>Вы прочитали, поняли и согласны с настоящими Условиями</li>
              <li>Вы обладаете необходимой правоспособностью для заключения договора</li>
              <li>Вы действуете добровольно и в своем интересе (или интересе представляемой организации)</li>
            </ul>
          </section>

          {/* 2. Предмет */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">2. Предмет настоящих Условий</h2>
            
            <p className="text-slate-700 mb-4">
              2.1. Мы предоставляем следующие услуги (далее — «Услуги»):
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li><strong>Разработка AI-систем</strong> для автоматизации юридической работы</li>
              <li><strong>Автоматизация договорной работы:</strong> анализ, генерация, выявление рисков</li>
              <li><strong>Автоматизация судебной работы:</strong> мониторинг арбитражных дел, анализ практики</li>
              <li><strong>Автоматизация корпоративного права:</strong> Due Diligence, документооборот</li>
              <li><strong>Налоговый комплаенс с AI:</strong> мониторинг изменений, прогноз рисков</li>
              <li><strong>Консультации</strong> по внедрению AI в юридическую практику</li>
              <li><strong>Техническая поддержка</strong> внедренных решений</li>
            </ul>
            
            <p className="text-slate-700">
              2.2. Конкретный объем, условия и стоимость Услуг определяются в индивидуальном порядке 
              после обсуждения задач Клиента.
            </p>
          </section>

          {/* 3. Порядок предоставления услуг */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">3. Порядок предоставления Услуг</h2>
            
            <p className="text-slate-700 mb-4">
              3.1. <strong>Запрос услуг:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Вы отправляете запрос через форму на Сайте, email, Telegram или по телефону</li>
              <li>Мы связываемся с вами для уточнения задач и требований</li>
              <li>Мы предоставляем коммерческое предложение с описанием объема работ и стоимости</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              3.2. <strong>Заключение договора:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>При согласии с условиями заключается договор (в простой письменной форме или путем обмена документами)</li>
              <li>Договор считается заключенным с момента оплаты аванса (если предусмотрено)</li>
              <li>Для корпоративных клиентов возможно заключение договора по вашей форме</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              3.3. <strong>Выполнение работ:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Мы выполняем работы в согласованные сроки</li>
              <li>Мы информируем вас о ходе выполнения работ</li>
              <li>Вы предоставляете необходимую информацию и документы для выполнения работ</li>
            </ul>
            
            <p className="text-slate-700">
              3.4. <strong>Приемка результата:</strong>
            </p>
            
            <ul className="list-disc pl-6 text-slate-700 space-y-2">
              <li>Мы предоставляем результат работ для приемки</li>
              <li>Вы проверяете результат и направляете акт приемки или мотивированный отказ</li>
              <li>При отсутствии претензий в течение 5 рабочих дней результат считается принятым</li>
            </ul>
          </section>

          {/* 4. Стоимость и оплата */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">4. Стоимость и оплата</h2>
            
            <p className="text-slate-700 mb-4">
              4.1. Стоимость Услуг определяется индивидуально и указывается в коммерческом предложении или договоре.
            </p>
            
            <p className="text-slate-700 mb-4">
              4.2. <strong>Ориентировочные цены:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Консультация (1 час): бесплатно (первичная)</li>
              <li>Типовые решения (анализ договоров, мониторинг дел): от 300 000 до 500 000 ₽</li>
              <li>Комплексная автоматизация юротдела: от 800 000 до 2 000 000 ₽</li>
              <li>Кастомные решения: рассчитываются индивидуально</li>
              <li>Техническая поддержка: от 30 000 ₽/мес</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              4.3. <strong>Порядок оплаты:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Аванс: обычно 50% от стоимости (по согласованию)</li>
              <li>Окончательный расчет: после приемки результата работ</li>
              <li>Способы оплаты: безналичный расчет (для юр. лиц и ИП), перевод на карту (для физ. лиц)</li>
            </ul>
            
            <p className="text-slate-700">
              4.4. Мы выставляем акт выполненных работ для бухгалтерии вашей организации.
            </p>
          </section>

          {/* 5. Права и обязанности */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">5. Права и обязанности сторон</h2>
            
            <p className="text-slate-700 mb-4">
              5.1. <strong>Мы обязуемся:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Выполнять Услуги качественно, в срок и в полном объеме</li>
              <li>Консультировать вас по вопросам использования результатов работ</li>
              <li>Обеспечивать конфиденциальность предоставленной вами информации</li>
              <li>Предоставлять техническую поддержку в рамках согласованных условий</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              5.2. <strong>Вы обязуетесь:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Своевременно оплачивать Услуги</li>
              <li>Предоставлять необходимую информацию и документы для выполнения работ</li>
              <li>Своевременно рассматривать и принимать результаты работ</li>
              <li>Не использовать результаты работ в целях, нарушающих законодательство</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              5.3. <strong>Мы вправе:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Отказать в предоставлении Услуг без объяснения причин</li>
              <li>Приостановить выполнение работ при нарушении вами условий оплаты</li>
              <li>Привлекать третьих лиц для выполнения части работ</li>
            </ul>
            
            <p className="text-slate-700">
              5.4. <strong>Вы вправе:</strong>
            </p>
            
            <ul className="list-disc pl-6 text-slate-700 space-y-2">
              <li>Требовать качественного выполнения работ в срок</li>
              <li>Отказаться от Услуг, возместив фактически понесенные нами расходы</li>
              <li>Запрашивать информацию о ходе выполнения работ</li>
            </ul>
          </section>

          {/* 6. Интеллектуальная собственность */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">6. Интеллектуальная собственность</h2>
            
            <p className="text-slate-700 mb-4">
              6.1. Исключительные права на результаты работ (программное обеспечение, методологии, документация) 
              передаются вам в объеме, согласованном в договоре.
            </p>
            
            <p className="text-slate-700 mb-4">
              6.2. <strong>Типовые решения:</strong> вы получаете неисключительную лицензию на использование.
            </p>
            
            <p className="text-slate-700 mb-4">
              6.3. <strong>Кастомные решения:</strong> исключительные права могут быть переданы вам за дополнительную плату.
            </p>
            
            <p className="text-slate-700">
              6.4. Вы не вправе воспроизводить, модифицировать или распространять результаты работ 
              без нашего письменного согласия (если иное не предусмотрено договором).
            </p>
          </section>

          {/* 7. Конфиденциальность */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">7. Конфиденциальность</h2>
            
            <p className="text-slate-700 mb-4">
              7.1. Мы обязуемся не разглашать конфиденциальную информацию, полученную от вас в ходе 
              выполнения работ, за исключением случаев, предусмотренных законодательством.
            </p>
            
            <p className="text-slate-700 mb-4">
              7.2. <strong>Конфиденциальной информацией</strong> является любая информация, 
              переданная нам и помеченная как конфиденциальная, а также:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Документы, договоры, финансовая информация</li>
              <li>Коммерческая тайна и бизнес-процессы</li>
              <li>Персональные данные</li>
            </ul>
            
            <p className="text-slate-700">
              7.3. Обязательства по конфиденциальности действуют в течение 5 лет после окончания договора.
            </p>
          </section>

          {/* 8. Гарантии и ответственность */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">8. Гарантии и ответственность</h2>
            
            <p className="text-slate-700 mb-4">
              8.1. <strong>Гарантии:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Мы гарантируем, что результаты работ будут соответствовать согласованным требованиям</li>
              <li>Гарантийный срок: 6 месяцев с момента приемки (если иное не предусмотрено договором)</li>
              <li>В гарантийный срок мы устраняем выявленные недостатки бесплатно</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              8.2. <strong>Ограничение ответственности:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Мы не несем ответственности за неработоспособность решения, вызванную действиями третьих лиц, 
              вашими действиями, форс-мажором</li>
              <li>Максимальная ответственность ограничена стоимостью оказанных Услуг</li>
              <li>Мы не несем ответственности за упущенную выгоду</li>
            </ul>
            
            <p className="text-slate-700">
              8.3. <strong>Важно:</strong> AI-системы являются вспомогательными инструментами. 
              Окончательные решения по юридическим вопросам должны приниматься квалифицированными специалистами.
            </p>
          </section>

          {/* 9. Форс-мажор */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">9. Форс-мажор</h2>
            
            <p className="text-slate-700 mb-4">
              9.1. Стороны освобождаются от ответственности за неисполнение или ненадлежащее исполнение 
              обязательств, если это вызвано обстоятельствами непреодолимой силы (форс-мажор).
            </p>
            
            <p className="text-slate-700">
              9.2. К форс-мажорным обстоятельствам относятся: стихийные бедствия, военные действия, 
              террористические акты, действия властей, техногенные катастрофы, 
              крупномасштабные сбои в работе интернета или инфраструктуры.
            </p>
          </section>

          {/* 10. Разрешение споров */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">10. Разрешение споров</h2>
            
            <p className="text-slate-700 mb-4">
              10.1. Все споры и разногласия разрешаются путем переговоров.
            </p>
            
            <p className="text-slate-700 mb-4">
              10.2. При недостижении согласия спор передается в суд по месту нахождения Исполнителя 
              (в соответствии с подсудностью, установленной законодательством РФ).
            </p>
            
            <p className="text-slate-700">
              10.3. Досудебный порядок урегулирования споров обязателен. Претензия направляется в письменной форме 
              и рассматривается в течение 10 рабочих дней.
            </p>
          </section>

          {/* 11. Заключительные положения */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">11. Заключительные положения</h2>
            
            <p className="text-slate-700 mb-4">
              11.1. Настоящие Условия регулируются законодательством Российской Федерации.
            </p>
            
            <p className="text-slate-700 mb-4">
              11.2. Мы вправе вносить изменения в настоящие Условия. Актуальная версия всегда доступна на Сайте.
            </p>
            
            <p className="text-slate-700 mb-4">
              11.3. Если какое-либо положение Условий будет признано недействительным, остальные положения 
              сохраняют силу.
            </p>
            
            <p className="text-slate-700">
              11.4. Настоящие Условия вступают в силу с момента начала использования Сайта или отправки запроса на Услуги.
            </p>
          </section>

          {/* 12. Контакты */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">12. Контактная информация</h2>
            
            <p className="text-slate-700 mb-4">
              12.1. Если у вас есть вопросы по настоящим Условиям использования, свяжитесь с нами:
            </p>
            
            <div className="bg-slate-50 p-6 rounded-lg">
              <p className="text-slate-900 font-semibold mb-3">Legal AI PRO</p>
              <ul className="space-y-2 text-slate-700">
                <li><strong>Email:</strong> <a href="mailto:a.popov.gv@gmail.com" className="text-amber-600 hover:text-amber-700">a.popov.gv@gmail.com</a></li>
                <li><strong>Телефон:</strong> <a href="tel:+79092330909" className="text-amber-600 hover:text-amber-700">+7 909 233-09-09</a></li>
                <li><strong>Telegram:</strong> <a href="https://t.me/legal_ai_helper_new_bot" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700">@legal_ai_helper_new_bot</a></li>
                <li><strong>Сайт:</strong> <a href="https://legalaipro.ru" className="text-amber-600 hover:text-amber-700">https://legalaipro.ru</a></li>
              </ul>
            </div>
          </section>

        </div>

        {/* Back button */}
        <div className="mt-12 pt-8 border-t border-slate-200">
          <a 
            href="/" 
            className="inline-flex items-center text-amber-600 hover:text-amber-700 font-semibold transition-colors"
          >
            ← Вернуться на главную
          </a>
        </div>
      </div>
    </main>
  );
}
