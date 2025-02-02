import re

from prettytable import PrettyTable

from dsdl.types.field import Field


class Util:
    @staticmethod
    def extract_key(field_obj: Field):
        field_cls_name = field_obj.__class__.__name__
        return "$" + field_cls_name.replace("Field", "").lower()

    @staticmethod
    def get_first_item(dic):
        if len(dic) == 0:
            return None
        for k in dic:
            return {"key": k, "value": dic[k]}

    @staticmethod
    def extract_sample_type(sample_type):
        c_dom = re.findall(r"\[(.*?)\]", sample_type)
        if c_dom:
            return sample_type.replace("[" + c_dom[0] + "]", "", 1).strip()
        else:
            return sample_type

    @staticmethod
    def format_sample(samples):
        """
        该方法的作用就是将parse_struct方法的返回值（单个样本）写到一个列表中，方便在命令行中展示样本的基本信息
        """
        table = PrettyTable()
        table.title = "Samples"
        table.field_names = ["sample idx", "media", "annotation"]
        table._max_width = {"media": 20, "annotation": 50}

        for idx, sample in enumerate(samples, start=1):
            anns = [s["ann"] for s in sample]
            medias = [s["media"] for s in sample]
            processed_anns = [[Util.strip(dic) for dic in lst] for lst in anns]
            if len(medias) == 1:
                processed_anns = processed_anns[0]
                medias = medias[0]
            table.add_row([idx, medias, processed_anns])
        return table

    @staticmethod
    def strip(dic):
        result_dic = {}
        for sub_dic in dic.values():
            for k in sub_dic:
                result_dic[k] = sub_dic[k]
        return result_dic
