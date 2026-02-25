# -*- coding: utf-8 -*-
"""
Payment Service - Stripe Integration
Handle subscriptions, payments, webhooks
"""
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from loguru import logger

try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

from sqlalchemy.orm import Session
from src.models.auth_models import User
from src.services.email_service import email_service


class PaymentService:
    """
    Stripe payment integration for subscription management

    Features:
    - Create checkout sessions
    - Manage subscriptions (create, cancel, upgrade)
    - Handle webhooks
    - Customer portal

    Usage:
    ```python
    payment_service = PaymentService()
    checkout_url = payment_service.create_checkout_session(
        user_id="...",
        price_id="price_xxx",
        success_url="https://...",
        cancel_url="https://..."
    )
    ```
    """

    # Subscription tiers
    TIERS = {
        'free': {
            'name': 'Бесплатный',
            'max_contracts_per_day': 1,
            'max_llm_requests_per_day': 5,
            'can_export_pdf': False,
            'can_use_disagreements': False,
            'can_use_changes_analyzer': False,
            'price_monthly': 0,
            'stripe_price_id': None
        },
        'basic': {
            'name': 'Базовый',
            'max_contracts_per_day': 5,
            'max_llm_requests_per_day': 50,
            'can_export_pdf': True,
            'can_use_disagreements': True,
            'can_use_changes_analyzer': False,
            'price_monthly': 1990,  # RUB
            'stripe_price_id': os.getenv('STRIPE_PRICE_BASIC', 'price_basic')
        },
        'professional': {
            'name': 'Профессиональный',
            'max_contracts_per_day': 20,
            'max_llm_requests_per_day': 200,
            'can_export_pdf': True,
            'can_use_disagreements': True,
            'can_use_changes_analyzer': True,
            'price_monthly': 4990,  # RUB
            'stripe_price_id': os.getenv('STRIPE_PRICE_PRO', 'price_professional')
        },
        'enterprise': {
            'name': 'Корпоративный',
            'max_contracts_per_day': 999999,
            'max_llm_requests_per_day': 999999,
            'can_export_pdf': True,
            'can_use_disagreements': True,
            'can_use_changes_analyzer': True,
            'price_monthly': 19990,  # RUB
            'stripe_price_id': os.getenv('STRIPE_PRICE_ENTERPRISE', 'price_enterprise')
        }
    }

    def __init__(self):
        """Initialize payment service"""
        if not STRIPE_AVAILABLE:
            logger.warning("Stripe library not installed. Payment features will be disabled.")
            return

        # Get Stripe API key from environment
        self.api_key = os.getenv('STRIPE_SECRET_KEY', '')
        self.publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')

        if self.api_key:
            stripe.api_key = self.api_key
            logger.info("Stripe payment service initialized")
        else:
            logger.warning("Stripe API key not configured. Set STRIPE_SECRET_KEY environment variable.")

    def create_customer(self, user: User) -> Optional[str]:
        """
        Create Stripe customer for user

        Returns:
            Customer ID or None if error
        """
        if not STRIPE_AVAILABLE or not self.api_key:
            return None

        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    'user_id': user.id,
                    'role': user.role
                }
            )

            logger.info(f"Stripe customer created: {customer.id} for user {user.id}")
            return customer.id

        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}", exc_info=True)
            return None

    def create_checkout_session(
        self,
        user: User,
        tier: str,
        success_url: str,
        cancel_url: str,
        db: Session
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Create Stripe checkout session for subscription

        Args:
            user: User object
            tier: Subscription tier (basic, professional, enterprise)
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            db: Database session

        Returns:
            (checkout_url, error)
        """
        if not STRIPE_AVAILABLE or not self.api_key:
            return None, "Stripe not configured"

        if tier not in self.TIERS or tier == 'free':
            return None, "Invalid subscription tier"

        tier_info = self.TIERS[tier]
        price_id = tier_info['stripe_price_id']

        if not price_id:
            return None, f"Price ID not configured for tier {tier}"

        try:
            # Create or get customer
            if not user.stripe_customer_id:
                customer_id = self.create_customer(user)
                if customer_id:
                    user.stripe_customer_id = customer_id
                    db.commit()
            else:
                customer_id = user.stripe_customer_id

            if not customer_id:
                return None, "Failed to create customer"

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                metadata={
                    'user_id': user.id,
                    'tier': tier
                },
                allow_promotion_codes=True,
                billing_address_collection='required',
                customer_update={
                    'address': 'auto',
                    'name': 'auto'
                }
            )

            logger.info(f"Checkout session created: {session.id} for user {user.id}, tier {tier}")
            return session.url, None

        except Exception as e:
            logger.error(f"Error creating checkout session: {e}", exc_info=True)
            return None, str(e)

    def create_customer_portal_session(
        self,
        user: User,
        return_url: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Create Stripe customer portal session for subscription management

        Allows users to:
        - View invoices
        - Update payment method
        - Cancel subscription
        - View subscription details

        Returns:
            (portal_url, error)
        """
        if not STRIPE_AVAILABLE or not self.api_key:
            return None, "Stripe not configured"

        if not user.stripe_customer_id:
            return None, "User has no Stripe customer ID"

        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url
            )

            logger.info(f"Customer portal session created for user {user.id}")
            return session.url, None

        except Exception as e:
            logger.error(f"Error creating portal session: {e}", exc_info=True)
            return None, str(e)

    def cancel_subscription(
        self,
        user: User,
        db: Session,
        immediately: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Cancel user subscription

        Args:
            user: User object
            db: Database session
            immediately: If True, cancel immediately. Otherwise, cancel at period end.

        Returns:
            (success, error)
        """
        if not STRIPE_AVAILABLE or not self.api_key:
            return False, "Stripe not configured"

        if not user.stripe_subscription_id:
            return False, "User has no active subscription"

        try:
            if immediately:
                stripe.Subscription.delete(user.stripe_subscription_id)
                logger.info(f"Subscription {user.stripe_subscription_id} cancelled immediately for user {user.id}")
            else:
                stripe.Subscription.modify(
                    user.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                logger.info(f"Subscription {user.stripe_subscription_id} will cancel at period end for user {user.id}")

            return True, None

        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}", exc_info=True)
            return False, str(e)

    def handle_webhook(
        self,
        payload: bytes,
        sig_header: str,
        db: Session
    ) -> tuple[bool, Optional[str]]:
        """
        Handle Stripe webhook events

        Important events:
        - checkout.session.completed: Subscription created
        - customer.subscription.updated: Subscription changed
        - customer.subscription.deleted: Subscription cancelled
        - invoice.payment_succeeded: Payment successful
        - invoice.payment_failed: Payment failed

        Args:
            payload: Request body bytes
            sig_header: Stripe signature header
            db: Database session

        Returns:
            (success, error)
        """
        if not STRIPE_AVAILABLE or not self.api_key:
            return False, "Stripe not configured"

        if not self.webhook_secret:
            logger.warning("Webhook secret not configured. Skipping signature verification.")
            # In development, you might want to skip verification
            # In production, this should always be set!

        try:
            # Verify webhook signature
            if self.webhook_secret:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, self.webhook_secret
                )
            else:
                # Unsafe: Skip verification in development
                import json
                event = json.loads(payload)

            event_type = event['type']
            data = event['data']['object']

            logger.info(f"Webhook received: {event_type}")

            # Handle different event types
            if event_type == 'checkout.session.completed':
                return self._handle_checkout_completed(data, db)

            elif event_type == 'customer.subscription.created':
                return self._handle_subscription_created(data, db)

            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(data, db)

            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(data, db)

            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(data, db)

            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(data, db)

            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return True, None

        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
            return False, str(e)

    def _handle_checkout_completed(self, session: Dict[str, Any], db: Session) -> tuple[bool, Optional[str]]:
        """Handle checkout.session.completed event"""
        try:
            user_id = session['metadata'].get('user_id')
            tier = session['metadata'].get('tier')
            customer_id = session['customer']
            subscription_id = session.get('subscription')

            if not user_id or not tier:
                return False, "Missing user_id or tier in metadata"

            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, f"User {user_id} not found"

            # Update user subscription
            tier_info = self.TIERS.get(tier)
            if not tier_info:
                return False, f"Invalid tier: {tier}"

            user.stripe_customer_id = customer_id
            user.stripe_subscription_id = subscription_id
            user.subscription_tier = tier
            user.subscription_status = 'active'
            user.subscription_expires = datetime.utcnow() + timedelta(days=30)  # Will be updated by subscription webhook

            # Update limits
            user.max_contracts_per_day = tier_info['max_contracts_per_day']
            user.max_llm_requests_per_day = tier_info['max_llm_requests_per_day']

            db.commit()

            logger.info(f"User {user_id} upgraded to {tier} (subscription {subscription_id})")

            # Send confirmation email
            email_service.send_email(
                to_email=user.email,
                subject=f"Подписка {tier_info['name']} активирована!",
                html_content=f"""
                <h1>Поздравляем!</h1>
                <p>Ваша подписка {tier_info['name']} успешно активирована.</p>
                <p>Вы получили доступ ко всем функциям вашего тарифного плана.</p>
                """
            )

            return True, None

        except Exception as e:
            logger.error(f"Error handling checkout completed: {e}", exc_info=True)
            return False, str(e)

    def _handle_subscription_created(self, subscription: Dict[str, Any], db: Session) -> tuple[bool, Optional[str]]:
        """Handle customer.subscription.created event"""
        # Usually handled by checkout.session.completed
        return True, None

    def _handle_subscription_updated(self, subscription: Dict[str, Any], db: Session) -> tuple[bool, Optional[str]]:
        """Handle customer.subscription.updated event"""
        try:
            subscription_id = subscription['id']
            status = subscription['status']
            current_period_end = datetime.fromtimestamp(subscription['current_period_end'])

            # Find user by subscription ID
            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if not user:
                logger.warning(f"User not found for subscription {subscription_id}")
                return True, None

            user.subscription_status = status
            user.subscription_expires = current_period_end

            # If subscription is cancelled or past_due, downgrade to free
            if status in ['canceled', 'unpaid', 'past_due']:
                user.subscription_tier = 'free'
                free_tier = self.TIERS['free']
                user.max_contracts_per_day = free_tier['max_contracts_per_day']
                user.max_llm_requests_per_day = free_tier['max_llm_requests_per_day']

            db.commit()

            logger.info(f"Subscription {subscription_id} updated to status: {status}")
            return True, None

        except Exception as e:
            logger.error(f"Error handling subscription updated: {e}", exc_info=True)
            return False, str(e)

    def _handle_subscription_deleted(self, subscription: Dict[str, Any], db: Session) -> tuple[bool, Optional[str]]:
        """Handle customer.subscription.deleted event"""
        try:
            subscription_id = subscription['id']

            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if not user:
                return True, None

            # Downgrade to free
            user.subscription_tier = 'free'
            user.subscription_status = 'cancelled'
            user.stripe_subscription_id = None

            free_tier = self.TIERS['free']
            user.max_contracts_per_day = free_tier['max_contracts_per_day']
            user.max_llm_requests_per_day = free_tier['max_llm_requests_per_day']

            db.commit()

            logger.info(f"User {user.id} subscription cancelled, downgraded to free")

            # Send notification email
            email_service.send_email(
                to_email=user.email,
                subject="Подписка отменена",
                html_content=f"""
                <h1>Подписка отменена</h1>
                <p>Ваша подписка была отменена.</p>
                <p>Вы были переведены на бесплатный тариф с ограничениями.</p>
                """
            )

            return True, None

        except Exception as e:
            logger.error(f"Error handling subscription deleted: {e}", exc_info=True)
            return False, str(e)

    def _handle_payment_succeeded(self, invoice: Dict[str, Any], db: Session) -> tuple[bool, Optional[str]]:
        """Handle invoice.payment_succeeded event"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return True, None

            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if not user:
                return True, None

            logger.info(f"Payment succeeded for user {user.id}, subscription {subscription_id}")

            # Send receipt email
            amount = invoice['amount_paid'] / 100  # Convert from cents
            email_service.send_email(
                to_email=user.email,
                subject="Оплата получена",
                html_content=f"""
                <h1>Спасибо за оплату!</h1>
                <p>Ваш платёж на сумму {amount} руб. успешно обработан.</p>
                <p>Ваша подписка продлена.</p>
                """
            )

            return True, None

        except Exception as e:
            logger.error(f"Error handling payment succeeded: {e}", exc_info=True)
            return False, str(e)

    def _handle_payment_failed(self, invoice: Dict[str, Any], db: Session) -> tuple[bool, Optional[str]]:
        """Handle invoice.payment_failed event"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return True, None

            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if not user:
                return True, None

            logger.warning(f"Payment failed for user {user.id}, subscription {subscription_id}")

            # Send notification email
            email_service.send_email(
                to_email=user.email,
                subject="Ошибка оплаты",
                html_content=f"""
                <h1>Ошибка оплаты</h1>
                <p>К сожалению, ваш платёж не прошёл.</p>
                <p>Пожалуйста, обновите платёжную информацию в настройках аккаунта.</p>
                <p>Если проблема не будет решена, ваша подписка может быть отменена.</p>
                """
            )

            return True, None

        except Exception as e:
            logger.error(f"Error handling payment failed: {e}", exc_info=True)
            return False, str(e)


# Singleton instance
payment_service = PaymentService()
