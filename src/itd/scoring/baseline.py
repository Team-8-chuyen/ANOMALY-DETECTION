
import numpy as np


def _validate_matrix(X_train) -> np.ndarray:
    """Validate statistics input (SPEC-001 §4.2)."""
    try:
        matrix = np.asarray(X_train, dtype=float)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("X_train must contain numeric values") from error
    if matrix.ndim != 2 or not all(matrix.shape):
        raise ValueError("X_train must be a non-empty 2D array with features")
    if not np.isfinite(matrix).all():
        raise ValueError("X_train contains invalid values")
    return matrix


def fit_global_baseline(X_train):
    """
    Tính Global Baseline từ dữ liệu huấn luyện.

    X_train: Ma trận gồm các user-day và
             các đặc trưng hành vi.
    """
    X_train = _validate_matrix(X_train)

    global_mean = np.mean(X_train, axis=0)
    global_std = np.std(X_train, axis=0)

    return {
        "mean": global_mean,
        "std": global_std
    }

def fit_role_baselines(X_train, roles):
    """
    Tính chuẩn hành vi riêng cho từng chức vụ.
    Chỉ sử dụng dữ liệu Train.
    """
    X_train = _validate_matrix(X_train)
    try:
        roles = np.asarray(roles, dtype=object)
    except (ValueError, TypeError) as error:
        raise ValueError("roles must be a 1D sequence of strings") from error
    if roles.ndim != 1 or any(not isinstance(role, str) for role in roles):
        raise ValueError("roles must be a 1D sequence of strings")
    roles = np.asarray([role.strip() for role in roles])

    if len(X_train) != len(roles):
        raise ValueError("Number of rows and roles must match")

    role_baselines = {}

    for role in np.unique(roles):

        # UNKNOWN không được coi là một chức vụ
        if role == "UNKNOWN" or not role:
            continue

        # Chọn dữ liệu thuộc chức vụ này
        role_data = X_train[roles == role]

        role_baselines[str(role)] = {
            "mean": np.mean(role_data, axis=0),
            "std": np.std(role_data, axis=0),
            "n_samples": len(role_data)
        }

    return role_baselines

if __name__ == "__main__":

    # Dữ liệu giả lập: 3 nhân viên, 2 đặc trưng
    # Cột 1: Số email mỗi ngày
    # Cột 2: Số lần truy cập file mỗi ngày

    X_train = np.array([
        [10, 5],
        [20, 10],
        [30, 15]
    ])

    result = fit_global_baseline(X_train)

    print("Global Baseline:")
    print("Mean:", result["mean"])
    print("Standard Deviation:", result["std"])
