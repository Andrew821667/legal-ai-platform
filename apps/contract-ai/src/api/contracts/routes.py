# -*- coding: utf-8 -*-
"""
Contract Operations API Routes
Upload, analyze, generate, and export contracts
"""
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.services.auth_service import AuthService
from src.services.document_parser import DocumentParser
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.agents.contract_generator_agent import ContractGeneratorAgent
from src.agents.disagreement_processor_agent import DisagreementProcessorAgent
from src.agents.changes_analyzer_agent import ChangesAnalyzerAgent
from src.agents.quick_export_agent import QuickExportAgent
from src.services.llm_gateway import LLMGateway
from src.utils.file_validator import save_uploaded_file_securely, FileValidationError
from config.settings import settings


router = APIRouter()


# Dependency: Get current user from token
async def get_current_user(
    authorization: str = Depends(lambda request: request.headers.get("Authorization")),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")
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


# Pydantic schemas
class ContractUploadResponse(BaseModel):
    contract_id: str
    file_name: str
    file_size: int
    status: str
    message: str


class AnalysisResultRequest(BaseModel):
    contract_id: str
    check_counterparty: bool = True
    counterparty_tin: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    analysis_id: str
    contract_id: str
    status: str
    risks_count: int
    recommendations_count: int
    message: str


class ContractGenerateRequest(BaseModel):
    contract_type: str = Field(..., description="Type of contract (supply, service, lease, etc.)")
    template_id: Optional[str] = None
    params: Dict[str, Any] = Field(..., description="Contract parameters")


class ContractGenerateResponse(BaseModel):
    contract_id: str
    file_path: str
    status: str
    message: str


class DisagreementGenerateRequest(BaseModel):
    contract_id: str
    analysis_id: str
    auto_prioritize: bool = True


class ExportRequest(BaseModel):
    contract_id: str
    export_format: str = Field(..., description="Format: docx, pdf, txt, json, xml, all")
    include_analysis: bool = False


class ContractListResponse(BaseModel):
    contracts: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


# ==================== CONTRACT UPLOAD ====================

@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    document_type: str = Form("contract"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a contract file for analysis

    **Supported formats:** DOCX, PDF, XML, TXT
    **Max size:** 10 MB

    **Returns:** Contract ID and status
    """
    try:
        # Read file data
        file_data = await file.read()

        # Validate and save file securely
        try:
            file_path, safe_filename, file_size = save_uploaded_file_securely(
                file_data=file_data,
                filename=file.filename,
                upload_dir="data/contracts"
            )
        except FileValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {str(e)}"
            )

        # Create contract record in database
        contract = Contract(
            file_name=safe_filename,
            file_path=file_path,
            document_type=document_type,
            contract_type='unknown',  # Will be determined during analysis
            status='uploaded',
            assigned_to=current_user.id,
            meta_info={}
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        logger.info(f"Contract uploaded: {contract.id} by user {current_user.id}")

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='uploaded',
            message='Contract uploaded successfully'
        )

    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading contract: {str(e)}"
        )


# ==================== CONTRACT ANALYSIS ====================

async def analyze_contract_background(
    contract_id: str,
    user_id: str,
    check_counterparty: bool,
    counterparty_tin: Optional[str],
    db: Session
):
    """Background task for contract analysis"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.error(f"Contract {contract_id} not found for background analysis")
            return

        # Update status
        contract.status = 'analyzing'
        db.commit()

        # Parse document
        parser = DocumentParser()
        parsed_xml = parser.parse(contract.file_path)

        if not parsed_xml:
            contract.status = 'error'
            db.commit()
            logger.error(f"Failed to parse contract {contract_id}")
            return

        # Store XML in contract
        contract.meta_info = {'xml': parsed_xml}
        db.commit()

        # Analyze with agent
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': contract_id,
            'parsed_xml': parsed_xml,
            'check_counterparty': check_counterparty,
            'metadata': {
                'counterparty_tin': counterparty_tin,
                'uploaded_by': user_id
            }
        })

        if result.success:
            contract.status = 'completed'
            logger.info(f"Contract {contract_id} analyzed successfully")
        else:
            contract.status = 'error'
            logger.error(f"Contract {contract_id} analysis failed: {result.error}")

        db.commit()

    except Exception as e:
        logger.error(f"Background analysis error for contract {contract_id}: {e}", exc_info=True)
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.status = 'error'
            db.commit()


@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_contract(
    request_data: AnalysisResultRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze an uploaded contract

    **Process:**
    1. Parse document to XML
    2. Extract contract structure
    3. Analyze each clause for risks
    4. Check legal compliance
    5. Generate recommendations
    6. (Optional) Check counterparty via ФНС API

    **Returns:** Analysis ID and initial status
    **Note:** Analysis runs in background. Use WebSocket or polling to get results.
    """
    try:
        # Get contract
        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to analyze this contract"
            )

        # Create analysis record
        analysis_id = str(uuid.uuid4())

        # Start background task
        background_tasks.add_task(
            analyze_contract_background,
            contract_id=request_data.contract_id,
            user_id=current_user.id,
            check_counterparty=request_data.check_counterparty,
            counterparty_tin=request_data.counterparty_tin,
            db=db
        )

        logger.info(f"Analysis started for contract {request_data.contract_id} by user {current_user.id}")

        return AnalysisResultResponse(
            analysis_id=analysis_id,
            contract_id=request_data.contract_id,
            status='analyzing',
            risks_count=0,
            recommendations_count=0,
            message='Analysis started. Use WebSocket /ws/analysis/{contract_id} to track progress.'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting analysis: {str(e)}"
        )


# ==================== CONTRACT GENERATION ====================

@router.post("/generate", response_model=ContractGenerateResponse)
async def generate_contract(
    request_data: ContractGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a new contract from template

    **Contract types:**
    - supply: Договор поставки
    - service: Договор услуг
    - lease: Договор аренды
    - purchase: Договор купли-продажи
    - confidentiality: Соглашение о конфиденциальности

    **Returns:** Generated contract ID and file path
    """
    try:
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractGeneratorAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'template_id': request_data.template_id or f"tpl_{request_data.contract_type}_001",
            'contract_type': request_data.contract_type,
            'params': request_data.params,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Contract generated: {result.data.get('contract_id')} by user {current_user.id}")
            return ContractGenerateResponse(
                contract_id=result.data.get('contract_id'),
                file_path=result.data.get('file_path'),
                status='generated',
                message='Contract generated successfully'
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Contract generation failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating contract: {str(e)}"
        )


# ==================== DISAGREEMENTS ====================

@router.post("/disagreements")
async def generate_disagreements(
    request_data: DisagreementGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate disagreement document with legal justifications

    **Process:**
    1. Retrieve contract analysis results
    2. Prioritize risks by severity
    3. Generate legal objections for each risk
    4. Format for ЭДО (electronic document management)

    **Returns:** Disagreement document ID and objections list
    """
    try:
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = DisagreementProcessorAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': request_data.contract_id,
            'analysis_id': request_data.analysis_id,
            'auto_prioritize': request_data.auto_prioritize,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Disagreements generated for contract {request_data.contract_id}")
            return result.data
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Disagreement generation failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating disagreements: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== EXPORT ====================

@router.post("/export")
async def export_contract(
    request_data: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export contract to various formats

    **Formats:**
    - docx: Microsoft Word
    - pdf: PDF document
    - txt: Plain text
    - json: JSON data
    - xml: XML format
    - all: All formats

    **Returns:** Download links for requested formats
    """
    try:
        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = QuickExportAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': request_data.contract_id,
            'export_format': request_data.export_format,
            'include_analysis': request_data.include_analysis,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Contract exported: {request_data.contract_id} to {request_data.export_format}")
            return result.data
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== CONTRACT LISTING ====================

@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List contracts for current user

    **Filters:**
    - status: uploaded, analyzing, completed, error
    - contract_type: supply, service, lease, etc.

    **Returns:** Paginated list of contracts
    """
    try:
        query = db.query(Contract)

        # Filter by user (non-admins can only see their own contracts)
        if current_user.role not in ['admin', 'manager']:
            query = query.filter(Contract.assigned_to == current_user.id)

        # Apply filters
        if status:
            query = query.filter(Contract.status == status)
        if contract_type:
            query = query.filter(Contract.contract_type == contract_type)

        # Get total count
        total = query.count()

        # Paginate
        contracts = query.order_by(Contract.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # Format response
        contracts_data = []
        for contract in contracts:
            contracts_data.append({
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None
            })

        return ContractListResponse(
            contracts=contracts_data,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error listing contracts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== CONTRACT DETAILS ====================

@router.get("/{contract_id}")
async def get_contract_details(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get contract details including analysis results"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this contract"
            )

        # Get analysis results if available
        analysis = db.query(AnalysisResult).filter(AnalysisResult.contract_id == contract_id).first()

        return {
            'contract': {
                'id': contract.id,
                'file_name': contract.file_name,
                'file_path': contract.file_path,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            },
            'analysis': {
                'id': analysis.id if analysis else None,
                'risks': analysis.risks if analysis else [],
                'recommendations': analysis.recommendations if analysis else [],
                'status': analysis.status if analysis else None
            } if analysis else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ==================== DOWNLOAD ====================

@router.get("/{contract_id}/download")
async def download_contract(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download original contract file"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin', 'manager']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to download this contract"
            )

        if not os.path.exists(contract.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract file not found on disk"
            )

        return FileResponse(
            path=contract.file_path,
            filename=contract.file_name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )
