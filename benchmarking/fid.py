import numpy as np
from scipy import linalg


def frechet_distance(stats1, stats2, eps=1e-6):
    mean1, cov1 = stats1
    mean2, cov2 = stats2
    cov_sqrt, _ = linalg.sqrtm(cov1 @ cov2, disp=False)

    if not np.isfinite(cov_sqrt).all():
        print('product of cov matrices is singular')
        offset = np.eye(cov1.shape[0]) * eps
        cov_sqrt = linalg.sqrtm((cov1 + offset) @ (cov1 + offset))

    if np.iscomplexobj(cov_sqrt):
        if not np.allclose(np.diagonal(cov_sqrt).imag, 0, atol=1e-3):
            m = np.max(np.abs(cov_sqrt.imag))

            raise ValueError(f'Imaginary component {m}')

        cov_sqrt = cov_sqrt.real

    mean_diff = mean1 - mean2
    mean_norm = mean_diff @ mean_diff

    trace = np.trace(cov1) + np.trace(cov2) - 2 * np.trace(cov_sqrt)

    fid = mean_norm + trace

    return fid

