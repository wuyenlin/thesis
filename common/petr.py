import os, math
import numpy as np
import torch, torchvision
import torch.nn as nn
from torchvision import transforms
from torchsummary import summary
try:
    from common.hrnet import *
    from common.pos_embed import *
except ModuleNotFoundError:
    from hrnet import *
    from pos_embed import *


class PatchEmbedding(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_channel=3, embed_dim=768):
        super().__init__()
        self.img_size = (img_size, img_size)
        self.patch_size = (patch_size, patch_size)
        self.H, self.W = self.img_size[0]/self.patch_size[0] , self.img_size[1]/self.patch_size[1] 
        self.num_patches = self.H * self.W
        self.in_channel = in_channel
        self.embed_dim = embed_dim

        self.proj = nn.Conv2d(in_channel, embed_dim, kernel_size=patch_size, stride=patch_size)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x):
        bs, c, h, w = x.shape
        x = self.proj(x).flatten(2).transpose(1,2)
        x = self.norm(x)
        H, W = h/self.patch_size[0] , w/self.patch_size[1]

        return x, (H,W)


class TransformerEncoder(nn.Module):
    """
    Pose Estimation with Transformer
    """
    def __init__(self, d_model=34, nhead=2, num_layers=6, 
                    num_joints_in=17, num_joints_out=17,
                    embed_dim=768, num_patches=196,
                    lift=True):
        super().__init__()
        if lift:
            print("INFO: Using default positional encoder")
            self.pe = PositionalEncoder(d_model)
        else:
            print("INFO: Using ViT positional embedding")
            self.pe = PostionalEmbedding(num_patches, embed_dim)
        encoder_layer = nn.TransformerEncoderLayer(d_model, nhead)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)

        self.lin_out = nn.Linear(d_model, num_joints_out*3)

        self.d_model = d_model
        self.nhead = nhead
        self.num_joints_in = num_joints_in
        self.num_joints_out = num_joints_out 

        self.lift = lift

    def forward(self, x):
        if self.lift:
            x = x.flatten(1).unsqueeze(1) #(bs,1,34)
            bs = x.size(0)
            x = self.pe(x)
            x = self.transformer(x)
            x = self.lin_out(x).squeeze(1)

        else:
        #(bs,196,768)
            bs = x.size(0)
            x = self.pe(x)
            x = self.transformer(x)
            x = self.lin_out(x[:,0])

        return x.reshape(bs, self.num_joints_out, 3)


class PETR(nn.Module):
    """
    PETR - Pose Estimation using TRansformer
    """
    def __init__(self, lift=True):
        super().__init__()
        
        self.lift = lift
        if self.lift:
            self.backbone = HRNet(32, 17, 0.1)
            pretrained_weight = "./weights/pose_hrnet_w32_256x192.pth"
            self.backbone.load_state_dict(torch.load(pretrained_weight))
            print("INFO: Pre-trained weights loaded from {}".format(pretrained_weight))
            self.transformer = TransformerEncoder(lift=self.lift)
        else:
            self.patch_embed = PatchEmbedding()
            self.transformer = TransformerEncoder(d_model=768,lift=self.lift)
                                    

    def forward(self, x):
        if self.lift:
            x = self.backbone(x)
            x = hmap_joints(x)
            out_x = self.transformer(x.cuda())
        else:
            x = self.patch_embed(x)
            out_x = self.transformer(x[0])

        return out_x


if __name__ == "__main__":
    transforms = transforms.Compose([
        transforms.Resize([224,224]),
        transforms.ToTensor(),  
        transforms.Normalize(mean=[0.5,0.5,0.5], std=[0.5,0.5,0.5]),
    ]) 
    model = PETR(lift=False)
    model = model.cuda()
    img = Image.open("dataset/S1/Seq1/imageSequence/video_8/frame006192.jpg")
    img = transforms(img)
    img = img.unsqueeze(0)
    print(img.shape)
    img = img.cuda()
    output = model(img)
    print(output.shape)