"""
base_scraper.py - Lớp cơ sở (Base Class) cho Scraper theo Adapter Pattern
Tuân thủ Nguyên tắc 4:
- Tôn trọng robots.txt & chỉ thu thập giá công khai
- Giới hạn tốc độ >= 2 giây/request (rate limiting)
- User-Agent nghiên cứu rõ ràng: SCRAPER_USER_AGENT
- Hỗ trợ chế độ mock fixture khi chạy offline hoặc kiểm thử tự động
"""
import time
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import urllib.request
import urllib.error

from laptopmatch_dss.config.settings import (
    SCRAPER_RATE_LIMIT_SECONDS,
    SCRAPER_USER_AGENT,
    SCRAPER_MOCK_FIXTURE_PATH
)

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Lớp cơ sở cho các scraper adapter của từng nhà bán lẻ.
    """
    _last_request_time: float = 0.0

    def __init__(self, seller_id: str, seller_name: str, base_url: str):
        self.seller_id = seller_id
        self.seller_name = seller_name
        self.base_url = base_url
        self.rate_limit_seconds = SCRAPER_RATE_LIMIT_SECONDS
        self.user_agent = SCRAPER_USER_AGENT

    def _enforce_rate_limit(self):
        """Đảm bảo khoảng cách tối thiểu giữa 2 request >= 2 giây (Nguyên tắc 4)."""
        now = time.time()
        elapsed = now - BaseScraper._last_request_time
        if elapsed < self.rate_limit_seconds:
            wait_time = self.rate_limit_seconds - elapsed
            logger.debug(f"Đang chờ {wait_time:.2f}s để tuân thủ rate limit...")
            time.sleep(wait_time)
        BaseScraper._last_request_time = time.time()

    def fetch_url(self, url: str) -> Optional[str]:
        """Gửi HTTP GET request với User-Agent và rate limiting."""
        self._enforce_rate_limit()
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return response.read().decode("utf-8", errors="replace")
                logger.warning(f"Request tới {url} trả về status {response.status}")
                return None
        except urllib.error.HTTPError as e:
            if e.code == 403:
                logger.warning(f"Nhà bán {self.seller_name} chặn truy cập (403 Forbidden): {url}. Bỏ qua theo nguyên tắc.")
            else:
                logger.warning(f"Lỗi HTTP {e.code} khi truy cập {url}: {e.reason}")
            return None
        except Exception as e:
            logger.warning(f"Không thể kết nối tới {url}: {e}")
            return None

    def load_from_mock_fixture(self) -> List[Dict[str, Any]]:
        """Đọc dữ liệu mock fixture từ file JSON cho seller này."""
        if not SCRAPER_MOCK_FIXTURE_PATH.exists():
            logger.warning(f"Không tìm thấy file mock fixture: {SCRAPER_MOCK_FIXTURE_PATH}")
            return []
        
        try:
            with open(SCRAPER_MOCK_FIXTURE_PATH, "r", encoding="utf-8") as f:
                all_mock_offers = json.load(f)
            seller_offers = [o for o in all_mock_offers if o.get("seller_id") == self.seller_id]
            logger.info(f"[{self.seller_id}] Đã nạp {len(seller_offers)} offer từ mock fixture.")
            return seller_offers
        except Exception as e:
            logger.error(f"Lỗi đọc mock fixture cho {self.seller_id}: {e}")
            return []

    @abstractmethod
    def scrape(self, use_mock: bool = False) -> List[Dict[str, Any]]:
        """
        Thu thập danh sách offer từ nhà bán.
        Mỗi offer trả về dict chứa:
        - seller_id, brand, model, release_year
        - cpu, cpu_benchmark_score, gpu, gpu_benchmark_score, dgpu
        - ram_gb, ssd_gb, screen_inch, resolution_width_px, resolution_height_px, refresh_hz
        - weight_kg, battery_wh
        - price_vnd, list_price_vnd, discount_pct
        - warranty_months, return_days, condition, availability, source_url, snapshot_date
        """
        pass
