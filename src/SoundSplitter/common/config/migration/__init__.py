from pydantic import ValidationError
from pydantic_yaml import parse_yaml_file_as, to_yaml_file

from .v1 import V1
from .v2 import V2

__all__: list[str] = ["V1", "V2"]


class Migration:
    def __new__(cls, file: str, /) -> V2:
        try:
            return parse_yaml_file_as(model_type=V2, file=file)
        except ValidationError:
            try:
                model: V2 = cls._v1_to_v2(file)
            except ValidationError:
                model = V2()
            to_yaml_file(file, model)
            return model

    @staticmethod
    def _v1_to_v2(file: str, /) -> V2:
        v1: V1 = parse_yaml_file_as(model_type=V1, file=file)
        return V2(
            left=v1.left,
            right=v1.right,
            source=v1.source,
            volume=v1.volume,
            left_latency_ms=v1.left_latency,
            right_latency_ms=v1.right_latency,
        )
