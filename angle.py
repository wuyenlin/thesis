#!/usr/bin/python3

from common.options import args_parser
from common.petra import *
from common.dataloader import *
from common.loss import *
from common.human import Human

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from tqdm import tqdm
import torch
import torch.nn as nn
from torchvision import transforms
import torch.optim as optim
from torch.utils.data import DataLoader, DistributedSampler
from time import time


transforms = transforms.Compose([
    transforms.Resize([256,256]),
    transforms.ToTensor(),  
    transforms.Normalize(mean=[0.5,0.5,0.5], std=[0.5,0.5,0.5]),
])


def train(start_epoch, epoch, train_loader, val_loader, model, device, optimizer, lr_scheduler):
    print("Training starts...")

    losses_3d_train = []
    losses_3d_valid = []

    for ep in tqdm(range(start_epoch, epoch)):
        start_time = time()
        epoch_loss_3d_train = 0.0
        N = 0
        model.train()
    # train
        for data in train_loader:
            _, images, _, inputs_3d = data
            inputs_3d = inputs_3d.to(device)
            images = images.to(device)

            optimizer.zero_grad()

            w, predicted_3d_pos = model(images)

            loss_3d_pos = new_mpjpe(predicted_3d_pos, inputs_3d, w)
            epoch_loss_3d_train += inputs_3d.shape[0]*inputs_3d.shape[1] * loss_3d_pos.item()
            N += inputs_3d.shape[0]*inputs_3d.shape[1]

            loss_total = loss_3d_pos
            loss_total.backward()

            optimizer.step()

        losses_3d_train.append(epoch_loss_3d_train / N)
    # val
        with torch.no_grad():
            model.load_state_dict(model.state_dict())
            model.eval()
            epoch_loss_3d_valid = 0.0
            N = 0

            for data in val_loader:
                _, images, _, inputs_3d = data
                inputs_3d = inputs_3d.to(device)
                images = images.to(device)

                optimizer.zero_grad()

                w, predicted_3d_pos = model(images)

                loss_3d_pos = new_mpjpe(predicted_3d_pos, inputs_3d, w)
                epoch_loss_3d_valid += inputs_3d.shape[0]*inputs_3d.shape[1] * loss_3d_pos.item()
                N += inputs_3d.shape[0]*inputs_3d.shape[1]

            losses_3d_valid.append(epoch_loss_3d_valid / N)

        lr_scheduler.step()
        elapsed = (time() - start_time)/60

        print('[%d] time %.2f 3d_train %f 3d_valid %f' % (
                ep + 1,
                elapsed,
                losses_3d_train[-1] * 1000,
                losses_3d_valid[-1] * 1000))

        if args.export_training_curves and ep > 3:
            plt.figure()
            epoch_x = np.arange(3, len(losses_3d_train)) + 1
            plt.plot(epoch_x, losses_3d_train[3:], '--', color='C0')
            plt.plot(epoch_x, losses_3d_valid[3:], color='C1')
            plt.legend(['3d train', '3d valid (eval)'])
            plt.ylabel('MPJPE (m)')
            plt.xlabel('Epoch')
            plt.xlim((3, epoch))
            plt.savefig('./angle_checkpoint/loss_3d.png')

            plt.close('all')

        if (ep)%5 == 0 and ep != 0:
            exp_name = "./angle_checkpoint/epoch_{}.bin".format(ep)
            torch.save({
                "epoch": ep,
                "lr_scheduler": lr_scheduler.state_dict(),
                "optimizer": optimizer.state_dict(),
                "model": model.state_dict(),
                "args": args,
            }, exp_name)
            print("Parameters saved to ", exp_name)

    print('Finished Training.')
    return losses_3d_train , losses_3d_valid


def evaluate(test_loader, model, device):
    print("Testing starts...")
    epoch_loss_3d_pos = 0.0

    with torch.no_grad():
        model.eval()
        N = 0
        for data in test_loader:
            _, images, _, inputs_3d = data
            inputs_3d = inputs_3d.to(device)
            images = images.to(device)

            _, predicted_3d_pos = model(images)
            error = mpjpe(predicted_3d_pos, inputs_3d)

            epoch_loss_3d_pos += inputs_3d.shape[0]*inputs_3d.shape[1] * error.item()
            N += inputs_3d.shape[0] * inputs_3d.shape[1]
            
            inputs = inputs_3d.cpu().numpy().reshape(-1, inputs_3d.shape[-2], inputs_3d.shape[-1])
            predicted_3d_pos = predicted_3d_pos.cpu().numpy().reshape(-1, inputs_3d.shape[-2], inputs_3d.shape[-1])



    e1 = (epoch_loss_3d_pos / N)*1000
    e2 = (epoch_loss_3d_pos_procrustes / N)*1000

    print('----------')
    print('Protocol #1 Error (MPJPE):', e1, 'mm')
    print('Protocol #2 Error (P-MPJPE):', e2, 'mm')
    print('----------')
    
    return e1, e2, ev


def main(args):

    device = torch.device(args.device)
    model = PETRA(device)
    print("INFO: Using PETRA")
    model = model.to(device)
    print("INFO: Using GPU device {}".format(torch.cuda.get_device_name(torch.cuda.current_device())))

    if args.distributed:
        gpus = list(range(torch.cuda.device_count()))
        model = nn.DataParallel(model, device_ids=gpus)
        print("INFO: Using {} GPUs.".format(torch.cuda.device_count()))

    print("INFO: Model loaded on {}. Using Lifting model to predict angles.".format(device))
    backbone_params = 0
    if args.lr_backbone == 0:
        print("INFO: Freezing HRNet")
        for param in model.backbone.parameters():
           param.requires_grad = False
           backbone_params += param.numel()

    model_params = 0
    for parameter in model.parameters():
        model_params += parameter.numel()
    if args.lr_backbone == 0:
        model_params -= backbone_params
    
    print("INFO: Trainable parameter count:", model_params, " (%.2f M)" %(model_params/1000000))

    if args.eval:
        test_dataset = Data(args.dataset, transforms, False)
        test_loader = DataLoader(test_dataset, batch_size=args.bs, shuffle=True, num_workers=args.num_workers, collate_fn=collate_fn)
        e1, e2, ev = evaluate(test_loader, model, device)
        return e1, e2, ev

    train_dataset = Data(args.dataset, transforms)
    train_loader = DataLoader(train_dataset, batch_size=args.bs, shuffle=True, num_workers=args.num_workers, drop_last=False, collate_fn=collate_fn)
    val_dataset = Data(args.dataset, transforms, False)
    val_loader = DataLoader(val_dataset, batch_size=args.bs, shuffle=False, num_workers=args.num_workers, drop_last=False, collate_fn=collate_fn)
    


    param_dicts = [
        {"params": [p for n, p in model.named_parameters() if "backbone" not in n and p.requires_grad]},
        {
            "params": [p for n, p in model.named_parameters() if "backbone" in n and p.requires_grad],
            "lr": args.lr_backbone,
        },
    ]

    optimizer = optim.Adam(param_dicts, lr=args.lr, weight_decay=args.weight_decay)

    lr_scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=args.lr_drop)

    if args.resume:
        checkpoint = torch.load(args.resume, map_location='cpu')
        model.load_state_dict(checkpoint['model'])

        if not args.eval and 'optimizer' in checkpoint and 'lr_scheduler' in checkpoint and 'epoch' in checkpoint:
            optimizer.load_state_dict(checkpoint['optimizer'])
            lr_scheduler.load_state_dict(checkpoint['lr_scheduler'])
            args.start_epoch = checkpoint['epoch'] + 1

    print("INFO: Using optimizer {}".format(optimizer))

    train_list, val_list = train(args.start_epoch, args.epoch, 
                                train_loader, val_loader, model, device,
                                optimizer, lr_scheduler)


if __name__ == "__main__":
    args = args_parser()
    main(args)