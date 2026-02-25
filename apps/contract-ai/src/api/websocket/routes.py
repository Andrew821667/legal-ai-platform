# -*- coding: utf-8 -*-
"""
WebSocket Routes for Real-Time Updates
Contract analysis progress, notifications, live updates
"""
import json
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.services.auth_service import AuthService


router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        # Maps: contract_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, contract_id: str):
        """Connect client to contract updates"""
        await websocket.accept()
        if contract_id not in self.active_connections:
            self.active_connections[contract_id] = set()
        self.active_connections[contract_id].add(websocket)
        logger.info(f"WebSocket connected for contract {contract_id}. Total: {len(self.active_connections[contract_id])}")

    def disconnect(self, websocket: WebSocket, contract_id: str):
        """Disconnect client"""
        if contract_id in self.active_connections:
            self.active_connections[contract_id].discard(websocket)
            if not self.active_connections[contract_id]:
                del self.active_connections[contract_id]
            logger.info(f"WebSocket disconnected for contract {contract_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast_to_contract(self, message: dict, contract_id: str):
        """Broadcast message to all clients watching this contract"""
        if contract_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[contract_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to contract {contract_id}: {e}")
                    disconnected.add(connection)

            # Remove disconnected clients
            for conn in disconnected:
                self.active_connections[contract_id].discard(conn)


manager = ConnectionManager()


@router.websocket("/analysis/{contract_id}")
async def websocket_analysis_updates(
    websocket: WebSocket,
    contract_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time contract analysis updates

    **Usage:**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/ws/analysis/CONTRACT_ID?token=ACCESS_TOKEN');

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data.progress);
        console.log('Status:', data.status);
        console.log('Message:', data.message);
    };
    ```

    **Message format:**
    ```json
    {
        "type": "progress",
        "contract_id": "...",
        "status": "analyzing",
        "progress": 45,
        "message": "Analyzing clause 5/10...",
        "data": {...}
    }
    ```

    **Status values:**
    - uploaded: Contract uploaded, waiting for analysis
    - analyzing: Analysis in progress
    - completed: Analysis finished successfully
    - error: Analysis failed

    **Message types:**
    - progress: Progress update (0-100%)
    - status_change: Status changed
    - clause_analyzed: Individual clause analysis complete
    - risk_found: New risk detected
    - analysis_complete: Full analysis finished
    - error: Error occurred
    """
    # Verify token
    auth_service = AuthService(db)
    user, error = auth_service.verify_access_token(token, db)
    if error or not user:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return

    # Check contract exists and user has access
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        await websocket.close(code=1008, reason="Contract not found")
        return

    if contract.assigned_to != user.id and user.role not in ['admin', 'manager']:
        await websocket.close(code=1008, reason="Permission denied")
        return

    # Connect client
    await manager.connect(websocket, contract_id)

    try:
        # Send initial status
        await manager.send_personal_message({
            "type": "connected",
            "contract_id": contract_id,
            "status": contract.status,
            "message": "Connected to analysis updates"
        }, websocket)

        # Keep connection alive and send updates
        while True:
            # Poll database for updates every 2 seconds
            await asyncio.sleep(2)

            # Refresh contract status
            db.refresh(contract)

            # Get analysis if available
            analysis = db.query(AnalysisResult).filter(
                AnalysisResult.contract_id == contract_id
            ).first()

            # Calculate progress based on status
            progress_map = {
                'uploaded': 0,
                'parsing': 10,
                'analyzing': 50,
                'completed': 100,
                'error': 0
            }
            progress = progress_map.get(contract.status, 0)

            # Send status update
            update_message = {
                "type": "progress",
                "contract_id": contract_id,
                "status": contract.status,
                "progress": progress,
                "message": f"Status: {contract.status}",
                "data": {
                    "risks_count": len(analysis.risks) if analysis and hasattr(analysis, 'risks') else 0,
                    "recommendations_count": len(analysis.recommendations) if analysis and hasattr(analysis, 'recommendations') else 0
                }
            }

            await manager.send_personal_message(update_message, websocket)

            # If analysis is complete or failed, send final message
            if contract.status in ['completed', 'error']:
                final_message = {
                    "type": "analysis_complete" if contract.status == 'completed' else "error",
                    "contract_id": contract_id,
                    "status": contract.status,
                    "progress": 100 if contract.status == 'completed' else 0,
                    "message": "Analysis completed successfully" if contract.status == 'completed' else "Analysis failed",
                    "data": {
                        "analysis_id": analysis.id if analysis else None,
                        "risks_count": len(analysis.risks) if analysis and hasattr(analysis, 'risks') else 0,
                        "recommendations_count": len(analysis.recommendations) if analysis and hasattr(analysis, 'recommendations') else 0
                    } if contract.status == 'completed' else {}
                }
                await manager.send_personal_message(final_message, websocket)
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket, contract_id)
        logger.info(f"Client disconnected from contract {contract_id} analysis updates")
    except Exception as e:
        logger.error(f"WebSocket error for contract {contract_id}: {e}", exc_info=True)
        manager.disconnect(websocket, contract_id)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for user notifications

    **Usage:**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/ws/notifications?token=ACCESS_TOKEN');

    ws.onmessage = (event) => {
        const notification = JSON.parse(event.data);
        showNotification(notification.title, notification.message);
    };
    ```

    **Notification types:**
    - analysis_complete: Contract analysis finished
    - contract_uploaded: New contract uploaded
    - export_ready: Export file ready for download
    - subscription_expiring: Subscription expiring soon
    - limit_reached: Daily limit reached
    """
    # Verify token
    auth_service = AuthService(db)
    user, error = auth_service.verify_access_token(token, db)
    if error or not user:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return

    await websocket.accept()
    logger.info(f"User {user.id} connected to notifications")

    try:
        # Send welcome notification
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to notification service",
            "user_id": user.id
        })

        # Keep connection alive
        while True:
            # Check for new notifications every 5 seconds
            await asyncio.sleep(5)

            # Refresh user data
            db.refresh(user)

            # Check demo expiration
            if user.is_demo and user.demo_expires:
                from datetime import datetime, timedelta
                time_left = user.demo_expires - datetime.utcnow()
                if timedelta(0) < time_left < timedelta(hours=1):
                    await websocket.send_json({
                        "type": "demo_expiring",
                        "title": "Демо-доступ истекает",
                        "message": f"Ваш демо-доступ истекает через {int(time_left.total_seconds() / 60)} минут",
                        "severity": "warning"
                    })

            # Check daily limits
            if user.contracts_today >= user.max_contracts_per_day:
                await websocket.send_json({
                    "type": "limit_reached",
                    "title": "Лимит достигнут",
                    "message": "Вы достигли дневного лимита контрактов",
                    "severity": "warning"
                })

    except WebSocketDisconnect:
        logger.info(f"User {user.id} disconnected from notifications")
    except Exception as e:
        logger.error(f"WebSocket error for user {user.id}: {e}", exc_info=True)


# Helper function to broadcast updates (can be called from agents)
async def broadcast_analysis_update(contract_id: str, message: dict):
    """
    Broadcast analysis update to all connected clients for this contract

    Usage from agents:
    ```python
    from src.api.websocket.routes import broadcast_analysis_update
    await broadcast_analysis_update(contract_id, {
        "type": "progress",
        "progress": 30,
        "message": "Analyzing clause 3/10..."
    })
    ```
    """
    await manager.broadcast_to_contract(message, contract_id)
