import os
import numpy as np

##########
# Pathes #
##########
SRC_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(SRC_DIR, os.pardir))

PASCAL_PATH = os.path.join(ROOT_DIR, 'data', 'VOCdevkit')
ILSVRC_PATH = os.path.join(ROOT_DIR, 'data', 'ILSVRC')
FLOWERS_PATH = os.path.join(ROOT_DIR, 'data', 'TF_flowers')

CACHE_PATH = os.path.join(ROOT_DIR, 'cache')

WEIGHTS_PATH = os.path.join(ROOT_DIR, 'weights')

CKPTS_PATH = os.path.join(ROOT_DIR, 'ckpts')

TENSORBOARD_PATH = os.path.join(ROOT_DIR, 'tensorboard')


TRAIN_SNAPSHOT_PREFIX = 'train'

BATCH_SIZE = 48

IMAGE_SIZE = 224
RAND_CROP_UPBOUND = 292

# YOLO1 VOC settings
S = 7
B = 2
YOLO_GRID_OFFSET = np.array(range(S) * S * B)
YOLO_GRID_OFFSET = np.reshape(YOLO_GRID_OFFSET, (B, S, S))
YOLO_GRID_OFFSET = np.transpose(YOLO_GRID_OFFSET, (1, 2, 0))  # [Y,X,B]

LAMBDA_COORD = 5
LAMBDA_NOOBJ = 0.5

FLIPPED = False
REBUILD = False
MULTITHREAD = True

###########################
# Configuration Functions #
###########################
def get_output_tb_dir(network_name, imdb_name, val=True):
    """Return the directories where tensorflow summaries are placed.
    If the directory does not exist, it is created. 
    If val is False, the second item in the returned list is None.
    A canonical path is built using the name from an imdb and a network
    (if not None).
    """
    outdir = os.path.abspath(os.path.join(
        ROOT_DIR, 'tensorboard', network_name, imdb_name))
    traindir = os.path.join(outdir, 'train')
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    if not os.path.exists(traindir):
        os.makedirs(traindir)
    if val:
        valdir = os.path.join(outdir, 'val')
        if not os.path.exists(outdir):
            os.makedirs(valdir)
    else:
        valdir = None
    return traindir, valdir


def get_ckpts_dir(network_name, imdb_name):
    """Return the directory where experimental artifacts are placed.
    If the directory does not exist, it is created.

    A canonical path is built using the name from an imdb and a network
    (if not None).
    """
    outdir = os.path.abspath(os.path.join(
        ROOT_DIR, 'ckpts', network_name, imdb_name))
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    return outdir
