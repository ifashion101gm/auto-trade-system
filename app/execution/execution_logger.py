"""Execution logging service for detailed audit trail."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import ExecutionLogs
from datetime import datetime
import json
import uuid


class ExecutionLogger:
    """Logs all execution attempts and API responses."""
    
    async def log_execution(
        self,
        action: str,
        exchange: str,
        symbol: str,
        trade_id: str = None,
        order_id: str = None,
        request_payload: dict = None,
        response_payload: dict = None,
        status: str = "SUCCESS",
        error_message: str = None,
        latency_ms: float = None,
        retry_count: int = 0,
        db_session: AsyncSession = None
    ):
        """Log execution attempt."""
        if not db_session:
            return
        
        log_entry = ExecutionLogs(
            id=str(uuid.uuid4()),
            trade_id=trade_id,
            order_id=order_id,
            action=action,
            exchange=exchange,
            symbol=symbol,
            request_payload=json.dumps(request_payload) if request_payload else None,
            response_payload=json.dumps(response_payload) if response_payload else None,
            status=status,
            error_message=error_message,
            latency_ms=latency_ms,
            retry_count=retry_count
        )
        
        db_session.add(log_entry)
        await db_session.commit()
