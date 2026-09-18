import bson
import pytest
from pydantic import ValidationError
from pydantic_core import PydanticSerializationError

# import like this to avoid re-running test classes that start with Test...
from .....unit.utils.test_models import TestMarbleBaseModel as _TestMarbleBaseModel
from .....unit.utils.test_models import TestMarbleBaseModelPublic as _TestMarbleBaseModelPublic
from .....unit.utils.test_models import TestMarbleBaseModelUpdate as _TestMarbleBaseModelUpdate
from .....unit.utils.test_models import TestMarbleUserModel as _TestMarbleUserModel
from .....unit.utils.test_models import TestMarbleUserModelPublic as _TestMarbleUserModelPublic
from .....unit.utils.test_models import TestMarbleUserModelUpdate as _TestMarbleUserModelUpdate


class _TestQuestion:
    def test_text_non_empty(self, fake_class):
        fake_class()
        with pytest.raises(ValidationError):
            fake_class(text="")

    def test_validate_answer_required(self, fake_class):
        instance = fake_class(required=True)
        with pytest.raises(ValueError):
            instance.validate_answer(None)
        instance.required = False
        instance.validate_answer(None)


class TestQuestion(_TestQuestion):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.question

    def test_field_required(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(unset=["text"])

    def test_required_default(self, fake_class):
        assert fake_class(unset=["required"]).required is False


class _TestQuestionUpdate:
    def test_all_optional(self, fake_class):
        fields = type(fake_class()).model_fields
        fake_class(unset=list(fields))


class TestTextQuestion(_TestQuestion):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.text_question

    def test_question_type_is_text(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(question_type="other")
        fake_class(question_type="text")

    def test_min_max_length_bounds(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_length=0)
        with pytest.raises(ValidationError):
            fake_class(max_length=1001)

    def test_validate_length(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_length=8, max_length=7)

    def test_validate_answer(self, fake_class, fake):
        instance = fake_class()
        instance.validate_answer(fake.answer(for_question=instance))

    @pytest.mark.parametrize("answer", [1, True, {"set"}, {"dict": 2}])
    def test_validate_answer_invalid_type(self, fake_class, fake, answer):
        with pytest.raises(ValueError):
            fake_class().validate_answer(answer)

    @pytest.mark.parametrize(
        "length", range(3, 8), ids=lambda i: f"in_range[{i}]" if 4 <= i <= 6 else f"out_range[{i}]"
    )
    def test_validate_answer_length(self, fake_class, length):
        instance = fake_class(min_length=4, max_length=6)
        if 4 <= length <= 6:
            instance.validate_answer("a" * length)
        else:
            with pytest.raises(ValueError):
                instance.validate_answer("a" * length)

    def test_pattern_none(self, fake_class, fake):
        instance = fake_class(min_length=1, max_length=10, pattern=None)
        instance.validate_answer(fake.pystr(min_chars=1, max_chars=10))

    def test_pattern_set(self, fake_class):
        instance = fake_class(min_length=1, max_length=10, pattern=r"^\d\daa$")
        instance.validate_answer("24aa")
        with pytest.raises(ValueError):
            instance.validate_answer("bad answer")
        with pytest.raises(ValueError):
            instance.validate_answer("2aa")  # close answer


class TestTextQuestionUpdate(TestTextQuestion, _TestQuestionUpdate):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.text_question_update

    def test_validate_length(self, fake_class):
        # don't validate partial models
        fake_class(min_length=8, max_length=7)


class TestChoiceQuestion(_TestQuestion):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.choice_question

    def test_question_type_is_choice(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(question_type="other")
        fake_class(question_type="choice")

    def test_min_choices_positive(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_choices=0)

    def test_min_choices_not_nullable(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_choices=None)

    def test_max_choices_positive(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(max_choices=0)

    def test_max_choices_nullable(self, fake_class):
        fake_class(max_choices=None)

    def test_choices_non_empty(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(choices={})

    def test_validate_min_max_choices(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_choices=8, max_choices=7)

    def test_min_max_length_bounds(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_length=0)
        with pytest.raises(ValidationError):
            fake_class(max_length=1001)

    def test_validate_length(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_length=8, max_length=7)

    def test_min_choices_choices_available(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(min_choices=3, choices={"a": "a", "b": "b"})

    def test_validate_answer(self, fake_class, fake):
        instance = fake_class()
        instance.validate_answer(fake.answer(for_question=instance))

    @pytest.mark.parametrize("answer", ["a", 1, True, {"set"}, {"dict": 2}])
    def test_validate_answer_invalid_type(self, fake_class, fake, answer):
        with pytest.raises(ValueError):
            fake_class().validate_answer(answer)

    @pytest.mark.parametrize(
        "length", range(3, 8), ids=lambda i: f"in_range[{i}]" if 4 <= i <= 6 else f"out_range[{i}]"
    )
    def test_validate_choice_count(self, fake_class, length):
        choices = {str(i): "a" for i in range(8)}
        instance = fake_class(min_choices=4, max_choices=6, choices=choices)
        if 4 <= length <= 6:
            instance.validate_answer(list(choices)[:length])
        else:
            with pytest.raises(ValueError):
                instance.validate_answer(list(choices)[:length])

    def test_pattern_none(self, fake_class, fake):
        instance = fake_class(
            min_choices=1,
            max_choices=1,
            min_length=1,
            max_length=10,
            pattern=None,
            allow_others=True,
            choices={"1": "a"},
        )
        # min_chars=2 guarantees that the pystr will not be one of the choices
        instance.validate_answer([fake.pystr(min_chars=2, max_chars=10)])

    def test_pattern_set(self, fake_class):
        instance = fake_class(
            min_choices=1,
            max_choices=1,
            min_length=1,
            max_length=10,
            allow_others=True,
            pattern=r"^\d\daa$",
            choices={"1": "a"},
        )
        instance.validate_answer(["24aa"])
        with pytest.raises(ValueError):
            instance.validate_answer(["bad answer"])
        with pytest.raises(ValueError):
            instance.validate_answer(["2aa"])  # close answer


class TestChoiceQuestionUpdate(TestChoiceQuestion, _TestQuestionUpdate):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.choice_question_update

    def test_validate_length(self, fake_class):
        # don't validate partial models
        fake_class(min_length=8, max_length=7)

    def test_validate_min_max_choices(self, fake_class):
        # don't validate partial models
        fake_class(min_choices=8, max_choices=7)

    def test_min_choices_choices_available(self, fake_class):
        # don't validate partial models
        fake_class(min_choices=3, choices={"a": "a", "b": "b"})


class _TestSurvey:
    def test_at_least_one_question(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(questions=[])


class TestSurvey(_TestSurvey, _TestMarbleBaseModel):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.survey


class TestSurveyUpdate(_TestSurvey, _TestMarbleBaseModelUpdate):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.survey_update


class TestSurveyPublic(_TestSurvey, _TestMarbleBaseModelPublic):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.survey_public


class _TestSurveyResponse:
    def test_validate_response_valid(self, fake_class, fake):
        survey = fake.survey()
        response = fake_class(for_survey=survey)
        response.validate_response(survey)

    def test_validate_response_survey_no_id_match(self, fake_class, fake):
        survey = fake.survey()
        response = fake_class(for_survey=survey)
        survey.id = bson.ObjectId()
        with pytest.raises(ValueError):
            response.validate_response(survey)

    def test_validate_response_wrong_number_answers(self, fake_class, fake):
        survey = fake.survey(allow_others=True)
        response = fake_class(for_survey=survey)
        with pytest.raises(ValueError):
            fake_class(survey_id=survey.id, answers=response.answers[:-1]).validate_response(survey)
        with pytest.raises(ValueError):
            fake_class(survey_id=survey.id, answers=response.answers + ["other"]).validate_response(survey)

    def test_validate_response_invalid_answers(self, fake_class, fake):
        survey = fake.survey(allow_others=True, required=True)

        def _patch_validate_answer(*_a, **_kw):
            raise ValueError()

        survey.questions[0]._validate_answer = _patch_validate_answer
        response = fake_class(for_survey=survey)
        with pytest.raises(ValueError):
            response.validate_response(survey)


class TestSurveyResponse(_TestSurveyResponse, _TestMarbleUserModel):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.response

    def test_survey_id_set_when_serialized(self, fake_class):
        with pytest.raises(PydanticSerializationError):
            fake_class(unset=["survey_id"]).model_dump()


class TestSurveyResponseUpdate(_TestSurveyResponse, _TestMarbleUserModelUpdate):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.response_update


class TestSurveyResponsePublic(_TestSurveyResponse, _TestMarbleUserModelPublic):
    @pytest.fixture
    def fake_class(self, fake):
        return fake.response_public

    def test_survey_id_required(self, fake_class):
        with pytest.raises(ValidationError):
            fake_class(unset=["survey_id"])
