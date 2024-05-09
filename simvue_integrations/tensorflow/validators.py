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
        other_values: dict, 
        name_of_parameter: str, 
        required_when_name: str, 
        required_when_values: list
        ):

    if other_values.get(required_when_name) in required_when_values:
        assert value_to_check, f"'{name_of_parameter}' must be provided for alerts using '{required_when_name} = {other_values.get(required_when_name)}'."
    elif other_values.get(required_when_name) not in required_when_values:
        assert not value_to_check, f"'{name_of_parameter}' must not be provided for alerts using '{required_when_name} = {other_values.get(required_when_name)}'."
    return value_to_check

class AlertValidator(pydantic.BaseModel):
    source: typing.Literal["metrics", "events"]
    frequency: pydantic.PositiveInt
    notification: typing.Optional[typing.Literal["none", "email"]] = "none"
    # For event based alerts:
    pattern: typing.Optional[str] = None
    # For metric based alerts:
    rule: typing.Optional[typing.Literal["is above", "is below", "is outside range", "is inside range"]] = None
    metric: typing.Optional[str] = None
    window: typing.Optional[pydantic.PositiveInt] = None
    # For 'is above' or 'is below':
    threshold: typing.Optional[typing.Union[int, float]] = None
    # For 'is outside range' or 'is inside range'
    range_low: typing.Optional[typing.Union[int, float]] = None
    range_high: typing.Optional[typing.Union[int, float]] = None

    @pydantic.validator("pattern", always=True)
    def check_pattern(cls, v, values):
        return check_input(v, values, "pattern", "source", ["events"])
    
    @pydantic.validator("rule", always=True)
    def check_rule(cls, v, values):
        return check_input(v, values, "rule", "source", ["metrics"])
    
    @pydantic.validator("metric", always=True)
    def check_metric(cls, v, values):
        return check_input(v, values, "metric", "source", ["metrics"])
    
    @pydantic.validator("window", always=True)
    def check_window(cls, v, values):
        return check_input(v, values, "window", "source", ["metrics"])

    @pydantic.validator("threshold", always=True)
    def check_threshold(cls, v, values):
        return check_input(v, values, "threshold", "rule", ["is above", "is below"])
    
    @pydantic.validator("range_low", always=True)
    def check_range_low(cls, v, values):
        return check_input(v, values, "range_low", "rule", ["is outside range", "is inside range"])
    
    @pydantic.validator("range_high", always=True)
    def check_range_high(cls, v, values):
        return check_input(v, values, "range_high", "rule", ["is outside range", "is inside range"])
