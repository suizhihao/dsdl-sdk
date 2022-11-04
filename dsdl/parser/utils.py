import re
from typing import Dict, List

import networkx as nx

TYPES_WITHOUT_PARS = [
    "Bool",
    "Num",
    "Int",
    "Str",
    "Coord",
    "Coord3D",
    "Interval",
    "BBox",
    "Polygon",
    "RlePolygon",
    "Image",
    "Video",
]
TYPES_TIME = ["Date", "Time"]
TYPES_LABEL = ["Label", "SegMap", "Keypoint"]
TYPES_LIST = ["List"]
TYPES_ALL = TYPES_WITHOUT_PARS + TYPES_TIME + TYPES_LABEL + TYPES_LIST


def sanitize_variable_name(varstr: str) -> str:
    """
    1. 将`.`替换为`__` 2.将（非字母开头）和（非字母数字及下划线）替换为`_`
    eg. apple.fruit_and_vegetables会转化为apple__fruit_and_vegetables
    """
    temp = varstr.split(".")
    temp = [re.sub("\W|^(?=\d)", "_", i) for i in temp]
    temp = "__".join(temp)
    return temp


def rreplace(s, old, new, occurrence):
    """
    从右向左的替换函数，类似replace,不过是反着的
    """
    li = s.rsplit(old, occurrence)
    return new.join(li)


def add_key_value_2_struct_field(field: str, key: str, value) -> str:
    """
    add key, value to field in struct,
    eg: key: optional, value: True, field: NumField(is_attr=True)
    return: NumField(optional=True, is_attr=True)
    """
    p = re.compile(r"[(](.*)[)]", re.S)  # 贪婪匹配
    k_v_list = re.findall(p, field)[0].strip()
    if k_v_list:
        k_v_list = k_v_list.split(",")
    else:
        k_v_list = []
    k_v_list.append(str(key) + "=" + str(value))
    temp = "(" + ", ".join(k_v_list) + ")"
    return field.replace("(" + re.findall(p, field)[0] + ")", temp)


def sort_nx(
    dict_sort_key: Dict[str, List[str]],
) -> List:
    """
    利用有向图对嵌套结构进行排序
    Args:
        dict_sort_key： {当前节点：[父节点],...}
    Returns: 排好序的节点的list，从父到子
    """
    define_graph = nx.DiGraph()
    define_graph.add_nodes_from(dict_sort_key.keys())
    for key, val in dict_sort_key.items():
        for base in val:
            for k in dict_sort_key.keys():
                if k in base:
                    define_graph.add_edge(k, key)
    if not nx.is_directed_acyclic_graph(define_graph):
        raise "define cycle found."
    ordered_keys = list(nx.topological_sort(define_graph))
    return ordered_keys
