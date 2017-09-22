import keras
import keras_retinanet

class Anchors(keras.layers.Layer):
	def __init__(self, anchor_size, stride, *args, **kwargs):
		self.anchor_size = anchor_size
		self.stride      = stride
		super(Anchors, self).__init__(*args, **kwargs)

	def call(self, inputs, **kwargs):
		features_shape = inputs

		# generate proposals from bbox deltas and shifted anchors
		anchors = keras_retinanet.backend.anchor(base_size=self.anchor_size)
		anchors = keras_retinanet.backend.shift(features_shape, self.stride, anchors)
		anchors = keras.backend.expand_dims(anchors, axis=0)

		return anchors

	def compute_output_shape(self, input_shape):
		return (None, 4)

	def get_config(self):
		return {
			'anchor_size': self.anchor_size,
			'stride'     : self.stride,
		}

class TensorReshape(keras.layers.Layer):
	""" Nearly identical to keras.layers.Reshape, but allows reshaping tensors of unknown shape.

	# Arguments
		target_shape: Target shape of the input.
	"""
	def __init__(self, target_shape, *args, **kwargs):
		self.target_shape = tuple(target_shape)
		super(TensorReshape, self).__init__(*args, **kwargs)

	def call(self, inputs, **kwargs):
		return keras.backend.reshape(inputs, (keras.backend.shape(inputs)[0],) + self.target_shape)

	def compute_output_shape(self, input_shape):
		return (input_shape[0],) + self.target_shape

	def get_config(self):
		return { 'target_shape': self.target_shape }

class Dimensions(keras.layers.Layer):
	def call(self, inputs, **kwargs):
		return keras.backend.shape(inputs)[1:3]

	def compute_output_shape(self, input_shape):
		return (2,)

class NonMaximumSuppression(keras.layers.Layer):
	def __init__(self, num_classes, nms_threshold=0.4, max_boxes=300, *args, **kwargs):
		self.num_classes   = num_classes
		self.nms_threshold = nms_threshold
		self.max_boxes     = max_boxes
		super(NonMaximumSuppression, self).__init__(*args, **kwargs)

	def call(self, inputs, **kwargs):
		boxes, classification = inputs

		boxes          = keras.backend.reshape(boxes, (-1, 4))
		classification = keras.backend.reshape(classification, (-1, self.num_classes))

		scores = keras.backend.max(classification, axis=1)
		labels = keras.backend.argmax(classification, axis=1)
		indices = keras_retinanet.backend.where(keras.backend.greater(labels, 0))

		boxes          = keras_retinanet.backend.gather_nd(boxes, indices)
		scores         = keras_retinanet.backend.gather_nd(scores, indices)
		classification = keras_retinanet.backend.gather_nd(classification, indices)

		nms_indices = keras_retinanet.backend.non_max_suppression(boxes, scores, max_output_size=self.max_boxes, iou_threshold=self.nms_threshold)

		boxes          = keras.backend.gather(boxes, nms_indices)
		classification = keras.backend.gather(classification, nms_indices)

		boxes          = keras.backend.expand_dims(boxes, axis=0)
		classification = keras.backend.expand_dims(classification, axis=0)

		return [boxes, classification]

	def compute_output_shape(self, input_shape):
		return [(None, 4), (None, self.num_classes)]

	def compute_mask(self, inputs, mask=None):
		return [None, None]

	def get_config(self):
		return {
			'num_classes'   : self.num_classes,
			'nms_threshold' : self.nms_threshold,
			'max_boxes'     : self.max_boxes,
		}

class UpsampleLike(keras.layers.Layer):
	def call(self, inputs, **kwargs):
		source, target = inputs
		target_shape = keras.backend.shape(target)
		return keras_retinanet.backend.resize_images(source, (target_shape[1], target_shape[2]))

	def compute_output_shape(self, input_shape):
		return (input_shape[0][0],) + input_shape[1][1:3] + (input_shape[0][-1],)

class RegressBoxes(keras.layers.Layer):
	def call(self, inputs, **kwargs):
		anchors, regression = inputs
		return keras_retinanet.backend.bbox_transform_inv(anchors, regression)

	def compute_output_shape(self, input_shape):
		return (None, 4)
