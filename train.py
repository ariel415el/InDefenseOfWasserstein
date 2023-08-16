import argparse

from time import time

import torch

from benchmarking.neural_metrics import InceptionMetrics
from utils.diffaug import DiffAugment
from utils.common import dump_images, compose_experiment_name
from utils.train_utils import copy_G_params, load_params, Prior, get_models_and_optimizers, parse_train_args
from losses import get_loss_function, calc_gradient_penalty
from utils.data import get_dataloader
from utils.logger import get_dir, PLTLogger, WandbLogger


def train_GAN(args):
    logger = (WandbLogger if args.wandb else PLTLogger)(args, plots_image_folder)
    prior = Prior(args.z_prior, args.z_dim)
    debug_fixed_noise = prior.sample(args.f_bs).to(device)
    debug_fixed_reals = next(iter(train_loader)).to(device)
    debug_all_reals = next(iter(full_batch_loader)).to(device)

    inception_metrics = InceptionMetrics([next(iter(train_loader)) for _ in range(args.fid_n_batches)], torch.device("cpu"))
    other_metrics = [
                get_loss_function("MiniBatchLoss-dist=w1"),
                # get_loss_function("MiniBatchPatchLoss-dist=w1-epsilon=10-p=11-s=4"),
                # get_loss_function("MiniBatchPatchLoss-dist=w1-epsilon=10-p=16-s=8"),
                # get_loss_function("MiniBatchPatchLoss-dist=w1-epsilon=10-p=48-s=16"),
                # LapSWD()
              ]

    loss_function = get_loss_function(args.loss_function)

    netG, netD, optimizerG, optimizerD, start_iteration = get_models_and_optimizers(args, device, saved_model_folder)

    avg_param_G = copy_G_params(netG)

    start = time()
    iteration = start_iteration
    while iteration < args.n_iterations:
        for real_images in train_loader:
            real_images = real_images.to(device)

            noise = prior.sample(args.f_bs).to(device)
            fake_images = netG(noise)

            real_images = DiffAugment(real_images, policy=args.augmentation)
            fake_images = DiffAugment(fake_images, policy=args.augmentation)

            # #####  1. train Discriminator #####
            if iteration % args.D_step_every == 0 and args.D_step_every > 0:
                Dloss, debug_Dlosses = loss_function.trainD(netD, real_images, fake_images)
                if args.gp_weight > 0:
                    gp, gradient_norm = calc_gradient_penalty(netD, real_images, fake_images)
                    debug_Dlosses['gradient_norm'] = gradient_norm
                    Dloss += args.gp_weight * gp
                    if "W1" in debug_Dlosses:
                        debug_Dlosses['normalized W1'] = (debug_Dlosses['W1'] /  gradient_norm) if  gradient_norm > 0 else 0
                netD.zero_grad()
                Dloss.backward()
                optimizerD.step()

                if args.weight_clipping is not None:
                    for p in netD.parameters():
                        p.data.clamp_(-args.weight_clipping, args.weight_clipping)

                logger.log(debug_Dlosses, step=iteration)

            # #####  2. train Generator #####
            if iteration % args.G_step_every == 0:
                if not args.no_fake_resample:
                    noise = prior.sample(args.f_bs).to(device)
                    fake_images = netG(noise)
                    fake_images = DiffAugment(fake_images, policy=args.augmentation)

                Gloss, debug_Glosses = loss_function.trainG(netD, real_images, fake_images)
                netG.zero_grad()
                Gloss.backward()
                optimizerG.step()
                logger.log(debug_Glosses, step=iteration)

            # Update avg weights
            for p, avg_p in zip(netG.parameters(), avg_param_G):
                avg_p.mul_(1 - args.avg_update_factor).add_(args.avg_update_factor * p.data)

            if iteration % 100 == 0:
                it_sec = max(1, iteration - start_iteration) / (time() - start)
                print(f"Iteration: {iteration}: it/sec: {it_sec:.1f}")
                logger.plot()

            if iteration % args.log_freq == 0:
                backup_para = copy_G_params(netG)
                load_params(netG, avg_param_G)

                evaluate(netG, netD, inception_metrics, other_metrics, debug_fixed_noise,
                         debug_fixed_reals, debug_all_reals, saved_image_folder, iteration, logger, args)
                fname = f"{saved_model_folder}/{'last' if not args.save_every else iteration}.pth"
                torch.save({"iteration": iteration, 'netG': netG.state_dict(), 'netD': netD.state_dict(),
                            "optimizerG":optimizerG.state_dict(), "optimizerD": optimizerD.state_dict()},
                           fname)

                load_params(netG, backup_para)

            iteration += 1


def evaluate(netG, netD, inception_metrics, other_metrics, fixed_noise, debug_fixed_reals,
             debug_all_reals, saved_image_folder, iteration, logger, args):
    netG.eval()
    netD.eval()
    start = time()
    with torch.no_grad():
        fixed_noise_fake_images = netG(fixed_noise)
        if args.D_step_every > 0 :
            D_fake = netD(fixed_noise_fake_images)
            D_real = netD(debug_fixed_reals)
            logger.log({'D_real': D_real.mean().item(),
                       'D_fake': D_fake.mean().item(),
                       }, step=iteration)

        if args.fid_n_batches > 0 and iteration % args.fid_freq == 0:
            fake_batches = [netG(torch.randn_like(fixed_noise).to(device)) for _ in range(args.fid_n_batches)]
            logger.log(inception_metrics(fake_batches), step=iteration)

        for metric in other_metrics:
            logger.log({
                f'{metric.name}_fixed_noise_gen_to_train': metric(fixed_noise_fake_images.cpu(), debug_all_reals.cpu()),
            }, step=iteration)

        dump_images(fixed_noise_fake_images,  f'{saved_image_folder}/{iteration}.png')
        if iteration == 0:
            dump_images(debug_fixed_reals, f'{saved_image_folder}/debug_fixed_reals.png')

    netG.train()
    netD.train()
    print(f"Evaluation finished in {time()-start} seconds")


if __name__ == "__main__":
    args = parse_train_args()

    device = torch.device(args.device)
    if args.device != 'cpu':
        print(f"Working on device: {torch.cuda.get_device_name(device)}")

    train_loader, _ = get_dataloader(args.data_path, args.im_size, args.r_bs, args.n_workers,
                                               val_percentage=0, gray_scale=args.gray_scale, center_crop=args.center_crop,
                                               load_to_memory=args.load_data_to_memory, limit_data=args.limit_data)

    data_size = len(train_loader.dataset)
    print(f"eval loader size {data_size}")
    full_batch_loader, _ = get_dataloader(args.data_path, args.im_size, data_size, args.n_workers,
                                               val_percentage=0, gray_scale=args.gray_scale, center_crop=args.center_crop,
                                               load_to_memory=args.load_data_to_memory, limit_data=len(train_loader.dataset))

    if args.r_bs == -1:
        args.r_bs = data_size

    args.name = compose_experiment_name(args)

    saved_model_folder, saved_image_folder, plots_image_folder = get_dir(args)

    train_GAN(args)



