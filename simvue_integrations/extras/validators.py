"""Common
----------

Classses which could be used in the construction of multiple adapters.
"""
import enum
import typing
import pydantic

class Operator(str, enum.Enum):
    """The operator to use to compare the reduced evaluation value to a given target threshold."""
    MORE_THAN = ">"
    LESS_THAN = "<"
    MORE_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="

OPERATORS: dict[str, typing.Callable[[typing.Union[int, float], typing.Union[int, float]], bool]] = {
    ">": lambda x, y: x > y,
    "<": lambda x, y: x < y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    "==": lambda x, y: x == y,
}

def check_input(
        value_to_check: typing.Union[str, float, int, None], 
        validation_info: pydantic.ValidationInfo, 
        name_of_parameter: str, 
        required_when_name: str, 
        required_when_values: list
        ):
    other_values = validation_info.data
    if other_values.get(required_when_name) in required_when_values:
        assert value_to_check, f"'{name_of_parameter}' must be provided for alerts using '{required_when_name} = {other_values.get(required_when_name)}'."
    elif other_values.get(required_when_name) not in required_when_values:
        assert not value_to_check, f"'{name_of_parameter}' must not be provided for alerts using '{required_when_name} = {other_values.get(required_when_name)}'."
    return value_to_check

class AlertValidator(pydantic.BaseModel, extra='forbid'):
    source: typing.Literal["metrics", "events"]
    frequency: pydantic.PositiveInt
    notification: typing.Optional[typing.Literal["none", "email"]] = pydantic.Field(default="none")
    description: typing.Optional[str] = pydantic.Field(default=None)
    # For event based alerts:
    pattern: typing.Optional[str] = pydantic.Field(default=None, validate_default=True)
    # For metric based alerts:
    rule: typing.Optional[typing.Literal["is above", "is below", "is outside range", "is inside range"]] = pydantic.Field(default=None, validate_default=True)
    metric: typing.Optional[str] = pydantic.Field(default=None, validate_default=True)
    window: typing.Optional[pydantic.PositiveInt] = pydantic.Field(default=None, validate_default=True)
    # For 'is above' or 'is below':
    threshold: typing.Optional[typing.Union[int, float]] = pydantic.Field(default=None, validate_default=True)
    # For 'is outside range' or 'is inside range'
    range_low: typing.Optional[typing.Union[int, float]] = pydantic.Field(default=None, validate_default=True)
    range_high: typing.Optional[typing.Union[int, float]] = pydantic.Field(default=None, validate_default=True)
    aggregation: typing.Optional[typing.Literal["average", "sum", "at least one", "all"]] = pydantic.Field(default="average", validate_default=True)
    trigger_abort: typing.Optional[bool] = pydantic.Field(default=None, validate_default=True)
        
    @pydantic.field_validator("pattern")
    def check_pattern(cls, v, validation_info):
        return check_input(v, validation_info, "pattern", "source", ["events"])
    
    @pydantic.field_validator("rule")
    def check_rule(cls, v, validation_info):
        return check_input(v, validation_info, "rule", "source", ["metrics"])
    
    @pydantic.field_validator("metric")
    def check_metric(cls, v, validation_info):
        return check_input(v, validation_info, "metric", "source", ["metrics"])
    
    @pydantic.field_validator("aggregation")
    def check_aggregation(cls, v, validation_info):
        return check_input(v, validation_info, "aggregation", "source", ["metrics"])
    
    @pydantic.field_validator("window")
    def check_window(cls, v, validation_info):
        return check_input(v, validation_info, "window", "source", ["metrics"])

    @pydantic.field_validator("threshold")
    def check_threshold(cls, v, validation_info):
        return check_input(v, validation_info, "threshold", "rule", ["is above", "is below"])
    
    @pydantic.field_validator("range_low")
    def check_range_low(cls, v, validation_info):
        return check_input(v, validation_info, "range_low", "rule", ["is outside range", "is inside range"])
    
    @pydantic.field_validator("range_high")
    def check_range_high(cls, v, validation_info):
        return check_input(v, validation_info, "range_high", "rule", ["is outside range", "is inside range"])
