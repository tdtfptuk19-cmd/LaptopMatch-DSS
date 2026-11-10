# LaptopMatch Decision Support System (Level 4 Production DSS)

**Môn học:** DSS301 – Hệ hỗ trợ ra quyết định (Giáo trình: Efraim Turban, Ramesh Sharda, Dursun Delen & Vicki L. Sauter)  
**Đồ án:** Nhóm 1 – LaptopMatch (Hỗ trợ mua sắm Laptop tối ưu dựa trên dữ liệu và khoa học quyết định)

---

## 📁 Cấu trúc Thư mục Chuẩn (Repository Architecture)

```
laptopmatch_dss/
├── config/                         # [QUY TẮC 5: KHÔNG HARD-CODE]
│   ├── __init__.py
│   ├── settings.py                 # Đường dẫn, DB URL (SQLite dev / Postgres prod), CORS
│   ├── models_config.json          # 6 hệ số β, XMAX, XMIN, hằng số sigmoid k=10
│   └── personas_config.json        # Cấu hình 5 Personas (Q1, U1, U2, U4, U5)
│
├── data_subsystem/                 # [HỆ THỐNG CON 1: DATA MANAGEMENT]
│   ├── __init__.py
│   ├── db.py                       # SQLAlchemy 2.0 engine, declarative base, session factory
│   ├── models.py                   # ORM: Laptop, Seller, Offer, TelemetryEvent, UserFeedback
│   ├── migrate.py                  # ETL idempotent nạp 210 offer T1 từ LaptopMatch_Clean.xlsx
│   ├── quality.py                  # Kiểm tra toàn vẹn, missing, outlier (OBS0075), duplication
│   └── scrapers/                   # Scraper Adapter Pattern (R6: thu thập T2, T3)
│       ├── __init__.py
│       ├── base_scraper.py         # Rate-limit (≥2s), robots.txt, custom User-Agent, mock mode
│       ├── fpt_scraper.py          # Adapter FPT Shop
│       ├── cellphones_scraper.py   # Adapter CellphoneS
│       ├── gearvn_scraper.py       # Adapter GEARVN
│       ├── sazo_scraper.py         # Adapter SAZO
│       ├── ttcenter_scraper.py     # Adapter T&T Center
│       ├── ncpc_scraper.py         # Adapter Nguyễn Công PC
│       └── scraper_runner.py       # CLI Runner chạy batch/cron ghi snapshot T2/T3
│
├── model_subsystem/                # [HỆ THỐNG CON 2: MODEL MANAGEMENT]
│   ├── __init__.py
│   ├── pricing.py                  # Huấn luyện Hedonic OLS Robust HC3, 5-fold CV, Breusch-Pagan, registry
│   ├── scoring.py                  # Engine tính Eligibility, S_k, Utility, Deal, DSS_Score
│   ├── ahp.py                     # Saaty Analytic Hierarchy Process, Eigenvector, Consistency Ratio (CR)
│   └── whatif.py                   # Tái hiện WS1–WS5 & mô phỏng What-if tham số tùy ý
│
├── api/                            # [GIAI ĐOẠN 3: BACKEND API FASTAPI]
│   ├── __init__.py
│   ├── main.py                     # Entrypoint, CORS, Exception Handler, Rate-limiter
│   ├── schemas.py                  # Pydantic v2 schemas (In/Out DTOs)
│   └── routes/
│       ├── __init__.py
│       ├── recommend.py            # POST /api/recommend
│       ├── offers.py               # GET /api/offers (lọc, phân trang, sort)
│       ├── whatif.py               # POST /api/what-if
│       ├── ahp.py                  # POST /api/ahp/weights (tính w_k & CR)
│       ├── health.py               # GET /api/health, GET /api/model/info
│       └── telemetry.py            # POST /api/events, POST /api/feedback, GET /api/rar/stats
│
├── ui/                             # [HỆ THỐNG CON 3: DIALOG / USER INTERFACE]
│   ├── index.html                  # 4 trang trực quan hóa Plotly.js gọi trực tiếp API
│   ├── app.js                      # Kết nối API, AHP câu hỏi tự nhiên, Side-by-side compare (2-3 máy)
│   └── style.css                   # Tuân thủ bảng 5 màu chuẩn & nguyên tắc Miller 7±2
│
├── knowledge_subsystem/            # [HỆ THỐNG CON 4: KNOWLEDGE-BASED & LLM ADVISOR]
│   ├── __init__.py
│   ├── advisor.py                  # Trợ lý ảo tư vấn Gemini API (Tool-calling: recommend, whatif, offers)
│   └── explainer.py                # Sinh lý giải tự nhiên tại sao máy Top-1 vượt trội (kèm Fallback template)
│
├── telemetry_subsystem/            # [GIAI ĐOẠN 6: TELEMETRY & RAR CONTINUOUS TRACKING]
│   ├── __init__.py
│   ├── tracker.py                  # Ghi nhận sự kiện click nơi bán, lưu máy, ghim so sánh
│   └── rar_calculator.py           # Tính RAR tự động theo thời gian, theo persona
│
├── tests/                          # [KIỂM THỬ TỰ ĐỘNG PYTEST]
│   ├── __init__.py
│   ├── test_regression_asm2.py     # Test hồi quy bắt buộc: so sánh DSS_Score với kết quả gốc (sai số ≤ 1e-6)
│   ├── test_data_subsystem.py      # Test DB schema, migration, data quality
│   ├── test_model_subsystem.py     # Test Hedonic pricing, scoring, what-if
│   ├── test_ahp.py                 # Test ma trận Saaty, tính vector w_k, kiểm tra ngưỡng CR < 0.1
│   ├── test_api.py                 # Test các endpoint FastAPI qua TestClient
│   └── test_telemetry.py           # Test ghi nhận event & công thức tính RAR
│
├── fixtures/                       # Dữ liệu mẫu & mock scraper khi chạy offline
│   └── mock_scraped_offers.json
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🏛️ Kiến trúc 4 Hệ thống con (Turban, Sharda & Delen)

```
                                  ┌───────────────────────────┐
                                  │   USER INTERFACE/DIALOG   │
                                  │  (Dashboard UI / app.js)  │
                                  └─────────────┬─────────────┘
                                                │ REST API / JSON
                                  ┌─────────────▼─────────────┐
                                  │      BACKEND ENGINE       │
                                  │   (FastAPI + Pydantic)    │
                                  └──────┬─────────────┬──────┘
                                         │             │
                 ┌───────────────────────┴───┐     ┌───┴───────────────────────┐
                 │  DATA MANAGEMENT SUBSYS   │     │  MODEL MANAGEMENT SUBSYS  │
                 │ - SQLite / PostgreSQL     │     │ - Hedonic OLS Robust HC3  │
                 │ - 6 Multi-Seller Scrapers │     │ - AHP Saaty 1-9 Matrix    │
                 │ - Data Quality Auditor    │     │ - Multi-Criteria Scoring  │
                 │ - T1, T2, T3 Snapshots    │     │ - What-If Simulator WS1-5 │
                 └───────────────────────────┘     └───────────────────────────┘
                                         │             │
                                  ┌──────▼─────────────▼──────┐
                                  │  KNOWLEDGE-BASED SUBSYS   │
                                  │ - Expert Forward-Chaining │
                                  │ - 20 Hypotheses & 6 Recs  │
                                  │ - Gemini AI / NLG Engine  │
                                  └───────────────────────────┘
```

1. **Data Management Subsystem (`data_subsystem/`)**:
   - Lược đồ CSDL: `dim_laptops`, `dim_sellers`, `fact_offers`, `fact_telemetry_events`, `fact_user_feedback`.
   - Bổ sung 2 trường quan trọng theo O8: `condition` (`new`, `likenew`, `display`) và `availability` (`in_stock`, `out_of_stock`, `pre_order`).
   - ETL Idempotent nạp dữ liệu từ `LaptopMatch_Clean.xlsx` (bảo toàn 210 offer T1).
   - Bộ Scraper theo Adapter Pattern cho 6 nhà bán lẻ (FPT Shop, CellphoneS, GEARVN, SAZO, T&T Center, Nguyễn Công PC) với rate limit $\ge 2$s và mock fixture offline.
   - Module kiểm toán chất lượng dữ liệu: phát hiện missing, duplicate, và ngoại lai `OBS0075`.

2. **Model Management Subsystem (`model_subsystem/`)**:
   - **Hedonic Pricing Model**: Linear 6 đặc trưng (GroupKFold Cross-Validation OOF) với $\ln(\text{Fair Price}) = 16.514 + 0.01395\cdot\text{CPU} + 0.01607\cdot\text{GPU} + 0.00909\cdot\text{RAM} + 0.00443\cdot\text{Pin} - 0.2007\cdot\text{Weight} + 0.1476\cdot\text{RTX}$. Đạt OOF $R^2 = 0.832$, GroupKFold MAPE = $12.80\%$ ($\le 15\%$), $\sigma_{\log} = 0.166307$, 80% CI $[-17\%, +25\%]$, Breusch-Pagan $p = 0.0186 < 0.05$ (HC3).
   - **DSS Multi-criteria Scoring**: $S_k$, điểm $\text{Utility} = \sum w_k S_k$, điểm $\text{Deal} = \sigma(1.5 \cdot z) \cdot \text{Shop\_Trust}$ với $z = \ln(\text{Fair Price} / \text{Price}) / \sigma_{\log}$, điểm $\text{DSS\_Score} = \text{Eligibility} \times [\alpha\cdot\text{Utility} + (1-\alpha)\cdot\text{Deal}]$. (Q1 chuẩn hóa `CPU >= 18,000` cho ra 82 offer đạt chuẩn, Top-1 ASUS Zenbook 14 @ SAZO đạt `DSS = 0.8310`).
   - **AHP Saaty 1–9**: Tính vector trọng số bằng Principal Eigenvector và Geometric Mean; đo lường tỷ số nhất quán $CR$; từ chối hoặc cảnh báo nếu $CR \ge 0.10$.
   - **What-If Engine**: Tái hiện chính xác các kịch bản WS1–WS6 (WS1: 82→42→28→12→1; WS3 hòa vốn giảm `8.05%` / `26.94M`; WS4: 82→4) và mô phỏng tùy ý.

3. **User Interface / Dialog Subsystem (`ui/` & `api/`)**:
   - Giao diện người dùng tuân thủ nguyên tắc Miller $7 \pm 2$, Edward Tufte Data-Ink Ratio, Don Norman & Alan Cooper HCI:
     - **Trang 1: Tổng quan KPI**: 6 tile KPI lớn, bảng Top-5, ngăn kéo so sánh song song đối đầu (2-3 máy), giải thích AI và thanh đánh giá RAR (R6).
     - **Trang 2: Insight Thị trường**: 3 biểu đồ Plotly (Chênh lệch giá H4, Chính sách giảm giá H15, Trade-off cân nặng vs giá H2/H14), bảng tương tác 20 giả thuyết.
     - **Trang 3: Dự báo Fair Price**: Scatter plot giá thực vs Fair Price dải $\pm 15\%$, Top 10 hời nhất, Top 5 đắt nhất kèm huy hiệu cảnh báo đỏ R2, máy tính định giá thời gian thực.
     - **Trang 4: What-if Simulator**: Điều khiển thanh trượt ngân sách, alpha, RAM/SSD, cân nặng cứng/mềm; 5 tab kịch bản WS1–WS5; 6 thẻ khuyến nghị R1–R6.
     - **Trang 5: Cá nhân hóa AHP**: Ma trận so sánh cặp Saaty 1–9 bằng câu hỏi tự nhiên, thước đo $CR$ xanh/đỏ, nút áp dụng trọng số trực tiếp vào Simulator.
   - Dual Mode: Tự động kết nối Live API (FastAPI) hoặc chuyển sang Offline Fallback Mode khi mở độc lập.

4. **Knowledge-based Subsystem (`knowledge_subsystem/`)**:
   - **Expert Rule Engine**: Cơ chế suy diễn tiến (Forward-chaining) với các luật R1-R6 và 20 giả định khoa học.
   - **Decision Explainer**: Tự động bóc tách định lượng phần đóng góp của Utility ($65\%$) vs Deal ($35\%$).
   - **LLM Advisor**: Tích hợp Gemini API với kiến trúc Tool-calling (gọi `recommend`, `whatif`, `offers`), chống ảo giác, trích dẫn chính xác số liệu, kèm Fallback template khi offline.

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy

### 1. Khởi chạy Backend API & Dashboard

```bash
# Cài đặt phụ thuộc
pip install -r requirements.txt

# Khởi chạy server FastAPI
python -m uvicorn laptopmatch_dss.api.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Dashboard UI**: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)
- **Tài liệu OpenAPI Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Tài liệu ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 2. Chạy Toàn bộ Bộ Kiểm thử Tự động (Pytest)

```bash
pytest laptopmatch_dss/tests/ -v
```

Kiểm tra toàn bộ 6 file test:
1. `test_regression_asm2.py`: Bài kiểm tra hồi quy bắt buộc so với kết quả gốc (sai số $\le 10^{-6}$)
2. `test_data_subsystem.py`: DB schema, migration, data quality
3. `test_model_subsystem.py`: Hedonic pricing, scoring, what-if
4. `test_ahp.py`: Ma trận Saaty, vector trọng số, ngưỡng $CR < 0.1$
5. `test_api.py`: Các endpoint FastAPI qua TestClient
6. `test_telemetry.py`: Ghi nhận event & công thức tính RAR

---

### 3. Triển khai Container hóa (Docker)

```bash
# Build & chạy với docker-compose
docker-compose -f docker/docker-compose.yml up --build -d

# Xem logs
docker-compose -f docker/docker-compose.yml logs -f
```
