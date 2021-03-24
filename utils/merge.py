import os, json, csv, sys
from numpy.linalg import norm
import numpy as np 
from tqdm import tqdm

def del_folder():
    for S in range(1,9):
        for seq in [1,2]:
            for vid in [0,1,2,4,5,6,7,8]:
                try:
                    path ="dataset/S{}/Seq{}/imageSequence/video_{}".format(S,seq,vid)
                    npz_path ="dataset/S{}/Seq{}/imageSequence/video_{}.npz".format(S,seq,vid)
                    os.system("rm -rf {}".format(path))
                    os.system("rm {}".format(npz_path))
                except FileNotFoundError:
                    pass

def merge_npz():
    merge_data = []
    for s in [1,2]:
        for k in [0,1,2,4,5,6,7,8]:
            npz = "dataset/S1/Seq{}/imageSequence/full_video_{}.npz".format(s,k)
            t = np.load(npz, allow_pickle=True)
            t = t['arr_0'].reshape(1,-1)
            merge_data.append(*t)
        np.savez_compressed("dataset/S1/Seq1/imageSequence/full_S1", merge_data)
    print("saved")

if __name__ == "__main__":
    merge_npz()