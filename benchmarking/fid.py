import numpy as np
from scipy import linalg

from benchmarking.inception import InceptionV3


def calc_fid(sample_mean, sample_cov, real_mean, real_cov, eps=1e-6):
    cov_sqrt, _ = linalg.sqrtm(sample_cov @ real_cov, disp=False)

    if not np.isfinite(cov_sqrt).all():
        print('product of cov matrices is singular')
        offset = np.eye(sample_cov.shape[0]) * eps
        cov_sqrt = linalg.sqrtm((sample_cov + offset) @ (real_cov + offset))

    if np.iscomplexobj(cov_sqrt):
        if not np.allclose(np.diagonal(cov_sqrt).imag, 0, atol=1e-3):
            m = np.max(np.abs(cov_sqrt.imag))

            raise ValueError(f'Imaginary component {m}')

        cov_sqrt = cov_sqrt.real

    mean_diff = sample_mean - real_mean
    mean_norm = mean_diff @ mean_diff

    trace = np.trace(sample_cov) + np.trace(real_cov) - 2 * np.trace(cov_sqrt)

    fid = mean_norm + trace

    return fid


inception = InceptionV3([3], normalize_input=False)


def fid_loss(real_images, fake_images):
    global inception
    inception = inception.to(real_images.device)
    real_features = inception(real_images)[0].view(real_images.shape[0], -1).cpu().numpy()
    fake_features = inception(fake_images)[0].view(fake_images.shape[0], -1).cpu().numpy()

    fid = calc_fid(np.mean(fake_features, 0), np.cov(fake_features, rowvar=False),
                   np.mean(real_features, 0), np.cov(real_features, rowvar=False))
    return fid