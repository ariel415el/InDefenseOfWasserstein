from torch import nn


def block(in_feat, out_feat, normalize='in'):
    layers = [nn.Linear(in_feat, out_feat)]
    if normalize == "bn":
        layers.append(nn.BatchNorm1d(out_feat))
    elif normalize == "in":
        layers.append(nn.InstanceNorm1d(out_feat))
    layers.append(nn.LeakyReLU(0.2, inplace=True))
    return layers


class Generator(nn.Module):
    def __init__(self, z_dim, output_dim=64, nf=128, depth=4, normalize='none', **kwargs):
        super(Generator, self).__init__()
        self.output_dim = output_dim
        nf = int(nf)
        depth = int(depth)

        layers = block(z_dim, nf, normalize=normalize)

        for i in range(depth - 1):
            layers += block(nf, nf, normalize=normalize)

        layers += [nn.Linear(nf, 3*output_dim**2), nn.Tanh()]
        self.model = nn.Sequential(*layers)

    def forward(self, z):
        img = self.model(z)
        img = img.view(img.size(0), 3, self.output_dim, self.output_dim)
        return img


class Discriminator(nn.Module):
    def __init__(self, input_dim=64,  nf=128, depth=2, normalize='none', **kwargs):
        super(Discriminator, self).__init__()
        nf = int(nf)
        depth = int(depth)

        layers = block(3*input_dim**2, nf, normalize='none') # bn is not good for RGB values

        for i in range(depth - 1):
            layers += block(nf, nf, normalize=normalize)

        layers += [nn.Linear(nf, 1)]
        self.model = nn.Sequential(*layers)

    def forward(self, img):
        img_flat = img.view(img.size(0), -1)
        validity = self.model(img_flat).view(img.size(0))

        return validity
