"""
Email отправка для Lead Magnets
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import Config
config = Config()

logger = logging.getLogger(__name__)


class EmailSender:
    """Класс для отправки email через SMTP"""

    def __init__(self):
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
        self.smtp_user = config.SMTP_USER
        self.smtp_password = config.SMTP_PASSWORD
        self.from_email = config.FROM_EMAIL
        self.from_name = config.FROM_NAME

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """
        Отправляет email

        Args:
            to_email: Email получателя
            subject: Тема письма
            html_body: HTML содержимое письма

        Returns:
            bool: True если отправлено успешно, False если ошибка
        """
        try:
            # Создаем сообщение
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email

            # Добавляем HTML часть
            html_part = MIMEText(html_body, "html", "utf-8")
            message.attach(html_part)

            # Подключаемся к SMTP серверу и отправляем
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_consultation_confirmation(self, to_email: str, name: Optional[str] = None) -> bool:
        """
        Отправляет подтверждение консультации

        Args:
            to_email: Email получателя
            name: Имя получателя (опционально)

        Returns:
            bool: True если успешно
        """
        name_greeting = f"Здравствуйте, {name}!" if name else "Здравствуйте!"

        subject = "Консультация с нашей командой - подтверждение"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }}
        h2 {{ color: #2c3e50; }}
        .contact-info {{ background-color: white; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Консультация с нашей командой</h1>
            <p style="margin: 5px 0 0 0; font-size: 14px;">Юристы-практики, которые сами разрабатывают AI-решения</p>
        </div>

        <div class="content">
            <h2>{name_greeting}</h2>

            <p>Спасибо за интерес к нашим AI-решениям для автоматизации юридической работы!</p>

            <p>Мы свяжемся с вами в ближайшее время для согласования удобного времени консультации (30 минут).</p>

            <h3>Что обсудим на консультации:</h3>
            <ul>
                <li>✅ Ваши текущие задачи и боли в юридической работе</li>
                <li>✅ Как AI может помочь именно в вашем случае</li>
                <li>✅ Примерные сроки и стоимость решения</li>
                <li>✅ Реальные кейсы и результаты внедрения</li>
            </ul>

            <div class="contact-info">
                <h3>Контакты для связи:</h3>
                <p>
                    <strong>Руководитель проектов - Андрей Попов</strong><br>
                    Юрист-разработчик с 24-летним опытом<br>
                    Команда юристов-практиков, которые сами пишут код
                </p>
                <p>
                    📧 Email: <a href="mailto:a.popov.gv@gmail.com">a.popov.gv@gmail.com</a><br>
                    📱 Telegram: <a href="https://t.me/AndrewPopov821667">@AndrewPopov821667</a><br>
                    📞 Телефон: +7 (909) 233-09-09<br>
                    💻 GitHub: <a href="https://github.com/Andrew821667">github.com/Andrew821667</a>
                </p>
            </div>

            <p>Если у вас появятся вопросы до консультации — пишите в любое удобное время!</p>

            <p style="margin-top: 30px;">
                <strong>С уважением,<br>
                Команда юристов-разработчиков</strong><br>
                <small style="color: #666;">Руководитель проектов: Андрей Попов</small>
            </p>
        </div>

        <div class="footer">
            <p>Это письмо отправлено в ответ на ваш запрос через Telegram бот @LegalAI_Popov_Andrew</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_body)

    def send_checklist(self, to_email: str, name: Optional[str] = None) -> bool:
        """
        Отправляет чек-лист "15 типовых ошибок в договорах"

        Args:
            to_email: Email получателя
            name: Имя получателя (опционально)

        Returns:
            bool: True если успешно
        """
        name_greeting = f"Здравствуйте, {name}!" if name else "Здравствуйте!"

        subject = "Чек-лист: 15 типовых ошибок в договорах"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #e74c3c; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        h2 {{ color: #e74c3c; }}
        .checklist {{ background-color: white; padding: 20px; }}
        .checklist-item {{
            padding: 12px;
            margin: 10px 0;
            border-left: 4px solid #e74c3c;
            background-color: #fff5f5;
        }}
        .checklist-item strong {{ color: #c0392b; }}
        .tip {{ background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0; }}
        .contact-info {{ background-color: white; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>15 типовых ошибок в договорах</h1>
            <p>И как их избежать</p>
        </div>

        <div class="content">
            <h2>{name_greeting}</h2>

            <p>Представляю вашему вниманию чек-лист из 15 самых частых ошибок, которые я встречал за 24 года юридической практики.</p>

            <div class="checklist">
                <h3>🔴 Критические ошибки:</h3>

                <div class="checklist-item">
                    <strong>1. Нет предмета договора или он описан неоднозначно</strong><br>
                    Суд может признать договор незаключенным. Описывайте предмет максимально конкретно.
                </div>

                <div class="checklist-item">
                    <strong>2. Отсутствуют существенные условия для данного типа договора</strong><br>
                    Для каждого типа договора есть свои существенные условия по ГК РФ.
                </div>

                <div class="checklist-item">
                    <strong>3. Цена не указана (когда это существенно)</strong><br>
                    В ряде договоров (возмездное оказание услуг, подряд) цена является существенным условием.
                </div>

                <div class="checklist-item">
                    <strong>4. Условия об ответственности противоречат закону</strong><br>
                    Нельзя полностью исключить ответственность за умышленные нарушения или грубую неосторожность.
                </div>

                <div class="checklist-item">
                    <strong>5. Сроки не указаны или размыты</strong><br>
                    "В разумный срок", "в кратчайшие сроки" — источник споров.
                </div>

                <h3 style="margin-top: 30px;">⚠️ Частые ошибки:</h3>

                <div class="checklist-item">
                    <strong>6. Нет порядка приемки работ/услуг</strong><br>
                    Как подтверждается выполнение? Акт? В какой срок?
                </div>

                <div class="checklist-item">
                    <strong>7. Не прописан порядок изменения договора</strong><br>
                    Может ли сторона в одностороннем порядке менять условия?
                </div>

                <div class="checklist-item">
                    <strong>8. Отсутствует претензионный порядок</strong><br>
                    Во многих случаях обязателен, без него суд не примет иск.
                </div>

                <div class="checklist-item">
                    <strong>9. Неверно указаны реквизиты сторон</strong><br>
                    Проверяйте по ЕГРЮЛ/ЕГРИП. Ошибка в ОГРН или адресе может быть критичной.
                </div>

                <div class="checklist-item">
                    <strong>10. Подписант не имел полномочий</strong><br>
                    Проверяйте устав и доверенность. Сделка может быть оспорена.
                </div>

                <div class="checklist-item">
                    <strong>11. Не согласованы способы обеспечения обязательств</strong><br>
                    Залог, поручительство, неустойка — все должно быть прописано.
                </div>

                <div class="checklist-item">
                    <strong>12. Противоречия между разделами договора</strong><br>
                    Условия об оплате в разных местах указаны по-разному.
                </div>

                <div class="checklist-item">
                    <strong>13. Форс-мажор описан слишком широко</strong><br>
                    "Любые обстоятельства" не сработает. Нужна конкретика.
                </div>

                <div class="checklist-item">
                    <strong>14. Нет порядка расторжения договора</strong><br>
                    Можно ли расторгнуть в одностороннем порядке? Как?
                </div>

                <div class="checklist-item">
                    <strong>15. Не учтены отраслевые особенности</strong><br>
                    Для агробизнеса, банков, застройщиков есть специальные требования.
                </div>
            </div>

            <div class="tip">
                <strong>💡 Совет:</strong> AI-система может проверять договоры на все эти 15 пунктов автоматически за 5-10 минут. Это экономит 2-4 часа юриста на каждом договоре и снижает риск пропустить критичную ошибку.
            </div>

            <h3>Хотите автоматизировать проверку договоров?</h3>
            <p>Мы поможем создать AI-систему, которая будет анализировать ваши договоры и выявлять все эти ошибки автоматически.</p>

            <div class="contact-info">
                <h3>Свяжитесь с нами:</h3>
                <p>
                    <strong>Команда юристов-разработчиков</strong><br>
                    Руководитель проектов: Андрей Попов<br>
                    Юристы-практики, которые сами пишут код
                </p>
                <p>
                    📧 Email: <a href="mailto:a.popov.gv@gmail.com">a.popov.gv@gmail.com</a><br>
                    📱 Telegram: <a href="https://t.me/AndrewPopov821667">@AndrewPopov821667</a><br>
                    📞 Телефон: +7 (909) 233-09-09<br>
                    💻 GitHub: <a href="https://github.com/Andrew821667">github.com/Andrew821667</a>
                </p>
            </div>

            <p style="margin-top: 30px;">
                <strong>С уважением,<br>
                Команда юристов-разработчиков</strong><br>
                <small style="color: #666;">Руководитель проектов: Андрей Попов</small>
            </p>
        </div>

        <div class="footer">
            <p>Это письмо отправлено в ответ на ваш запрос через Telegram бот @LegalAI_Popov_Andrew</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_body)

    def send_demo_request_confirmation(self, to_email: str, name: Optional[str] = None) -> bool:
        """
        Отправляет подтверждение запроса на демо-анализ

        Args:
            to_email: Email получателя
            name: Имя получателя (опционально)

        Returns:
            bool: True если успешно
        """
        name_greeting = f"Здравствуйте, {name}!" if name else "Здравствуйте!"

        subject = "Демо-анализ договора - следующие шаги"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #9b59b6; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        h2 {{ color: #9b59b6; }}
        .steps {{ background-color: white; padding: 20px; margin: 20px 0; }}
        .step {{
            padding: 15px;
            margin: 15px 0;
            border-left: 4px solid #9b59b6;
            background-color: #f8f5fb;
        }}
        .contact-info {{ background-color: white; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0; }}
        .highlight {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Демо-анализ договора</h1>
            <p>Увидите возможности AI на вашем примере</p>
        </div>

        <div class="content">
            <h2>{name_greeting}</h2>

            <p>Отлично! Мы проведем демо-анализ вашего договора, чтобы вы увидели как работает AI-система на реальном документе.</p>

            <div class="steps">
                <h3>Следующие шаги:</h3>

                <div class="step">
                    <strong>Шаг 1:</strong> Отправьте нам ваш договор<br>
                    <small>Можно в любом формате: Word, PDF, скан. Конфиденциальность гарантируем.</small>
                </div>

                <div class="step">
                    <strong>Шаг 2:</strong> Мы проведем анализ (1-2 часа)<br>
                    <small>Система проверит договор на риски, неоднозначности, отсутствующие условия.</small>
                </div>

                <div class="step">
                    <strong>Шаг 3:</strong> Вы получите отчет<br>
                    <small>Подробный анализ с выявленными проблемами и рекомендациями.</small>
                </div>

                <div class="step">
                    <strong>Шаг 4:</strong> Обсудим результаты<br>
                    <small>Разберем как можно автоматизировать такой анализ для всех ваших договоров.</small>
                </div>
            </div>

            <div class="highlight">
                <strong>🎯 Что вы увидите в демо-анализе:</strong>
                <ul>
                    <li>Выявленные юридические риски (с указанием статей ГК РФ)</li>
                    <li>Отсутствующие или неоднозначные условия</li>
                    <li>Несбалансированные положения</li>
                    <li>Рекомендации по доработке</li>
                    <li>Оценка общего уровня риска договора</li>
                </ul>
            </div>

            <h3>Как отправить договор:</h3>
            <ul>
                <li>📧 Email: <a href="mailto:a.popov.gv@gmail.com">a.popov.gv@gmail.com</a></li>
                <li>📱 Telegram: <a href="https://t.me/AndrewPopov821667">@AndrewPopov821667</a></li>
            </ul>

            <div class="contact-info">
                <h3>Контакты для связи:</h3>
                <p>
                    <strong>Команда юристов-разработчиков</strong><br>
                    Руководитель проектов: Андрей Попов<br>
                    Юристы-практики, которые сами пишут код
                </p>
                <p>
                    📧 Email: <a href="mailto:a.popov.gv@gmail.com">a.popov.gv@gmail.com</a><br>
                    📱 Telegram: <a href="https://t.me/AndrewPopov821667">@AndrewPopov821667</a><br>
                    📞 Телефон: +7 (909) 233-09-09<br>
                    💻 GitHub: <a href="https://github.com/Andrew821667">github.com/Andrew821667</a>
                </p>
            </div>

            <p style="margin-top: 30px;">
                <strong>С уважением,<br>
                Команда юристов-разработчиков</strong><br>
                <small style="color: #666;">Руководитель проектов: Андрей Попов</small>
            </p>
        </div>

        <div class="footer">
            <p>Это письмо отправлено в ответ на ваш запрос через Telegram бот @LegalAI_Popov_Andrew</p>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_body)


# Глобальный экземпляр
email_sender = EmailSender()
