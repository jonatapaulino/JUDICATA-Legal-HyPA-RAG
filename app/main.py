"""
FastAPI main application for Judicial Sovereignty Backend.
Provides the /adjudicate endpoint for judicial reasoning.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
License: MIT
"""
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.database import (
    connect_databases,
    disconnect_databases,
    health_check_databases
)
from app.models.requests import AdjudicateRequest, HealthCheckRequest
from app.models.responses import ToulminResponse, HealthCheckResponse, ErrorResponse
from app.agents.orchestrator import orchestrator

# Configure logging before creating logger
configure_logging()
logger = get_logger(__name__)

# API Key Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Validate API Key if enabled."""
    if settings.api_key_enabled:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key"
            )
        if api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API Key"
            )
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("application_starting", environment=settings.environment)

    try:
        await connect_databases()
        logger.info("application_ready")
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await disconnect_databases()
    logger.info("application_stopped")


# Create FastAPI app
app = FastAPI(
    title="Judicial Sovereignty Backend",
    description="Sistema de Soberania Judicial - Framework Neuro-Simbólico e Agêntico",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for request tracing
@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """Add trace_id to each request for tracking."""
    trace_id = request.headers.get("X-Trace-ID") or f"req_{uuid.uuid4().hex[:12]}"

    # Bind trace_id to logging context
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    # Add to request state
    request.state.trace_id = trace_id

    response = await call_next(request)

    # Add trace_id to response headers
    response.headers["X-Trace-ID"] = trace_id

    # Clear context
    structlog.contextvars.clear_contextvars()

    return response


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    trace_id = getattr(request.state, "trace_id", "unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            message=str(exc.detail),
            trace_id=trace_id
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    trace_id = getattr(request.state, "trace_id", "unknown")

    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        trace_id=trace_id
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An internal error occurred. Please try again later.",
            trace_id=trace_id
        ).model_dump()
    )


# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Judicial Sovereignty Backend",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment,
        "documentation": "/docs"
    }


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check(request: Request):
    """
    Health check endpoint.

    Returns the health status of the API and connected services.
    """
    trace_id = request.state.trace_id

    logger.info("health_check_requested", trace_id=trace_id)

    # Check databases
    db_status = await health_check_databases()

    # Determine overall status
    all_healthy = all(db_status.values())
    overall_status = "healthy" if all_healthy else "unhealthy"

    return HealthCheckResponse(
        status=overall_status,
        databases=db_status,
        version="1.0.0"
    )


@app.post("/adjudicate", response_model=ToulminResponse, tags=["Adjudication"], dependencies=[Depends(verify_api_key)])
async def adjudicate(request: Request, adjudicate_request: AdjudicateRequest):
    """
    Main adjudication endpoint.

    Processes a judicial query through the complete reasoning pipeline:
    1. Input validation (Guardian)
    2. Document retrieval (HyPA-RAG)
    3. Logical-semantic reasoning (LSIM)
    4. Output validation (Guardian + SCOT)
    5. Toulmin-structured response
    6. Anonymization (if enabled)

    Args:
        adjudicate_request: The adjudication request with query and options

    Returns:
        ToulminResponse with structured judicial reasoning

    Raises:
        HTTPException: If processing fails
    """
    trace_id = adjudicate_request.trace_id or request.state.trace_id

    logger.info(
        "adjudicate_request_received",
        trace_id=trace_id,
        query_length=len(adjudicate_request.query),
        anonymize=adjudicate_request.anonymize,
        enable_scot=adjudicate_request.enable_scot
    )

    try:
        # Execute orchestrator
        result = await orchestrator.adjudicate(
            query=adjudicate_request.query,
            anonymize=adjudicate_request.anonymize,
            enable_scot=adjudicate_request.enable_scot,
            trace_id=trace_id
        )

        # Check for errors
        if "error" in result:
            logger.error(
                "adjudication_failed",
                error=result.get("error"),
                trace_id=trace_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Processing failed")
            )

        logger.info(
            "adjudicate_request_completed",
            trace_id=trace_id,
            processing_time_ms=result.get("processing_time_ms", 0)
        )

        # Return as ToulminResponse
        return ToulminResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "adjudication_exception",
            error=str(e),
            error_type=type(e).__name__,
            trace_id=trace_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Adjudication failed: {str(e)}"
        )


@app.post("/api/v1/classify", tags=["API v1"])
async def classify_query_endpoint(request: Request, classify_request: "ClassifyQueryRequest"):
    """
    Classify query complexity without full processing.

    Returns the detected complexity level (BAIXA/MEDIA/ALTA) and recommended RAG parameters.
    Useful for frontend to show estimated processing time or adjust UI.
    """
    from app.models.requests import ClassifyQueryRequest
    from app.models.responses import ClassifyQueryResponse
    from app.retrieval.query_classifier import query_classifier

    trace_id = request.state.trace_id

    logger.info("classify_query_request", trace_id=trace_id, query_length=len(classify_request.query))

    try:
        complexity = query_classifier.classify(classify_request.query)
        rag_params = query_classifier.get_rag_params(complexity)

        # Calculate internal score for transparency
        score = 0
        if len(classify_request.query.split()) > 40:
            score = 4
        elif len(classify_request.query.split()) > 30:
            score = 2
        elif len(classify_request.query.split()) > 10:
            score = 1

        return ClassifyQueryResponse(
            query=classify_request.query,
            complexity=complexity.value,
            score=score,
            rag_params=rag_params.model_dump()
        )
    except Exception as e:
        logger.error("classify_query_error", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}"
        )


@app.post("/api/v1/validate", tags=["API v1"])
async def validate_text_endpoint(request: Request, validate_request: "ValidateTextRequest"):
    """
    Validate text for security threats without processing.

    Checks for injection attacks, XSS, SQL injection, jailbreak attempts, etc.
    Returns whether text is safe and any blocked patterns.
    """
    from app.models.requests import ValidateTextRequest
    from app.models.responses import ValidateTextResponse
    from app.agents.guardian import GuardianAgent

    trace_id = request.state.trace_id

    logger.info("validate_text_request", trace_id=trace_id, text_length=len(validate_request.text))

    try:
        # Create guardian with optional strict mode override
        guardian = GuardianAgent()
        if validate_request.strict_mode is not None:
            guardian.strict_mode = validate_request.strict_mode

        result = guardian.validate_input(validate_request.text, source="api")

        return ValidateTextResponse(
            text=validate_request.text[:100] + "..." if len(validate_request.text) > 100 else validate_request.text,
            safe=result.safe,
            reason=result.reason,
            blocked_patterns=result.blocked_patterns or []
        )
    except Exception as e:
        logger.error("validate_text_error", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


@app.get("/api/v1/status", tags=["API v1"])
async def status_endpoint(request: Request):
    """
    Get detailed status of all services.

    Returns operational status of API and all connected services (Qdrant, Neo4j, Redis, Ollama).
    Includes latency information for each service.
    """
    from app.models.responses import StatusResponse
    import time

    trace_id = request.state.trace_id

    logger.info("status_check_requested", trace_id=trace_id)

    try:
        services_status = {}

        # Check databases
        db_status = await health_check_databases()

        # Add database statuses
        for db_name, is_healthy in db_status.items():
            services_status[db_name] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "latency_ms": 0  # Could measure actual latency if needed
            }

        # Determine API status
        all_healthy = all(db_status.values())
        api_status = "operational" if all_healthy else "degraded"

        return StatusResponse(
            api_status=api_status,
            version="1.0.0",
            environment=settings.environment,
            services=services_status
        )
    except Exception as e:
        logger.error("status_check_error", error=str(e), trace_id=trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status check failed: {str(e)}"
        )


# Development/Debug endpoints (only in development)
if settings.is_development:

    @app.get("/debug/config", tags=["Debug"])
    async def debug_config():
        """Show current configuration (development only)."""
        return {
            "environment": settings.environment,
            "log_level": settings.log_level,
            "qdrant_host": settings.qdrant_host,
            "neo4j_uri": settings.neo4j_uri,
            "redis_host": settings.redis_host,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
            "guardian_enabled": settings.guardian_enabled,
            "scot_enabled": settings.scot_enabled,
            "anonymizer_enabled": settings.anonymizer_enabled
        }

    @app.post("/debug/test-guardian", tags=["Debug"])
    async def debug_test_guardian(text: str):
        """Test Guardian validation (development only)."""
        from app.agents.guardian import guardian

        input_result = guardian.validate_input(text, source="debug")
        output_result = guardian.validate_output(text, context="debug")

        return {
            "text": text,
            "input_validation": input_result.model_dump(),
            "output_validation": output_result.model_dump()
        }


# Entry point for local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )
