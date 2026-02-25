"""
Authentication API Routes

Provides REST API endpoints for:
- User registration and login
- Demo token generation and activation
- Admin user management
- Session management
- Analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from src.models import get_db, User
from src.services.auth_service import AuthService


# ==================== Pydantic Models ====================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    role: Optional[str] = "junior_lawyer"
    subscription_tier: Optional[str] = "demo"


class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class DemoTokenGenerateRequest(BaseModel):
    """Demo token generation request"""
    max_contracts: int = Field(default=3, ge=1, le=10)
    max_llm_requests: int = Field(default=10, ge=1, le=100)
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    campaign: Optional[str] = None
    source: str = "admin_panel"


class DemoActivateRequest(BaseModel):
    """Demo token activation request"""
    token: str
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class CreateUserRequest(BaseModel):
    """Admin: Create user request"""
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(..., pattern="^(admin|senior_lawyer|lawyer|junior_lawyer|demo)$")
    subscription_tier: str = Field(default="demo", pattern="^(demo|basic|pro|enterprise)$")


class UpdateRoleRequest(BaseModel):
    """Admin: Update role request"""
    role: str = Field(..., pattern="^(admin|senior_lawyer|lawyer|junior_lawyer|demo)$")
    subscription_tier: Optional[str] = Field(None, pattern="^(demo|basic|pro|enterprise)$")


# ==================== OAuth2 Setup ====================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ==================== Dependencies ====================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token

    Raises:
        HTTPException 401: Invalid or expired token
    """
    auth_service = AuthService(db)

    # Verify token
    payload = auth_service.verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Require admin role

    Raises:
        HTTPException 403: User is not admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# ==================== Router Setup ====================

router = APIRouter(tags=["authentication"])


# ==================== Public Endpoints ====================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request_data: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register new user

    Creates a new user account with DEMO role by default.
    Sends email verification link (if email service configured).

    **Flow:**
    1. Validates email uniqueness
    2. Hashes password (bcrypt)
    3. Creates user with specified role
    4. Sends verification email
    5. Returns JWT tokens

    **Rate Limit:** 5 requests per minute per IP

    **Example:**
    ```json
    {
        "email": "user@example.com",
        "name": "John Doe",
        "password": "SecurePass123"
    }
    ```

    **Returns:**
    ```json
    {
        "user_id": "uuid",
        "email": "user@example.com",
        "access_token": "jwt_token",
        "message": "Registration successful. Please verify your email."
    }
    ```
    """
    auth_service = AuthService(db)

    user, error = auth_service.register_user(
        email=request_data.email,
        name=request_data.name,
        password=request_data.password,
        role=request_data.role,
        subscription_tier=request_data.subscription_tier
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Create initial access token
    access_token = auth_service.create_access_token(user.id)

    # Log registration from IP
    ip_address = get_client_ip(request)
    auth_service.log_action(
        user_id=user.id,
        action="registration_completed",
        status="success",
        ip_address=ip_address
    )
    db.commit()

    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "access_token": access_token,
        "message": "Registration successful. Please verify your email."
    }


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Login user with email and password

    **Flow:**
    1. Validates credentials
    2. Checks account status (not locked, email verified)
    3. Creates JWT session
    4. Returns access & refresh tokens

    **Security:**
    - Passwords hashed with bcrypt
    - Account locked after 5 failed attempts (30 min)
    - All attempts logged

    **Rate Limit:** 10 requests per minute per IP

    **Example:**
    ```
    POST /api/v1/auth/login
    Content-Type: application/x-www-form-urlencoded

    username=user@example.com&password=SecurePass123
    ```

    **Returns:**
    ```json
    {
        "user": {
            "id": "uuid",
            "email": "user@example.com",
            "name": "John Doe",
            "role": "lawyer"
        },
        "access_token": "jwt_access_token",
        "refresh_token": "jwt_refresh_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
    ```
    """
    auth_service = AuthService(db)

    ip_address = get_client_ip(request) if request else None
    user_agent = request.headers.get("User-Agent") if request else None

    login_data, error = auth_service.login_user(
        email=form_data.username,
        password=form_data.password,
        ip_address=ip_address,
        user_agent=user_agent
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return login_data


@router.post("/demo-activate")
async def activate_demo(
    request_data: DemoActivateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Activate demo access using token from link

    **Flow:**
    1. User clicks demo link (e.g., from website)
    2. Enters email and name
    3. System creates DEMO account automatically
    4. User gets instant access (no password required for demo period)

    **Example Link:**
    ```
    https://contract-ai.example.com/demo?token=abc123xyz
    ```

    **Request:**
    ```json
    {
        "token": "abc123xyz",
        "email": "demo@example.com",
        "name": "Demo User"
    }
    ```

    **Returns:**
    ```json
    {
        "user": {
            "id": "uuid",
            "email": "demo@example.com",
            "name": "Demo User",
            "role": "demo",
            "is_demo": true,
            "demo_expires": "2025-01-16T10:00:00"
        },
        "access_token": "jwt_token",
        "refresh_token": "jwt_refresh_token",
        "expires_at": "2025-01-16T10:00:00"
    }
    ```
    """
    auth_service = AuthService(db)

    ip_address = get_client_ip(request)

    activation_data, error = auth_service.activate_demo_token(
        token=request_data.token,
        email=request_data.email,
        name=request_data.name,
        ip_address=ip_address
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    return activation_data


@router.post("/refresh")
async def refresh_token(
    request_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token

    **Flow:**
    1. Client sends refresh token
    2. Server validates refresh token
    3. Issues new access + refresh tokens
    4. Old tokens are revoked

    **Use When:**
    - Access token expired (401 error)
    - Before expiration (proactive refresh)

    **Example:**
    ```json
    {
        "refresh_token": "old_refresh_token"
    }
    ```

    **Returns:**
    ```json
    {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
    ```
    """
    auth_service = AuthService(db)

    new_tokens, error = auth_service.refresh_session(request_data.refresh_token)

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error
        )

    return new_tokens


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Logout user (revoke session)

    **Flow:**
    1. Extracts access token from Authorization header
    2. Revokes session in database
    3. Logs logout action

    **Headers:**
    ```
    Authorization: Bearer {access_token}
    ```

    **Returns:**
    ```json
    {
        "message": "Logged out successfully"
    }
    ```
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization header"
        )

    access_token = authorization.replace("Bearer ", "")

    auth_service = AuthService(db)
    success = auth_service.logout_user(access_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed"
        )

    return {"message": "Logged out successfully"}


# ==================== Protected Endpoints ====================

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information

    **Requires:** Valid JWT access token

    **Headers:**
    ```
    Authorization: Bearer {access_token}
    ```

    **Returns:**
    ```json
    {
        "id": "uuid",
        "email": "user@example.com",
        "name": "John Doe",
        "role": "lawyer",
        "subscription_tier": "pro",
        "is_demo": false,
        "email_verified": true,
        "created_at": "2025-01-01T00:00:00",
        "last_login": "2025-01-15T10:00:00",
        "contracts_today": 5,
        "llm_requests_today": 25
    }
    ```
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "subscription_tier": current_user.subscription_tier,
        "is_demo": current_user.is_demo,
        "email_verified": current_user.email_verified,
        "two_factor_enabled": current_user.two_factor_enabled,
        "active": current_user.active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "login_count": current_user.login_count,
        "contracts_today": current_user.contracts_today,
        "llm_requests_today": current_user.llm_requests_today,
        "demo_expires": current_user.demo_expires.isoformat() if current_user.demo_expires else None
    }


# ==================== Admin Endpoints ====================

@router.post("/admin/demo-link", dependencies=[Depends(require_admin)])
async def generate_demo_link(
    request_data: DemoTokenGenerateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Generate demo access link (Admin only)

    **Requires:** Admin role

    **Flow:**
    1. Admin creates demo token with parameters
    2. System generates unique link
    3. Link can be shared on website/marketing materials
    4. Anyone with link can activate demo access

    **Example:**
    ```json
    {
        "max_contracts": 3,
        "max_llm_requests": 10,
        "expires_in_hours": 24,
        "campaign": "website_header_cta"
    }
    ```

    **Returns:**
    ```json
    {
        "token": "abc123xyz...",
        "url": "https://contract-ai.example.com/demo?token=abc123xyz",
        "expires_at": "2025-01-16T10:00:00",
        "max_contracts": 3,
        "max_llm_requests": 10
    }
    ```
    """
    auth_service = AuthService(db)

    demo_token = auth_service.generate_demo_token(
        created_by_user_id=current_user.id,
        max_contracts=request_data.max_contracts,
        max_llm_requests=request_data.max_llm_requests,
        expires_in_hours=request_data.expires_in_hours,
        campaign=request_data.campaign,
        source=request_data.source
    )

    # Generate URL (you can customize domain here)
    demo_url = f"https://contract-ai.example.com/demo?token={demo_token.token}"

    return {
        "token": demo_token.token,
        "url": demo_url,
        "expires_at": demo_token.expires_at.isoformat(),
        "max_contracts": demo_token.max_contracts,
        "max_llm_requests": demo_token.max_llm_requests,
        "created_by": current_user.email
    }


@router.post("/admin/users", dependencies=[Depends(require_admin)])
async def create_user_as_admin(
    request_data: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create user as admin

    **Requires:** Admin role

    **Flow:**
    1. Admin creates user with specified role
    2. System generates temporary password
    3. Invitation email sent to user
    4. User must change password on first login

    **Example:**
    ```json
    {
        "email": "newuser@example.com",
        "name": "New User",
        "role": "lawyer",
        "subscription_tier": "pro"
    }
    ```

    **Returns:**
    ```json
    {
        "user_id": "uuid",
        "email": "newuser@example.com",
        "temp_password": "TempPass123xyz",
        "message": "User created. Invitation email sent."
    }
    ```
    """
    auth_service = AuthService(db)

    user, temp_password, error = auth_service.create_user_as_admin(
        email=request_data.email,
        name=request_data.name,
        role=request_data.role,
        subscription_tier=request_data.subscription_tier,
        admin_user_id=current_user.id
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Send invitation email with temp_password
    email_sent = False
    try:
        from config.settings import settings
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        if settings.smtp_user and settings.smtp_password:
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{settings.smtp_from_name} <{settings.smtp_from_email or settings.smtp_user}>"
            msg['To'] = user.email
            msg['Subject'] = "Приглашение в Contract AI System"

            # Email body (HTML)
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #3B82F6;">Добро пожаловать в Contract AI System!</h2>

                    <p>Здравствуйте, {user.name}!</p>

                    <p>Для вас создан аккаунт в системе автоматизации работы с договорами.</p>

                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p><strong>Email:</strong> {user.email}</p>
                        <p><strong>Временный пароль:</strong> <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px;">{temp_password}</code></p>
                        <p><strong>Роль:</strong> {user.role}</p>
                    </div>

                    <p>⚠️ <strong>Важно:</strong> Пожалуйста, измените временный пароль после первого входа в систему.</p>

                    <p style="margin-top: 30px;">
                        <a href="{settings.app_url if hasattr(settings, 'app_url') else 'http://localhost:8501'}"
                           style="background: #3B82F6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            Войти в систему
                        </a>
                    </p>

                    <p style="margin-top: 30px; font-size: 12px; color: #666;">
                        С уважением,<br>
                        Команда Contract AI System
                    </p>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, 'html', 'utf-8'))

            # Send email
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
            server.quit()

            email_sent = True
            logger.info(f"Invitation email sent to {user.email}")

    except Exception as e:
        logger.warning(f"Failed to send invitation email: {e}")
        # Don't fail the request if email sending fails

    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "temp_password": temp_password,
        "message": "User created successfully. Temporary password provided."
    }


@router.patch("/admin/users/{user_id}/role", dependencies=[Depends(require_admin)])
async def update_user_role(
    user_id: str,
    request_data: UpdateRoleRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update user role and subscription tier (Admin only)

    **Requires:** Admin role

    **Example:**
    ```json
    {
        "role": "senior_lawyer",
        "subscription_tier": "pro"
    }
    ```

    **Returns:**
    ```json
    {
        "message": "Role updated successfully",
        "user_id": "uuid",
        "new_role": "senior_lawyer",
        "new_tier": "pro"
    }
    ```
    """
    auth_service = AuthService(db)

    success, error = auth_service.update_user_role(
        user_id=user_id,
        new_role=request_data.role,
        admin_user_id=current_user.id,
        subscription_tier=request_data.subscription_tier
    )

    if error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return {
        "message": "Role updated successfully",
        "user_id": user_id,
        "new_role": request_data.role,
        "new_tier": request_data.subscription_tier
    }


@router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users(
    page: int = 1,
    limit: int = 50,
    role: Optional[str] = None,
    search: Optional[str] = None,
    is_demo: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users with filtering and pagination (Admin only)

    **Requires:** Admin role

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 50, max: 100)
    - `role`: Filter by role (admin, senior_lawyer, lawyer, junior_lawyer, demo)
    - `search`: Search in email or name
    - `is_demo`: Filter demo users (true/false)

    **Example:**
    ```
    GET /api/v1/auth/admin/users?page=1&limit=20&role=lawyer&search=john
    ```

    **Returns:**
    ```json
    {
        "total": 150,
        "page": 1,
        "limit": 20,
        "pages": 8,
        "users": [
            {
                "id": "uuid",
                "email": "user@example.com",
                "name": "John Doe",
                "role": "lawyer",
                "subscription_tier": "pro",
                "active": true,
                "is_demo": false,
                "created_at": "2025-01-01T00:00:00",
                "last_login": "2025-01-15T10:00:00"
            }
        ]
    }
    ```
    """
    if limit > 100:
        limit = 100

    auth_service = AuthService(db)

    result = auth_service.list_users(
        page=page,
        limit=limit,
        role=role,
        search=search,
        is_demo=is_demo
    )

    return result


@router.get("/admin/analytics", dependencies=[Depends(require_admin)])
async def get_analytics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get system analytics (Admin only)

    **Requires:** Admin role

    **Returns:**
    ```json
    {
        "total_users": 250,
        "active_users": 180,
        "demo_users": 50,
        "users_by_role": {
            "admin": 5,
            "senior_lawyer": 20,
            "lawyer": 100,
            "junior_lawyer": 75,
            "demo": 50
        },
        "active_last_week": 120,
        "demo_converted": 30,
        "conversion_rate": 60.0
    }
    ```
    """
    auth_service = AuthService(db)
    analytics = auth_service.get_analytics()

    return analytics
