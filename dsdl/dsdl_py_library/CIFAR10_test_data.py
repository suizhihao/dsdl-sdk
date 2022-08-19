# Generated by the dsdl parser. DO NOT EDIT!

from dsdl.types import *
from enum import Enum, unique


class Cifar10ImageClassificationClassDom(ClassDomain):
    Classes = [
        Label("airplane"),
        Label("automobile"),
        Label("bird"),
        Label("cat"),
        Label("deer"),
        Label("dog"),
        Label("frog"),
        Label("horse"),
        Label("ship"),
        Label("truck"),
    ]


class TemplateClassification(Struct):
    image = ImageField()
    label = LabelField(dom=Cifar10ImageClassificationClassDom, optional=True)
    confidence = NumField(optional=True)
    is_crowd = BoolField(optional=True, is_attr=True)
