import io

import numpy as np
from PIL import Image

from ..exception import FileReadError
from .base_geometry import BaseGeometry
from .box import BBox
from .label import LabelList
from .utils import bytes_to_numpy


class SegmentationMap(BaseGeometry):
    """
    A Geometry class for semantic segmentation map.
    """

    def __init__(self, location, file_reader, dom):
        self._loc = location
        self._reader = file_reader
        self._dom = dom

    @property
    def class_domain(self):
        return self._dom

    @property
    def location(self):
        return self._loc

    def to_bytes(self):
        """
        turn SegmentationMap object to bytes
        """
        return io.BytesIO(self._reader.read())

    def to_image(self):
        """
        turn SegmentationMap object to PIL.Image
        """
        try:
            img = Image.open(self.to_bytes())
        except Exception as e:
            raise FileReadError(f"Failed to convert bytes to an array. {e}") from None
        return img

    def to_array(self):
        """
        turn SegmentationMap object to numpy.ndarray
        """
        return bytes_to_numpy(self.to_bytes())

    def visualize(self, image, palette, **kwargs):
        seg = self.to_array()
        color_seg = np.zeros((seg.shape[0], seg.shape[1], 3), dtype=np.uint8)
        category_ids = np.unique(seg)
        label_lst = []
        for category_id in category_ids:
            label = self._dom.get_label(int(category_id))
            category_name = label.category_name
            if category_name not in palette:
                palette[category_name] = tuple(np.random.randint(0, 255, size=[3]))
            label_lst.append(label)
            color_seg[seg == category_id, :] = np.array(palette[category_name])
        overlay = Image.fromarray(color_seg).convert("RGBA")
        overlayed = Image.blend(image, overlay, 0.5)
        LabelList(label_lst).visualize(image=overlayed, palette=palette, bbox={"temp": BBox(0, 0, 0, 0)})
        return overlayed

    def __repr__(self):
        return f"path:{self.location}, class domain: {self._dom.__name__}"
