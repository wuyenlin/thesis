#!/usr/bin/python3
import torch
from torchvision import transforms
from PIL import Image
import matplotlib.pyplot as plt
from common.dataloader import *
from torch.utils.data import DataLoader
from common.peltra import PELTRA
from common.human import *



transforms = transforms.Compose([
    transforms.Resize([256,256]),
    transforms.ToTensor(),  
    transforms.Normalize(mean=[0.5,0.5,0.5], std=[0.5,0.5,0.5]),
]) 


bones = {
    "mpi": (
        (2,1), (1,0), (0,3), (3,4),  # spine + head
        (0,5), (5,6), (6,7), 
        (0,8), (8,9), (9,10), # arms
        (2,14), (11,12), (12,13),
        (2,11), (14,15), (15,16) # legs
    ),
    "h36m": (
        (0,7), (7,8), (8,9), (9,10),  # spine + head
        (8,14), (14,15), (15,16), 
        (8,11), (11,12), (12,13), # arms
        (0,1), (1,2), (2,3),
        (0,4), (4,5), (5,6) # legs
    )
}


def plot3d(ax, bones, output, dataset="mpi"):
    for p in output:
        ax.scatter(p[0], p[1], p[2], c="r", alpha=0.5)

    bones = bones[dataset]
    for index in bones:
        xS = (output[index[0]][0],output[index[1]][0])
        yS = (output[index[0]][1],output[index[1]][1])
        zS = (output[index[0]][2],output[index[1]][2])
        ax.plot(xS, yS, zS)
    ax.view_init(elev=-90, azim=-90)
    ax.set_xlim3d([-1.0, 1.0])
    ax.set_xlabel("X")
    ax.set_ylim3d([-1.0, 1.0])
    ax.set_ylabel("Y")
    ax.set_zlim3d([-1.0, 1.0])
    ax.set_zlabel("Z")


def viz(dataset="mpi", savefig=False):
    # train_npz = "./dataset/S1/Seq1/imageSequence/S1.npz"
    train_npz = "./h36m/data_h36m_frame_S1.npz"
    train_dataset = Data(train_npz, transforms, True)
    trainloader = DataLoader(train_dataset, batch_size=4, 
                        shuffle=True, num_workers=8, drop_last=True)
    print("data loaded!")
    dataiter = iter(trainloader)
    img_path, image, kpts, labels = dataiter.next()

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    net = PELTRA(device)
    # net.load_state_dict(torch.load("./peltra/ft_1_zero.bin")["model"])
    net.load_state_dict(torch.load("./peltra/ft_1_h36m.bin")["model"])
    net = net.cuda()
    net.eval()

    fig = plt.figure()
    for k in range(1,5):
        ax = fig.add_subplot(2, 4, k)
        plt.imshow(Image.open(img_path[k-1]))

        pts = kpts[k-1].unsqueeze(0).cuda()
        output = net(pts)
        h = Human(1.8, "cpu")
        output = h.update_pose(output.detach().numpy())

        ax = fig.add_subplot(2, 4, k+4, projection="3d")
        plot3d(ax, bones, output, dataset)

    plt.show()

    if savefig:
        plt.savefig("./checkpoint/this.svg", format="svg", dpi=1200)


if __name__ == "__main__":
    viz()
