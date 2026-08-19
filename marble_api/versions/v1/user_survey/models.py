import re
from abc import ABC, abstractmethod
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, PositiveInt, model_validator

from marble_api.utils.models import (
    MarbleBaseModel,
    MarbleBaseModelPublic,
    MarbleBaseModelUpdate,
    MarbleUserModel,
    MarbleUserModelPublic,
    MarbleUserModelUpdate,
    partial_model,
)


class Question(BaseModel, ABC):
    """
    Base class for survey questions.

    Question text is the text of the question itself.
    The required field indicates if a SurveyResponse must contain an answer to this question.
    """

    text: str = Field(..., min_length=1)
    required: bool = False

    @abstractmethod
    def validate_response(self, response: Any) -> None:  # noqa: ANN401
        """Validate the response is valid for this question."""
        raise NotImplementedError


class TextQuestion(Question):
    """
    Question with a text (string) response.

    Specify minimum and maximum character length of the response.
    Optionally specify a regular expression pattern that the answer must match.
    """

    question_type: Literal["text"] = "text"
    min_length: int = Field(0, ge=0)
    max_length: int = Field(1000, le=1000)  # 1000 char limit to prevent abuse
    pattern: re.Pattern | None = None

    @model_validator(mode="after")
    def validate_length(self) -> Self:
        """Check that length values make sense."""
        assert self.min_length <= self.max_length, "max_length must be >= min_length"
        return self

    def validate_response(self, response: str) -> None:
        """Validate that a response is valid for this question."""
        assert isinstance(response, str), "Response '{r}'"


class ChoiceQuestion(Question):
    """
    Question with a multiple choice response.

    Specify minimum and maximum number of choices that a user can choose in a given answer.

    Specify the choices themselves as a dictionary where keys are unique choice IDs and values are the
    choice text to present to the user.

    The allow_other boolean indicates that users are allowed to specify another option (other than those
    specified in the choices dictionary).

    If the allow_other boolean is True, specify an optional regular expression pattern that the other option
    must match.
    """

    question_type: Literal["choice"] = "choice"
    min_choices: int = Field(1, ge=0)
    max_choices: PositiveInt | None = 1
    choices: dict[str, str] = Field(..., min_length=1)
    allow_other: bool = False
    pattern: re.Pattern | None = None

    @model_validator(mode="after")
    def validate_min_max_choices(self) -> Self:
        """Check that length values make sense."""
        if self.max_choices is not None:
            assert self.min_choices <= self.max_choices, "max_choices must be None or >= min_choices"
        return self

    @model_validator(mode="after")
    def validate_min_choices(self) -> Self:
        """Check that length values make sense."""
        assert self.min_choices <= len(self.choices), f"specify at least min_choices ({self.min_choices}) choices"
        return self


class Survey(MarbleBaseModel):
    """Survey containing questions."""

    survey: list[TextQuestion | ChoiceQuestion]


@partial_model
class SurveyUpdate(MarbleBaseModelUpdate, Survey):
    """Model to update a survey."""

    # TODO: ensure that can't be updated if there are associated responses.
    # TODO: allow updating/viewing a survey by the index of the question


class SurveyPublic(MarbleBaseModelPublic, Survey):
    """Model that shows publicly visible survey."""


class SurveyResponse(MarbleUserModel):
    """Response to a survey question."""


@partial_model
class SurveyResponseUpdate(MarbleUserModelUpdate, SurveyResponse):
    """Model to update a response to a survey question."""


class SurveyResponsePublic(MarbleUserModelPublic, SurveyResponse):
    """Model that shows publicly visible response to a survey question."""
