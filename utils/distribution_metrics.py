import numpy as np
import ot
import torch
from scipy import linalg
from tqdm import tqdm
from utils.metrics import get_metric, compute_nearest_neighbors_in_batches


def w1(x, y, epsilon=0., b=None,  **kwargs):
    """Compute Optimal transport with L2 norm as base metric
        param x: (b1,d) shaped tensor
        param y: (b2,d) shaped tensor
    """
    base_metric = get_metric("L2")
    if b is None:
        C = base_metric(x, y, **kwargs)
    else:
        b = int(b)
        C = compute_nearest_neighbors_in_batches(x,y,base_metric, bx=b, by=b)
    OTPlan = _compute_ot_plan(C.detach().cpu().numpy(), float(epsilon))
    OTPlan = torch.from_numpy(OTPlan).to(C.device)
    W1 = torch.sum(OTPlan * C)
    return W1, {"W1-L2": W1}


def swd(x, y, num_proj=128, **kwargs):
    """
    Project samples to 1d and compute OT there with the sorting trick. Average over num_proj directions
    param x: (b1,d) shaped tensor
    param y: (b2,d) shaped tensor
    """
    num_proj = int(num_proj)
    assert (len(x.shape) == len(y.shape)) and x.shape[1] == y.shape[1]
    _, d = x.shape

    # Sample random normalized projections
    rand = torch.randn(d, num_proj).to(x.device)  # (slice_size**2*ch)
    rand = rand / torch.norm(rand, dim=0, keepdim=True)  # noramlize to unit directions

    # Project images
    projx = torch.mm(x, rand)
    projy = torch.mm(y, rand)

    projx, projy = _duplicate_to_match_lengths(projx.T, projy.T)

    # Sort and compute L1 loss
    projx, _ = torch.sort(projx, dim=1)
    projy, _ = torch.sort(projy, dim=1)

    SWD = (projx - projy).abs().mean() # This is same for L2 and L1 since in 1d: .pow(2).sum(1).sqrt() == .pow(2).sqrt() == .abs()

    return SWD, {"SWD": SWD}


def discrete_dual(x, y, n_steps=500, batch_size=None, lr=0.001, verbose=False, nnb=256, dist="L2"):
    """Solve the discrete dual OT problem with minibatches and SGD:
     Optimize n scalars (dual potentials) defining the dual formulation"""

    pbar = range(n_steps)
    if verbose:
        print(f"Optimizing duals: {x.shape}, {y.shape}")
        pbar = tqdm(pbar)

    if batch_size is None:
        batch_size = len(x)

    with torch.enable_grad():
        loss_func = get_metric(dist)
        psi = torch.zeros(len(x), requires_grad=True, device=x.device)
        opt_psi = torch.optim.Adam([psi], lr=lr)
        # scheduler = ReduceLROnPlateau(opt_psi, 'min', threshold=0.0001, patience=200)
        for _ in pbar:
            opt_psi.zero_grad()

            mini_batch = y[torch.randperm(len(y))[:batch_size]]

            phi, outputs_idx = _batch_NN(mini_batch, x, psi, nnb, loss_func)

            dual_estimate = torch.mean(phi) + torch.mean(psi)

            loss = -1 * dual_estimate  # maximize over psi
            loss.backward()
            opt_psi.step()
            # scheduler.step(dual_estimate)
            if verbose:
                pbar.set_description(f"dual estimate: {dual_estimate.item()}, LR: {opt_psi.param_groups[0]['lr']}")

        return dual_estimate, {"dual": dual_estimate.item()}


def fd(x, y):
    # TODO make differenctiable
    """Model each set with a MV Gaussian distribution and compute the OT between them (Frechet distance)
        param x: (b1,d) shaped tensor
        param y: (b2,d) shaped tensor
    """

    stats_x = torch.mean(x, 0).cpu().numpy(), np.cov(x.cpu().numpy(), rowvar=False)  # torch.matmul(x.T, x).cpu().numpy()
    stats_y = torch.mean(y, 0).cpu().numpy(), np.cov(y.cpu().numpy(), rowvar=False)  # torch.matmul(y.T, x).cpu().numpy()
    fd = _frechet_distance(stats_x, stats_y)
    return torch.tensor(fd), {'Frechet-distance': fd}


def _batch_NN(X, Y, f, b, dist_function):
    """
    For each x find the best index i s.t i = argmin_i(x,y_i)-f_i
    return the value and the argmin
    """
    NNs = torch.zeros(X.shape[0], dtype=torch.long, device=X.device)
    NN_dists = torch.zeros(X.shape[0], device=X.device)
    n_batches = len(X) // b
    for i in range(n_batches):
        s = slice(i * b,(i + 1) * b)
        dists = dist_function(X[s], Y) - f
        NN_dists[s], NNs[s] = dists.min(1)
    if len(X) % b != 0:
        s = slice(n_batches * b, len(X))
        dists = dist_function(X[s], Y) - f
        NN_dists[s], NNs[s] = dists.min(1)

    return NN_dists, NNs


def _frechet_distance(stats1, stats2, eps=1e-6):
    mean1, cov1 = stats1
    mean2, cov2 = stats2
    cov_sqrt, _ = linalg.sqrtm(cov1 @ cov2, disp=False)

    if not np.isfinite(cov_sqrt).all():
        print('product of cov matrices is singular')
        offset = np.eye(cov1.shape[0]) * eps
        cov_sqrt = linalg.sqrtm((cov1 + offset) @ (cov1 + offset))

    if np.iscomplexobj(cov_sqrt):
        if not np.allclose(np.diagonal(cov_sqrt).imag, 0, atol=1e-3):
            # m = np.max(np.abs(cov_sqrt.imag))
            # raise ValueError(f'Imaginary component {m}')
            return np.nan

        cov_sqrt = cov_sqrt.real

    mean_diff = mean1 - mean2
    mean_norm = mean_diff @ mean_diff

    trace = np.trace(cov1) + np.trace(cov2) - 2 * np.trace(cov_sqrt)

    fd = mean_norm + trace

    return fd


def _compute_ot_plan(C, epsilon=0):
    """Use POT to compute optimal transport between two emprical (uniforms) distriutaion with distance matrix C"""
    uniform_x = np.ones(C.shape[0]) / C.shape[0]
    uniform_y = np.ones(C.shape[1]) / C.shape[1]
    if epsilon > 0:
        OTplan = ot.sinkhorn(uniform_x, uniform_y, C, reg=epsilon)
    else:
        OTplan = ot.emd(uniform_x, uniform_y, C)
    return OTplan


def _duplicate_to_match_lengths(arr1, arr2):
    """
    Duplicates randomly selected entries from the smaller array to match its size to the bigger one
    :param arr1: (r, n) torch tensor
    :param arr2: (r, m) torch tensor
    :return: (r,max(n,m)) torch tensor
    """
    if arr1.shape[1] == arr2.shape[1]:
        return arr1, arr2
    elif arr1.shape[1] < arr2.shape[1]:
        tmp = arr1
        arr1 = arr2
        arr2 = tmp

    b = arr1.shape[1] // arr2.shape[1]
    arr2 = torch.cat([arr2] * b, dim=1)
    if arr1.shape[1] > arr2.shape[1]:
        indices = torch.randperm(arr2.shape[1])[:arr1.shape[1] - arr2.shape[1]]
        arr2 = torch.cat([arr2, arr2[:, indices]], dim=1)

    return arr1, arr2
