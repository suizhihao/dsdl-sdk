# Generated by the dsdl parser. DO NOT EDIT!

from enum import Enum, unique

from dsdl.types import *


class COCO2017ClassFatherDom(ClassDomain):
    Classes = [
        Label("food"),
        Label("tool"),
    ]


class COCO2017ClassFatherDom1(ClassDomain):
    Classes = [
        Label("fruit", supercategories=[COCO2017ClassFatherDom.get_label("food")]),
        Label("sports tool", supercategories=[COCO2017ClassFatherDom.get_label("tool")]),
    ]


class COCO2017ClassDom(ClassDomain):
    Classes = [
        Label("airplane", supercategories=[COCO2017ClassFatherDom1.get_label("sports tool")]),
        Label("apple", supercategories=[COCO2017ClassFatherDom1.get_label("fruit")]),
        Label("backpack", supercategories=[COCO2017ClassFatherDom1.get_label("")]),
        Label("banana", supercategories=[COCO2017ClassFatherDom1.get_label("fruit")]),
        Label("baseball bat", supercategories=[COCO2017ClassFatherDom1.get_label("sports tool")]),
        Label("baseball glove", supercategories=[COCO2017ClassFatherDom1.get_label("sports tool")]),
    ]


class LocalObjectEntry(Struct):
    bbox = BBoxField()
    label = LabelField(dom=COCO2017ClassDom, optional=True)


class SceneAndObjectSample(Struct):
    image = ImageField()
    sclabel = LabelField(dom=COCO2017ClassFatherDom, optional=True)
    objects = ListField(ele_type=LocalObjectEntry())
