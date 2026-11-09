"""
test_ahp.py - Unit tests cho mô-đun AHP (Saaty Analytic Hierarchy Process)
Kiểm thử:
1. Tính toán vector trọng số riêng (Eigenvector method)
2. Tính toán ma trận chuẩn hóa trung bình nhân (Geometric mean)
3. Tính toán CI, CR và kiểm tra ngưỡng chấp nhận CR < 0.10
4. Xử lý trường hợp ma trận không nhất quán (CR >= 0.10) và gợi ý cặp cần chỉnh
"""
import pytest
import numpy as np
from laptopmatch_dss.model_subsystem.ahp import AHPAnalyzer

def test_ahp_consistent_matrix():
    """Kiểm tra ma trận so sánh cặp nhất quán (CR < 0.10)."""
    criteria = ["cpu", "ram", "ssd", "weight"]
    analyzer = AHPAnalyzer(criteria=criteria)

    # Ma trận so sánh cặp giả định thực tế
    matrix = np.array([
        [1.0,    1.0,    4.0,    0.5],
        [1.0,    1.0,    3.0,    0.4154],
        [0.25,   0.3333, 1.0,    0.1231],
        [2.0,    2.4073, 8.1235, 1.0]
    ])

    res = analyzer.calculate_weights(matrix, criteria=criteria, method="eigen")

    assert res["is_consistent"] is True, "Ma trận này phải nhất quán."
    assert res["consistency_ratio"] < 0.10, f"CR phải < 0.10, nhưng thực tế là {res['consistency_ratio']}"
    assert abs(sum(res["weights"].values()) - 1.0) < 1e-4, "Tổng trọng số phải bằng 1.0."

    # w_weight phải lớn nhất (khoảng 0.50)
    assert res["weights"]["weight"] > 0.45, "Trọng số cân nặng phải lớn nhất."

def test_ahp_inconsistent_matrix():
    """Kiểm tra ma trận cố tình tạo mâu thuẫn (bắc cầu sai: A > B, B > C, C > A) để kích hoạt cảnh báo CR >= 0.10."""
    criteria = ["cpu", "ram", "ssd"]
    analyzer = AHPAnalyzer(criteria=criteria)

    # A (cpu) gấp 5 B (ram), B gấp 5 C (ssd), nhưng C gấp 5 A (cpu) -> mâu thuẫn nặng
    inconsistent_matrix = np.array([
        [1.0,  5.0,  0.2],
        [0.2,  1.0,  5.0],
        [5.0,  0.2,  1.0]
    ])

    res = analyzer.calculate_weights(inconsistent_matrix, criteria=criteria)

    assert res["is_consistent"] is False, "Ma trận mâu thuẫn phải bị đánh dấu là không nhất quán."
    assert res["consistency_ratio"] >= 0.10, "CR phải >= 0.10 khi mâu thuẫn bắc cầu."
    assert res["warning"] is not None, "Phải có thông báo cảnh báo."
    assert len(res["inconsistency_hints"]) > 0, "Phải có gợi ý cặp tiêu chí gây mâu thuẫn."
