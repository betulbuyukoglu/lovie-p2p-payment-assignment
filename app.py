from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import router as auth_router
from api.payments import router as payments_router
from api.requests import router as requests_router
from core.config import settings
from core.db import Base, engine
from core.errors import AppError, error_envelope
from schemas.common import fail

from models import ledger as _ledger  # noqa: F401
from models import payment_attempt as _payment_attempt  # noqa: F401
from models import request as _request  # noqa: F401
from models import user as _user  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="P2P Payment Request API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.extestception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=error_envelope(exc))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=fail(code="VALIDATION_ERROR", message="Geçersiz istek.", details={"errors": exc.errors()}),
    )


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(requests_router, prefix="/requests", tags=["Requests"])
app.include_router(payments_router, prefix="/requests", tags=["Payments"])


@app.get("/healthz", tags=["System"])
async def health():
    return {"status": "ok"}
