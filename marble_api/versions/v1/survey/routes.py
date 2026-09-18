from typing import Annotated, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response

from marble_api.database import collection
from marble_api.utils.models import object_id
from marble_api.utils.routes import delete_record, get_record, get_records, patch_record, post_record
from marble_api.versions.v1.survey.models import (
    AnyAnswer,
    ChoiceQuestionUpdate,
    Survey,
    SurveyPublic,
    SurveyResponse,
    SurveyResponsePublic,
    SurveyResponsesResponse,
    SurveyResponseUpdate,
    SurveysResponse,
    SurveyUpdate,
    TextQuestionUpdate,
)

survey_user_router = APIRouter(prefix="/surveys")
survey_admin_router = APIRouter(prefix="/surveys")
survey_response_admin_router = APIRouter(prefix="/survey-responses")


def _survey_id(id_: str) -> ObjectId:
    return object_id(id_, HTTPException(status_code=404, detail=f"user survey with id={id_} not found"))


def _survey_response_id(id_: str) -> ObjectId:
    return object_id(id_, HTTPException(status_code=404, detail=f"user survey response with id={id_} not found"))


_survey_collection = collection("survey")
_response_collection = collection("survey-response")


@survey_admin_router.post("/")
async def post_survey(survey: Survey) -> SurveyPublic:
    """Create a new user survey and return the newly created user survey."""
    return await post_record(_survey_collection(), None, survey)


async def _check_survey_updatable(survey_id: str) -> None:
    """
    Surveys cannot be updated once answers exist for that survey or it is visible.

    This ensures that surveys cannot be updated to make a response invalid after the fact.
    """
    survey = await _survey_collection().find_one({"_id": ObjectId(survey_id)})
    if survey is None:
        raise HTTPException(status_code=404, detail="Not found")
    if survey.get("user_visible"):
        raise HTTPException(status_code=403, detail="Unable to update a user-visible survey")
    response = await _response_collection().find_one({"survey_id": survey_id})
    if response is not None:
        raise HTTPException(status_code=403, detail="Unable to update a survey with existing responses")


@survey_admin_router.patch("/{survey_id}")
async def patch_survey(survey_id: str, survey: SurveyUpdate) -> SurveyPublic:
    """Update fields of a user survey and return the updated user survey."""
    survey_update = survey.model_dump(exclude_unset=True, by_alias=True)
    if set(survey_update) != {"user_visible"}:
        # always allow updating the user_visible tag even if the survey is visible or has responses
        await _check_survey_updatable(survey_id)
    return await patch_record(_survey_collection(), _survey_id(survey_id), None, survey, SurveyPublic)


@survey_admin_router.patch("/{survey_id}/questions/{question_index}", dependencies=[Depends(_check_survey_updatable)])
async def patch_survey_question(
    survey_id: str, question_index: Annotated[int, Path(ge=0)], question: TextQuestionUpdate | ChoiceQuestionUpdate
) -> SurveyPublic:
    """Update a single question of a user survey and return the updated user survey."""
    return await patch_record(
        _survey_collection(),
        _survey_id(survey_id),
        None,
        question,
        SurveyPublic,
        set_prefix=f"questions.{question_index}.",
    )


@survey_user_router.get("/{survey_id}")
async def get_survey(survey_id: str) -> SurveyPublic:
    """Get a user survey with the given survey_id."""
    return await get_record(
        _survey_collection(), _survey_id(survey_id), None, additional_selector={"user_visible": True}
    )


@survey_admin_router.get("/{survey_id}")
async def get_survey_(survey_id: str) -> SurveyPublic:
    """Get a user survey with the given survey_id."""
    return await get_record(_survey_collection(), _survey_id(survey_id), None)


@survey_admin_router.delete("/{survey_id}", dependencies=[Depends(_check_survey_updatable)])
async def delete_survey(survey_id: str) -> Response:
    """Delete a user user survey with the given survey_id."""
    return await delete_record(_survey_collection(), _survey_id(survey_id), None)


@survey_user_router.get("/")
@survey_admin_router.get("/")
async def get_surveys(
    request: Request,
    user: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: Annotated[int, Query(le=100, gt=0)] = 10,
    sort_by: Literal["id", "created", "updated", "user_visible"] = "id",
    ascending: bool = True,
) -> SurveysResponse:
    """
    Return all user surveys.

    This response is paginated and will only return at most limit objects at a time (maximum 100).
    Use the offset and limit parameters to select specific ranges of user surveys.
    """
    return await get_records(
        collection=_survey_collection(),
        request=request,
        user=None,
        after=_survey_id(after) if after else None,
        before=_survey_id(before) if before else None,
        limit=limit,
        sort_by=sort_by,
        ascending=ascending,
        additional_selector=None if user is None else {"user_visible": True},
        records_key="surveys",
    )


async def _visible_survey(survey_id: str) -> Survey:
    """Check that the survey exists and is user visible."""
    record = await get_record(  # this will raise a 404 if the record is not found
        _survey_collection(),
        _survey_id(survey_id),
        None,
        additional_selector={"user_visible": True},
    )
    return Survey(**record)


def validate_response(survey: Survey, survey_response: SurveyResponse) -> None:
    """Validate a survey response for a given survey and raise an HTTP error if invalid."""
    try:
        survey_response.validate_response(survey)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@survey_user_router.post("/{survey_id}/response")
async def post_survey_response(
    user: str, survey_id: str, survey_response: SurveyResponse, survey: Annotated[Survey, Depends(_visible_survey)]
) -> SurveyResponsePublic:
    """
    Create a new user survey response and return the newly created user survey response.

    A user is only allowed one response per survey.
    """
    try:
        await get_record(_response_collection(), None, user=user, additional_selector={"survey_id": survey_id})
    except HTTPException:
        validate_response(survey, survey_response)
        return await post_record(_response_collection(), user, survey_response)
    raise HTTPException(status_code=409, detail="A response already exists for this survey. Use PUT to update instead.")


@survey_user_router.put("/{survey_id}/response")
async def put_survey_response(
    survey_id: str,
    survey_response: SurveyResponseUpdate,
    user: str,
    survey: Annotated[Survey, Depends(_visible_survey)],
) -> SurveyResponsePublic:
    """Update fields of survey response and return the updated survey response."""
    # uses patch_record even though this is a PUT method because there is only one updatable field
    updated_fields = survey_response.model_dump(exclude_unset=True)
    if "survey_id" in updated_fields and survey_id != updated_fields["survey_id"]:
        # do not allow updating survey_id field
        raise HTTPException(status_code=403, detail="Forbidden")
    if "answers" in updated_fields:
        survey_response_synth = SurveyResponse(survey_id=survey_id, answers=updated_fields["answers"])
        validate_response(survey, survey_response_synth)
    return await patch_record(
        _response_collection(),
        None,
        user,
        survey_response,
        SurveyResponsePublic,
        additional_selector={"survey_id": survey_id},
    )


@survey_user_router.patch("/{survey_id}/response/{answer_index}")
async def patch_survey_response(
    survey_id: str,
    user: str,
    answer_index: Annotated[int, Path(ge=0)],
    survey: Annotated[Survey, Depends(_visible_survey)],
    answer: AnyAnswer = None,  # default None means leaving this blank will set this answer to None (not answered)
) -> SurveyResponsePublic:
    """Update a single question of a user survey and return the updated user survey."""
    try:
        survey.questions[answer_index].validate_answer(answer)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except IndexError:
        raise HTTPException(status_code=404, detail=f"No question with index {answer_index} exists.")
    return await patch_record(
        _response_collection(),
        None,
        user,
        {f"answers.{answer_index}": answer},
        SurveyResponsePublic,
        additional_selector={"survey_id": survey_id},
    )


@survey_user_router.get("/{survey_id}/response", dependencies=[Depends(_visible_survey)])
async def get_survey_response(survey_id: str, user: str) -> SurveyResponsePublic:
    """Return the user survey response for the given survey."""
    return await get_record(_response_collection(), None, user, additional_selector={"survey_id": survey_id})


@survey_response_admin_router.get("/{response_id}")
async def get_survey_response_(response_id: str) -> SurveyResponsePublic:
    """Return a user survey response."""
    return await get_record(_response_collection(), _survey_response_id(response_id), None)


@survey_response_admin_router.delete("/{response_id}")
async def delete_survey_response(response_id: str) -> Response:
    """Delete a user survey response."""
    return await delete_record(_response_collection(), _survey_response_id(response_id), None)


@survey_response_admin_router.get("/")
async def get_survey_responses(
    request: Request,
    user: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: Annotated[int, Query(le=100, gt=0)] = 10,
    sort_by: Literal["id", "created", "updated", "survey_id"] = "id",
    ascending: bool = True,
) -> SurveyResponsesResponse:
    """
    Return all user survey responses.

    This response is paginated and will only return at most limit objects at a time (maximum 100).
    Use the offset and limit parameters to select specific ranges of user survey responses.
    """
    return await get_records(
        collection=_response_collection(),
        request=request,
        user=user,
        after=_survey_response_id(after) if after else None,
        before=_survey_response_id(before) if before else None,
        limit=limit,
        sort_by=sort_by,
        ascending=ascending,
        records_key="survey_responses",
    )
