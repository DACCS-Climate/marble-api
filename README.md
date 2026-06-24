# Marble API

An API for the Marble platform.

## Requirement

- MongoDB server

## Authentication and Authorization

Marble API uses [Magpie](https://github.com/ouranosinc/magpie) for authentication.

Authentication is enforced for the following routes:

- admin routes: `/vX/admin/` (where `X` is a version number)
- user routes: `/vX/users/Y/` (where `X` is a version number and `Y` is a user name)

Only users who belong to the group named "administrators" in Magpie will have access to
the admin routes. Only users whose Magpie user name matches the `Y` in user routes will
have access to the given user route.

Authn/z can be configured with the following environment variables:

- `MARBLE_API_MAGPIE_AUTH_ENABLED`
    - default: `True`
    - type: boolean
    - set to `False` to disable authentication entirely (this is not recommended in a production environment)
- `MARBLE_API_MAGPIE_URL`
    - default: `None`
    - type: string (URL format)
    - set to the URL for the Magpie instance used to authenticate users
- `MARBLE_API_MAGPIE_ADMIN_GROUP`
    - default: `administrators`
    - type: string
    - change this if you want a different Magpie group to be have access to the admin routes

When integrating Marble API with the [birdhouse](https://github.com/bird-house/birdhouse-deploy/) platform we
recommend enabling it with the 
[Marble API component](https://github.com/DACCS-Climate/marble-config/tree/main/components/marble-api). 
This sets default environment variables that will work with most birdhouse deployments.

## Developing

To start a development server:

```sh
python3 -m pip install .[dev]
MARBLE_API_MONGODB_URI="mongodb://localhost:27017" fastapi dev marble_api
```

This assumes that you have a mongodb service running at `mongodb://localhost:27017`.

Or to start developing using docker:

```sh
docker compose -f docker-compose.dev.yml up
```

This will start a dedicated mongodb container for use with your app. Note that this will
track changes you make dynamically so you don't have to restart the container if you make
changes to the source code while the container is running.

### Contributing

We welcome any contributions to this code. To submit suggested changes, please do the following:

- create a new feature branch off of `main`
- update the code, write/update tests, write/update documentation
- submit a pull request targetting the `main` branch

### Coding Style

This codebase uses the [`ruff`](https://docs.astral.sh/ruff/) formatter and linter to enforce style policies.

To check that your changes conform to these policies please run:

```sh
ruff format
ruff check
```

You can also set up pre-commit hooks that will run these checks before you create any commit in this repo:

```sh
pre-commit install
```

### Versioning

Marble API is a versioned REST API. Backwards compatible changes can be made to existing versions.
If you wish to introduce backwards incompatible changes, you must create a new version.

To create a new version:

- create a new directory under `app/versions` with the name of the next version (eg: v2, v3, etc.)
- create a new `fastapi.APIRouter` router in that directory and add any routes, models, etc. 
- the new router should have a prefix of the form `vX` where `X` is the version number (eg: `/v2`, `/v3`, etc.)
- in `app/main.py` import the app from the new version and add it to the app with `.include_router`.

## Testing

To run tests:

```sh
python3 -m pip install .[dev]
MARBLE_API_MONGODB_URI="mongodb://localhost:27017" pytest ./test
```

This assumes that you have a mongodb service running at `mongodb://localhost:27017`.

Alternatively you can run start up the development stack with docker compose and then
run tests in the docker container:

```sh
docker compose -f docker-compose.dev.yml up -d
docker compose exec marble_api pytest ./test
```
