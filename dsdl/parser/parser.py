import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

import click
from yaml import load as yaml_load

from dsdl.exception import DefineSyntaxError, ValidationError
from dsdl.warning import DuplicateDefineWarning

from .parse_class import EleClass, ParserClass
from .parse_field import EleStruct, ParserField
from .parse_params import ParserParam
from .utils import *

try:
    from yaml import CSafeLoader as YAMLSafeLoader
except ImportError:
    from yaml import SafeLoader as YAMLSafeLoader


class Parser(ABC):
    """
    定义一个Parser的抽象基类（没法实例化的）：
    用处： 强制子类实现某些方法：写框架时常用。
    """

    @abstractmethod
    def _parse(self, data_file: str, library_path: str):
        """
        将yaml文件中的模型（struct）和标签(label)部分校验之后读入某个变量中
        """
        pass

    @abstractmethod
    def _generate(self, output_file: str) -> Optional[str]:
        """
        将内存里面的模型（struct）和标签(label)部分输出成ORM模型（python代码）
        """
        pass

    def process(self, data_file, library_path, output_file):
        self._parse(data_file, library_path)
        dsdl_py = self._generate(output_file)
        print(
            f"Convert Yaml File to Python Code Successfully!\n"
            f"Yaml file (source): {data_file}\n"
            f"Output file (output): {output_file}"
        )
        return dsdl_py


class TypeEnum(Enum):
    CLASS_DOMAIN = "class_domain"
    STRUCT = "struct"


@dataclass()
class StructORClassDomain:
    name: str
    type: TypeEnum = TypeEnum.STRUCT
    field_list: List[Union[EleStruct, EleClass]] = field(default_factory=list)
    parent: List[str] = None  # class_dom 特有的super category
    skeleton: List[List[int]] = None

    def __post_init__(self):
        """
        按照规定struct和class dom的名字不能是白皮书中已经包含的类型名，如List这些内定的名字
        """
        if self.name in TYPES_ALL:
            raise ValidationError(f"{self.name} is dsdl build-in value name, please rename it."
                                  f"Build-in value names are: {','.join(TYPES_ALL)}")
        if self.name in [i + 'Field' for i in TYPES_ALL]:
            raise ValidationError(f"{self.name} is dsdl build-in value name, please rename it."
                                  f"Build-in value names are: {','.join(TYPES_ALL)}")


class DSDLParser(Parser, ABC):
    def __init__(self):
        self.struct_name = set()
        self.define_map = defaultdict(StructORClassDomain)
        self.dsdl_version = None
        self.meta = dict()

    def _parse(self, data_file: str, library_path: str):
        """
        将yaml文件中的模型（struct）和标签(label)部分校验之后读入变量self.define_map中
            input_file_list: 读入的yaml文件
        """
        with open(data_file, "r") as f:
            desc = yaml_load(f, Loader=YAMLSafeLoader)

        # 校验必须有meta和$dsdl-version字段，见白皮书2.1
        try:
            self.dsdl_version = desc["$dsdl-version"]  # 存版本号，后续应该会使用（目前木有用）
        except KeyError as e:
            raise DefineSyntaxError(f"data yaml must contains {e} section")
        try:
            self.meta = desc["meta"]  # 存版meta信息，后续应该会使用（目前木有用）
        except KeyError as e:
            raise DefineSyntaxError(f"data yaml must contains {e} section")

        # 校验必须有data字段和data中的sample-type字段
        try:
            data_sample_type = desc["data"]["sample-type"]
        except KeyError as e:
            raise DefineSyntaxError(f"data yaml must contains {e} in `data` section")

        if "$import" in desc:
            import_list = desc["$import"]
            import_list = [
                os.path.join(library_path, p.strip() + ".yaml") for p in import_list
            ]
        else:
            import_list = []
        if "defs" in desc:
            # 获取yaml中模型（struct）和标签(label)部分的内容，存储在变量class_defi中，
            # 因为有不同格式的yaml(数据和模型放同一个yaml中或者分开放)，所以用if...else分别做处理
            # 注意区分这个root_class_defi,为啥要把他先存好？如果import的yaml中，有重复的模型，需要用它覆盖，参见白皮书2.5.1
            root_class_defi = desc["defs"].items()
            self.dsdl_version = desc["$dsdl-version"]  # 存版本号，后续应该会使用（目前木有用）
        else:
            root_class_defi = dict()

        import_desc = dict()
        for input_file in import_list:
            with open(input_file, "r") as f:
                import_desc.update(yaml_load(f, Loader=YAMLSafeLoader))

        if "defs" in import_desc:
            # 获取yaml中模型（struct）和标签(label)部分的内容，存储在变量class_defi中，
            # 因为有不同格式的yaml(数据和模型放同一个yaml中或者分开放)，所以用if...else分别做处理
            class_defi = import_desc["defs"]
        else:
            class_defi = import_desc
        # root_class_defi是数据yaml里面定义的模型，如果和import里面的重复了，会覆盖掉前面import的。参见白皮书2.5.1
        class_defi.update(root_class_defi)

        # get self.data_sample_type and self.sample_param_map
        PARAMS = ParserParam(data_type=data_sample_type, struct_defi=class_defi)
        for define_name, define_value in class_defi.items():
            if define_name.startswith("$"):
                continue
            try:
                define_type = define_value["$def"]
            except KeyError as e:
                raise DefineSyntaxError(
                    f"{define_name} section must contains {e} sub-section"
                )
            if define_type == "struct" or define_type == "class_domain":
                if define_name in self.struct_name:
                    raise DuplicateDefineWarning(f"{define_name} has defined.")
                self.struct_name.add(define_name)

        # loop for `class_defi` section，deal with each `struct` and `class_domain`
        for define_name, define_value in class_defi.items():
            if define_name.startswith("$"):
                # skip section like: $dsdl-version
                continue

            # each yaml file must contain '$def' section
            define_type = define_value["$def"]

            if define_type == "struct":
                define_info = StructORClassDomain(name=define_name)
                define_info.type = TypeEnum.STRUCT
                FIELD_PARSER = ParserField(self.struct_name)
                # verify each ele of `struct` in `class_defi`, and save in define_info
                struct_params = define_value.get("$params", None)
                field_list = dict()
                for raw_field in define_value["$fields"].items():
                    field_name = raw_field[0].strip()
                    field_type = raw_field[1].strip()
                    if not field_name.isidentifier():
                        err = (
                            f"'{field_name}' must be a a valid identifier. "
                            f"Field name is considered a valid identifier if "
                            f"it only contains alphanumeric letters (a-z) and (0-9), or underscores (_). "
                            f"A valid identifier cannot start with a number, or contain any spaces."
                        )
                        raise DefineSyntaxError(err)
                    if struct_params:
                        for param, value in PARAMS.general_param_map[
                            define_name
                        ].params_dict.items():
                            field_type = field_type.replace("$" + param, value)
                    field_list[field_name] = EleStruct(
                        name=field_name,
                        type=FIELD_PARSER.pre_parse_struct_field(
                            field_name, field_type
                        ),
                    )
                # deal with `$optional` section after `$fields` section，
                # because we must ensure filed in `$optional` is the `filed_name` in `$fields` section.
                if "$optional" in define_value or FIELD_PARSER.optional:
                    optional_set = (
                        set(define_value["$optional"]) | FIELD_PARSER.optional
                    )
                    for optional_name in optional_set:
                        optional_name = optional_name.strip()
                        if optional_name in field_list:
                            temp_type = field_list[optional_name].type
                            temp_type = add_key_value_2_struct_field(
                                temp_type, "optional", True
                            )
                            field_list[optional_name].type = temp_type
                        else:
                            raise DefineSyntaxError(f"Error in $optional: {optional_name} is not in $field")
                for attr_name in FIELD_PARSER.is_attr:
                    temp_type = field_list[attr_name].type
                    temp_type = add_key_value_2_struct_field(temp_type, "is_attr", True)
                    field_list[attr_name].type = temp_type

                # get processed struct filed and save it in define_info
                if not field_list:
                    raise DefineSyntaxError(
                        "Struct must have fields more than or equal to 1"
                    )
                define_info.field_list = list(field_list.values())

            elif define_type == "class_domain":
                if "skeleton" in define_value:
                    CLASS_PARSER = ParserClass(define_name, define_value["classes"], define_value["skeleton"])
                else:
                    CLASS_PARSER = ParserClass(define_name, define_value["classes"])
                define_info = StructORClassDomain(name=CLASS_PARSER.class_name)
                # verify each ele (in other words: each label) of `class_domain`, and save in define_info
                define_info.type = TypeEnum.CLASS_DOMAIN
                define_info.field_list = CLASS_PARSER.class_field
                define_info.parent = CLASS_PARSER.super_class_list
                define_info.skeleton = CLASS_PARSER.skeleton
            else:
                raise DefineSyntaxError(
                    f"error type {define_type} in yaml, type must be class_dom or struct."
                )

            self.define_map[define_info.name] = define_info

    def _generate(self, output_file: str = None) -> Optional[str]:
        """
        将内存里面的模型（struct）和标签(label)部分输出成ORM模型（python代码）
        """
        # check define cycles. 如果有环形（就是循环定义）那是不行滴～
        define_graph = nx.DiGraph()
        define_graph.add_nodes_from(self.define_map.keys())
        for key, val in self.define_map.items():
            if val.type == TypeEnum.STRUCT:
                for field_list in val.field_list:
                    for k in self.define_map.keys():
                        if k in field_list.type:
                            define_graph.add_edge(k, key)
            elif val.type == TypeEnum.CLASS_DOMAIN:
                for field_list in val.parent:
                    for k in self.define_map.keys():
                        if k in field_list:
                            define_graph.add_edge(k, key)
        if not nx.is_directed_acyclic_graph(define_graph):
            raise "define cycle found."

        dsdl_py = "# Generated by the dsdl parser. DO NOT EDIT!\n"
        dsdl_py += "from dsdl.types import *\n"
        dsdl_py += "from dsdl.geometry import *\n\n\n"
        ordered_keys = list(nx.topological_sort(define_graph))
        for idx, key in enumerate(ordered_keys):
            val = self.define_map[key]
            if val.type == TypeEnum.STRUCT:
                dsdl_py += f"class {key}(Struct):\n"
                for field_list in val.field_list:
                    dsdl_py += f"""    {field_list.name} = {field_list.type}\n"""
            if val.type == TypeEnum.CLASS_DOMAIN:
                dsdl_py += f"class {key}(ClassDomain):\n"
                dsdl_py += "    Classes = [\n"
                for ele_class in val.field_list:
                    if ele_class.super_categories:
                        temp = ", ".join(ele_class.super_categories)
                        dsdl_py += f"""        Label("{ele_class.label_value}", supercategories=[{temp}]),\n"""
                    else:
                        dsdl_py += f"""        Label("{ele_class.label_value}"),\n"""
                dsdl_py += "    ]\n"
                if val.skeleton:
                    dsdl_py += f"""    Skeleton = {val.skeleton}\n"""
            if idx != len(ordered_keys) - 1:
                dsdl_py += "\n\n"

        if output_file:
            with open(output_file, "w") as of:
                print(dsdl_py, file=of)
        else:
            return dsdl_py


def dsdl_parse(
    dsdl_yaml: str,
    dsdl_library_path: str = "dsdl/dsdl_library",
    output_file: str = None,
) -> Optional[str]:
    """
    Main function of parser yaml files to .py dsdl struct definition code.

    Arguments:
        dsdl_yaml: file path of `data definition yaml file`;
        dsdl_library_path: file path of '`$import` path' in `dsdl_yaml` file.
        output_file: output file path. if None, return string, else, generate .py file in output file path.

    Returns:
        Optional[str]: if output_file=None, return string of dsdl definition .py file;
                       else generate a .py file in `output_file` path.
    """
    dsdl_parser = DSDLParser()
    res = dsdl_parser.process(dsdl_yaml, dsdl_library_path, output_file)
    return res


@click.command()
@click.option(
    "-y",
    "--yaml",
    "dsdl_yaml",
    type=str,
    required=True,
)
@click.option(
    "-p",
    "--path",
    "dsdl_library_path",
    type=str,
    default="dsdl/dsdl_library",
)
def parse(dsdl_yaml: str, dsdl_library_path: str):
    """
    a separate cli tool function for user to parser yaml files to .py dsdl struct definition code.

    Arguments:
        dsdl_yaml: file path of `data definition yaml file`;
        dsdl_library_path: file path of '`$import` path' in `dsdl_yaml` file.

    Returns:
        None: generate a .py file in the same folder of `dsdl_yaml` file.
    """
    dsdl_name = os.path.splitext(os.path.basename(dsdl_yaml))[0]
    output_file = os.path.join(os.path.dirname(dsdl_yaml), f"{dsdl_name}.py")
    dsdl_parse(dsdl_yaml, dsdl_library_path, output_file)
