import torch
from torch.nn import functional as F

from losses import get_ot_plan

class AdverserialFeatureMatchingLoss:
    def trainD(self, netD, real_data, fake_data):
        preds = torch.cat([netD(real_data), netD(fake_data.detach())], dim=0).to(real_data.device).unsqueeze(1)
        labels = torch.cat([torch.ones(len(real_data), 1), torch.zeros(len(fake_data), 1)], dim=0).to(real_data.device)
        Dloss = F.binary_cross_entropy_with_logits(preds, labels)
        return Dloss, {"Dloss": Dloss.item()}

    def trainG(self, netD, real_data, fake_data):
        real_features = netD.features(real_data).reshape(len(real_data), -1)
        fake_features = netD.features(fake_data).reshape(len(fake_data), -1)

        C = torch.mean((real_features[:, None] - fake_features[None, :]) ** 2, dim=-1)

        OTPlan = get_ot_plan(C.detach().cpu().numpy())
        OTPlan = torch.from_numpy(OTPlan).to(C.device)

        OT = torch.sum(OTPlan * C)

        return OT, {"OT": OT.item()}