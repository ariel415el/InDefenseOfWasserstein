import os
import sys
import torch
from matplotlib import pyplot as plt
import numpy as np
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from losses.optimal_transport import MiniBatchLoss, MiniBatchPatchLoss
from scripts.experiments.experiment_utils import get_data, batch_to_image
from torchvision.transforms import transforms

COLORS =['r', 'g', 'b', 'k']


def main():
    """Compare batch of blurred images with increasing sigma to batch of sharp data
        Comparison is done with different metrics (W1, SWD) and on image and patch level
    """
    os.makedirs(output_dir, exist_ok=True)
    with torch.no_grad():
        data = get_data(data_path, im_size, c=c, center_crop=center_crop, gray_scale=gray_scale, flatten=False, limit_data=b+n_images).to(device)
        b1 = data[:b]
        data = data[-n_images:]

        names_and_batches = [
            ("sigma=0", b1),
            ("sigma=1", transforms.GaussianBlur(kernel_size=15, sigma=1)(b1)),
            ("sigma=2", transforms.GaussianBlur(kernel_size=15, sigma=2)(b1)),
            ("sigma=3", transforms.GaussianBlur(kernel_size=15, sigma=3)(b1)),
            ("sigma=4", transforms.GaussianBlur(kernel_size=15, sigma=4)(b1)),
        ]
        plot_images(names_and_batches)

        image_dists = {dist: [] for dist in dists}
        patch_dists = {dist: [] for dist in dists}

        for name, batch in names_and_batches:
            for dist in dists:
                print(name, dist)
                image_dists[dist].append(MiniBatchLoss(dist)(batch, data))
                patch_dists[dist].append(MiniBatchPatchLoss(dist, p=p, s=s)(batch, data))

        plot_per_level(names_and_batches, dists, image_dists, patch_dists)
        plot_per_level(names_and_batches, dists, image_dists, patch_dists, normalize=True)
        plot_per_dist(names_and_batches, dists, image_dists, patch_dists)


def plot_images(names_and_batches):
    """Plot the blurred images in all sigmas"""
    w = len(names_and_batches)
    fig, ax = plt.subplots(nrows=1, ncols=w, figsize=(w * size, size * 1.1))
    for i, (name, batch) in enumerate(names_and_batches):
        ax[i].imshow(batch_to_image(batch, im_size, c))
        ax[i].axis('off')
        ax[i].set_title(f"{name}:")

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'blurred_batches.png'))
    plt.clf()


def plot_per_level(names_and_batches, dists, image_dists, patch_dists, normalize=False):
    """Compare the plots of different metrics on the same level (Image/Patch)"""
    for dict, line_type in [(image_dists, '-'), (patch_dists, '--')]:
        plt.figure()
        for i, dist in enumerate(dists):
            n = len(dict[dist])
            label = dist if line_type == '-' else f"patch({p}-{s})-" + dist

            vals = np.array(dict[dist])
            if normalize:
                vals -= vals.min()
                vals /= vals.max()
            # vals += desired_mean

            plt.plot(range(len(dict[dist])), vals, line_type, label=label, alpha=0.75, color=COLORS[i])
            # plt.annotate(f"{dict[dist][-1]:.2f}", (n - 1, dict[dist][-1]), textcoords="offset points", xytext=(-2, 2), ha="center")

        plt.xticks(range(n), [x[0] for x in names_and_batches], rotation=0)
        plt.legend()
        plt.savefig(os.path.join(output_dir, f'blurred_plot{"" if line_type == "-" else f"-patch({p}-{s})"}{"_normalize" if normalize else ""}.png'))
        plt.clf()


def plot_per_dist(names_and_batches, dists, image_dists, patch_dists):
    """Compare the plots of different levels (Image/Patch) for each metric"""
    for i, dist in enumerate(dists):
        plt.figure()
        for dict, line_type in [(image_dists, '-'), (patch_dists, '--')]:
            n = len(image_dists[dist])
            label = dist if line_type == '-' else f"patch({p}-{s})-" + dist
            plt.plot(range(len(dict[dist])),dict[dist], line_type, label=label, alpha=0.75, color=COLORS[i])
            plt.annotate(f"{dict[dist][-1]:.2f}", (n - 1, dict[dist][-1]), textcoords="offset points", xytext=(-2, 2), ha="center")

        plt.xticks(range(n), [x[0] for x in names_and_batches], rotation=0)
        plt.legend()
        plt.savefig(os.path.join(output_dir, f'blurred_plot_{dist}.png'))
        plt.clf()


if __name__ == '__main__':
    device = torch.device('cpu')
    b = 64
    n_images = 10000
    im_size = 64
    size = 5
    dists = ["w1", "discrete_dual", 'swd']
    p = 8
    s = 4

    data_path = '/cs/labs/yweiss/ariel1/data/FFHQ/FFHQ'
    c = 3
    gray_scale = False
    center_crop = 80

    output_dir = os.path.join(os.path.dirname(__file__), "outputs", "compare_blured_batches")

    main()