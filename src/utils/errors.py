import functools
from src.utils.logger import get_logger 

logger = get_logger(__name__)

class MovieAgentError(Exception):
    """Base class for all custom exceptions in the movie agent system"""
    def __init__(self, message:str, code:str, recoverable:bool=True):
        self.message = message
        self.code = code
        self.recoverable = recoverable
        super().__init__(message)

class ToolError(MovieAgentError):
    """Raised when a tool encounters an error during execution"""
    pass

class ValidationError(MovieAgentError):
    """Raised when input validation fails"""
    pass

class ModelError(MovieAgentError):
    """Raise when model error"""
    pass

class AgentError(MovieAgentError):
    """Raised for general agent errors that don't fit other categories"""
    pass

class MemoryError(MovieAgentError):
    """Raised when there is an error related to memory operations (e.g. Qdrant)"""
    pass

class BookingError(MovieAgentError):
    """Raised when there is an error during the booking process"""
    pass

class RAGError(MovieAgentError):
    """Raised when there is an error during the Retrieval-Augmented Generation process"""
    pass


def handle_errors(error_class=ToolError, default_return = None):
    """Decorator to wrap functions with standardized error handling and logging"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except MovieAgentError:
                raise
            except FileNotFoundError as e:
                raise error_class(
                    message=f"Data file not found: {e}",
                    code="FILE_NOT_FOUND",
                    recoverable=False
                )
            except KeyError as e:
                raise error_class(
                    message=f"Missing key: {e}",
                    code="KEY_NOT_FOUND",
                    recoverable=True
                )
            except ValueError as e:
                raise error_class(
                    message=f"Invalid value: {e}",
                    code="INVALID_VALUE",
                    recoverable=True
                )
            except Exception as e:
                logger.error(f"{func.__name__} failed: {type(e).__name__}: {e}")
                raise error_class(
                    message=str(e),
                    code="UNEXPECTED_ERROR",
                    recoverable=True
                )
        return wrapper
    return decorator
