# Marble API

An API for the Marble platform.

## Requirement

- MongoDB server

## Developing

To start a development server:

```sh
python3 -m pip install .[dev]
MONGODB_URI="mongodb://localhost:27017" fastapi dev marble_api
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
- create a new `FastAPI` app in that directory and add any routes, models, etc. 
- in `app/main.py` import the app from the new version and append it to the `VERSIONS` constant.
- the `VERSIONS` constant contains tuples where the first value is the version prefix (eg: `/v2`, `/v3`, etc.)
  and the second value contains the corresponding app.

Note that all applications in the `VERSIONS` constant will implement any routes defined in previous versions
(ie. versions that are listed earlier in `VERSIONS`). 

If a route should not be made available in later versions, add the `@last_version` decorator to it.

For example, if v1 defines:

```python
@app.get("/test")
def test():
    ...
```

Then the `/test` route will be available in versions `/v2`, `/v3`, etc.

If v2 then redefines it as:

```python
@app.get("/test")
@last_version
def test():
    ...
```

Then the `/test` route will not be available from `/v3` onwards.

## Testing

To run tests:

```sh
python3 -m pip install -r requirements.test.txt
pytest test/
```
