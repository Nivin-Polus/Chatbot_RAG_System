from contextvars import ContextVar
import logging

logger = logging.getLogger(__name__)

# Context variable to track if we are inside a request
IN_REQUEST_CONTEXT: ContextVar[bool] = ContextVar("IN_REQUEST_CONTEXT", default=False)

def enter_request_context():
    """Mark the beginning of a request."""
    IN_REQUEST_CONTEXT.set(True)

def exit_request_context():
    """Mark the end of a request."""
    IN_REQUEST_CONTEXT.set(False)

def ensure_safe_qdrant_operation(operation_name: str = "scroll"):
    """
    Raises RuntimeError if a dangerous Qdrant operation is attempted during a request.
    This protects against stability issues caused by heavy operations in hot paths.
    """
    if IN_REQUEST_CONTEXT.get():
        error_msg = (
            f"Dangerous Qdrant operation '{operation_name}' is FORBIDDEN in request context. "
            "Scrolls and heavy scans must be done in background jobs or offline scripts."
        )
        logger.error(f"⛔ SAFETY GUARD TRIGGERED: {error_msg}")
        raise RuntimeError(error_msg)
