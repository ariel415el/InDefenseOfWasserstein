import subprocess
from time import sleep, strftime
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from sbatch_python import run_sbatch


def send_tasks(project_name, dataset, additional_params):
    hours = 8
    for gen_arch in ["Pixels --lrG 0.001", "FC-depth=3 --lrG 0.0001"]:
        base = f"python3 train.py  --data_path {dataset}  {additional_params}" \
               f" --load_data_to_memory --n_workers 0 --project_name {project_name} --z_prior const=64" \
               f"  --n_iterations 100000 " \
               f"--gen_arch {gen_arch} "

        # run_sbatch(base + f" --loss_function WGANLoss --gp_weight 10  --lrD 0.0001  --G_step_every 5 --disc_arch FC-depth=3",
        #            f"PixelWGAN-FC", hours)

        # run_sbatch(base + f" --loss_function WGANLoss --gp_weight 10 --lrD 0.001 --G_step_every 5 --disc_arch FC-df=512",
        #            f"PixelWGAN-FC-512", hours)

        run_sbatch(base + f" --loss_function WGANLoss --gp_weight 10 --lrD 0.001 --G_step_every 5 --disc_arch FC-df=1024",
                   f"PixelWGAN-FC-1024", hours)

        run_sbatch(base + f" --loss_function CtransformLoss --gp_weight 10 --lrD 0.0001 --G_step_every 5 --disc_arch FC-df=1024",
                   f"PixelCTGAN-FC-1024", hours)

        run_sbatch(base + f" --loss_function MiniBatchLoss-dist=w1 --D_step_every -1",
                   f"Pixel-W1", hours)

        # run_sbatch(base + f" --loss_function MiniBatchLoss-dist=sinkhorn-epsilon=100 --D_step_every -1",
        #            f"Pixel-sinkhorn100", hours)


if __name__ == '__main__':
    # send_tasks(project_name="discreteWGAN-1k",
    #            dataset='/cs/labs/yweiss/ariel1/data/FFHQ/FFHQ',
    #            additional_params=' --center_crop 90 --limit_data 1000')

    send_tasks(project_name="discreteWGAN-10k",
               dataset='/cs/labs/yweiss/ariel1/data/FFHQ/FFHQ',
               additional_params=' --center_crop 100 --limit_data 10000')