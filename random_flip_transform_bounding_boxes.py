# -*- coding: utf-8 -*-
"""Random_Flip_transform_bounding_boxes.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1LQEOczv4WLYycS5UnhkXMlZH02CRPSI2
"""

import tensorflow_datasets as tfds

import keras
from keras.src import ops
import matplotlib.pyplot as plt

from keras.src.api_export import keras_export
from keras.src.layers.preprocessing.image_preprocessing.base_image_preprocessing_layer import (  # noqa: E501
    BaseImagePreprocessingLayer,
)
from keras.src.layers.preprocessing.image_preprocessing.bounding_boxes.converters import (  # noqa: E501
    convert_format,
)
from keras.src.random.seed_generator import SeedGenerator

HORIZONTAL = "horizontal"
VERTICAL = "vertical"
HORIZONTAL_AND_VERTICAL = "horizontal_and_vertical"


@keras_export("keras.layers.RandomFlip")
class RandomFlip(BaseImagePreprocessingLayer):
    """A preprocessing layer which randomly flips images during training.

    This layer will flip the images horizontally and or vertically based on the
    `mode` attribute. During inference time, the output will be identical to
    input. Call the layer with `training=True` to flip the input.
    Input pixel values can be of any range (e.g. `[0., 1.)` or `[0, 255]`) and
    of integer or floating point dtype.
    By default, the layer will output floats.

    **Note:** This layer is safe to use inside a `tf.data` pipeline
    (independently of which backend you're using).

    Input shape:
        3D (unbatched) or 4D (batched) tensor with shape:
        `(..., height, width, channels)`, in `"channels_last"` format.

    Output shape:
        3D (unbatched) or 4D (batched) tensor with shape:
        `(..., height, width, channels)`, in `"channels_last"` format.

    Args:
        mode: String indicating which flip mode to use. Can be `"horizontal"`,
            `"vertical"`, or `"horizontal_and_vertical"`. `"horizontal"` is a
            left-right flip and `"vertical"` is a top-bottom flip. Defaults to
            `"horizontal_and_vertical"`
        seed: Integer. Used to create a random seed.
        **kwargs: Base layer keyword arguments, such as
            `name` and `dtype`.
    """

    _USE_BASE_FACTOR = False

    def __init__(
        self,
        mode=HORIZONTAL_AND_VERTICAL,
        seed=None,
        data_format=None,
        **kwargs
    ):
        super().__init__(data_format=data_format, **kwargs)
        self.seed = seed
        self.generator = SeedGenerator(seed)
        self.mode = mode
        self._convert_input_args = False
        self._allow_non_tensor_positional_args = True

    def get_random_transformation(self, data, training=True, seed=None):
        if not training:
            return None

        if isinstance(data, dict):
            images = data["images"]
        else:
            images = data
        shape = self.backend.core.shape(images)
        if len(shape) == 3:
            flips_shape = (1, 1, 1)
        else:
            flips_shape = (shape[0], 1, 1, 1)

        if seed is None:
            seed = self._get_seed_generator(self.backend._backend)

        flips = self.backend.numpy.less_equal(
            self.backend.random.uniform(shape=flips_shape, seed=seed), 0.5
        )
        return {"flips": flips}

    def transform_images(self, images, transformation, training=True):
        images = self.backend.cast(images, self.compute_dtype)
        if training:
            return self._flip_inputs(images, transformation)
        return images

    def transform_labels(self, labels, transformation, training=True):
        return labels

    def transform_bounding_boxes(
        self,
        bounding_boxes,
        transformation,
        training=True,
        input_shape=None,
    ):
        flips = transformation["flips"][0]
        input_height, input_width = input_shape

        bounding_boxes = convert_format(
            bounding_boxes,
            source=self.bounding_box_format,
            target="xyxy",
            height=input_height,
            width=input_width,
        )

        x1, y1, x2, y2 = self.backend.numpy.split(
            bounding_boxes["boxes"], 4, axis=-1
        )
        if self.mode in {HORIZONTAL, HORIZONTAL_AND_VERTICAL}:
            x1 = self.backend.numpy.where(flips, input_width - x1, x1)
            x2 = self.backend.numpy.where(flips, input_width - x2, x2)

        if self.mode in {VERTICAL, HORIZONTAL_AND_VERTICAL}:
            y1 = self.backend.numpy.where(flips, input_height - y1, y1)
            y2 = self.backend.numpy.where(flips, input_height - y2, y2)

        transformed_bounding_boxes = self.backend.numpy.concatenate(
            [x1, y1, x2, y2], axis=-1
        )

        bounding_boxes["boxes"] = transformed_bounding_boxes

        bounding_boxes = convert_format(
            bounding_boxes,
            source="xyxy",
            target=self.bounding_box_format,
            height=input_height,
            width=input_width,
        )

        return bounding_boxes

    def transform_segmentation_masks(
        self, segmentation_masks, transformation, training=True
    ):
        return self.transform_images(
            segmentation_masks, transformation, training=training
        )

    def _flip_inputs(self, inputs, transformation):
        if transformation is None:
            return inputs

        flips = transformation["flips"]
        inputs_shape = self.backend.shape(inputs)
        unbatched = len(inputs_shape) == 3
        if unbatched:
            inputs = self.backend.numpy.expand_dims(inputs, axis=0)

        flipped_outputs = inputs
        if self.data_format == "channels_last":
            horizontal_axis = -2
            vertical_axis = -3
        else:
            horizontal_axis = -1
            vertical_axis = -2

        if self.mode == HORIZONTAL or self.mode == HORIZONTAL_AND_VERTICAL:
            flipped_outputs = self.backend.numpy.where(
                flips,
                self.backend.numpy.flip(flipped_outputs, axis=horizontal_axis),
                flipped_outputs,
            )
        if self.mode == VERTICAL or self.mode == HORIZONTAL_AND_VERTICAL:
            flipped_outputs = self.backend.numpy.where(
                flips,
                self.backend.numpy.flip(flipped_outputs, axis=vertical_axis),
                flipped_outputs,
            )
        if unbatched:
            flipped_outputs = self.backend.numpy.squeeze(
                flipped_outputs, axis=0
            )
        return flipped_outputs

    def compute_output_shape(self, input_shape):
        return input_shape

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "seed": self.seed,
                "mode": self.mode,
                "data_format": self.data_format,
            }
        )
        return config

def plot_image(image, bboxes):
    image_np = tf.image.convert_image_dtype(image, dtype=tf.uint8).numpy()

    fig, ax = plt.subplots(1)
    ax.imshow(image_np)

    # Loop through the bounding boxes and add them to the plot
    for bbox in bboxes:
        x1, y1, x2, y2 = bbox  # Bounding box in absolute pixel (x1, y1, x2, y2) format

        # Calculate width and height directly from absolute coordinates
        width = x2 - x1
        height = y2 - y1

        # Create a rectangle patch and add it to the plot
        rect = patches.Rectangle((x1, y1), width, height, linewidth=2, edgecolor='blue', facecolor='none')
        ax.add_patch(rect)

    plt.axis("off")
    plt.show()

dataset = tfds.load("voc/2007", split="train[:10%]", shuffle_files=True, as_supervised=False)
dataset_iter = iter(dataset)

# Commented out IPython magic to ensure Python compatibility.
# %load_ext autoreload
# %autoreload 2

import matplotlib.patches as patches
import tensorflow as tf

example = next(dataset_iter)

image = example['image']
bboxes = example['objects']['bbox']
labels = example['objects']['label']

bboxes_xyxy = keras.utils.bounding_boxes.convert_format(bboxes,
                                                        'REL_YXYX',
                                                        'xyxy',
                                                        height=image.shape[0],
                                                        width=image.shape[1],
                                                        dtype='float32')


plot_image(image, bboxes_xyxy)


bounding_boxes = {
    "boxes": tf.convert_to_tensor(bboxes, dtype=tf.float32).numpy(),
    "labels": labels
}

image_size = image.shape[:2]

augmentation = RandomFlip(bounding_box_format="REL_YXYX")
transformation = augmentation.get_random_transformation(image, training=True)
cropped_image = augmentation.transform_images(image, transformation, True) / 255
bbox_extracted = augmentation.transform_bounding_boxes(bounding_boxes, transformation=transformation, training=True, input_shape=image_size)

bboxes_xyxy = keras.utils.bounding_boxes.convert_format(bbox_extracted['boxes'],
                                                        'REL_YXYX',
                                                        'xyxy',
                                                        height=cropped_image.shape[0],
                                                        width=cropped_image.shape[1],
                                                        dtype='float32')

plot_image(cropped_image, bboxes_xyxy)

!pip install git+https://github.com/keras-team/keras.git