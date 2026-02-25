# -*- coding: utf-8 -*-
"""
Payment API Routes
Stripe integration for subscriptions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from loguru import logger

from src.models.database import get_db
from src.models.auth_models import User
from src.services.auth_service import AuthService
from src.services.payment_service import payment_service


router = APIRouter()


# Dependency: Get current user
async def get_current_user(
    authorization: str = Depends(lambda request: request.headers.get("Authorization")),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)
    user, error = auth_service.verify_access_token(token, db)

    if error or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid token"
        )

    return user


# Schemas
class CheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: Optional[str] = None


class PortalRequest(BaseModel):
    return_url: str


class PortalResponse(BaseModel):
    portal_url: str


class CancelSubscriptionRequest(BaseModel):
    immediately: bool = False


# ==================== PRICING ====================

@router.get("/pricing")
async def get_pricing():
    """
    Get available subscription tiers and pricing

    **Returns:** List of subscription tiers with features and pricing
    """
    tiers = []
    for tier_key, tier_data in payment_service.TIERS.items():
        tiers.append({
            'tier': tier_key,
            'name': tier_data['name'],
            'price_monthly': tier_data['price_monthly'],
            'features': {
                'max_contracts_per_day': tier_data['max_contracts_per_day'],
                'max_llm_requests_per_day': tier_data['max_llm_requests_per_day'],
                'can_export_pdf': tier_data['can_export_pdf'],
                'can_use_disagreements': tier_data['can_use_disagreements'],
                'can_use_changes_analyzer': tier_data['can_use_changes_analyzer']
            }
        })

    return {'tiers': tiers}


# ==================== CHECKOUT ====================

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request_data: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe checkout session for subscription

    **Tiers:**
    - basic: 1,990 руб/месяц
    - professional: 4,990 руб/месяц
    - enterprise: 19,990 руб/месяц

    **Returns:** Checkout URL to redirect user to Stripe payment page
    """
    try:
        # Check if user already has this tier
        if current_user.subscription_tier == request_data.tier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have this subscription tier"
            )

        # Create checkout session
        checkout_url, error = payment_service.create_checkout_session(
            user=current_user,
            tier=request_data.tier,
            success_url=request_data.success_url,
            cancel_url=request_data.cancel_url,
            db=db
        )

        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create checkout session: {error}"
            )

        logger.info(f"Checkout session created for user {current_user.id}, tier {request_data.tier}")

        return CheckoutResponse(checkout_url=checkout_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== CUSTOMER PORTAL ====================

@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    request_data: PortalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe customer portal session

    **Features:**
    - View and download invoices
    - Update payment method
    - Cancel subscription
    - View subscription details

    **Returns:** Portal URL to redirect user to Stripe customer portal
    """
    try:
        if not current_user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Stripe customer associated with this account"
            )

        portal_url, error = payment_service.create_customer_portal_session(
            user=current_user,
            return_url=request_data.return_url
        )

        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create portal session: {error}"
            )

        logger.info(f"Customer portal session created for user {current_user.id}")

        return PortalResponse(portal_url=portal_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== SUBSCRIPTION STATUS ====================

@router.get("/subscription")
async def get_subscription_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's subscription status

    **Returns:** Subscription details, limits, and usage
    """
    return {
        'tier': current_user.subscription_tier,
        'status': current_user.subscription_status,
        'expires_at': current_user.subscription_expires.isoformat() if current_user.subscription_expires else None,
        'limits': {
            'max_contracts_per_day': current_user.max_contracts_per_day,
            'max_llm_requests_per_day': current_user.max_llm_requests_per_day,
            'contracts_today': current_user.contracts_today,
            'llm_requests_today': current_user.llm_requests_today
        },
        'features': {
            'can_export_pdf': current_user.subscription_tier in ['basic', 'professional', 'enterprise'],
            'can_use_disagreements': current_user.subscription_tier in ['basic', 'professional', 'enterprise'],
            'can_use_changes_analyzer': current_user.subscription_tier in ['professional', 'enterprise']
        },
        'stripe': {
            'has_customer': bool(current_user.stripe_customer_id),
            'has_subscription': bool(current_user.stripe_subscription_id)
        }
    }


# ==================== CANCEL SUBSCRIPTION ====================

@router.post("/subscription/cancel")
async def cancel_subscription(
    request_data: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel user subscription

    **Modes:**
    - immediately=false: Cancel at end of billing period (default)
    - immediately=true: Cancel immediately and lose access

    **Returns:** Success message
    """
    try:
        success, error = payment_service.cancel_subscription(
            user=current_user,
            db=db,
            immediately=request_data.immediately
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel subscription: {error}"
            )

        logger.info(f"Subscription cancelled for user {current_user.id} (immediately={request_data.immediately})")

        return {
            'success': True,
            'message': 'Subscription cancelled successfully' if request_data.immediately else 'Subscription will cancel at end of billing period'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== WEBHOOKS ====================

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db)
):
    """
    Stripe webhook endpoint

    **Important:** Configure this URL in Stripe Dashboard:
    https://your-domain.com/api/v1/payments/webhooks/stripe

    **Events handled:**
    - checkout.session.completed
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed

    **Returns:** 200 OK if webhook processed successfully
    """
    try:
        # Get raw body
        payload = await request.body()

        if not stripe_signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header"
            )

        # Handle webhook
        success, error = payment_service.handle_webhook(
            payload=payload,
            sig_header=stripe_signature,
            db=db
        )

        if not success:
            logger.error(f"Webhook processing failed: {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Webhook error: {error}"
            )

        return {'received': True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error: {str(e)}"
        )
