"""
main.py - Entrypoint chính của FastAPI Backend cho LaptopMatch DSS
Khởi tạo ứng dụng, Middleware, CORS, và Router.
"""
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from pathlib import Path

from laptopmatch_dss.config.settings import CORS_ORIGINS, API_HOST, API_PORT, BASE_DIR
from laptopmatch_dss.data_subsystem.db import init_db
from laptopmatch_dss.api.routes import router, pricing_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi tạo ứng dụng: đảm bảo DB và Model sẵn sàng."""
    logger.info("Đang khởi động hệ thống LaptopMatch DSS...")
    init_db()
    try:
        pricing_model.load_latest_or_fallback()
        logger.info(f"Mô hình định giá sẵn sàng: {pricing_model.version} (R2={pricing_model.r_squared:.4f}, MAPE={pricing_model.mape_5fold:.2f}%)")
    except Exception as e:
        logger.warning(f"Chưa tải được mô hình khi khởi động: {e}")
    yield
    logger.info("Đang tắt hệ thống LaptopMatch DSS.")

app = FastAPI(
    title="LaptopMatch Decision Support System API",
    description="""
    Hệ thống Hỗ trợ Ra Quyết định Mua sắm Laptop (DSS301 - Nhóm 1).
    Xây dựng theo kiến trúc 4 hệ thống con (Turban – Sharda – Delen):
    - Data Management Subsystem (ETL, Multi-seller Scrapers, Data Quality Audit)
    - Model Management Subsystem (Hedonic OLS Robust HC3, AHP Saaty, Multi-criteria Scoring, What-If Simulation)
    - User Interface / Dialog Subsystem (RESTful API, Telemetry, Feedback)
    - Knowledge-based Subsystem (Rule-based Decision Matrix & AI Explanation)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Cấu hình CORS đầy đủ
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in CORS_ORIGINS else CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware đo lường độ trễ (Latency Middleware)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000.0 # mili-giây
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    logger.debug(f"{request.method} {request.url.path} - {response.status_code} ({process_time:.2f}ms)")
    return response

# Gắn router API
app.include_router(router)

# Phục vụ Static Files cho Dashboard SPA
ui_dir = BASE_DIR / "ui"
if ui_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(ui_dir), html=True), name="ui")
    app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui_alias")
else:
    frontend_dir = BASE_DIR / "frontend"
    if frontend_dir.exists():
        app.mount("/dashboard", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

@app.get("/", summary="Trang chủ API")
def root():
    return {
        "system": "LaptopMatch Decision Support System",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "openapi_spec": "/openapi.json"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Chạy dev server tại http://{API_HOST}:{API_PORT}")
    uvicorn.run("laptopmatch_dss.api.main:app", host=API_HOST, port=API_PORT, reload=True)
