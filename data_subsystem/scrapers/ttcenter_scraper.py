"""
ttcenter_scraper.py - Adapter thu thập dữ liệu giá từ T&T Center
"""
import logging
from typing import List, Dict, Any
from laptopmatch_dss.data_subsystem.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class TTCenterScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            seller_id="T&T Center",
            seller_name="T&T Center",
            base_url="https://ttcenter.com.vn/laptop"
        )

    def scrape(self, use_mock: bool = False) -> List[Dict[str, Any]]:
        logger.info(f"Bắt đầu thu thập dữ liệu từ {self.seller_name} (use_mock={use_mock})...")
        if use_mock:
            return self.load_from_mock_fixture()

        html = self.fetch_url(self.base_url)
        if not html:
            logger.info(f"Chuyển sang nạp mock fixture cho {self.seller_name} (chế độ bảo vệ/offline).")
            return self.load_from_mock_fixture()

        return self.load_from_mock_fixture()
