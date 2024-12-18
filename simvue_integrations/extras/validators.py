"""Common.

Classses which could be used in the construction of multiple adapters.
"""
# ruff: noqa: DOC201

import enum
from typing import Callable, Literal, Optional, Union

from pydantic import BaseModel, Field, PositiveInt, ValidationInfo, field_validator

NAME_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:]+$"


# temp
class Operator(str, enum.Enum):
    """The operator to use to compare the reduced evaluation value to a given target threshold."""

    MORE_THAN = ">"
    LESS_THAN = "<"
    MORE_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="


OPERATORS: dict[str, Callable[[Union[int, float], Union[int, float]], bool]] = {
    ">": lambda x, y: x > y,
    "<": lambda x, y: x < y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    "==": lambda x, y: x == y,
}


def check_input(
    value_to_check: Union[str, float, int, None],
    validation_info: ValidationInfo,
    name_of_parameter: str,
    required_when_name: str,
    required_when_values: list,
) -> Union[str, float, int, None]:
    """Check that alert fields are correctly defined in cases where parameters are only required if another parameter is set.

    Parameters
    ----------
    value_to_check : Union[str, float, int, None]
        The value entered for the field being validated
    validation_info : ValidationInfo
        The values given for all other fields defined in the validator up to this point
    name_of_parameter : str
        The name of the field being validated
    required_when_name : str
        The name of the parameter which defines whether the field is required
    required_when_values : list
        The values of the parameter above which mean that the field is required

    Returns
    -------
    value_to_check : Union[str, float, int, None]
        The validated value

    Raises
    ------
    ValueError
        Raised if the parameter IS required but has NOT been provided, or if the parameter is NOT required but HAS been provided

    """
    other_values = validation_info.data
    if (
        other_values.get(required_when_name) in required_when_values
    ) and value_to_check is None:
        raise ValueError(
            f"'{name_of_parameter}' must be provided for alerts using '{required_when_name} = {other_values.get(required_when_name)}'."
        )
    elif (
        other_values.get(required_when_name) not in required_when_values
    ) and value_to_check is not None:
        raise ValueError(
            f"'{name_of_parameter}' must not be provided for alerts using '{required_when_name} = {other_values.get(required_when_name)}'."
        )
    return value_to_check


class AlertValidator(BaseModel, extra="forbid"):  # type: ignore
    """Validate the alerts when provided as a dictionary, before they are passed to create_alert."""

    name: Optional[str] = Field(None, pattern=NAME_REGEX)
    source: Literal["metrics", "events", "user"]
    frequency: Optional[PositiveInt] = Field(default=None, validate_default=True)
    notification: Optional[Literal["none", "email"]] = Field(default="none")
    description: Optional[str] = Field(default=None)
    # For event based alerts:
    pattern: Optional[str] = Field(default=None, validate_default=True)
    # For metric based alerts:
    rule: Optional[
        Literal["is above", "is below", "is outside range", "is inside range"]
    ] = Field(default=None, validate_default=True)
    metric: Optional[str] = Field(default=None, validate_default=True)
    window: Optional[PositiveInt] = Field(default=None, validate_default=True)
    # For 'is above' or 'is below':
    threshold: Optional[Union[int, float]] = Field(default=None, validate_default=True)
    # For 'is outside range' or 'is inside range'
    range_low: Optional[Union[int, float]] = Field(default=None, validate_default=True)
    range_high: Optional[Union[int, float]] = Field(default=None, validate_default=True)
    aggregation: Optional[Literal["average", "sum", "at least one", "all"]] = Field(
        default="average"
    )
    trigger_abort: Optional[bool] = Field(default=None, validate_default=True)

    @field_validator("frequency")
    def _check_frequency(cls, v, validation_info):
        """Check that frequency is specified if the alert source is metrics or events."""
        return check_input(
            v, validation_info, "frequency", "source", ["metrics", "events"]
        )

    @field_validator("pattern")
    def _check_pattern(cls, v, validation_info):
        """Check that pattern is specified if the alert source is events."""
        return check_input(v, validation_info, "pattern", "source", ["events"])

    @field_validator("rule")
    def _check_rule(cls, v, validation_info):
        """Check that rule is specified if the alert source is metrics."""
        return check_input(v, validation_info, "rule", "source", ["metrics"])

    @field_validator("metric")
    def _check_metric(cls, v, validation_info):
        """Check that metric is specified if the alert source is metrics."""
        return check_input(v, validation_info, "metric", "source", ["metrics"])

    @field_validator("aggregation")
    def _check_aggregation(cls, v, validation_info):
        """Check that aggregation is specified if the alert source is metrics."""
        return check_input(v, validation_info, "aggregation", "source", ["metrics"])

    @field_validator("window")
    def _check_window(cls, v, validation_info):
        """Check that window is specified if the alert source is metrics."""
        return check_input(v, validation_info, "window", "source", ["metrics"])

    @field_validator("threshold")
    def _check_threshold(cls, v, validation_info):
        """Check that threshold is specified if the alert rule is 'is above' or 'is below'."""
        return check_input(
            v, validation_info, "threshold", "rule", ["is above", "is below"]
        )

    @field_validator("range_low")
    def _check_range_low(cls, v, validation_info):
        """Check that range_low is specified if the alert rule is 'is outside range' or 'is inside range'."""
        return check_input(
            v,
            validation_info,
            "range_low",
            "rule",
            ["is outside range", "is inside range"],
        )

    @field_validator("range_high")
    def _check_range_high(cls, v, validation_info):
        """Check that range_high is specified if the alert rule is 'is outside range' or 'is inside range'."""
        return check_input(
            v,
            validation_info,
            "range_high",
            "rule",
            ["is outside range", "is inside range"],
        )
