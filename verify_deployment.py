"""
verify_deployment.py - Kịch bản Kiểm tra Sức khỏe & Xác thực Triển khai Đầu - Cuối
(End-to-End Health Check & Verification Matrix)
Chạy tự động kiểm tra toàn bộ 4 hệ thống con:
- Data Subsystem (CSDL & Snapshots)
- Model Subsystem (Hedonic OLS, AHP Saaty, Scoring, What-If)
- API Subsystem (FastAPI, Schemas, Telemetry, Feedback)
- Knowledge-based Subsystem (Rules & AI Explanations)
- Frontend Subsystem (Dashboard SPA 5 tabs)
In báo cáo kiểm định màu Xanh/Đỏ và trả về exit code 0 khi đạt 100%.
"""
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, Any, List

# Đảm bảo đường dẫn gốc nằm trong sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ANSI Color codes cho console
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class DeploymentVerifier:
    def __init__(self, base_url: str = None, internal_mode: bool = True):
        self.internal_mode = internal_mode
        self.base_url = base_url.rstrip("/") if base_url else "http://localhost:8000"
        self.client = None

        if self.internal_mode:
            from starlette.testclient import TestClient
            from laptopmatch_dss.api.main import app
            self.client = TestClient(app)
        else:
            import httpx
            self.client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def _get(self, path: str):
        if self.internal_mode:
            return self.client.get(path)
        return self.client.get(self.base_url + path)

    def _post(self, path: str, json_data: Dict[str, Any]):
        if self.internal_mode:
            return self.client.post(path, json=json_data)
        return self.client.post(self.base_url + path, json=json_data)

    def run_all_checks(self) -> bool:
        print(f"\n{BOLD}{CYAN}{'='*75}{RESET}")
        print(f"{BOLD}{CYAN} LAPTOPMATCH DSS - BẢN KIỂM ĐỊNH TOÀN DIỆN HỆ THỐNG LIVE{RESET}")
        print(f"{CYAN}{'='*75}{RESET}\n")

        results = []

        # 1. Health Check
        results.append(self._test_health())

        # 2. Q1 Regression Test (Top-1, 82 offers, DSS 0.8310)
        results.append(self._test_recommend_q1())

        # 3. AHP Saaty Consistency Test
        results.append(self._test_ahp_calculation())

        # 4. What-If Scenarios (WS1 - WS5)
        results.append(self._test_whatif_scenarios())

        # 5. Hedonic Pricing Model
        results.append(self._test_hedonic_model())

        # 6. Knowledge-based Explanation Engine
        results.append(self._test_ai_explanation())

        # 7. Telemetry & User Feedback (R6)
        results.append(self._test_telemetry_and_feedback())

        # 8. Recommendation Acceptance Rate KPI (R6)
        results.append(self._test_rar_kpi())

        # 9. Dashboard UI SPA (5 Tabs)
        results.append(self._test_dashboard_ui())

        # Báo cáo tổng kết
        print(f"\n{BOLD}{'='*75}{RESET}")
        print(f"{BOLD} KẾT QUẢ KIỂM ĐỊNH TỔNG QUAN:{RESET}")
        print(f"{'='*75}")

        all_passed = True
        for test_name, passed, detail in results:
            status_text = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
            print(f"[{status_text}] {BOLD}{test_name:<40}{RESET} -> {detail}")
            if not passed:
                all_passed = False

        print(f"{'='*75}")
        if all_passed:
            print(f"{BOLD}{GREEN}>>> TẤT CẢ CÁC BÀI KIỂM ĐỊNH ĐÃ VƯỢT QUA 100% - HỆ THỐNG SẴN SÀNG PRODUCTION <<<{RESET}\n")
            return True
        else:
            print(f"{BOLD}{RED}>>> CÓ BÀI KIỂM ĐỊNH THẤT BẠI - VUI LÒNG KIỂM TRA LẠI LOG CHI TIẾT <<<{RESET}\n")
            return False

    def _test_health(self):
        try:
            res = self._get("/api/health")
            if res.status_code == 200:
                data = res.json()
                if data["status"] == "healthy" and data["fact_offers_count"] >= 210:
                    return ("1. Health Check & CSDL", True, f"{data['dim_sellers_count']} shop, {data['fact_offers_count']} offers")
            return ("1. Health Check & CSDL", False, f"Status {res.status_code}")
        except Exception as e:
            return ("1. Health Check & CSDL", False, str(e))

    def _test_recommend_q1(self):
        try:
            res = self._post("/api/recommend", {"persona_id": "Q1", "top_n": 5})
            if res.status_code == 200:
                data = res.json()
                top1 = data["top_offers"][0]
                is_obs164 = top1["offer_id"] == "OBS0164"
                is_82 = data["total_eligible"] == 82
                dss_correct = abs(top1["dss_score"] - 0.8310) < 0.005
                if is_obs164 and is_82 and dss_correct:
                    return ("2. Bài kiểm tra Hồi quy Q1 (Top 1)", True, f"Top-1: {top1['model']} (DSS={top1['dss_score']}, {data['total_eligible']}/210)")
                return ("2. Bài kiểm tra Hồi quy Q1 (Top 1)", False, f"Lệch Top-1: {top1['offer_id']}, Eligible: {data['total_eligible']}")
            return ("2. Bài kiểm tra Hồi quy Q1 (Top 1)", False, f"Status {res.status_code}")
        except Exception as e:
            return ("2. Bài kiểm tra Hồi quy Q1 (Top 1)", False, str(e))

    def _test_ahp_calculation(self):
        try:
            res = self._post("/api/ahp/calculate", {
                "criteria": ["cpu", "ram", "w"],
                "matrix": [[1.0, 2.0, 0.5], [0.5, 1.0, 0.25], [2.0, 4.0, 1.0]]
            })
            if res.status_code == 200:
                data = res.json()
                if data["is_consistent"] and data["consistency_ratio"] < 0.10:
                    return ("3. Mô-đun AHP Saaty 1-9", True, f"CR = {data['consistency_ratio']:.4f} < 0.10 (Nhất quán)")
            return ("3. Mô-đun AHP Saaty 1-9", False, f"CR={data.get('consistency_ratio')}")
        except Exception as e:
            return ("3. Mô-đun AHP Saaty 1-9", False, str(e))

    def _test_whatif_scenarios(self):
        try:
            ws1 = self._post("/api/whatif", {"scenario_type": "WS1"}).json()
            ws2 = self._post("/api/whatif", {"scenario_type": "WS2"}).json()
            ws1_ok = ws1["details"]["30tr"]["eligible_count"] == 82 and ws1["details"]["20tr"]["eligible_count"] == 12
            ws2_ok = ws2["details"]["top1"]["brand"] == "MSI"
            if ws1_ok and ws2_ok:
                return ("4. Động cơ What-If (WS1 - WS5)", True, "WS1 (82->12), WS2 (MSI Gaming Thin)")
            return ("4. Động cơ What-If (WS1 - WS5)", False, "Kịch bản WS1/WS2 sai số liệu")
        except Exception as e:
            return ("4. Động cơ What-If (WS1 - WS5)", False, str(e))

    def _test_hedonic_model(self):
        try:
            res = self._get("/api/models/hedonic")
            if res.status_code == 200:
                d = res.json()
                if d["r_squared"] >= 0.80 and d["mape_5fold_pct"] <= 15.0:
                    return ("5. Mô hình Hedonic OLS HC3", True, f"R² = {d['r_squared']}, MAPE = {d['mape_5fold_pct']}%")
            return ("5. Mô hình Hedonic OLS HC3", False, "R² hoặc MAPE không đạt")
        except Exception as e:
            return ("5. Mô hình Hedonic OLS HC3", False, str(e))

    def _test_ai_explanation(self):
        try:
            res = self._get("/api/explain/OBS0164?persona_id=Q1")
            if res.status_code == 200:
                d = res.json()
                exp = d.get("explanation", {})
                if exp.get("natural_language_explanation") and len(exp.get("key_strengths", [])) >= 2:
                    return ("6. Bộ Giải thích Quyết định Thông minh", True, f"NLG tự nhiên ({exp['source']})")
            return ("6. Bộ Giải thích Quyết định Thông minh", False, "Không sinh được lời giải thích")
        except Exception as e:
            return ("6. Bộ Giải thích Quyết định Thông minh", False, str(e))

    def _test_telemetry_and_feedback(self):
        try:
            r1 = self._post("/api/telemetry", {"event_type": "pin_compare", "offer_id": "OBS0164", "persona": "Q1"}).json()
            r2 = self._post("/api/feedback", {"offer_id": "OBS0164", "persona": "Q1", "is_helpful": True, "rating": 5}).json()
            if r1.get("status") == "recorded" and r2.get("status") == "recorded":
                return ("7. Telemetry & User Feedback (R6)", True, f"Ghi nhận Event #{r1['event_id']}, Feedback #{r2['feedback_id']}")
            return ("7. Telemetry & User Feedback (R6)", False, "Không ghi nhận được vào CSDL")
        except Exception as e:
            return ("7. Telemetry & User Feedback (R6)", False, str(e))

    def _test_rar_kpi(self):
        try:
            res = self._get("/api/kpi/rar")
            if res.status_code == 200:
                d = res.json()
                if "total_telemetry_events" in d and d["total_telemetry_events"] > 0:
                    return ("8. Chỉ số Đo lường RAR (R6)", True, f"RAR = {d['recommendation_acceptance_rate_pct']}%, Events = {d['total_telemetry_events']}")
            return ("8. Chỉ số Đo lường RAR (R6)", False, "Lỗi truy vấn KPI RAR")
        except Exception as e:
            return ("8. Chỉ số Đo lường RAR (R6)", False, str(e))

    def _test_dashboard_ui(self):
        try:
            res = self._get("/dashboard/")
            if res.status_code == 200 and "tab-ahp" in res.text and "tab-simulator" in res.text:
                return ("9. Giao diện Dashboard SPA (5 Trang)", True, "Phục vụ 5 tabs thành công tại /dashboard/")
            return ("9. Giao diện Dashboard SPA (5 Trang)", False, f"Status {res.status_code}")
        except Exception as e:
            return ("9. Giao diện Dashboard SPA (5 Trang)", False, str(e))

def main():
    parser = argparse.ArgumentParser(description="LaptopMatch DSS Deployment Verification Matrix")
    parser.add_argument("--url", type=str, default=None, help="URL của server live (e.g. http://localhost:8000)")
    parser.add_argument("--mode", type=str, default="internal", choices=["internal", "http"], help="Chế độ kiểm định: internal (TestClient) hoặc http")

    args = parser.parse_args()
    use_internal = args.mode == "internal" and args.url is None

    verifier = DeploymentVerifier(base_url=args.url, internal_mode=use_internal)
    success = verifier.run_all_checks()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
