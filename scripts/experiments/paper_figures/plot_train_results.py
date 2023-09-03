import os
import pickle
import sys

import numpy as np
from PIL import Image
from matplotlib import pyplot as plt

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from experiment_utils import find_dir, find_last_file

COLORS=['r', 'g', 'b', 'c', 'm', 'y', 'k']


def plot(root, plot_name, titles_and_name_lists, plot_loss=None, s=4,  n=5):
    """
    s: base unit for the size of plot
    n: #images in row of displayed images
    h: Ratio of image height to plot height is (h-1)/h
    """
    width = len(titles_and_name_lists)
    if plot_loss == "common":
        width += 1
    h=2 if plot_loss == "separate" else 1
    fig, axes = plt.subplots(h, width, figsize=(width * s, h*s), squeeze=False, sharey='row' if plot_loss == "separate" else 'none')
    all_axs = []
    for i, (name, names_list, non_names) in enumerate(titles_and_name_lists):
        found_path = find_dir(root, names_list, non_names)
        if not found_path:
            continue
        dir = os.path.join(root, found_path)
        img_name = find_last_file(os.path.join(dir, "images"))
        images = os.path.join(dir, "images", img_name)
        images = np.array(Image.open(images))
        d = images.shape[0] // 2
        f = n * d // 2
        images = images[d - f:d + f, d - f:d + f]

        ax = axes[0, i]
        ax.imshow(images)
        ax.axis('off')

        plot = os.path.join(dir, "plots", "MiniBatchLoss-dist=w1_fixed_noise_gen_to_train.pkl")
        plot = pickle.load((open(plot, "rb")))

        if plot_loss is not None:
            ax.set_title(f"{name}", fontsize=4 * s)
            if plot_loss == "separate":
                ax2 = axes[-1, i]
                ax2.plot(np.arange(len(plot)), plot, color=COLORS[0], label=f"Image W1")
                ax2.annotate(f"{plot[-1]:.2f}", (len(plot)-1, plot[-1]), textcoords="offset points", xytext=(-2, 2), ha="center")

                names_and_plot_paths = [
                    # ("Image-swd", "MiniBatchLoss-dist=w1_fixed_noise_gen_to_train.pkl", COLORS[0], '-'),
                    ("Patch-8-swd", "MiniBatchPatchLoss-dist=swd-p=8-s=4_fixed_noise_gen_to_train.pkl", COLORS[1], '--'),
                    ("Patch-16-swd", "MiniBatchPatchLoss-dist=swd-p=16-s=8_fixed_noise_gen_to_train.pkl", COLORS[2], '--'),
                ]

                for j, (name, path, color, line_type) in enumerate(names_and_plot_paths):
                    patch_plot = os.path.join(dir, "plots", path)
                    patch_plot = pickle.load((open(patch_plot, "rb")))

                    ax2.plot(np.arange(len(patch_plot)), patch_plot, line_type, color=color, label=name)
                    ax2.annotate(f"{patch_plot[-1]:.4f}", (len(patch_plot) - 1, patch_plot[-1]), textcoords="offset points", xytext=(-2, 2), ha="center")

                all_axs.append(ax2)

                handles, labels = ax2.get_legend_handles_labels()
                fig.legend(handles, labels, loc='center', ncol=1+len(names_and_plot_paths), prop={'size': s*width})

            else:
                ax2 = axes[0, -1]
                ax2.plot(np.arange(len(plot)), plot, color=COLORS[i], label=f"{name}")
                plt.annotate(f"{plot[-1]:.2f}", (len(plot)-1, plot[-1]), textcoords="offset points", xytext=(-2, 2), ha="center")
                ax2.legend()

            ax2.set_yscale('log')
            ax2.set_ylabel(f"BatchW1")
        else:
            ax.set_title(f"{name}  W1: {plot[-1]:.3f}", fontsize=4 * s)


        plt.tight_layout()
        plt.savefig(os.path.join(root, plot_name))
        plt.cla()
