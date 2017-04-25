"""Use pretained resnet50 on tensorflow to imitate YOLOv1"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np
import cv2
import xml.etree.ElementTree as ET

from tensorflow.python.ops import control_flow_ops
from slim_dir.datasets import dataset_factory
from slim_dir.deployment import model_deploy
from slim_dir.nets import nets_factory, resnet_v1, resnet_utils
from slim_dir.preprocessing import preprocessing_factory

slim = tf.contrib.slim

_CLASSES = ('aeroplane', 'bicycle', 'bird', 'boat',
            'bottle', 'bus', 'car', 'cat', 'chair',
            'cow', 'diningtable', 'dog', 'horse',
            'motorbike', 'person', 'pottedplant',
            'sheep', 'sofa', 'train', 'tvmonitor')
NUM_CLASS = 20
IMAGE_SIZE = 224
# TODO: may need to change 7 to S to add flexibility
S = 7
B = 2

_class_to_ind = dict(list(zip(_CLASSES, list(range(NUM_CLASS)))))

def load_pascal_annotation():
    """
    Load image and bounding boxes info from XML file in the PASCAL VOC
    format.
    """

    imname = 'testImg2.jpg'
    im = cv2.imread(imname)
    h_ratio = 1.0 * IMAGE_SIZE / im.shape[0]
    w_ratio = 1.0 * IMAGE_SIZE / im.shape[1]

    label = np.zeros((S, S, 25))
    filename = 'testImg2Anno.xml'
    tree = ET.parse(filename)
    objs = tree.findall('object')

    for obj in objs:
        bbox = obj.find('bndbox')
        # Make pixel indexes 0-based
        x1 = max(min((float(bbox.find('xmin').text) - 1) * w_ratio, IMAGE_SIZE - 1), 0)
        y1 = max(min((float(bbox.find('ymin').text) - 1) * h_ratio, IMAGE_SIZE - 1), 0)
        x2 = max(min((float(bbox.find('xmax').text) - 1) * w_ratio, IMAGE_SIZE - 1), 0)
        y2 = max(min((float(bbox.find('ymax').text) - 1) * h_ratio, IMAGE_SIZE - 1), 0)
        cls_ind = _class_to_ind[obj.find('name').text.lower().strip()]
        boxes = [(x2 + x1) / 2.0, (y2 + y1) / 2.0, x2 - x1, y2 - y1]
        x_ind = int(boxes[0] * S / IMAGE_SIZE)
        y_ind = int(boxes[1] * S / IMAGE_SIZE)
        if label[y_ind, x_ind, 0] == 1:
            continue
        label[y_ind, x_ind, 0] = 1
        label[y_ind, x_ind, 1:5] = boxes
        label[y_ind, x_ind, 5 + cls_ind] = 1

    return label

# read in one image to test the flow of the network
# PIXEL_MEANS = np.array([[[102.9801, 115.9465, 122.7717]]])
im = cv2.imread('testImg2.jpg')
im = im.astype(np.float32, copy=False)
im = (im / 255.0) * 2.0 - 1.0
# im_shape = im.shape
# im_size_min = np.min(im_shape[0:2])
# im_size_max = np.max(im_shape[0:2])
im = cv2.resize(im, (IMAGE_SIZE, IMAGE_SIZE))
image = im.reshape([1, IMAGE_SIZE, IMAGE_SIZE, 3])
label = load_pascal_annotation()
label = label.reshape([1, S, S, 5+NUM_CLASS])


# ALPHA = 0.1
LAMBDA_COORD = 5
LAMBDA_NOOBJ = 0.5
BATCH_SIZE = 1
OFFSET = np.array(range(7) * 7 * B)
OFFSET = np.reshape(OFFSET, (B, 7, 7))
OFFSET = np.transpose(OFFSET, (1,2,0)) #[Y,X,B]

x = tf.placeholder(tf.float32,[None, 224, 224, 3])
labels = tf.placeholder(tf.float32, [None, 7, 7, 5 + NUM_CLASS])

def resnet_v1_50(inputs,
                 num_classes=None,
                 is_training=True,
                 global_pool=False,
                 output_stride=None,
                 reuse=None,
                 scope='resnet_v1_50'):
  """ResNet-50 model of [1]. See resnet_v1() for arg and return description."""
  blocks = [
      resnet_utils.Block(
          'block1', resnet_v1.bottleneck, [(256, 64, 1)] * 2 + [(256, 64, 2)]),
      resnet_utils.Block(
          'block2', resnet_v1.bottleneck, [(512, 128, 1)] * 3 + [(512, 128, 2)]),
      resnet_utils.Block(
          'block3', resnet_v1.bottleneck, [(1024, 256, 1)] * 5 + [(1024, 256, 2)]),
      resnet_utils.Block(
          'block4', resnet_v1.bottleneck, [(2048, 512, 1)] * 3)
  ]
  return resnet_v1.resnet_v1(inputs, blocks, num_classes, is_training,
                    global_pool=global_pool, output_stride=output_stride,
                    include_root_block=True, spatial_squeeze=False, reuse=reuse,
                    scope=scope)


def get_iou(boxes1, boxes2, scope='iou'):
    """calculate IOUs between boxes1 and boxes2.
    Args:
        boxes1: 5-D tensor [BATCH_SIZE, S, S, B, 4] with last dimension: (x_center, y_center, w, h)
        boxes2: 5-D tensor [BATCH_SIZE, S, S, B, 4] with last dimension: (x_center, y_center, w, h)
    Return:
        iou: 4-D tensor [BATCH_SIZE, S, S, B]
    """
    with tf.variable_scope(scope):
        boxes1 = tf.stack([boxes1[:, :, :, :, 0] - boxes1[:, :, :, :, 2] / 2.0,
                            boxes1[:, :, :, :, 1] - boxes1[:, :, :, :, 3] / 2.0,
                            boxes1[:, :, :, :, 0] + boxes1[:, :, :, :, 2] / 2.0,
                            boxes1[:, :, :, :, 1] + boxes1[:, :, :, :, 3] / 2.0])
        boxes1 = tf.transpose(boxes1, [1, 2, 3, 4, 0])

        boxes2 = tf.stack([boxes2[:, :, :, :, 0] - boxes2[:, :, :, :, 2] / 2.0,
                            boxes2[:, :, :, :, 1] - boxes2[:, :, :, :, 3] / 2.0,
                            boxes2[:, :, :, :, 0] + boxes2[:, :, :, :, 2] / 2.0,
                            boxes2[:, :, :, :, 1] + boxes2[:, :, :, :, 3] / 2.0])
        boxes2 = tf.transpose(boxes2, [1, 2, 3, 4, 0])

        # calculate the left up point & right down point
        lu = tf.maximum(boxes1[:, :, :, :, :2], boxes2[:, :, :, :, :2])
        rd = tf.minimum(boxes1[:, :, :, :, 2:], boxes2[:, :, :, :, 2:])

        # intersection
        intersection = tf.maximum(0.0, rd - lu)
        inter_square = intersection[:, :, :, :, 0] * intersection[:, :, :, :, 1]

        # calculate the boxs1 square and boxs2 square
        square1 = (boxes1[:, :, :, :, 2] - boxes1[:, :, :, :, 0]) * \
            (boxes1[:, :, :, :, 3] - boxes1[:, :, :, :, 1])
        square2 = (boxes2[:, :, :, :, 2] - boxes2[:, :, :, :, 0]) * \
            (boxes2[:, :, :, :, 3] - boxes2[:, :, :, :, 1])

        union_square = tf.maximum(square1 + square2 - inter_square, 1e-10)

    return tf.clip_by_value(inter_square / union_square, 0.0, 1.0)


def get_loss(net, labels, scope='loss_layer'):
    """Create loss from the last fc layer.
    
    Args:
        net: the last fc layer reshaped to (BATCH_SIZE, 7, 7, 5B+NUM_CLASS).
        lables: the ground truth of shape (BATCH_SIZE, 7, 7, 5+NUMCLASS) with the following content:
                lables[:,:,:,0] : ground truth of responsibility of the predictor
                lables[:,:,:,1:5] : ground truth bounding box coordinates
                labels[:,:,:,5:] : ground truth classes

    Return:
        loss: class loss + object loss + noobject loss + coordinate loss
              with shape (BATCH_SIZE)
    """

    with tf.variable_scope(scope):
        predict_classes = net[:, :, :, :NUM_CLASS]
        # confidence is defined as Pr(Object) * IOU
        predict_confidence = net[:, :, :, NUM_CLASS:NUM_CLASS+B]
        # predict_boxes has last dimenion has [x, y, w, h] * B
        # where (x, y) "represent the center of the box relative to the bounds of the grid cell"
        predict_boxes = tf.reshape(net[:, :, :, NUM_CLASS+B:], [BATCH_SIZE, S, S, B, 4])

        ########################
        # calculate class loss #
        ########################
        responsible =  tf.reshape(labels[:, :, :, 0], [BATCH_SIZE, S, S, 1]) # [BATCH_SIZE, S, S]
        classes = labels[:, :, :, 5:]

        class_delta = responsible * (predict_classes - classes) # [:,S,S,NUM_CLASS]
        class_loss = tf.reduce_mean(tf.reduce_sum(tf.square(class_delta), axis=[1, 2, 3]), name='class_loss')

        #############################
        # calculate coordinate loss #
        #############################
        # TODO: need to make the ground truth labels last dimension [x, y, w, h]
        # with the same rule as predict_boxes
        gt_boxes = tf.reshape(labels[:, :, :, 1:5], [BATCH_SIZE, S, S, 1, 4])
        gt_boxes = tf.tile(gt_boxes, [1, 1, 1, B, 1]) / float(IMAGE_SIZE)

        # add offsets to the predicted box and ground truth box coordinates to get absolute coordinates between 0 and 1
        offset = tf.constant(OFFSET, dtype=tf.float32)
        offset = tf.reshape(offset, [1, 7, 7, B])
        offset = tf.tile(offset, [BATCH_SIZE, 1, 1, 1])
        predict_xs = predict_boxes[:, :, :, :, 0] + (offset / 7.0)
        gt_xs = gt_boxes[:, :, :, :, 0] + (offset / 7.0)
        offset = tf.transpose(offset, (0, 2, 1, 3))
        predict_ys = predict_boxes[:, :, :, :, 1] + (offset / 7.0)
        gt_ys = gt_boxes[:, :, :, :, 1] + (offset / 7.0)
        predict_ws = predict_boxes[:, :, :, :, 2]
        gt_ws = gt_boxes[:, :, :, :, 2]
        predict_hs = predict_boxes[:, :, :, :, 3]
        gt_hs = gt_boxes[:, :, :, :, 3]
        predict_boxes_offset = tf.stack([predict_xs, predict_ys, predict_ws, predict_hs], axis=4)
        gt_boxes_offset = tf.stack([gt_xs, gt_ys, gt_ws, gt_hs], axis=4)
        

        # calculate IOUs
        ious = get_iou(predict_boxes_offset, gt_boxes_offset)
        
        # calculate object masks and nonobject masks tensor [BATCH_SIZE, S, S, B]
        object_mask = tf.reduce_max(ious, 3, keep_dims=True)
        object_mask = tf.cast((ious >= object_mask), tf.float32) * responsible
        noobject_mask = tf.ones_like(object_mask, dtype=tf.float32) - object_mask

        # coordinate loss
        coord_mask = tf.expand_dims(object_mask, 4)
        boxes_delta_xs = predict_boxes[:, :, :, :, 0] - gt_boxes[:, :, :, :, 0]
        boxes_delta_ys = predict_boxes[:, :, :, :, 1] - gt_boxes[:, :, :, :, 1]
        boxes_delta_ws = tf.sqrt(predict_boxes[:, :, :, :, 2]) - tf.sqrt(gt_boxes[:, :, :, :, 2])
        boxes_delta_hs = tf.sqrt(predict_boxes[:, :, :, :, 3]) - tf.sqrt(gt_boxes[:, :, :, :, 3])
        boxes_delta = tf.stack([boxes_delta_xs, boxes_delta_ys, boxes_delta_ws, boxes_delta_hs], axis=4)
        boxes_delta = coord_mask * boxes_delta
        coord_loss = tf.reduce_mean(tf.reduce_sum(tf.square(boxes_delta), axis=[1, 2, 3, 4]), name='coord_loss') * LAMBDA_COORD

        #########################
        # calculate object loss #
        #########################
        # object loss
        object_delta = object_mask * (predict_confidence - ious)
        object_loss = tf.reduce_mean(tf.reduce_sum(tf.square(object_delta), axis=[1, 2, 3]), name='object_loss')
        # noobject loss
        noobject_delta = noobject_mask * predict_confidence
        noobject_loss = tf.reduce_mean(tf.reduce_sum(tf.square(noobject_delta), axis=[1, 2, 3]), name='noobject_loss') * LAMBDA_NOOBJ

        tf.summary.scalar('class_loss', class_loss)
        tf.summary.scalar('object_loss', object_loss)
        tf.summary.scalar('noobject_loss', noobject_loss)
        tf.summary.scalar('coord_loss', coord_loss)

        tf.summary.histogram('boxes_delta_x', boxes_delta_xs)
        tf.summary.histogram('boxes_delta_y', boxes_delta_ys)
        tf.summary.histogram('boxes_delta_w', boxes_delta_ws)
        tf.summary.histogram('boxes_delta_h', boxes_delta_hs)
        tf.summary.histogram('iou', ious)

    return class_loss + object_loss + noobject_loss + coord_loss


# get the right arg_scope in order to load weights
with slim.arg_scope(resnet_v1.resnet_arg_scope()):
    # net is shape [batch_size, 7, 7, 2048] if input size is 244 x 244
    net, end_points = resnet_v1_50(x)

net = slim.flatten(net)

fcnet = slim.fully_connected(net, 4096, scope='yolo_fc1')

fcnet = tf.nn.dropout(fcnet, 0.5)

# in this case 7x7x30
fcnet = slim.fully_connected(net, 7*7*(5*B+NUM_CLASS), scope='yolo_fc2')

grid_net = tf.reshape(fcnet,[-1,7,7,(5*B+NUM_CLASS)])

loss = get_loss(grid_net, labels)

# get all variable names
# variable_names = [n.name for n in tf.get_default_graph().as_graph_def().node]

# get tensor by name
# t = tf.get_default_graph().get_tensor_by_name("tensor_name")

# get variables by scope
# vars_in_scope = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='scope_name')

# op to initialized variables that does not have pretrained weights
uninit_vars = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='yolo_fc1') \
              + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='yolo_fc2') \
              + tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='loss_layer')
init_op = tf.variables_initializer(uninit_vars)


########op restore all the pretrained variables###########
# Restore only the convolutional layers:
variables_to_restore = slim.get_variables_to_restore(exclude=['yolo_fc1', 'yolo_fc2'])
saver = tf.train.Saver(variables_to_restore)

with tf.Session() as sess:
    sess.run(init_op)
  
    saver.restore(sess, '/Users/wenxichen/Desktop/TensorFlow/ckpts/resnet_v1_50.ckpt')

    loss_value = sess.run([loss], {x:image, labels:label})