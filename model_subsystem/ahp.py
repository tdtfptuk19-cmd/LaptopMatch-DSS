"""
ahp.py - Mô-đun Analytic Hierarchy Process (AHP - Saaty)
Model Management Subsystem
Nhiệm vụ:
- Tiếp nhận ma trận so sánh cặp theo thang đo Saaty 1-9
- Tính toán vector trọng số ưu tiên (Eigenvector / Geometric Mean)
- Tính toán chỉ số nhất quán (CI) và tỷ số nhất quán (CR)
- Kiểm định tính nhất quán (CR < 0.10): cảnh báo/từ chối nếu vi phạm
- Trả về trọng số cá nhân hóa w_k để tích hợp vào Persona của DSS
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Bảng chỉ số ngẫu nhiên ngẫu nhiên (Random Index - RI) của Thomas L. Saaty (1980)
SAATY_RI = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.54,
    13: 1.56,
    14: 1.57,
    15: 1.59
}

class AHPAnalyzer:
    """
    Phân tích thứ bậc AHP để xác định trọng số đa tiêu chí khách quan và cá nhân hóa.
    """
    def __init__(self, criteria: Optional[List[str]] = None):
        self.criteria = criteria if criteria else ["cpu", "ram", "ssd", "w"]

    def create_empty_matrix(self, criteria: Optional[List[str]] = None) -> np.ndarray:
        """Tạo ma trận đơn vị ban đầu với đường chéo chính bằng 1."""
        crit = criteria if criteria else self.criteria
        n = len(crit)
        return np.eye(n, dtype=float)

    def validate_matrix(self, matrix: np.ndarray) -> bool:
        """Kiểm tra ma trận đối xứng nghịch đảo: a_ij * a_ji = 1 và a_ii = 1."""
        n = matrix.shape[0]
        if matrix.shape[0] != matrix.shape[1]:
            raise ValueError(f"Ma trận phải là ma trận vuông: kích thước hiện tại {matrix.shape}")
        
        for i in range(n):
            if not np.isclose(matrix[i, i], 1.0, atol=1e-5):
                raise ValueError(f"Phần tử đường chéo chính [{i}, {i}] phải bằng 1, giá trị: {matrix[i, i]}")
            for j in range(i + 1, n):
                if matrix[i, j] <= 0 or matrix[j, i] <= 0:
                    raise ValueError(f"Giá trị so sánh phải dương: a[{i},{j}]={matrix[i, j]}, a[{j},{i}]={matrix[j, i]}")
                if not np.isclose(matrix[i, j] * matrix[j, i], 1.0, atol=1e-4):
                    raise ValueError(f"Vi phạm tính nghịch đảo Saaty: a[{i},{j}] * a[{j},{i}] = {matrix[i, j] * matrix[j, i]} != 1")
        return True

    def calculate_weights(self, matrix: np.ndarray, criteria: Optional[List[str]] = None, method: str = "eigen") -> Dict[str, Any]:
        """
        Tính toán vector trọng số và chỉ số nhất quán.
        method:
        - 'eigen': Phương pháp vector riêng chính (Exact Principal Eigenvector của Saaty)
        - 'geometric': Phương pháp trung bình nhân hình học (Logarithmic Least Squares)
        """
        self.validate_matrix(matrix)
        crit = criteria if criteria else self.criteria
        n = len(crit)

        if matrix.shape[0] != n:
            raise ValueError(f"Số lượng tiêu chí ({n}) không khớp kích thước ma trận ({matrix.shape[0]})")

        if method == "eigen":
            # Tính bằng vector riêng tương ứng trị riêng lớn nhất
            eigvals, eigvecs = np.linalg.eig(matrix)
            max_idx = int(np.argmax(np.real(eigvals)))
            lambda_max = float(np.real(eigvals[max_idx]))
            weights = np.real(eigvecs[:, max_idx])
            weights = weights / np.sum(weights)
        else: # geometric mean
            geom_means = np.prod(matrix, axis=1) ** (1.0 / n)
            weights = geom_means / np.sum(geom_means)
            # Ước lượng lambda_max
            lambda_max = float(np.mean(np.dot(matrix, weights) / weights))

        # Đảm bảo trọng số dương
        weights = np.abs(weights)
        weights = weights / np.sum(weights)

        # Tính chỉ số nhất quán CI (Consistency Index)
        ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
        ci = max(0.0, ci) # tránh sai số làm tròn số học

        # Tính tỷ số nhất quán CR (Consistency Ratio)
        ri = SAATY_RI.get(n, 1.49)
        cr = (ci / ri) if ri > 0 else 0.0

        is_consistent = bool(cr < 0.10)

        # Tìm cặp tiêu chí có độ lệch nhất quán lớn nhất nếu CR >= 0.1
        inconsistency_hints = []
        if not is_consistent and n >= 3:
            max_deviation = 0.0
            worst_pair = (0, 1)
            for i in range(n):
                for j in range(i + 1, n):
                    ratio = weights[i] / weights[j]
                    dev = abs(matrix[i, j] - ratio) / ratio
                    if dev > max_deviation:
                        max_deviation = dev
                        worst_pair = (i, j)
            inconsistency_hints.append({
                "criterion_1": crit[worst_pair[0]],
                "criterion_2": crit[worst_pair[1]],
                "current_judgment": float(matrix[worst_pair[0], worst_pair[1]]),
                "recommended_value": round(float(weights[worst_pair[0]] / weights[worst_pair[1]]), 2)
            })

        result = {
            "is_consistent": is_consistent,
            "consistency_ratio": round(cr, 4),
            "consistency_index": round(ci, 4),
            "lambda_max": round(lambda_max, 4),
            "random_index": ri,
            "matrix_size": n,
            "weights": {crit[i]: round(float(weights[i]), 6) for i in range(n)},
            "method_used": method,
            "warning": None if is_consistent else f"Tỷ số nhất quán CR = {cr:.4f} >= 0.10. Cần điều chỉnh ma trận so sánh cặp.",
            "inconsistency_hints": inconsistency_hints
        }

        return result

    def build_matrix_from_pairs(self, criteria: List[str], comparisons: Dict[Tuple[str, str], float]) -> np.ndarray:
        """
        Xây dựng ma trận hoàn chỉnh từ danh sách các so sánh cặp:
        comparisons dạng: {('cpu', 'ram'): 3.0, ('cpu', 'w'): 0.5, ...}
        Nếu ('A', 'B') = 3.0 thì a[A, B] = 3.0 và a[B, A] = 1/3.
        """
        n = len(criteria)
        matrix = np.eye(n, dtype=float)
        idx_map = {c: i for i, c in enumerate(criteria)}

        for (c1, c2), val in comparisons.items():
            if c1 in idx_map and c2 in idx_map:
                i, j = idx_map[c1], idx_map[c2]
                matrix[i, j] = float(val)
                matrix[j, i] = 1.0 / float(val)

        return matrix
