import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from dsdl.exception import DefineSyntaxError, ValidationError

from .utils import TYPES_ALL, sort_nx


@dataclass()
class SingleStructParam:
    struct_name: str
    params_dict: Dict[str, str] = field(default_factory=dict)
    parents_struct: List[str] = field(default_factory=list)

    def __post_init__(self):
        """
        按照规定struct和class dom的名字不能是白皮书中已经包含的类型名，如List这些内定的名字
        """
        if self.struct_name in TYPES_ALL:
            raise ValidationError(f"{self.struct_name} is dsdl build-in value name, please rename it. "
                                  f"Build-in value names are: {','.join(TYPES_ALL)}")
        if self.struct_name in [i + 'Field' for i in TYPES_ALL]:
            raise ValidationError(f"{self.struct_name} is dsdl build-in value name, please rename it. "
                                  f"Build-in value names are: {', '.join(TYPES_ALL)}")


@dataclass()
class StructParams:
    params_list: List[SingleStructParam] = field(default_factory=list)


class ParserParam:
    def __init__(self, data_type, struct_defi):
        self.sample_param_map = self._parse_param_sample_type(raw=data_type)
        self.general_param_map = self._get_params(class_defi=struct_defi)

    @staticmethod
    def _parse_param_sample_type(raw: str) -> Optional[SingleStructParam]:
        """
        raw: ObjectDetectionSample[cdom=COCOClassFullDom]
        """
        c_dom = re.findall(r"\[(.*)\]", raw)
        if c_dom:
            data_sample_type = raw.replace("[" + c_dom[0] + "]", "", 1).strip()
            sample_param_map = SingleStructParam(struct_name=data_sample_type)
            temp = c_dom[0].split(",")
            for param in temp:
                param = param.strip()
                temp = param.split("=")
                sample_param_map.params_dict.update({temp[0].strip(): temp[1].strip()})
            return sample_param_map
        else:
            return None

    def _get_params(self, class_defi: Dict[str, Dict]) -> Dict[str, SingleStructParam]:
        self.general_param_map = defaultdict(SingleStructParam)
        ###################################################################################
        # 1。对class_defi循环，先拿到每个struct的params(self.general_param_map), 需要一个单独的循环，因为定义的顺序不一定
        # 以白皮书实例演练：计算机视觉：带场景分类的目标检测为列：
        # 先得到self.general_param_map =
        # {SceneAndObjectSample:{struct_name: SceneAndObjectSample
        #     params_dict: {scenedom: None, objectdom: None}
        #     parents_struct: []},
        # LocalObjectEntry:{struct_name: SceneAndObjectSample
        #     cdom: {cdom: None}
        #     parents_struct: []},}
        for define_name, define_value in class_defi.items():
            if "$def" in define_value and define_value["$def"] == "struct":
                struct_params = define_value.get("$params", None)
                if struct_params:
                    temp = SingleStructParam(
                        struct_name=define_name,
                        params_dict={key: None for key in struct_params},
                    )
                    self.general_param_map[define_name] = temp
        ###################################################################################
        # 2。然后填充`SingleStructParam`中的params_dict和parents_struct元素，
        # self.general_param_map =
        # {SceneAndObjectSample:{struct_name: SceneAndObjectSample
        #     params_dict: {scenedom: SceneDom, objectdom: ObjectDom}
        #     parents_struct: []},
        # LocalObjectEntry:{struct_name: SceneAndObjectSample
        #     cdom: {cdom: $scenedom}
        #     parents_struct: [SceneAndObjectSample]},}
        if len(self.general_param_map) == 0:
            return None
        if len(self.general_param_map) == 1:
            temp_param_map = list(self.general_param_map.values())[0]
            temp_name = list(self.general_param_map.keys())[0]
            for key in temp_param_map.params_dict.keys():
                try:
                    self.general_param_map[temp_name].params_dict[
                        key
                    ] = self.sample_param_map.params_dict[key]
                except KeyError as e:
                    raise DefineSyntaxError(f"miss the params {e} in definition")
        else:
            for define_name, define_value in class_defi.items():
                if "$def" in define_value and define_value["$def"] == "struct":
                    struct_params = define_value.get("$params", None)
                    if struct_params:
                        if define_name == self.sample_param_map.struct_name:
                            for key in self.general_param_map[define_name].params_dict:
                                try:
                                    self.general_param_map[define_name].params_dict[
                                        key
                                    ] = self.sample_param_map.params_dict[key]
                                except KeyError as e:
                                    raise DefineSyntaxError(
                                        f"miss the params {e} in definition"
                                    )

                        for raw_type in define_value["$fields"].values():
                            field_type = raw_type.replace(" ", "")
                            # 得到中括号中的 [...] 中的东西，贪婪匹配
                            for structure in self.general_param_map.keys():
                                if structure in field_type:
                                    self.general_param_map[
                                        structure
                                    ].parents_struct.append(define_name)
                                    try:
                                        # 如List[LocalObjectEntry[cdom=$objectdom]]会提取到'cdom=$objectdom'
                                        temp = re.findall(
                                            r"%s\[(.*?)\]" % str(structure), field_type
                                        )[0]
                                    except KeyError:
                                        raise DefineSyntaxError(
                                            f"definition error of filed {field_type}"
                                        )
                                    for param in temp.split(","):
                                        param = param.split("=")
                                        if len(param) != 2:
                                            raise DefineSyntaxError(
                                                f"error in params definition {field_type}"
                                            )
                                        key, value = param[0], param[1]
                                        try:
                                            self.general_param_map[
                                                structure
                                            ].params_dict[key] = value
                                        except KeyError as e:
                                            raise DefineSyntaxError(
                                                f"miss the params {e} in definition"
                                            )
                                    break
            ###################################################################################
            # 3。最后利用有向图对struct_name进行排序（父->子），本例中是[SceneAndObjectSample, LocalObjectEntry]
            # sort_param_dict = {SceneAndObjectSample: [], LocalObjectEntry:[SceneAndObjectSample]}
            sort_param_dict = {}
            for key, val in self.general_param_map.items():
                if len(val.parents_struct) > 1:  # 目前只能处理只有一个父节点的情况
                    raise DefineSyntaxError(f"error in definition")
                else:
                    sort_param_dict[key] = val.parents_struct  # {list[str]}
            ordered_keys = sort_nx(sort_param_dict)  # 用有向图排序
            # 对排序后的struct，按顺序填充参数的具体值，最后得到
            # self.general_param_map =
            # {SceneAndObjectSample:{struct_name: SceneAndObjectSample
            #     params_dict: {scenedom: SceneDom, objectdom: ObjectDom}
            #     parents_struct: []},
            # LocalObjectEntry:{struct_name: SceneAndObjectSample
            #     cdom: {cdom: ObjectDom}
            #     parents_struct: [SceneAndObjectSample]},}
            for struct in ordered_keys[1:]:
                parent_struct = self.general_param_map[struct].parents_struct
                if not parent_struct:
                    raise DefineSyntaxError(
                        f"each struct must have one parent struct, but {struct} can have no"
                    )
                if len(parent_struct) > 1:
                    raise DefineSyntaxError(
                        "each struct must have one parent struct, but can have more than one child struct.\n"
                        f"{struct} have more than one parent struct"
                    )
                parent_struct = parent_struct[0]
                for key, val in self.general_param_map[struct].params_dict.items():
                    if val.startswith("$"):
                        parent_key = val.replace("$", "").strip()
                        self.general_param_map[struct].params_dict[
                            key
                        ] = self.general_param_map[parent_struct].params_dict[
                            parent_key
                        ]
        return self.general_param_map

    def validate_params(self, struct_params_field: Set, struct_name: str) -> Set:
        input_params = set(self.general_param_map[struct_name].params_dict.keys())
        if input_params != struct_params_field:
            raise DefineSyntaxError(
                f"error of definition of params {struct_params_field}"
            )
        return struct_params_field
