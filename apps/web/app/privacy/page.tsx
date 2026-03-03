import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Политика конфиденциальности",
  description: "Политика конфиденциальности и обработки персональных данных Legal AI PRO. Защита информации пользователей в соответствии с 152-ФЗ.",
  alternates: {
    canonical: "/privacy",
  },
  openGraph: {
    title: "Политика конфиденциальности | Legal AI PRO",
    description:
      "Как Legal AI PRO обрабатывает и защищает персональные данные пользователей.",
    url: "/privacy",
    type: "article",
  },
  twitter: {
    card: "summary",
    title: "Политика конфиденциальности | Legal AI PRO",
    description:
      "Как Legal AI PRO обрабатывает и защищает персональные данные пользователей.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function PrivacyPolicy() {
  return (
    <main className="min-h-screen bg-slate-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
            Политика конфиденциальности
          </h1>
          <p className="text-lg text-slate-600">
            Настоящая Политика конфиденциальности определяет порядок обработки и защиты персональных данных пользователей сайта legalaipro.ru
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
              1.1. Настоящая Политика конфиденциальности (далее — «Политика») разработана в соответствии с 
              Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных» и определяет порядок обработки 
              персональных данных и меры по обеспечению безопасности персональных данных.
            </p>
            
            <p className="text-slate-700 mb-4">
              1.2. Оператором персональных данных является: <strong>Попов Андрей</strong> (самозанятый), 
              осуществляющий деятельность через сайт <strong>legalaipro.ru</strong> (далее — «Сайт», «мы», «Оператор»).
            </p>
            
            <p className="text-slate-700 mb-4">
              1.3. Оператор ставит своей важнейшей целью и условием осуществления своей деятельности 
              соблюдение прав и свобод человека и гражданина при обработке его персональных данных, 
              в том числе защиты прав на неприкосновенность частной жизни, личную и семейную тайну.
            </p>
            
            <p className="text-slate-700">
              1.4. Используя Сайт, вы соглашаетесь с условиями настоящей Политики конфиденциальности.
            </p>
          </section>

          {/* 2. Какую информацию мы собираем */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">2. Какую информацию мы собираем</h2>
            
            <p className="text-slate-700 mb-4">
              2.1. <strong>Персональные данные:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Имя, фамилия, отчество</li>
              <li>Адрес электронной почты</li>
              <li>Номер телефона</li>
              <li>Название организации и должность (для корпоративных клиентов)</li>
              <li>Telegram username (при обращении через бот)</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              2.2. <strong>Техническая информация:</strong>
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>IP-адрес</li>
              <li>Данные cookies и аналогичных технологий</li>
              <li>Информация о браузере и устройстве</li>
              <li>Информация о посещенных страницах и действиях на Сайте</li>
              <li>Дата и время посещения</li>
              <li>Реферальная ссылка (с какого сайта вы пришли)</li>
            </ul>
            
            <p className="text-slate-700">
              2.3. Мы не собираем специальные категории персональных данных (данные о расовой, национальной 
              принадлежности, политических взглядах, религиозных или философских убеждениях, состоянии здоровья, 
              интимной жизни).
            </p>
          </section>

          {/* 3. Цели обработки */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">3. Цели обработки персональных данных</h2>
            
            <p className="text-slate-700 mb-4">
              3.1. Мы обрабатываем персональные данные в следующих целях:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li><strong>Предоставление услуг:</strong> консультации, разработка AI-решений, техническая поддержка</li>
              <li><strong>Коммуникация:</strong> ответы на запросы, информирование об услугах, отправка коммерческих предложений</li>
              <li><strong>Аналитика:</strong> улучшение работы Сайта, анализ поведения пользователей, оптимизация контента</li>
              <li><strong>Маркетинг:</strong> персонализированные предложения, рассылки (с вашего согласия)</li>
              <li><strong>Безопасность:</strong> защита от мошенничества, выполнение требований законодательства</li>
            </ul>
          </section>

          {/* 4. Правовые основания */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">4. Правовые основания обработки</h2>
            
            <p className="text-slate-700 mb-4">
              4.1. Правовыми основаниями обработки персональных данных являются:
            </p>
            
            <ul className="list-disc pl-6 text-slate-700 space-y-2">
              <li><strong>Ваше согласие</strong> на обработку персональных данных (п. 1 ч. 1 ст. 6 152-ФЗ)</li>
              <li><strong>Договор</strong> или предварительный договор с вами (п. 5 ч. 1 ст. 6 152-ФЗ)</li>
              <li><strong>Законные интересы</strong> Оператора, за исключением случаев, когда такие интересы 
              нарушают ваши права и свободы (п. 7 ч. 1 ст. 6 152-ФЗ)</li>
            </ul>
          </section>

          {/* 5. Как мы используем cookies */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">5. Cookies и аналитика</h2>
            
            <p className="text-slate-700 mb-4">
              5.1. Мы используем cookies и аналогичные технологии для:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li>Сохранения ваших предпочтений</li>
              <li>Аналитики посещаемости через Google Analytics и Yandex Metrika</li>
              <li>Улучшения функциональности Сайта</li>
              <li>Маркетинговых целей (ретаргетинг)</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              5.2. Вы можете отключить cookies в настройках вашего браузера, однако это может ограничить 
              функциональность Сайта.
            </p>
            
            <p className="text-slate-700">
              5.3. <strong>Используемые сервисы:</strong>
            </p>
            
            <ul className="list-disc pl-6 text-slate-700 space-y-2">
              <li><strong>Google Analytics 4:</strong> анализ трафика и поведения пользователей</li>
              <li><strong>Yandex Metrika:</strong> веб-аналитика и тепловые карты</li>
            </ul>
          </section>

          {/* 6. Передача третьим лицам */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">6. Передача персональных данных третьим лицам</h2>
            
            <p className="text-slate-700 mb-4">
              6.1. Мы можем передавать ваши персональные данные третьим лицам только в следующих случаях:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li><strong>С вашего согласия:</strong> явно выраженное согласие на передачу данных</li>
              <li><strong>Партнерам:</strong> для выполнения услуг (хостинг, аналитика) с соблюдением конфиденциальности</li>
              <li><strong>По требованию закона:</strong> государственным органам при наличии законных оснований</li>
            </ul>
            
            <p className="text-slate-700">
              6.2. <strong>Используемые сервисы третьих лиц:</strong>
            </p>
            
            <ul className="list-disc pl-6 text-slate-700 space-y-2">
              <li><strong>Провайдер хостинга:</strong> инфраструктура, через которую размещается сайт и его серверные функции</li>
              <li><strong>Google (Analytics):</strong> веб-аналитика</li>
              <li><strong>Yandex (Metrika):</strong> веб-аналитика (Россия)</li>
              <li><strong>Telegram:</strong> коммуникация через бот</li>
            </ul>
          </section>

          {/* 7. Хранение данных */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">7. Срок хранения персональных данных</h2>
            
            <p className="text-slate-700 mb-4">
              7.1. Персональные данные хранятся в течение:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li><strong>Клиенты:</strong> в течение срока действия договора + 5 лет после его окончания</li>
              <li><strong>Потенциальные клиенты:</strong> до момента отзыва согласия, но не более 3 лет</li>
              <li><strong>Техническая информация:</strong> не более 2 лет с момента последнего посещения</li>
            </ul>
            
            <p className="text-slate-700">
              7.2. По истечении сроков хранения персональные данные уничтожаются или обезличиваются.
            </p>
          </section>

          {/* 8. Безопасность */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">8. Меры защиты персональных данных</h2>
            
            <p className="text-slate-700 mb-4">
              8.1. Мы применяем следующие меры защиты:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li><strong>Шифрование:</strong> SSL/TLS сертификат (HTTPS) для защиты передачи данных</li>
              <li><strong>Контроль доступа:</strong> ограничение доступа к персональным данным</li>
              <li><strong>Резервное копирование:</strong> регулярные бэкапы данных</li>
              <li><strong>Мониторинг:</strong> отслеживание несанкционированного доступа</li>
              <li><strong>Обновления:</strong> своевременное обновление программного обеспечения</li>
            </ul>
            
            <p className="text-slate-700">
              8.2. Несмотря на принимаемые меры, ни один метод передачи данных через Интернет 
              не является на 100% безопасным.
            </p>
          </section>

          {/* 9. Ваши права */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">9. Ваши права</h2>
            
            <p className="text-slate-700 mb-4">
              9.1. В соответствии с 152-ФЗ вы имеете следующие права:
            </p>
            
            <ul className="list-disc pl-6 mb-4 text-slate-700 space-y-2">
              <li><strong>Доступ:</strong> получить информацию о ваших персональных данных, которые мы обрабатываем</li>
              <li><strong>Исправление:</strong> уточнить или исправить неточные данные</li>
              <li><strong>Удаление:</strong> запросить удаление ваших персональных данных</li>
              <li><strong>Ограничение:</strong> ограничить обработку в определенных случаях</li>
              <li><strong>Отзыв согласия:</strong> в любой момент отозвать согласие на обработку данных</li>
              <li><strong>Жалоба:</strong> обратиться в Роскомнадзор при нарушении ваших прав</li>
            </ul>
            
            <p className="text-slate-700 mb-4">
              9.2. Для реализации своих прав обратитесь к нам:
            </p>
            
            <ul className="list-none text-slate-700 space-y-2">
              <li>📧 Email: <a href="mailto:a.popov.gv@gmail.com" className="text-amber-600 hover:text-amber-700">a.popov.gv@gmail.com</a></li>
              <li>📞 Телефон: <a href="tel:+79092330909" className="text-amber-600 hover:text-amber-700">+7 909 233-09-09</a></li>
              <li>💬 Telegram: <a href="https://t.me/legal_ai_helper_new_bot" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700">@legal_ai_helper_new_bot</a></li>
            </ul>
          </section>

          {/* 10. Изменения политики */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">10. Изменения Политики конфиденциальности</h2>
            
            <p className="text-slate-700 mb-4">
              10.1. Мы оставляем за собой право вносить изменения в настоящую Политику конфиденциальности.
            </p>
            
            <p className="text-slate-700 mb-4">
              10.2. При внесении изменений в Политику мы уведомим вас путем размещения новой версии на Сайте 
              с указанием даты последнего обновления.
            </p>
            
            <p className="text-slate-700">
              10.3. Продолжая использовать Сайт после внесения изменений, вы соглашаетесь с новой версией Политики.
            </p>
          </section>

          {/* 11. Контакты */}
          <section className="mb-8 bg-white rounded-xl p-8 shadow-sm">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">11. Контактная информация</h2>
            
            <p className="text-slate-700 mb-4">
              11.1. Если у вас есть вопросы по настоящей Политике конфиденциальности или обработке ваших 
              персональных данных, свяжитесь с нами:
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
