import os

##########
# Pathes #
##########
ROOT_DIR = os.path.dirname(__file__)

PASCAL_PATH = os.path.join(ROOT_DIR, 'data', 'VOCdevkit')
ILSVRC_PATH = os.path.join(ROOT_DIR, 'data', 'ILSVRC')

CACHE_PATH = os.path.join(ROOT_DIR, 'cache')

WEIGHTS_PATH = os.path.join(ROOT_DIR, 'weights')

CKPTS_PATH = os.path.join(ROOT_DIR, 'ckpts')


TRAIN_SNAPSHOT_PREFIX = 'train'

BATCH_SIZE = 64

IMAGE_SIZE = 224

S = 7

B = 2

FLIPPED = False

REBUILD = False


###########################
# Configuration Functions #
###########################
def get_output_tb_dir(network_name, imdb_name):
    """Return the directory where tensorflow summaries are placed.
    If the directory does not exist, it is created.

    A canonical path is built using the name from an imdb and a network
    (if not None).
    """
    outdir = os.path.abspath(os.path.join(
        ROOT_DIR, 'tensorboard', network_name, imdb_name))
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    return outdir


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
