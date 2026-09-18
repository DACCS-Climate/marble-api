from typing import Literal

import httpx
import pytest


class AuthEnabledTest:
    request_method: str
    request_path_type: Literal["member", "collection"]
    auth_type: Literal["user", "admin"]

    @pytest.fixture
    async def make_request(self, async_client, member_route, collection_route):
        route = member_route if self.request_path_type == "member" else collection_route
        return getattr(async_client, self.request_method.lower())(route)

    async def test_authenticate_failure_unauthorized(self, auth_mock, make_request):
        auth_mock.mock(return_value=httpx.Response(200, json={"authenticated": False}))
        response = await make_request
        assert response.status_code == 403, response.json()

    async def test_authenticate_failure_upstream(self, auth_mock, make_request):
        auth_mock.mock(return_value=httpx.Response(500, json={}))
        response = await make_request
        assert response.status_code == 403, response.json()


class UserAuthTest(AuthEnabledTest):
    auth_type: str = "user"

    async def test_authenticate_failure_different_user(self, auth_mock, user, make_request):
        auth_mock.mock(
            return_value=httpx.Response(200, json={"authenticated": True, "user": {"user_name": user + "suffix"}})
        )
        response = await make_request
        assert response.status_code == 403, response.json()

    async def test_authenticate_success(self, auth_mock, user, make_request, member_route, records):
        auth_mock.mock(return_value=httpx.Response(200, json={"authenticated": True, "user": {"user_name": user}}))
        response = await make_request
        # note that 422 is ok here because we're just checking that the authentication worked, not that the
        # request was well formed otherwise
        assert response.status_code < 300 or response.status_code == 422, member_route


class AdminAuthTest(AuthEnabledTest):
    auth_type: str = "admin"

    async def test_authenticate_failure_not_admin(self, auth_mock, make_request):
        auth_mock.mock(return_value=httpx.Response(200, json={"authenticated": True, "user": {"group_names": []}}))
        response = await make_request
        assert response.status_code == 403

    async def test_authenticate_success(self, auth_mock, make_request, test_config):
        auth_mock.mock(
            return_value=httpx.Response(
                200, json={"authenticated": True, "user": {"group_names": [test_config.magpie_admin_group]}}
            )
        )
        response = await make_request
        # note that 422 is ok here because we're just checking that the authentication worked, not that the
        # request was well formed otherwise
        assert response.status_code < 300 or response.status_code == 422
