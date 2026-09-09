from collections.abc import Sequence
from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    FieldSerializationInfo,
    PositiveInt,
    field_serializer,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema
from stac_pydantic.links import Links

from marble_api.utils.models import (
    MarbleBaseModel,
    MarbleBaseModelPublic,
    MarbleBaseModelUpdate,
    MarbleUserModel,
    MarbleUserModelPublic,
    MarbleUserModelUpdate,
    PartialModel,
    Pattern,
    PyObjectId,
)

type AnyAnswer = str | list[str] | None


class Question(BaseModel):
    """
    Base class for survey questions.

    Question text is the text of the question itself.
    The required field indicates if a SurveyResponse must contain an answer to this question.
    """

    text: str = Field(..., min_length=1)
    required: bool = False

    def _validate_answer(self, answer: AnyAnswer) -> None:
        """
        Validate the answer is valid for this question.

        Subclasses should extend this function if additional validation logic is required.
        """

    def validate_answer(self, answer: AnyAnswer) -> None:
        """Validate the answer is valid for this question."""
        if self.required and answer is None:
            raise ValueError("Answer is required for this question.")
        if answer is not None:
            self._validate_answer(answer)


class TextQuestion(Question):
    """
    Question with a text (string) response.

    Specify minimum and maximum character length of the response.
    Optionally specify a regular expression pattern that the answer must match.
    """

    question_type: Literal["text"] = "text"
    min_length: int = Field(1, ge=1)
    max_length: int = Field(1000, le=1000)  # 1000 char limit to prevent abuse
    pattern: Pattern | None = None

    @model_validator(mode="after")
    def validate_length(self) -> Self:
        """Check that length values make sense."""
        if self.min_length > self.max_length:
            raise ValueError("max_length must be >= min_length")
        return self

    def _validate_answer(self, answer: AnyAnswer) -> None:
        """Check that an answer is valid for this question."""
        if not isinstance(answer, str):
            raise ValueError(f"Answer '{answer}' must be a valid string.")
        if not (self.min_length <= len(answer) <= self.max_length):
            raise ValueError(
                f"Answer '{answer}' must be between {self.min_length} and {self.max_length} characters long."
            )
        if self.pattern is not None:
            if self.pattern.search(answer) is None:
                raise ValueError(f"Answer '{answer}' must match pattern '{self.pattern.pattern}'")


class TextQuestionUpdate(TextQuestion, PartialModel):
    """Model to update a question with a text (string) response."""

    # skip inherited model validators for partial models
    validate_length = model_validator(mode="after")(lambda _: _)


class ChoiceQuestion(Question):
    """
    Question with a multiple choice response.

    Specify minimum and maximum number of choices that a user can choose in a given answer.

    Specify the choices themselves as a dictionary where keys are unique choice IDs and values are the
    choice text to present to the user.

    The allow_other boolean indicates that users are allowed to specify another option (other than those
    specified in the choices dictionary).

    If the allow_other boolean is True, specify an optional regular expression pattern that the other option
    must match and a minimum and maximum length of the other response.
    """

    question_type: Literal["choice"] = "choice"
    min_choices: PositiveInt = 1
    max_choices: PositiveInt | None = 1
    choices: dict[str, str] = Field(..., min_length=1)
    allow_others: bool = False
    min_length: int = Field(1, ge=1)
    max_length: int = Field(1000, le=1000)  # 1000 char limit to prevent abuse
    pattern: Pattern | None = None

    @model_validator(mode="after")
    def validate_min_max_choices(self) -> Self:
        """Check that length values make sense."""
        if self.max_choices is not None:
            if self.min_choices > self.max_choices:
                raise ValueError("max_choices must be None or >= min_choices")
        return self

    @model_validator(mode="after")
    def validate_min_choices(self) -> Self:
        """Check that length values make sense."""
        if self.min_choices > len(self.choices):
            raise ValueError(
                f"specify at least min_choices ({self.min_choices}) choices. ({len(self.choices)}) specified."
            )
        return self

    @model_validator(mode="after")
    def validate_length(self) -> Self:
        """Check that length values make sense."""
        if self.min_length > self.max_length:
            raise ValueError("max_length must be >= min_length")
        return self

    def _validate_answer(self, answer: AnyAnswer) -> None:
        """Check that an answer is valid for this question."""
        if not (
            isinstance(answer, Sequence) and not isinstance(answer, str) and all(isinstance(r, str) for r in answer)
        ):
            raise ValueError(f"Answer '{answer}' must be a sequence of strings.")
        if self.min_choices > len(answer):
            raise ValueError(f"Answer must contain at least {self.min_choices} options. Found {len(answer)}")
        if self.max_choices is not None and len(answer) > self.max_choices:
            raise ValueError(f"Answer cannot contain more than {self.max_choices} options. Found {len(answer)}")
        others = [r for r in answer if r not in self.choices]
        if self.allow_others:
            if not all(self.min_length <= len(o) <= self.max_length for o in others):
                raise ValueError(
                    f"Other answers must be between {self.min_length} and {self.max_length} characters long."
                )
            if self.pattern is not None:
                if not all(self.pattern.search(o) for o in others):
                    raise ValueError(f"Other option in answer does not match the pattern {self.pattern}")
        elif others:
            raise ValueError(f"Answer contains options that are not valid choices for this question: {others}")


class ChoiceQuestionUpdate(ChoiceQuestion, PartialModel):
    """Model to update a question with multiple choice response."""

    # skip inherited model validators for partial models
    validate_min_max_choices = model_validator(mode="after")(lambda _: _)
    validate_min_choices = model_validator(mode="after")(lambda _: _)
    validate_length = model_validator(mode="after")(lambda _: _)


class Survey(MarbleBaseModel):
    """Survey containing questions."""

    user_visible: bool
    questions: list[TextQuestion | ChoiceQuestion] = Field(..., min_length=1)


class SurveyUpdate(MarbleBaseModelUpdate, Survey):
    """Model to update a survey."""


class SurveyPublic(MarbleBaseModelPublic, Survey):
    """Model that shows publicly visible survey."""


class SurveyResponse(MarbleUserModel):
    """Responses to a survey."""

    # survey_id is set by the route after the model is first validated
    survey_id: SkipJsonSchema[PyObjectId | None] = None
    answers: list[AnyAnswer]

    @field_serializer("survey_id")
    def require_survey_id_set(self, value: str, info: FieldSerializationInfo) -> str:
        """Require that the survey id be set when the model is serialized."""
        if not value:
            raise ValueError(f"{info.field_name} must be set and non-empty")
        return value

    def validate_response(self, survey: Survey) -> None:
        """Check that all answers are valid according to the survey."""
        if self.survey_id != str(survey.id):
            raise ValueError("Responses are not for this survey. Survey ids do not match.")
        if len(self.answers) != len(survey.questions):
            raise ValueError(
                f"Survey has {len(survey.questions)} questions but only {len(self.answers)} answers given."
            )
        for question, answer in zip(survey.questions, self.answers):
            question.validate_answer(answer)


class SurveyResponseUpdate(MarbleUserModelUpdate, SurveyResponse):
    """Model to update responses to a survey."""


class SurveyResponsePublic(MarbleUserModelPublic, SurveyResponse):
    """Model that shows publicly visible responses to a survey."""

    survey_id: PyObjectId


class SurveysResponse(BaseModel):
    """Response model for returning multiple surveys."""

    surveys: list[SurveyPublic]
    links: Links


class SurveyResponsesResponse(BaseModel):
    """Response model for returning multiple surveys."""

    survey_responses: list[SurveyResponsePublic]
    links: Links
