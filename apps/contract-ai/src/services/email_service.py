# -*- coding: utf-8 -*-
"""
Email Service
Send verification emails, password reset, notifications, etc.
Supports SMTP and SendGrid
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from datetime import datetime

from loguru import logger

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

from config.settings import settings


class EmailService:
    """
    Email service for sending transactional emails

    Supports two backends:
    1. SMTP (Gmail, Yandex, custom SMTP server)
    2. SendGrid API (recommended for production)

    Usage:
    ```python
    email_service = EmailService()
    email_service.send_verification_email(
        to_email="user@example.com",
        verification_token="abc123...",
        user_name="Иван Петров"
    )
    ```
    """

    def __init__(self):
        """Initialize email service"""
        # Get settings from environment or config
        self.backend = os.getenv('EMAIL_BACKEND', 'smtp')  # smtp or sendgrid
        self.from_email = os.getenv('EMAIL_FROM', 'noreply@contract-ai.com')
        self.from_name = os.getenv('EMAIL_FROM_NAME', 'Contract AI System')

        # SMTP settings
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

        # SendGrid settings
        self.sendgrid_api_key = os.getenv('SENDGRID_API_KEY', '')

        # Frontend URL for links
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')

        logger.info(f"Email service initialized with backend: {self.backend}")

    def _send_smtp(self, to_email: str, subject: str, html_content: str, text_content: str) -> tuple[bool, Optional[str]]:
        """Send email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email

            # Attach text and HTML parts
            part1 = MIMEText(text_content, 'plain', 'utf-8')
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            # Connect and send
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.smtp_use_tls:
                server.starttls()
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)

            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent via SMTP to {to_email}: {subject}")
            return True, None

        except Exception as e:
            logger.error(f"SMTP email error: {e}", exc_info=True)
            return False, str(e)

    def _send_sendgrid(self, to_email: str, subject: str, html_content: str, text_content: str) -> tuple[bool, Optional[str]]:
        """Send email via SendGrid API"""
        if not SENDGRID_AVAILABLE:
            return False, "SendGrid library not installed. Run: pip install sendgrid"

        if not self.sendgrid_api_key:
            return False, "SendGrid API key not configured"

        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            logger.info(f"Email sent via SendGrid to {to_email}: {subject} (status: {response.status_code})")
            return True, None

        except Exception as e:
            logger.error(f"SendGrid email error: {e}", exc_info=True)
            return False, str(e)

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Send email using configured backend

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text email content (fallback)

        Returns:
            (success: bool, error: Optional[str])
        """
        # Generate text content from HTML if not provided
        if not text_content:
            # Simple HTML to text conversion
            import re
            text_content = re.sub('<[^<]+?>', '', html_content)

        # Send via configured backend
        if self.backend == 'sendgrid':
            return self._send_sendgrid(to_email, subject, html_content, text_content)
        else:
            return self._send_smtp(to_email, subject, html_content, text_content)

    def send_verification_email(
        self,
        to_email: str,
        verification_token: str,
        user_name: str
    ) -> tuple[bool, Optional[str]]:
        """
        Send email verification link

        Args:
            to_email: User email
            verification_token: Verification token
            user_name: User's name
        """
        verification_url = f"{self.frontend_url}/verify-email?token={verification_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📄 Contract AI System</h1>
                </div>
                <div class="content">
                    <h2>Подтверждение email</h2>
                    <p>Здравствуйте, {user_name}!</p>
                    <p>Спасибо за регистрацию в Contract AI System. Для активации вашего аккаунта, пожалуйста, подтвердите ваш email адрес.</p>
                    <p style="text-align: center;">
                        <a href="{verification_url}" class="button">Подтвердить Email</a>
                    </p>
                    <p>Или скопируйте эту ссылку в браузер:</p>
                    <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">
                        {verification_url}
                    </p>
                    <p><strong>Ссылка действительна 24 часа.</strong></p>
                    <p>Если вы не регистрировались в Contract AI System, просто проигнорируйте это письмо.</p>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} Contract AI System. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
Contract AI System - Подтверждение email

Здравствуйте, {user_name}!

Спасибо за регистрацию в Contract AI System.
Для активации вашего аккаунта, пожалуйста, перейдите по ссылке:

{verification_url}

Ссылка действительна 24 часа.

Если вы не регистрировались в Contract AI System, просто проигнорируйте это письмо.

© {datetime.now().year} Contract AI System
        """

        return self.send_email(
            to_email=to_email,
            subject="Подтвердите ваш email - Contract AI System",
            html_content=html_content,
            text_content=text_content
        )

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: str
    ) -> tuple[bool, Optional[str]]:
        """Send password reset link"""
        reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Сброс пароля</h1>
                </div>
                <div class="content">
                    <h2>Запрос на сброс пароля</h2>
                    <p>Здравствуйте, {user_name}!</p>
                    <p>Вы запросили сброс пароля для вашего аккаунта в Contract AI System.</p>
                    <p style="text-align: center;">
                        <a href="{reset_url}" class="button">Сбросить пароль</a>
                    </p>
                    <p>Или скопируйте эту ссылку в браузер:</p>
                    <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">
                        {reset_url}
                    </p>
                    <div class="warning">
                        <strong>⚠️ Важно:</strong>
                        <ul>
                            <li>Ссылка действительна только 1 час</li>
                            <li>После смены пароля все активные сессии будут завершены</li>
                            <li>Если вы не запрашивали сброс пароля, немедленно свяжитесь с поддержкой</li>
                        </ul>
                    </div>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} Contract AI System. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
Contract AI System - Сброс пароля

Здравствуйте, {user_name}!

Вы запросили сброс пароля для вашего аккаунта.
Перейдите по ссылке для установки нового пароля:

{reset_url}

ВАЖНО:
- Ссылка действительна только 1 час
- После смены пароля все активные сессии будут завершены
- Если вы не запрашивали сброс пароля, немедленно свяжитесь с поддержкой

© {datetime.now().year} Contract AI System
        """

        return self.send_email(
            to_email=to_email,
            subject="Сброс пароля - Contract AI System",
            html_content=html_content,
            text_content=text_content
        )

    def send_welcome_email(
        self,
        to_email: str,
        user_name: str,
        is_demo: bool = False
    ) -> tuple[bool, Optional[str]]:
        """Send welcome email to new user"""
        demo_info = ""
        if is_demo:
            demo_info = """
            <div class="warning">
                <strong>Демо-режим</strong>
                <p>Вы используете демо-версию с ограничениями:</p>
                <ul>
                    <li>До 3 контрактов</li>
                    <li>До 10 LLM запросов</li>
                    <li>Доступ действителен 24 часа</li>
                </ul>
                <p>Для получения полного доступа, пожалуйста, перейдите на платный тариф.</p>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .feature {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #667eea; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Добро пожаловать!</h1>
                </div>
                <div class="content">
                    <h2>Здравствуйте, {user_name}!</h2>
                    <p>Спасибо за регистрацию в <strong>Contract AI System</strong> - интеллектуальной системе для автоматизации работы с договорами.</p>

                    {demo_info}

                    <h3>Возможности системы:</h3>

                    <div class="feature">
                        <strong>📥 Анализ договоров</strong>
                        <p>Загрузите договор контрагента и получите детальный анализ рисков, соответствия законодательству и рекомендации по улучшению.</p>
                    </div>

                    <div class="feature">
                        <strong>✍️ Генерация договоров</strong>
                        <p>Создавайте договоры по готовым шаблонам с автоматическим заполнением через LLM.</p>
                    </div>

                    <div class="feature">
                        <strong>⚖️ Возражения</strong>
                        <p>Генерируйте документы с возражениями с правовыми обоснованиями для отправки в ЭДО.</p>
                    </div>

                    <div class="feature">
                        <strong>📊 Анализ изменений</strong>
                        <p>Сравнивайте версии договора и анализируйте влияние изменений.</p>
                    </div>

                    <p style="text-align: center;">
                        <a href="{self.frontend_url}/dashboard" class="button">Перейти в систему</a>
                    </p>

                    <p>Если у вас есть вопросы, обращайтесь в поддержку: support@contract-ai.com</p>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} Contract AI System. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(
            to_email=to_email,
            subject="Добро пожаловать в Contract AI System!",
            html_content=html_content
        )

    def send_analysis_complete_email(
        self,
        to_email: str,
        user_name: str,
        contract_name: str,
        contract_id: str,
        risks_count: int,
        recommendations_count: int
    ) -> tuple[bool, Optional[str]]:
        """Send notification when contract analysis is complete"""
        analysis_url = f"{self.frontend_url}/contracts/{contract_id}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .stat {{ background: white; padding: 15px; border-radius: 5px; text-align: center; flex: 1; margin: 0 5px; }}
                .stat-value {{ font-size: 32px; font-weight: bold; color: #667eea; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Анализ завершён</h1>
                </div>
                <div class="content">
                    <h2>Здравствуйте, {user_name}!</h2>
                    <p>Анализ договора <strong>"{contract_name}"</strong> успешно завершён.</p>

                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">{risks_count}</div>
                            <div>Рисков</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{recommendations_count}</div>
                            <div>Рекомендаций</div>
                        </div>
                    </div>

                    <p style="text-align: center;">
                        <a href="{analysis_url}" class="button">Просмотреть результаты</a>
                    </p>

                    <p>Система провела детальный анализ договора и выявила потенциальные риски, несоответствия законодательству и области для улучшения.</p>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} Contract AI System. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(
            to_email=to_email,
            subject=f'Анализ договора "{contract_name}" завершён',
            html_content=html_content
        )

    def send_demo_expiring_email(
        self,
        to_email: str,
        user_name: str,
        hours_left: int
    ) -> tuple[bool, Optional[str]]:
        """Send notification when demo access is expiring"""
        upgrade_url = f"{self.frontend_url}/pricing"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⏰ Демо-доступ истекает</h1>
                </div>
                <div class="content">
                    <h2>Здравствуйте, {user_name}!</h2>
                    <p>Ваш демо-доступ к Contract AI System истекает через <strong>{hours_left} часов</strong>.</p>

                    <div class="warning">
                        <strong>После истечения демо-доступа:</strong>
                        <ul>
                            <li>Вы не сможете загружать новые договоры</li>
                            <li>Анализ договоров будет недоступен</li>
                            <li>Экспорт результатов будет ограничен</li>
                        </ul>
                    </div>

                    <p>Не упустите возможность продолжить работу с системой!</p>

                    <p style="text-align: center;">
                        <a href="{upgrade_url}" class="button">Перейти на полную версию</a>
                    </p>

                    <p><strong>Преимущества полной версии:</strong></p>
                    <ul>
                        <li>Неограниченный анализ договоров</li>
                        <li>Генерация возражений с правовыми обоснованиями</li>
                        <li>Экспорт в PDF, DOCX, JSON</li>
                        <li>Приоритетная поддержка</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} Contract AI System. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(
            to_email=to_email,
            subject=f"Ваш демо-доступ истекает через {hours_left} ч",
            html_content=html_content
        )


# Singleton instance
email_service = EmailService()
