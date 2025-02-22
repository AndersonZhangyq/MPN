import numpy as np
import torch
import torch.nn.functional as F
from torch.autograd import Variable
from collections import OrderedDict
from .meta_prototype_3d import Meta_Prototype_3d
from .layers import conv3d, leakyrelu
from matplotlib import pyplot as plt
import pandas as pd
import seaborn as sns


class Encoder(torch.nn.Module):
    def __init__(self, t_length=5, n_channel=3):
        super(Encoder, self).__init__()

        def Basic(intInput, intOutput):
            return torch.nn.Sequential(
                torch.nn.Conv3d(in_channels=intInput,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False),
                torch.nn.Conv3d(in_channels=intOutput,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False))

        def Basic_(intInput, intOutput):
            return torch.nn.Sequential(
                torch.nn.Conv3d(in_channels=intInput,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1),
                torch.nn.LeakyReLU(inplace=False),
                torch.nn.Conv3d(in_channels=intOutput,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1),
            )

        self.moduleConv1 = Basic(n_channel, 32)
        self.modulePool1 = torch.nn.MaxPool3d(kernel_size=2, stride=2)

        self.moduleConv2 = Basic(32, 64)
        self.modulePool2 = torch.nn.MaxPool3d(kernel_size=2, stride=2)

        self.moduleConv3 = Basic(64, 128)
        self.modulePool3 = torch.nn.MaxPool3d(kernel_size=2, stride=2)

        self.moduleConv4 = Basic_(128, 256)

    def forward(self, x):

        tensorConv1 = self.moduleConv1(x)
        tensorPool1 = self.modulePool1(tensorConv1)

        tensorConv2 = self.moduleConv2(tensorPool1)
        tensorPool2 = self.modulePool2(tensorConv2)

        tensorConv3 = self.moduleConv3(tensorPool2)
        tensorPool3 = self.modulePool3(tensorConv3)

        tensorConv4 = self.moduleConv4(tensorPool3)

        return tensorConv4, tensorConv1, tensorConv2, tensorConv3


class Decoder_new(torch.nn.Module):
    def __init__(self, t_length=5, n_channel=3):
        super(Decoder_new, self).__init__()

        def Basic(intInput, intOutput):
            return torch.nn.Sequential(
                torch.nn.Conv3d(in_channels=intInput,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False),
                torch.nn.Conv3d(in_channels=intOutput,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False))

        def Upsample(nc, intOutput):
            return torch.nn.Sequential(
                torch.nn.ConvTranspose3d(in_channels=nc,
                                         out_channels=intOutput,
                                         kernel_size=3,
                                         stride=2,
                                         padding=1,
                                         output_padding=1),
                torch.nn.LeakyReLU(inplace=False))

        self.moduleConv = Basic(256, 256)
        self.moduleUpsample4 = Upsample(256, 128)

        self.moduleDeconv3 = Basic(256, 128)
        self.moduleUpsample3 = Upsample(128, 64)

        self.moduleDeconv2 = Basic(128, 64)
        self.moduleUpsample2 = Upsample(64, 32)

    def forward(self, x, skip1, skip2, skip3):

        tensorConv = self.moduleConv(x)

        tensorUpsample4 = self.moduleUpsample4(tensorConv)
        cat4 = torch.cat((skip3, tensorUpsample4), dim=1)

        tensorDeconv3 = self.moduleDeconv3(cat4)
        tensorUpsample3 = self.moduleUpsample3(tensorDeconv3)
        cat3 = torch.cat((skip2, tensorUpsample3), dim=1)

        tensorDeconv2 = self.moduleDeconv2(cat3)
        tensorUpsample2 = self.moduleUpsample2(tensorDeconv2)
        cat2 = torch.cat((skip1, tensorUpsample2), dim=1)

        return cat2


class convAE(torch.nn.Module):
    def __init__(self,
                 n_channel=3,
                 t_length=5,
                 proto_size=10,
                 feature_dim=512,
                 key_dim=512,
                 temp_update=0.1,
                 temp_gather=0.1,
                 need_act=False):
        super(convAE, self).__init__()

        def Outhead(intInput, intOutput, nc):
            return torch.nn.Sequential(
                torch.nn.Conv3d(in_channels=intInput,
                                out_channels=nc,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False),
                torch.nn.Conv3d(in_channels=nc,
                                out_channels=nc,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False),
                torch.nn.Conv3d(in_channels=nc,
                                out_channels=intOutput,
                                kernel_size=3,
                                stride=1,
                                padding=1), torch.nn.LeakyReLU(inplace=False))

        self.encoder = Encoder(t_length, n_channel)
        self.decoder = Decoder_new(t_length, n_channel)
        self.prototype = Meta_Prototype_3d(proto_size,
                                           feature_dim,
                                           key_dim,
                                           temp_update,
                                           temp_gather,
                                           need_act=need_act)
        self.need_act = need_act
        # output_head
        self.ohead = Outhead(64, n_channel, 32)
        self.temporal_head = torch.nn.Sequential(
            torch.nn.Conv3d(t_length - 1,
                            1,
                            kernel_size=(3, 1, 1),
                            stride=1,
                            padding=(1, 0, 0)), torch.nn.Tanh())

    def set_learnable_params(self, layers):
        for k, p in self.named_parameters():
            if any([k.startswith(l) for l in layers]):
                p.requires_grad = True
            else:
                p.requires_grad = False

    def get_learnable_params(self):
        params = OrderedDict()
        for k, p in self.named_parameters():
            if p.requires_grad:
                # print(k)
                params[k] = p
        return params

    def get_params(self, layers):
        params = OrderedDict()
        for k, p in self.named_parameters():
            if any([k.startswith(l) for l in layers]):
                # print(k)
                params[k] = p
        return params

    def forward(self, x, weights=None, train=True):

        fea, skip1, skip2, skip3 = self.encoder(x)
        new_fea = self.decoder(fea, skip1, skip2, skip3)

        new_fea = F.normalize(new_fea, dim=1)
        batch_size, c, t, h, w = new_fea.size()

        new_fea = new_fea.transpose(1, 2).reshape(batch_size * t, c, h, w)
        if train:
            updated_fea, keys, fea_loss, cst_loss, dis_loss = self.prototype(
                new_fea, new_fea, weights, train)
            updated_fea = updated_fea.reshape(batch_size, t, c, h,
                                              w).transpose(1, 2)
            if weights is None:
                output = self.ohead(updated_fea)
            else:
                x = conv3d(updated_fea,
                           weights['ohead.0.weight'],
                           weights['ohead.0.bias'],
                           stride=1,
                           padding=1)
                x = leakyrelu(x)
                x = conv3d(x,
                           weights['ohead.2.weight'],
                           weights['ohead.2.bias'],
                           stride=1,
                           padding=1)
                x = leakyrelu(x)
                x = conv3d(x,
                           weights['ohead.4.weight'],
                           weights['ohead.4.bias'],
                           stride=1,
                           padding=1)
            temporal_output = output.transpose(1, 2)
            temporal_output = self.temporal_head(temporal_output)
            temporal_output = temporal_output.squeeze(1)
            # return None, fea, None, keys, None, None, None

            return temporal_output, fea, updated_fea, keys, fea_loss, cst_loss, dis_loss

        # test
        else:
            ret = self.prototype(new_fea, new_fea, weights, train)
            if self.need_act:
                updated_fea, keys, query, fea_loss, act = ret
            else:
                updated_fea, keys, query, fea_loss = ret
            updated_fea = updated_fea.reshape(batch_size, t, c, h,
                                              w).transpose(1, 2)
            if weights is None:
                output = self.ohead(updated_fea)
            else:
                x = conv3d(updated_fea,
                           weights['ohead.0.weight'],
                           weights['ohead.0.bias'],
                           stride=1,
                           padding=1)
                x = leakyrelu(x)
                x = conv3d(x,
                           weights['ohead.2.weight'],
                           weights['ohead.2.bias'],
                           stride=1,
                           padding=1)
                x = leakyrelu(x)
                x = conv3d(x,
                           weights['ohead.4.weight'],
                           weights['ohead.4.bias'],
                           stride=1,
                           padding=1)
            temporal_output = output.transpose(1, 2)
            temporal_output = self.temporal_head(temporal_output)
            temporal_output = temporal_output.squeeze(1)

            if self.need_act:
                return temporal_output, fea_loss, act
            return temporal_output, fea_loss


def meta_update(model, model_weights, meta_init_grads, model_alpha,
                meta_alpha_grads, meta_init_optimizer, meta_alpha_optimizer):
    # Unpack the list of grad dicts
    # init_gradients = {k: sum(d[k] for d in meta_init_grads) for k in meta_init_grads[0].keys()}
    init_gradients = {
        k: (sum(d[k] for d in meta_init_grads) / len(meta_init_grads))
        for k in meta_init_grads[0].keys()
    }
    # alpha_gradients = {k: sum(d[k] for d in meta_alpha_grads) for k in meta_alpha_grads[0].keys()}
    alpha_gradients = {
        k: (sum(d[k] for d in meta_alpha_grads) / len(meta_init_grads))
        for k in meta_alpha_grads[0].keys()
    }

    # dummy variable to mimic forward and backward
    dummy_x = Variable(torch.Tensor(np.random.randn(1)),
                       requires_grad=False).cuda()

    # update meta_init(for initial weights)
    for k, init in model_weights.items():
        dummy_x = torch.sum(dummy_x * init)
    meta_init_optimizer.zero_grad()
    dummy_x.backward()
    for k, init in model_weights.items():
        init.grad = init_gradients[k]
    meta_init_optimizer.step()

    # update meta_alpha(for learning rate)
    dummy_y = Variable(torch.Tensor(np.random.randn(1)),
                       requires_grad=False).cuda()
    for k, alpha in model_alpha.items():
        dummy_y = torch.sum(dummy_y * alpha)
    meta_alpha_optimizer.zero_grad()
    dummy_y.backward()
    for k, alpha in model_alpha.items():
        alpha.grad = alpha_gradients[k]
    meta_alpha_optimizer.step()


def train_init(model, model_weights, model_alpha, loss_fn, img, lh_img, gt,
               lh_gt, idx, args):

    pred, _, _, _, fea_loss, _, dis_loss = model.forward(
        img, model_weights, True)

    loss_pixel = loss_fn(pred, gt)
    loss = args.loss_fea_reconstruct * fea_loss + args.loss_distinguish * dis_loss + args.loss_fra_reconstruct * loss_pixel

    grads = torch.autograd.grad(loss,
                                model_weights.values(),
                                create_graph=True)

    update_weights = OrderedDict(
        (name, param - torch.mul(meta_alpha, grad))
        for ((name, param), (_, meta_alpha),
             grad) in zip(model_weights.items(), model_alpha.items(), grads))

    lh_pred, _, _, _, lh_fea_loss, _, lh_dis_loss = model.forward(
        lh_img, update_weights, True)

    idx = idx + 1

    lh_loss_pixel = loss_fn(lh_pred, lh_gt)
    lh_loss = args.loss_fea_reconstruct * lh_fea_loss + args.loss_distinguish * lh_dis_loss + args.loss_fra_reconstruct * lh_loss_pixel

    grads_ = torch.autograd.grad(lh_loss,
                                 model_weights.values(),
                                 retain_graph=True)
    alpha_grads = torch.autograd.grad(lh_loss, model_alpha.values())
    meta_init_grads = {}
    meta_alpha_grads = {}
    count = 0
    for k, _ in model_weights.items():
        meta_init_grads[k] = grads_[count]
        meta_alpha_grads[k] = alpha_grads[count]
        count = count + 1
    return meta_init_grads, meta_alpha_grads, loss, lh_loss, idx


def test_init(model, model_weights, model_alpha, loss_fn, imgs, gts, args):
    update_weights = model_weights
    for j in range(args.test_iter):

        grad_list = []
        for k in range(imgs.shape[0]):
            pred, _, _, _, fea_loss, _, dis_loss = model.forward(
                imgs[k:k + 1], model_weights, True)

            loss_pixel = loss_fn(pred, gts[k:k + 1]).mean()
            loss = args.loss_fea_reconstruct * fea_loss + args.loss_distinguish * dis_loss + args.loss_fra_reconstruct * loss_pixel
            grads = torch.autograd.grad(loss, model_weights.values())
            grad_list.append(grads)

        k_grads = ()
        for i in range(len(grad_list[0])):
            grad_temp = grad_list[0][i]
            for k in range(1, len(grad_list)):
                grad_temp += grad_list[k][i]
            k_grads += (grad_temp / len(grad_list), )

        update_weights = OrderedDict(
            (name, param - torch.mul(meta_alpha, grad))
            for ((name, param), (_, meta_alpha), grad
                 ) in zip(model_weights.items(), model_alpha.items(), k_grads))
        model_weights = update_weights

    return update_weights


def test_ft(model, model_weights, model_alpha, loss_fn, img, gt, args):

    update_weights = model_weights
    for j in range(args.test_iter):
        pred, _, _, _, fea_loss, _, dis_loss = model.forward(
            img, model_weights, True)

        loss_pixel = loss_fn(pred, gt).mean()
        loss = args.loss_fea_reconstruct * fea_loss + args.loss_distinguish * dis_loss + args.loss_fra_reconstruct * loss_pixel

        grads = torch.autograd.grad(loss, model_weights.values())

        update_weights = OrderedDict(
            (name, param - torch.mul(meta_alpha, grad))
            for ((name, param), (_, meta_alpha), grad
                 ) in zip(model_weights.items(), model_alpha.items(), grads))

        model_weights = update_weights

    return update_weights


def dismap(x, name='pred'):

    x = x.data.cpu().numpy()
    x = x.mean(1)
    for j in range(x.shape[0]):
        plt.cla()
        y = x[j]
        df = pd.DataFrame(y)
        sns.heatmap(df)
        plt.savefig('results/dismap/{}_{}.png'.format(name, str(j)))
        plt.close()
    return True
