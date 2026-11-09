"""
settings.py - Cấu hình hệ thống LaptopMatch DSS
Tuân thủ nguyên tắc không hard-code hằng số.
"""
import os
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent

# Cấu hình Cơ sở dữ liệu (SQLite dev, PostgreSQL prod)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'laptopmatch.db'}")

# Đường dẫn file dữ liệu gốc
ORIGINAL_DATASET_PATH = Path(os.getenv("ORIGINAL_DATASET_PATH", BASE_DIR.parent / "LaptopMatch_Clean.xlsx"))

# Đường dẫn file cấu hình JSON
CONFIG_DIR = BASE_DIR / "config"
MODELS_CONFIG_PATH = CONFIG_DIR / "models_config.json"
PERSONAS_CONFIG_PATH = CONFIG_DIR / "personas_config.json"

# API & Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Scraper settings (Tuân thủ Nguyên tắc 4: delay >= 2s, User-Agent rõ ràng)
SCRAPER_RATE_LIMIT_SECONDS = float(os.getenv("SCRAPER_RATE_LIMIT_SECONDS", "2.0"))
SCRAPER_USER_AGENT = os.getenv("SCRAPER_USER_AGENT", "LaptopMatch-DSS-ResearchBot/1.0 (+http://laptopmatch.local/bot)")
SCRAPER_MOCK_FIXTURE_PATH = BASE_DIR / "fixtures" / "mock_scraped_offers.json"

# Gemini API Key (Knowledge-based Subsystem)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
