import argparse
import importlib

from utils.common import parse_classnames_and_kwargs
from models.model_utils.discriminator_ensamble import Ensemble, StochasticEnsemble


def get_models(args, device):
    model_name, kwargs = parse_classnames_and_kwargs(args.gen_arch, kwargs={"output_dim": args.im_size, "z_dim": args.z_dim})
    netG = importlib.import_module("models." + model_name).Generator(**kwargs)

    model_name, kwargs = parse_classnames_and_kwargs(args.disc_arch, kwargs={"input_dim": args.im_size})
    netD = importlib.import_module("models." + model_name).Discriminator(**kwargs)

    if args.spectral_normalization:
        from models.model_utils.spectral_normalization import make_model_spectral_normalized
        netD = make_model_spectral_normalized(netD)

    if args.ensemble_models != 1:
        if args.stochastic_ensemble:
            netD = StochasticEnsemble(netD, args.ensemble_models)
        else:
            netD = Ensemble(netD, args.ensemble_models)

    print(f"G params: {print_num_params(netG)}, D params: {print_num_params(netD)}", )

    return netG.to(device), netD.to(device)


def human_format(num):
    """
    :param num: A number to print in a nice readable way.
    :return: A string representing this number in a readable way (e.g. 1000 --> 1K).
    """
    magnitude = 0

    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0

    return '%.2f%s' % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])  # add more suffices if you need them


def print_num_params(model):
    # n = sum(p.nelement() * p.element_size() for p in model.parameters() if p.requires_grad)
    # n += sum(p.nelement() * p.element_size() for p in model.buffers() if p.requires_grad)
    n = sum(p.nelement() for p in model.parameters() if p.requires_grad)
    n += sum(p.nelement() for p in model.buffers() if p.requires_grad)
    return human_format(n)


if __name__ == '__main__':
    for arch_name, s in [('FC', 64), ("DCGAN-nf=32", 64), ('ResNet', 64),
                         ('FC', 128), ("DCGAN", 128),('ResNet', 128) , ("FastGAN", 128), ('StyleGAN', 128),
                         ('BagNet-rf=9', 64), ('BagNet-rf=9', 128)]:
        print(f"{arch_name}: {s}x{s}")

        try:
            model_name, kwargs = parse_classnames_and_kwargs(arch_name, kwargs={"output_dim": s, "z_dim": s})
            netG = importlib.import_module("models." + model_name).Generator(**kwargs)


            print("\t-G params (MB): ", print_num_params(netG))
        except Exception as e:
            pass
        model_name, kwargs = parse_classnames_and_kwargs(arch_name, kwargs={"input_dim": s})
        netD = importlib.import_module("models." + model_name).Discriminator(**kwargs)
        print("\t-D params (MB): ", print_num_params(netD))
