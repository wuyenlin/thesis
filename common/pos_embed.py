import os, math
import numpy as np
import torch, torchvision
import torch.nn as nn
from torchvision import transforms
from torchsummary import summary

class PositionalEncoder(nn.Module):
    """
    Original PE from Attention is All You Need
    """
    def __init__(self, d_model, max_seq_len=200, dropout=0.1):
        super().__init__()
        self.d_model = d_model
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_seq_len, d_model)
        for pos in range(max_seq_len):
            for i in range(0, d_model, 2):
                pe[pos, i] = math.sin(pos / (10000 ** ((2 * i)/d_model)))
                pe[pos, i + 1] = math.cos(pos / (10000 ** ((2 * (i + 1))/d_model)))

        self.pe = pe
        if torch.cuda.is_available():
            self.pe = pe.cuda()
 
    def forward(self, x):
        bs, seq_len, d_model = x.size(0), x.size(1), x.size(2)
        x *= math.sqrt(d_model)
        pe = self.pe[:seq_len, :d_model]
        pe_all = pe.repeat(bs, 1, 1)

        assert x.shape == pe_all.shape, "{},{}".format(x.shape, pe_all.shape)
        x += pe_all
        return x


class PostionalEmbedding(nn.Module):
    """
    Positional embedding used in Vision Transformer (An Image is Worth 16x16 Words)
    """
    def __init__(self, num_patches, emb_dim, dropout=0.1):
        super().__init__()
        self.pos_embed = nn.Parameter(torch.randn(1, num_patches, emb_dim))
        self.dropout = nn.Dropout(dropout) if dropout>0 else None

    def forward(self, x):
        x += self.pos_embed
        if self.dropout:
            x = self.dropout(x)
        
        return x