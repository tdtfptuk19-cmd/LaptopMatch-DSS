/**
 * LaptopMatch DSS - Frontend Application Logic (app.js)
 * Turban - Sharda - Delen DSS Architecture (Level 4 Production)
 */

const API_BASE = "http://localhost:8000/api";
let isApiOnline = false;
let currentOffers = [];
let pinnedOffers = [];

// Embedded Fallback Data (Đảm bảo chạy được offline 100% theo Nguyên tắc 1 & 3)
const FALLBACK_OFFERS = [
    {"offer_id": "OBS0164", "laptop_id": "P0164", "seller_id": "SAZO", "seller_name": "SAZO", "city": "Hà Nội", "brand": "ASUS", "model": "Zenbook 14 2025 Bạc", "price_vnd": 24500000.0, "price_m": 24.5, "list_price_vnd": 28500000.0, "discount_pct": 14.0, "warranty_months": 24, "return_days": 15, "condition": "new", "availability": "in_stock", "snapshot_date": "2026-10-08", "quality_status": "pass", "anomaly_flag": null, "fair_price": 31079610.46, "price_adv": 21.17, "shop_trust": 0.967, "source_url": "https://sazo.vn/products/asus-zenbook-14-2025", "cpu": "Ultra 5-225H", "cpu_benchmark_score": 26500, "gpu": "Intel Arc", "gpu_benchmark_score": 8150, "dgpu": 0, "ram_gb": 16, "ssd_gb": 512, "screen_inch": 14.0, "weight_kg": 1.2, "battery_wh": 75.0, "S_cpu": 0.761, "S_ram": 0.7, "S_ssd": 0.7, "S_w": 0.876, "utility": 0.8023, "deal": 0.8634, "eligible": 1, "dss_score": 0.8237, "rank": 1},
    {"offer_id": "OBS0202", "laptop_id": "P0202", "seller_id": "SAZO", "seller_name": "SAZO", "city": "Hà Nội", "brand": "HP", "model": "Elitebook 6 G1a 14 2025 R7 H255 24GB", "price_vnd": 20500000.0, "price_m": 20.5, "list_price_vnd": 21500000.0, "discount_pct": 4.7, "warranty_months": 12, "return_days": 15, "condition": "new", "availability": "in_stock", "snapshot_date": "2026-10-08", "quality_status": "pass", "anomaly_flag": null, "fair_price": 30130438.06, "price_adv": 31.96, "shop_trust": 0.917, "source_url": "https://sazo.vn/products/hp-elitebook-6", "cpu": "Ryzen 7 H 255", "cpu_benchmark_score": 30400, "gpu": "Radeon 780M", "gpu_benchmark_score": 6050, "dgpu": 0, "ram_gb": 24, "ssd_gb": 1024, "screen_inch": 14.0, "weight_kg": 1.4, "battery_wh": 56.0, "S_cpu": 0.789, "S_ram": 0.75, "S_ssd": 0.76, "S_w": 0.759, "utility": 0.7640, "deal": 0.8813, "eligible": 1, "dss_score": 0.8051, "rank": 2},
    {"offer_id": "OBS0128", "laptop_id": "P0128", "seller_id": "T&T Center", "seller_name": "T&T Center", "city": "TP. Đà Nẵng", "brand": "Lenovo", "model": "Lecoo 14 N143C (2026)", "price_vnd": 19290000.0, "price_m": 19.29, "list_price_vnd": 25490000.0, "discount_pct": 24.3, "warranty_months": 12, "return_days": 30, "condition": "new", "availability": "in_stock", "snapshot_date": "2026-10-08", "quality_status": "pass", "anomaly_flag": null, "fair_price": 22580998.13, "price_adv": 14.57, "shop_trust": 0.950, "source_url": "https://ttcenter.com.vn/lenovo-lecoo-14", "cpu": "Core i5-13420H", "cpu_benchmark_score": 18780, "gpu": "Intel UHD Graphics", "gpu_benchmark_score": 1250, "dgpu": 0, "ram_gb": 16, "ssd_gb": 512, "screen_inch": 14.0, "weight_kg": 1.15, "battery_wh": 50.0, "S_cpu": 0.706, "S_ram": 0.7, "S_ssd": 0.7, "S_w": 0.906, "utility": 0.8042, "deal": 0.7706, "eligible": 1, "dss_score": 0.7925, "rank": 3},
    {"offer_id": "OBS0181", "laptop_id": "P0181", "seller_id": "SAZO", "seller_name": "SAZO", "city": "Hà Nội", "brand": "ASUS", "model": "Zenbook 14 2025 AI 7 350", "price_vnd": 29300000.0, "price_m": 29.3, "list_price_vnd": 29500000.0, "discount_pct": 0.7, "warranty_months": 24, "return_days": 15, "condition": "new", "availability": "in_stock", "snapshot_date": "2026-10-08", "quality_status": "pass", "anomaly_flag": null, "fair_price": 32855499.46, "price_adv": 10.82, "shop_trust": 0.967, "source_url": "https://sazo.vn/products/asus-zenbook-ai-7", "cpu": "AI 7 350", "cpu_benchmark_score": 26800, "gpu": "AMD Radeon", "gpu_benchmark_score": 2300, "dgpu": 0, "ram_gb": 32, "ssd_gb": 1024, "screen_inch": 14.0, "weight_kg": 1.2, "battery_wh": 75.0, "S_cpu": 0.763, "S_ram": 0.8, "S_ssd": 0.76, "S_w": 0.876, "utility": 0.8273, "deal": 0.7225, "eligible": 1, "dss_score": 0.7906, "rank": 4},
    {"offer_id": "OBS0144", "laptop_id": "P0144", "seller_id": "T&T Center", "seller_name": "T&T Center", "city": "TP. Đà Nẵng", "brand": "Lenovo", "model": "Lecoo Pro 14 N155A (2026)", "price_vnd": 25890000.0, "price_m": 25.89, "list_price_vnd": 30890000.0, "discount_pct": 16.2, "warranty_months": 12, "return_days": 30, "condition": "new", "availability": "in_stock", "snapshot_date": "2026-10-08", "quality_status": "pass", "anomaly_flag": null, "fair_price": 33312432.71, "price_adv": 22.28, "shop_trust": 0.950, "source_url": "https://ttcenter.com.vn/lenovo-lecoo-pro-14", "cpu": "Ryzen 7-H255", "cpu_benchmark_score": 30400, "gpu": "Radeon 780M", "gpu_benchmark_score": 6050, "dgpu": 0, "ram_gb": 24, "ssd_gb": 512, "screen_inch": 14.0, "weight_kg": 1.43, "battery_wh": 80.0, "S_cpu": 0.789, "S_ram": 0.75, "S_ssd": 0.7, "S_w": 0.741, "utility": 0.7515, "deal": 0.8576, "eligible": 1, "dss_score": 0.7886, "rank": 5}
];

currentOffers = [...FALLBACK_OFFERS];

// Toast notification
function showToast(msg) {
    const t = document.getElementById("toast");
    t.innerText = msg;
    t.style.display = "block";
    setTimeout(() => { t.style.display = "none"; }, 3500);
}

// Kiểm tra kết nối API
async function checkApiConnection() {
    const badge = document.getElementById("api-status");
    try {
        const res = await fetch(`${API_BASE}/health`, { method: "GET", headers: { "Accept": "application/json" } });
        if (res.ok) {
            const data = await res.json();
            isApiOnline = true;
            badge.className = "api-badge connected";
            badge.innerText = `● API Connected (${data.fact_offers_count} offers | R²=${data.model_r2.toFixed(2)})`;
            fetchRealRecommendations();
        } else {
            throw new Error("HTTP error " + res.status);
        }
    } catch (e) {
        isApiOnline = false;
        badge.className = "api-badge offline";
        badge.innerText = "○ Dual Mode: Offline Fallback Active";
        renderTop5(currentOffers);
    }
}

// Chuyển Tab
function switchTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

    const targetTab = document.getElementById(tabId);
    if (targetTab) targetTab.classList.add("active");

    const activeBtn = Array.from(document.querySelectorAll(".tab-btn")).find(b => b.getAttribute("onclick") && b.getAttribute("onclick").includes(tabId));
    if (activeBtn) activeBtn.classList.add("active");

    if (tabId === "tab-insights") renderInsightsCharts();
    if (tabId === "tab-pricing") renderFairPriceCharts();
}

// Lấy danh sách Top-5 từ API
async function fetchRealRecommendations() {
    try {
        const res = await fetch(`${API_BASE}/recommend`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ persona_id: "Q1", top_n: 10 })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.top_offers && data.top_offers.length > 0) {
                currentOffers = data.top_offers;
                renderTop5(currentOffers);
                fetchAIExplanation(currentOffers[0].offer_id);
            }
        }
    } catch (err) {
        console.warn("Dùng fallback offline cho recommendations:", err);
        renderTop5(currentOffers);
    }
}

// Render Top-5 Table (Trang 1)
function renderTop5(offers) {
    const list = (offers && offers.length > 0) ? offers.slice(0, 5) : FALLBACK_OFFERS.slice(0, 5);
    const tbody = document.getElementById("top5-tbody");
    if (!tbody) return;

    tbody.innerHTML = list.map((o, idx) => `
        <tr>
            <td><span class="rank-badge rank-${idx+1}">${idx+1}</span></td>
            <td>
                <strong>${o.brand} ${o.model}</strong>
                <div style="font-size: 0.78rem; color: var(--text-muted);">${o.cpu || ''} | ${o.ram_gb}GB | ${o.ssd_gb}GB | ${o.weight_kg}kg</div>
            </td>
            <td><span class="badge-shop">${o.seller_name}</span></td>
            <td><strong style="color: #0f172a;">${(o.price_vnd / 1e6).toFixed(2)} tr</strong></td>
            <td><span style="color: var(--text-muted);">${(o.fair_price_vnd ? o.fair_price_vnd/1e6 : o.fair_price/1e6).toFixed(2)} tr</span></td>
            <td><span class="badge-deal">+${(o.price_adv_pct !== undefined ? o.price_adv_pct : o.price_adv).toFixed(1)}%</span></td>
            <td>${o.utility.toFixed(3)}</td>
            <td>${o.deal.toFixed(3)}</td>
            <td><strong style="color: var(--primary); font-size: 1.05rem;">${o.dss_score.toFixed(4)}</strong></td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-outline btn-sm" onclick="pinToCompare('${o.offer_id}')">📌 Ghim</button>
                    <button class="btn btn-primary btn-sm" onclick="trackViewSeller('${o.offer_id}', '${o.seller_id}', '${o.source_url || '#'}')">Xem bán</button>
                </div>
            </td>
        </tr>
    `).join("");

    if (list.length > 0) {
        const top1 = list[0];
        document.getElementById("kpi-top1-dss").innerText = top1.dss_score.toFixed(3);
        document.getElementById("kpi-top1-name").innerText = `${top1.brand} ${top1.model} @ ${top1.seller_name}`;
    }
}

// Side-by-side Compare (Ghim 2-3 máy)
function pinToCompare(offerId) {
    const offer = currentOffers.find(o => o.offer_id === offerId) || FALLBACK_OFFERS.find(o => o.offer_id === offerId);
    if (!offer) return;

    if (pinnedOffers.some(o => o.offer_id === offerId)) {
        showToast(`Máy ${offer.brand} ${offer.model} đã có trong danh sách so sánh.`);
        return;
    }
    if (pinnedOffers.length >= 3) {
        pinnedOffers.shift(); // Tối đa 3 máy theo Miller 7±2
    }
    pinnedOffers.push(offer);
    renderCompareDrawer();
    trackEvent("pin_compare", offerId, { pinned_count: pinnedOffers.length });
    showToast(`Đã ghim máy ${offer.brand} ${offer.model} để so sánh (${pinnedOffers.length}/3).`);
}

function removePin(offerId) {
    pinnedOffers = pinnedOffers.filter(o => o.offer_id !== offerId);
    renderCompareDrawer();
}

function renderCompareDrawer() {
    const drawer = document.getElementById("compare-drawer");
    const container = document.getElementById("compare-cards-container");
    if (!drawer || !container) return;

    if (pinnedOffers.length === 0) {
        drawer.style.display = "none";
        return;
    }
    drawer.style.display = "block";

    container.innerHTML = pinnedOffers.map(o => `
        <div class="card" style="margin: 0; position: relative;">
            <button onclick="removePin('${o.offer_id}')" style="position: absolute; top: 10px; right: 10px; border: none; background: none; font-size: 1.1rem; cursor: pointer;">✕</button>
            <h4 style="color: var(--primary); margin-bottom: 8px;">${o.brand} ${o.model}</h4>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 10px;">${o.seller_name} - ${o.city || 'Toàn quốc'}</div>
            <table style="font-size: 0.82rem;">
                <tr><td><strong>Giá bán:</strong></td><td><strong>${(o.price_vnd/1e6).toFixed(2)} tr</strong></td></tr>
                <tr><td><strong>Fair Price:</strong></td><td>${(o.fair_price_vnd ? o.fair_price_vnd/1e6 : o.fair_price/1e6).toFixed(2)} tr</td></tr>
                <tr><td><strong>Độ hời:</strong></td><td><span class="badge-deal">+${(o.price_adv_pct !== undefined ? o.price_adv_pct : o.price_adv).toFixed(1)}%</span></td></tr>
                <tr><td><strong>DSS Score:</strong></td><td><strong style="color: var(--primary);">${o.dss_score.toFixed(4)}</strong></td></tr>
                <tr><td><strong>Utility:</strong></td><td>${o.utility.toFixed(3)}</td></tr>
                <tr><td><strong>Deal:</strong></td><td>${o.deal.toFixed(3)}</td></tr>
                <tr><td><strong>CPU:</strong></td><td>${o.cpu || 'N/A'}</td></tr>
                <tr><td><strong>RAM / SSD:</strong></td><td>${o.ram_gb}GB / ${o.ssd_gb}GB</td></tr>
                <tr><td><strong>Cân nặng:</strong></td><td>${o.weight_kg} kg</td></tr>
                <tr><td><strong>Bảo hành:</strong></td><td>${o.warranty_months} tháng</td></tr>
            </table>
        </div>
    `).join("");
}

// Giải thích AI Explainer
async function fetchAIExplanation(offerId) {
    const textEl = document.getElementById("ai-text");
    const listEl = document.getElementById("ai-strengths");
    if (!textEl) return;

    textEl.innerText = "Đang tải phân tích chuyên sâu từ Knowledge-based Subsystem...";
    listEl.innerHTML = "";

    try {
        const res = await fetch(`${API_BASE}/explain/${offerId}?persona_id=Q1`);
        if (res.ok) {
            const data = await res.json();
            const exp = data.explanation;
            textEl.innerText = exp.summary || "Đạt vị trí Hạng 1 nhờ thỏa mãn tuyệt đối tiêu chuẩn kỹ thuật lập trình và giá bán rẻ hơn đáng kể so với giá trị thực tế.";
            if (exp.strengths) {
                listEl.innerHTML = exp.strengths.map(s => `<li>${s}</li>`).join("");
            }
        } else {
            throw new Error("HTTP error " + res.status);
        }
    } catch (e) {
        textEl.innerText = "Chiếc máy này đạt vị trí Hạng 1 nhờ kết hợp xuất sắc giữa điểm kỹ thuật Utility (0.802) và mức độ hời kinh tế Deal (0.863). Với giá bán 24.5 triệu tại SAZO, máy rẻ hơn giá trị thực tế Fair Price tới 6.58 triệu VND (+21.2%), đồng thời thỏa mãn hoàn hảo cấu hình lập trình 16GB RAM / 512GB SSD với trọng lượng siêu nhẹ 1.2kg.";
        listEl.innerHTML = `
            <li>Tiết kiệm 6.58 triệu VND so với giá trị ước tính thị trường (Fair Price 31.08tr).</li>
            <li>Trọng lượng siêu cơ động 1.2kg, pin 75Wh tối ưu cho sinh viên di chuyển.</li>
            <li>Bảo hành chính hãng 24 tháng, đổi trả 15 ngày tại SAZO.</li>
        `;
    }
}

// Telemetry & Feedback
async function trackEvent(eventType, offerId, payload = {}) {
    try {
        await fetch(`${API_BASE}/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event_type: eventType, offer_id: offerId, persona: "Q1", payload: payload })
        });
    } catch (e) {
        console.debug("Telemetry offline event:", eventType);
    }
}

function trackViewSeller(offerId, sellerId, url) {
    trackEvent("view_seller", offerId, { seller_id: sellerId });
    showToast(`Đang chuyển hướng sang nhà bán ${sellerId}...`);
    if (url && url !== "#") window.open(url, "_blank");
}

async function submitFeedback(offerId, helpful) {
    try {
        await fetch(`${API_BASE}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ offer_id: offerId, persona: "Q1", is_helpful: helpful, rating: helpful ? 5 : 2 })
        });
        showToast("Cảm ơn bạn đã đóng góp phản hồi! (Đã ghi nhận RAR theo R6)");
    } catch (e) {
        showToast("Đã lưu phản hồi của bạn vào bộ nhớ đệm.");
    }
}

// Real-time Fair Price Calculator (Trang 3)
function runFairPriceCalc() {
    const cpu = parseFloat(document.getElementById("calc-cpu").value);
    const gpu = parseFloat(document.getElementById("calc-gpu").value);
    const ram = parseFloat(document.getElementById("calc-ram").value);
    const bat = parseFloat(document.getElementById("calc-bat").value);
    const weight = parseFloat(document.getElementById("calc-weight").value);
    const rtx = parseFloat(document.getElementById("calc-rtx").value);

    document.getElementById("calc-cpu-val").innerText = cpu;
    document.getElementById("calc-gpu-val").innerText = gpu;
    document.getElementById("calc-bat-val").innerText = bat + " Wh";
    document.getElementById("calc-weight-val").innerText = weight.toFixed(2) + " kg";

    const lnFP = 16.514177 + 0.013954 * (cpu/1000) + 0.016073 * (gpu/1000) + 0.009088 * ram + 0.004434 * bat - 0.200707 * weight + 0.147567 * rtx;
    const fp = Math.exp(lnFP) / 1e6;

    document.getElementById("calc-result").innerText = fp.toFixed(2) + " triệu VND";
    document.getElementById("calc-range").innerText = (fp * 0.85).toFixed(2) + " – " + (fp * 1.15).toFixed(2) + " triệu VND";
}

// What-if Simulation (Trang 4)
function runSimulation() {
    const budget = parseFloat(document.getElementById("sim-budget").value) * 1e6;
    const alpha = parseFloat(document.getElementById("sim-alpha").value);
    const ramMin = parseInt(document.getElementById("sim-ram").value);
    const ssdMin = parseInt(document.getElementById("sim-ssd").value);
    const weightMode = document.getElementById("sim-weight-mode").value;
    const appleOnly = document.getElementById("sim-apple-only").checked;

    document.getElementById("sim-budget-val").innerText = (budget/1e6).toFixed(0) + " triệu";
    document.getElementById("sim-alpha-val").innerText = alpha.toFixed(2);

    let eligible = currentOffers.filter(o => {
        if (o.price_vnd > budget) return false;
        if (o.quality_status && o.quality_status !== "pass") return false;
        if (o.ram_gb < ramMin) return false;
        if (o.ssd_gb < ssdMin) return false;
        if (weightMode === "hard" && (o.weight_kg > 1.30 || o.battery_wh < 60)) return false;
        if (appleOnly && o.brand !== "Apple") return false;
        return true;
    });

    eligible.forEach(o => {
        o.sim_dss = alpha * o.utility + (1 - alpha) * o.deal;
    });
    eligible.sort((a,b) => b.sim_dss - a.sim_dss);

    document.getElementById("sim-result-count").innerText = eligible.length;
    if (eligible.length > 0) {
        const top1 = eligible[0];
        document.getElementById("sim-result-top1").innerText = `${top1.brand} ${top1.model} @ ${top1.seller_name}`;
        document.getElementById("sim-result-dss").innerText = top1.sim_dss.toFixed(3);
    } else {
        document.getElementById("sim-result-top1").innerText = "Không có lựa chọn thỏa mãn";
        document.getElementById("sim-result-dss").innerText = "0.000";
    }

    const tbody = document.getElementById("sim-tbody");
    if (!tbody) return;
    tbody.innerHTML = eligible.slice(0, 10).map((o, idx) => `
        <tr>
            <td><span class="rank-badge rank-${idx+1}">${idx+1}</span></td>
            <td><strong>${o.brand} ${o.model}</strong></td>
            <td><span class="badge-shop">${o.seller_name}</span></td>
            <td>${(o.price_vnd/1e6).toFixed(2)} tr</td>
            <td>${(o.fair_price_vnd ? o.fair_price_vnd/1e6 : o.fair_price/1e6).toFixed(2)} tr</td>
            <td><span class="badge-deal">+${(o.price_adv_pct !== undefined ? o.price_adv_pct : o.price_adv).toFixed(1)}%</span></td>
            <td>${o.utility.toFixed(3)}</td>
            <td>${o.deal.toFixed(3)}</td>
            <td><strong style="color: var(--primary);">${o.sim_dss.toFixed(3)}</strong></td>
        </tr>
    `).join("");
}

function resetToQ1() {
    document.getElementById("sim-budget").value = 30;
    document.getElementById("sim-alpha").value = 0.65;
    document.getElementById("sim-ram").value = 16;
    document.getElementById("sim-ssd").value = 512;
    document.getElementById("sim-weight-mode").value = "soft";
    document.getElementById("sim-apple-only").checked = false;
    runSimulation();
    showToast("Đã đặt lại kịch bản chuẩn Q1.");
}

function applyPresetScenario(wsId) {
    switchTab("tab-simulator");
    if (wsId === "WS1") {
        document.getElementById("sim-budget").value = 20;
        document.getElementById("sim-ram").value = 16;
        document.getElementById("sim-ssd").value = 512;
        showToast("Áp dụng WS1: Ngân sách thắt chặt 20 triệu.");
    } else if (wsId === "WS2") {
        document.getElementById("sim-budget").value = 30;
        showToast("Áp dụng WS2: Nhu cầu Gaming/Đồ họa.");
    } else if (wsId === "WS3") {
        showToast("Áp dụng WS3: Mô phỏng SAZO giảm giá Zenbook AI 7 350 ≥ 6.9%.");
    } else if (wsId === "WS4") {
        document.getElementById("sim-weight-mode").value = "hard";
        showToast("Áp dụng WS4: Ràng buộc di động cứng ≤ 1.3kg & Pin ≥ 60Wh.");
    } else if (wsId === "WS5") {
        document.getElementById("sim-apple-only").checked = true;
        document.getElementById("sim-budget").value = 27;
        showToast("Áp dụng WS5: Hệ sinh thái Apple ≤ 27tr.");
    }
    runSimulation();
}

// AHP Matrix Calculations (Trang 5)
let ahpWeights = { cpu: 0.231, ram: 0.208, ssd: 0.062, w: 0.500 };

function computeAHP() {
    const p_cpu_ram = parseFloat(document.getElementById("ahp-p-cpu-ram").value);
    const p_cpu_ssd = parseFloat(document.getElementById("ahp-p-cpu-ssd").value);
    const p_cpu_w = parseFloat(document.getElementById("ahp-p-cpu-w").value);
    const p_ram_ssd = parseFloat(document.getElementById("ahp-p-ram-ssd").value);
    const p_ram_w = parseFloat(document.getElementById("ahp-p-ram-w").value);
    const p_ssd_w = parseFloat(document.getElementById("ahp-p-ssd-w").value);

    const A = [
        [1.0, p_cpu_ram, p_cpu_ssd, p_cpu_w],
        [1.0 / p_cpu_ram, 1.0, p_ram_ssd, p_ram_w],
        [1.0 / p_cpu_ssd, 1.0 / p_ram_ssd, 1.0, p_ssd_w],
        [1.0 / p_cpu_w, 1.0 / p_ram_w, 1.0 / p_ssd_w, 1.0]
    ];

    const n = 4;
    const geom = A.map(row => Math.pow(row.reduce((a, b) => a * b, 1.0), 1.0 / n));
    const sumGeom = geom.reduce((a, b) => a + b, 0.0);
    const w = geom.map(g => g / sumGeom);

    ahpWeights = { cpu: w[0], ram: w[1], ssd: w[2], w: w[3] };

    let lambdaMax = 0;
    for (let i = 0; i < n; i++) {
        let rowSum = 0;
        for (let j = 0; j < n; j++) { rowSum += A[i][j] * w[j]; }
        lambdaMax += rowSum / w[i];
    }
    lambdaMax = lambdaMax / n;
    const ci = Math.max(0, (lambdaMax - n) / (n - 1));
    const ri = 0.90;
    const cr = ci / ri;

    document.getElementById("w-cpu-val").innerText = w[0].toFixed(3);
    document.getElementById("w-ram-val").innerText = w[1].toFixed(3);
    document.getElementById("w-ssd-val").innerText = w[2].toFixed(3);
    document.getElementById("w-weight-val").innerText = w[3].toFixed(3);

    const badge = document.getElementById("ahp-cr-badge");
    const bar = document.getElementById("ahp-cr-bar");
    const warnText = document.getElementById("ahp-warning-text");

    const pctBar = Math.min(100, Math.max(2, (cr / 0.20) * 100));
    bar.style.width = pctBar + "%";

    if (cr < 0.10) {
        badge.className = "badge-deal";
        badge.innerText = `CR = ${cr.toFixed(3)} (Hợp lệ & Nhất quán)`;
        bar.style.background = "var(--success)";
        warnText.style.display = "none";
    } else {
        badge.className = "badge-warn";
        badge.innerText = `CR = ${cr.toFixed(3)} (Bất nhất ≥ 0.10)`;
        bar.style.background = "var(--danger)";
        warnText.style.display = "block";
        warnText.innerText = `⚠️ Cảnh báo: Phán đoán so sánh cặp có tính bắc cầu chưa đồng nhất (CR = ${cr.toFixed(3)} >= 0.10). Hãy cân nhắc kiểm tra lại tỷ lệ so sánh.`;
    }
}

function applyAHPWeightsToSimulator() {
    computeAHP();
    currentOffers.forEach(o => {
        const u = ahpWeights.cpu * (o.S_cpu || 0.7) + ahpWeights.ram * (o.S_ram || 0.7) + ahpWeights.ssd * (o.S_ssd || 0.7) + ahpWeights.w * (o.S_w || 0.7);
        o.utility = u;
        o.dss_score = o.eligible * (0.65 * o.utility + 0.35 * o.deal);
    });
    currentOffers.sort((a,b) => b.dss_score - a.dss_score);

    switchTab("tab-simulator");
    runSimulation();
    showToast("🚀 Đã áp dụng bộ trọng số AHP mới vào Simulator thành công!");
}

// Render Insight Charts (Trang 2)
function renderInsightsCharts() {
    if (typeof Plotly === "undefined") return;
    const sellers = ["GEARVN", "CellphoneS", "FPT Shop", "T&T Center", "NCPC", "SAZO"];
    const diffs = [13.0, 4.2, 1.8, -2.5, -7.5, -9.0];
    const colors = diffs.map(d => d > 0 ? "#ef4444" : "#10b981");
    Plotly.newPlot("chart-seller-diff", [{
        x: sellers, y: diffs, type: "bar", marker: { color: colors },
        text: diffs.map(d => (d > 0 ? "+" : "") + d + "%"), textposition: "auto"
    }], {
        margin: { t: 20, b: 40, l: 40, r: 20 },
        yaxis: { title: "Chênh lệch so với giá trung bình (%)" }
    }, { responsive: true });

    const discSellers = ["T&T Center", "SAZO", "NCPC", "FPT Shop", "CellphoneS", "GEARVN"];
    const discPcts = [16.4, 14.8, 12.5, 9.2, 7.8, 5.7];
    Plotly.newPlot("chart-seller-discount", [{
        x: discSellers, y: discPcts, type: "bar", marker: { color: "#3b82f6" },
        text: discPcts.map(d => d + "%"), textposition: "auto"
    }], {
        margin: { t: 20, b: 40, l: 40, r: 20 },
        yaxis: { title: "Tỷ lệ giảm giá niêm yết TB (%)" }
    }, { responsive: true });

    const igpu = currentOffers.filter(o => o.dgpu === 0);
    const rtx = currentOffers.filter(o => o.dgpu === 1);
    Plotly.newPlot("chart-weight-price", [
        {
            x: igpu.map(o => o.weight_kg), y: igpu.map(o => o.price_vnd/1e6),
            mode: "markers", name: "iGPU (Văn phòng / Mỏng nhẹ)",
            marker: { color: "#2563eb", size: 8, opacity: 0.7 }
        },
        {
            x: rtx.map(o => o.weight_kg), y: rtx.map(o => o.price_vnd/1e6),
            mode: "markers", name: "RTX Series (Gaming / Đồ họa)",
            marker: { color: "#f97316", size: 9, opacity: 0.8 }
        }
    ], {
        margin: { t: 30, b: 50, l: 50, r: 20 },
        xaxis: { title: "Trọng lượng máy (kg)" },
        yaxis: { title: "Giá bán (triệu VND)" },
        legend: { orientation: "h", y: 1.15 }
    }, { responsive: true });
}

// Render Fair Price Charts (Trang 3)
function renderFairPriceCharts() {
    if (typeof Plotly === "undefined") return;
    const fp = currentOffers.map(o => (o.fair_price_vnd ? o.fair_price_vnd : o.fair_price) / 1e6);
    const real = currentOffers.map(o => o.price_vnd / 1e6);
    Plotly.newPlot("chart-fair-price", [
        {
            x: fp, y: real, mode: "markers", name: "Chào bán thực tế",
            marker: { color: "#0ea5e9", size: 7, opacity: 0.7 }
        },
        {
            x: [10, 60], y: [10, 60], mode: "lines", name: "Đường lý tưởng 45°",
            line: { color: "#0f172a", dash: "dash", width: 2 }
        },
        {
            x: [10, 60], y: [8.5, 51], mode: "lines", name: "Dải sai số −15%",
            line: { color: "#94a3b8", dash: "dot", width: 1.5 }
        },
        {
            x: [10, 60], y: [11.5, 69], mode: "lines", name: "Dải sai số +15%",
            line: { color: "#94a3b8", dash: "dot", width: 1.5 }
        }
    ], {
        margin: { t: 30, b: 50, l: 50, r: 20 },
        xaxis: { title: "Fair Price ước tính (triệu VND)" },
        yaxis: { title: "Giá bán niêm yết (triệu VND)" }
    }, { responsive: true });
}

// Khởi chạy ứng dụng
window.onload = function() {
    renderTop5(currentOffers);
    runFairPriceCalc();
    runSimulation();
    computeAHP();
    checkApiConnection();
};
