"""Train ILSVRC2017 Data using homemade scripts."""

import cv2
import os
import math
import tensorflow as tf
from multiprocessing import Process, Queue

import os
import sys
FILE_DIR = os.path.dirname(__file__)
sys.path.append(FILE_DIR + '/../')

import config as cfg
from img_dataset.ilsvrc2017_cls_multithread import ilsvrc_cls
from yolo2_nets.darknet import darknet19
from yolo2_nets.net_utils import get_ordered_ckpts
from utils.timer import Timer

slim = tf.contrib.slim


def get_validation_process(imdb, queue_in, queue_out):
    """Get validation dataset. Run in a child process."""
    while True:
        queue_in.get()
        images, labels = imdb.get()
        queue_out.put([images, labels])


imdb = ilsvrc_cls('train', data_aug=True, multithread=cfg.MULTITHREAD)
val_imdb = ilsvrc_cls('val', batch_size=64)
# set up child process for getting validation data
queue_in = Queue()
queue_out = Queue()
val_data_process = Process(target=get_validation_process,
                           args=(val_imdb, queue_in, queue_out))
val_data_process.start()
queue_in.put(True)  # start getting the first batch

CKPTS_DIR = cfg.get_ckpts_dir('darknet19', imdb.name)
TENSORBOARD_TRAIN_DIR, TENSORBOARD_VAL_DIR = cfg.get_output_tb_dir(
    'darknet19', imdb.name)


input_data = tf.placeholder(tf.float32, [None, 224, 224, 3])
label_data = tf.placeholder(tf.int32, None)
is_training = tf.placeholder(tf.bool)

logits = darknet19(input_data, is_training=is_training)
loss = tf.nn.sparse_softmax_cross_entropy_with_logits(
    labels=label_data, logits=logits)
loss = tf.reduce_mean(loss)

update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
with tf.control_dependencies(update_ops):
    # train_op = tf.train.AdamOptimizer(0.0005).minimize(loss)
    train_op = tf.train.MomentumOptimizer(0.001, 0.9).minimize(loss)

correct_pred = tf.equal(tf.cast(tf.argmax(logits, 1), tf.int32), label_data)
accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

tf.summary.scalar('loss', loss)
tf.summary.scalar('accuracy', accuracy)

######################
# Initialize Session #
######################
tfconfig = tf.ConfigProto(allow_soft_placement=True)
tfconfig.gpu_options.allow_growth = True
sess = tf.Session(config=tfconfig)

merged = tf.summary.merge_all()
train_writer = tf.summary.FileWriter(TENSORBOARD_TRAIN_DIR)
val_writer = tf.summary.FileWriter(TENSORBOARD_VAL_DIR)

# # initialize variables, assume all vars are new now
# init_op = tf.global_variables_initializer()
# sess.run(init_op)
# load previous models
ckpts = get_ordered_ckpts(sess, imdb, 'darknet19')
variables_to_restore = slim.get_variables_to_restore()

# # change optimizer
# print('Initializing variables for the new optimizer')
# optimzer_vars = [var for var in tf.global_variables()
#                  if "Momentum" in var.name]
# init_op = tf.variables_initializer(optimzer_vars)
# sess.run(init_op)
# for var in optimzer_vars:
#     if var in variables_to_restore:
#         variables_to_restore.remove(var)

print('Restorining model snapshots from {:s}'.format(ckpts[-1]))
old_saver = tf.train.Saver(variables_to_restore)
old_saver.restore(sess, str(ckpts[-1]))
print('Restored.')
fnames = ckpts[-1].split('_')
old_epoch = int(fnames[-1][:-5])
imdb.epoch = old_epoch + 1

# simple model saver
cur_saver = tf.train.Saver()

T = Timer()
for i in range(imdb.total_batch * 10 + 1):
    T.tic()
    images, labels = imdb.get()
    _, loss_value, acc_value, train_summary = sess.run(
        [train_op, loss, accuracy, merged], {input_data: images, label_data: labels, is_training: 1})
    _time = T.toc(average=False)

    print('epoch {:d}, iter {:d}/{:d}, training loss: {:.3}, training acc: {:.3}, take {:.2}s'
          .format(imdb.epoch, (i + 1) % imdb.total_batch,
                  imdb.total_batch, loss_value, acc_value, _time))

    if (i + 1) % 25 == 0:
        T.tic()
        val_images, val_labels = queue_out.get()
        val_loss_value, val_acc_value, val_summary = sess.run(
            [loss, accuracy, merged], {input_data: val_images, label_data: val_labels, is_training: 0})
        _val_time = T.toc(average=False)
        print('###validation loss: {:.3}, validation acc: {:.3}, take {:.2}s'
              .format(val_loss_value, val_acc_value, _val_time))
        queue_in.put(True)

        global_step = imdb.epoch * imdb.total_batch + (i % imdb.total_batch)
        train_writer.add_summary(train_summary, global_step)
        val_writer.add_summary(val_summary, global_step)

    if (i % (imdb.total_batch * 2) == 0):
        save_path = cur_saver.save(sess, os.path.join(
            CKPTS_DIR,
            cfg.TRAIN_SNAPSHOT_PREFIX + '_epoch_' + str(imdb.epoch - 1) + '.ckpt'))
        print("Model saved in file: %s" % save_path)

# terminate child processes
if cfg.MULTITHREAD:
    imdb.close_all_processes()
queue_in.cancel_join_thread()
queue_out.cancel_join_thread()
val_data_process.terminate()
