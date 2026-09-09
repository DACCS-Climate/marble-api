import bson
from faker.providers import BaseProvider
from geojson_pydantic import (
    Feature,
    FeatureCollection,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from marble_api.versions.v1.data_request.models import DataRequest, DataRequestPublic, DataRequestUpdate
from marble_api.versions.v1.survey.models import (
    ChoiceQuestion,
    ChoiceQuestionUpdate,
    Survey,
    SurveyPublic,
    SurveyResponse,
    SurveyResponsePublic,
    SurveyResponseUpdate,
    SurveyUpdate,
    TextQuestion,
    TextQuestionUpdate,
)


class GeoJsonProvider(BaseProvider):
    def point(self, dimensions=None):
        point = [self.generator.random.uniform(-180, 180), self.generator.random.uniform(-90, 90)]
        if dimensions == 3 or (dimensions is None and self.generator.pybool()):
            point.append(self.generator.random.uniform(-100, 100))
        return point

    def bbox(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.pybool()
        return [a for b in zip(*(sorted(x) for x in zip(self.point(dimensions), self.point(dimensions)))) for a in b]

    def line(self, dimensions=None):
        return [self.point(dimensions) for _ in range(self.generator.pyint(min_value=2, max_value=12))]

    def linear_ring(self, dimensions=None):
        ring = [self.point(dimensions) for _ in range(self.generator.random.randint(3, 100))]
        ring.append(list(ring[0]))
        return ring

    def _geo_base(self):
        base = {}
        if self.generator.random.random() < 0.5:
            base["bbox"] = self.bbox()
        return base

    def geo_point(self, dimensions=None):
        return Point(type="Point", coordinates=self.point(dimensions), **self._geo_base())

    def geo_multipoint(self, dimensions=None):
        return MultiPoint(
            type="MultiPoint",
            coordinates=[self.point(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))],
            **self._geo_base(),
        )

    def geo_linestring(self, dimensions=None):
        return LineString(type="LineString", coordinates=self.line(dimensions), **self._geo_base())

    def geo_multilinestring(self, dimensions=None):
        return MultiLineString(
            type="MultiLineString",
            coordinates=[self.line(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))],
            **self._geo_base(),
        )

    def geo_polygon(self, dimensions=None):
        return Polygon(type="Polygon", coordinates=[self.linear_ring(dimensions)], **self._geo_base())

    def geo_multipolygon(self, dimensions=None):
        return MultiPolygon(
            type="MultiPolygon",
            coordinates=[
                [self.linear_ring(dimensions) for _ in range(self.generator.pyint(min_value=1, max_value=12))]
            ],
            **self._geo_base(),
        )

    def stac_geometries(self, dimensions=None):
        return [
            self.geo_point(dimensions=dimensions),
            self.geo_multipoint(dimensions=dimensions),
            self.geo_linestring(dimensions=dimensions),
            self.geo_multilinestring(dimensions=dimensions),
            self.geo_polygon(dimensions=dimensions),
            self.geo_multipolygon(dimensions=dimensions),
        ]

    def collapsible_geometry_combos(self, dimensions=None):
        stac_geometries = self.stac_geometries(dimensions=dimensions)
        return [
            combo
            for i in range(0, len(stac_geometries), 2)
            for combo in ([stac_geometries[i]], [stac_geometries[i + 1]], stac_geometries[i : i + 2])
        ]

    def uncollapsible_geometry_combos(self, dimensions=None):
        stac_geometries = self.stac_geometries(dimensions=dimensions)
        combos = []
        for i in range(0, len(stac_geometries), 2):
            for j in range(i + 2, len(stac_geometries)):
                combos.append([stac_geometries[i], stac_geometries[j]])
                combos.append([stac_geometries[i + 1], stac_geometries[j]])
        return combos

    def collapsible_geometry_collections(self, dimensions=None):
        collapsible_geometry_combos = self.collapsible_geometry_combos(dimensions=dimensions)
        return [
            GeometryCollection(type="GeometryCollection", geometries=geos)
            for geos in collapsible_geometry_combos
            if len(geos) > 1
        ]

    def uncollapsible_geometry_collections(self, dimensions=None):
        uncollapsible_geometry_combos = self.uncollapsible_geometry_combos(dimensions=dimensions)
        return [
            GeometryCollection(type="GeometryCollection", geometries=geos) for geos in uncollapsible_geometry_combos
        ]

    def collapsible_features(self, dimensions=None):
        stac_geometries = self.stac_geometries(dimensions=dimensions)
        collapsible_geometry_collections = self.collapsible_geometry_collections(dimensions=dimensions)
        return [
            Feature(type="Feature", geometry=geo, properties={})
            for geo in stac_geometries + collapsible_geometry_collections
        ]

    def uncollapsible_features(self, dimensions=None):
        uncollapsible_geometry_collections = self.uncollapsible_geometry_collections(dimensions=dimensions)
        return [Feature(type="Feature", geometry=geo, properties={}) for geo in uncollapsible_geometry_collections]

    def collapsible_feature_collections(self, dimensions=None):
        collapsible_geometry_combos = self.collapsible_geometry_combos(dimensions=dimensions)
        collapsible_features = self.collapsible_features(dimensions=dimensions)
        collections = []
        for combo in collapsible_geometry_combos:
            collections.append(
                FeatureCollection(
                    type="FeatureCollection",
                    features=[Feature(type="Feature", geometry=geo, properties={}) for geo in combo],
                )
            )
        for feature in collapsible_features:
            collections.append(FeatureCollection(type="FeatureCollection", features=[feature]))
        return collections

    def uncollapsible_feature_collections(self, dimensions=None):
        uncollapsible_geometry_combos = self.uncollapsible_geometry_combos(dimensions=dimensions)
        uncollapsible_features = self.uncollapsible_features(dimensions=dimensions)
        collections = []
        for combo in uncollapsible_geometry_combos:
            collections.append(
                FeatureCollection(
                    type="FeatureCollection",
                    features=[Feature(type="Feature", geometry=geo, properties={}) for geo in combo],
                )
            )
        for feature in uncollapsible_features:
            collections.append(FeatureCollection(type="FeatureCollection", features=[feature]))
        return collections

    def collapsible_geojsons(self, dimensions=None):
        return (
            self.stac_geometries(dimensions=dimensions)
            + self.collapsible_geometry_collections(dimensions=dimensions)
            + self.collapsible_feature_collections(dimensions=dimensions)
        )

    def uncollapsible_geojsons(self, dimensions=None):
        return self.uncollapsible_geometry_collections(dimensions=dimensions) + self.uncollapsible_feature_collections(
            dimensions=dimensions
        )

    def collapsible_geojson(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.random.choice([3, 2])
        return self.generator.random.choice(self.collapsible_geojsons(dimensions))

    def uncollapsible_geojson(self, dimensions=None):
        if dimensions is None:
            dimensions = self.generator.random.choice([3, 2])
        return self.generator.random.choice(self.uncollapsible_geojsons(dimensions))


class DatetimeProvider(BaseProvider):
    def tz_aware_date_time_seconds_precision(self):
        return self.generator.date_time(tzinfo=self.generator.pytimezone()).replace(microsecond=0)


class DataRequestProvider(GeoJsonProvider, DatetimeProvider):
    def author(self):
        author_ = {"last_name": self.generator.last_name()}
        if self.generator.pybool():
            author_["first_name"] = self.generator.first_name()
        if self.generator.pybool():
            author_["email"] = self.generator.email()
        return author_

    def temporal(self):
        opt = self.generator.random.random()
        if opt < 1 / 3:
            return sorted(
                [
                    self.tz_aware_date_time_seconds_precision(),
                    self.tz_aware_date_time_seconds_precision(),
                ]
            )
        elif opt < 2 / 3:
            return [self.tz_aware_date_time_seconds_precision()] * 2
        else:
            return [self.tz_aware_date_time_seconds_precision()]

    def link(self):
        return {"href": self.generator.uri(), "rel": self.generator.word(), "type": self.generator.mime_type()}

    def asset(self):
        return {
            "href": self.generator.uri(),
            "type": self.generator.mime_type(),
            "title": self.generator.word(),
            "description": self.generator.sentence(),
            "roles": self.generator.words(nb=self.generator.random.randint(0, 10)),
        }

    def _data_request_inputs(self, unset=None):
        inputs = dict(
            id=bson.ObjectId(),
            user=self.generator.profile("username")["username"],
            updated=self.generator.tz_aware_date_time_seconds_precision(),
            title=self.generator.sentence(),
            description=(None if self.generator.pybool(30) else self.generator.paragraph()),
            authors=[self.author() for _ in range(self.generator.random.randint(1, 10))],
            geometry=self.collapsible_geojson(),
            temporal=self.temporal(),
            links=[self.link() for _ in range(self.generator.random.randint(0, 10))],
            assets={
                key: self.asset()
                for key in self.generator.pylist(
                    nb_elements=self.generator.pyint(1, 10), variable_nb_elements=False, value_types=[str]
                )
            },
            contact=self.generator.email(),
            extra_properties=({} if self.generator.pybool(10) else self.generator.pydict(value_types=[str])),
        )
        if unset:
            for field in unset:
                inputs.pop(field)
        return inputs

    def data_request(self, unset=None, **kwargs):
        return DataRequest(**{**self._data_request_inputs(unset=unset), **kwargs})

    def data_request_public(self, unset=None, **kwargs):
        return DataRequestPublic(**{**self._data_request_inputs(unset=unset), **kwargs})

    def data_request_update(self, unset=None, **kwargs):
        return DataRequestUpdate(**{**self._data_request_inputs(unset=unset), **kwargs})


class SurveyProvider(DatetimeProvider):
    example_pattern = r"^\w*\d*$"

    def question(self, unset=None, **kwargs):
        return (
            self.text_question(unset=unset, **kwargs)
            if self.generator.pybool()
            else self.choice_question(unset=unset, **kwargs)
        )

    def question_update(self, unset=None, **kwargs):
        return (
            self.text_question_update(unset=unset, **kwargs)
            if self.generator.pybool()
            else self.choice_question_update(unset=unset, **kwargs)
        )

    def _text_question_inputs(self, unset=None):
        min_length = self.generator.pyint(min_value=1, max_value=1000)
        max_length = self.generator.pyint(min_value=min_length, max_value=1000)
        inputs = dict(
            text=self.generator.sentence(),
            required=self.generator.pybool(),
            question_type="text",
            min_length=min_length,
            max_length=max_length,
            pattern=[None, self.example_pattern][self.generator.pybool()],
        )
        if unset:
            for field in unset:
                inputs.pop(field)
        return inputs

    def text_question(self, unset=None, **kwargs):
        return TextQuestion(**{**self._text_question_inputs(unset=unset), **kwargs})

    def text_question_update(self, unset=None, **kwargs):
        return TextQuestionUpdate(**{**self._text_question_inputs(unset=unset), **kwargs})

    def _choice_question_inputs(self, unset=None):
        min_choices = self.generator.pyint(min_value=1, max_value=10)
        max_choices = self.generator.pyint(min_value=min_choices, max_value=10) if self.generator.pybool() else None
        min_length = self.generator.pyint(min_value=1, max_value=1000)
        max_length = self.generator.pyint(min_value=min_length, max_value=1000)
        inputs = dict(
            text=self.generator.sentence(),
            required=self.generator.pybool(),
            question_type="choice",
            min_choices=min_choices,
            max_choices=max_choices,
            min_length=min_length,
            max_length=max_length,
            choices=self.generator.pydict(
                self.generator.pyint(min_value=min_choices, max_value=10), variable_nb_elements=False, value_types=[str]
            ),
            allow_others=self.generator.pybool(),
            pattern=[None, self.example_pattern][self.generator.pybool()],
        )
        if unset:
            for field in unset:
                inputs.pop(field)
        return inputs

    def choice_question(self, unset=None, **kwargs):
        return ChoiceQuestion(**{**self._choice_question_inputs(unset=unset), **kwargs})

    def choice_question_update(self, unset=None, **kwargs):
        return ChoiceQuestionUpdate(**{**self._choice_question_inputs(unset=unset), **kwargs})

    def _survey_inputs(self, unset=None):
        inputs = dict(
            id=bson.ObjectId(),
            updated=self.generator.tz_aware_date_time_seconds_precision(),
            user=self.generator.profile("username")["username"],
            user_visible=self.generator.pybool(),
            questions=[self.question() for _ in range(self.generator.random.randint(1, 10))],
        )
        if unset:
            for field in unset:
                inputs.pop(field)
        return inputs

    def survey(self, unset=None, **kwargs):
        return Survey(**{**self._survey_inputs(unset=unset), **kwargs})

    def survey_public(self, unset=None, **kwargs):
        return SurveyPublic(**{**self._survey_inputs(unset=unset), **kwargs})

    def survey_update(self, unset=None, **kwargs):
        return SurveyUpdate(**{**self._survey_inputs(unset=unset), **kwargs})

    def _string_answer_value(self, min_length, max_length, pattern):
        if pattern is None:
            return self.generator.pystr(min_chars=min_length, max_chars=max_length)
        else:
            # pattern is assumed to always match example_pattern
            format = "?" * self.generator.pyint(max_value=max_length)
            format += "#" * self.generator.pyint(
                min_value=max(0, min_length - len(format)),
                max_value=max(0, max_length - len(format)),
            )
            return self.generator.pystr_format(format)

    # Note: there is a 10% chance that a non-required answer will be None
    def text_answer(self, for_question: TextQuestion | None = None):
        if for_question is None:
            return self.generator.pystr(max_chars=10) if self.generator.pybool(90) else None
        if for_question.required or self.generator.pybool(90):
            return self._string_answer_value(for_question.min_length, for_question.max_length, for_question.pattern)

    def choice_answer(self, for_question: ChoiceQuestion | None = None):
        if for_question is None:
            if self.generator.pybool(90):
                return [self.generator.pystr(max_chars=10) for _ in range(self.generator.pyint(10))]
            return
        if not for_question.required and self.generator.pybool(10):
            return
        max_choices = for_question.max_choices or len(for_question.choices)
        answers = self.generator.words(
            nb=self.generator.pyint(for_question.min_choices, max_choices),
            ext_word_list=list(for_question.choices),
        )
        if for_question.allow_others:
            answers += [
                self._string_answer_value(for_question.min_length, for_question.max_length, for_question.pattern)
                for _ in range(
                    self.generator.pyint(
                        min_value=max(0, for_question.min_choices - len(answers)),
                        max_value=max(0, max_choices - len(answers)),
                    )
                )
            ]
        return answers

    def answer(self, for_question=None):
        if for_question:
            gen_text = for_question.question_type == "text"
        else:
            gen_text = self.generator.pybool()

        ans_generator = self.generator.text_answer if gen_text else self.generator.choice_answer
        return ans_generator(for_question=for_question)

    def _response_inputs(self, unset=None, for_survey=None):
        inputs = dict(
            id=bson.ObjectId(),
            updated=self.generator.tz_aware_date_time_seconds_precision(),
            user=self.generator.profile("username")["username"],
            survey_id=for_survey.id if for_survey else bson.ObjectId(),
            answers=[self.answer(for_question=question) for question in for_survey.questions]
            if for_survey
            else [self.answer() for _ in range(self.generator.random.randint(1, 10))],
        )

        if unset:
            for field in unset:
                inputs.pop(field)
        return inputs

    def response(self, unset=None, for_survey=None, **kwargs):
        return SurveyResponse(**{**self._response_inputs(unset=unset, for_survey=for_survey), **kwargs})

    def response_public(self, unset=None, for_survey=None, **kwargs):
        return SurveyResponsePublic(**{**self._response_inputs(unset=unset, for_survey=for_survey), **kwargs})

    def response_update(self, unset=None, for_survey=None, **kwargs):
        return SurveyResponseUpdate(**{**self._response_inputs(unset=unset, for_survey=for_survey), **kwargs})
