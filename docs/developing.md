Developing SOAuth
=================

SOAuth is primarily built on top of two libraries:

- [SQLModel](https://sqlmodel.tiangolo.com), an ORM built on top of
  [pydantic](https://docs.pydantic.dev/latest/) and
  [sqlalchemy](https://www.sqlalchemy.org)
- [FastAPI](https://fastapi.tiangolo.com), a web framework built on top of
  [pydantic](https://docs.pydantic.dev/latest/) and
  [starlette](https://www.starlette.io)

Understanding these two libraries is critical to understanding how SOAuth
works and should be developed.

SOAuth is built out of six major layers:

- The database layer, specifying the object-relational mapping (ORM). This
  is found in `soauth/database`.
- The core layer, specifying basic functions like wrappers around hashlib and
  token encoding/decoding. Found in `soauth/core`.
- The service layer, encoding CRUD behaviours and internal application flow.
  This is found in `soauth/service`. The service layer builds heavily on top
  of the database and core layers.
- The API layer, which is served using FastAPI, allowing for HTTP access to
  various functionality like logins and token generation. This is found in
  `soauth/api`. This builds heavily on top of the service and core layers.
- The toolkit layer, which contains various library components used inside
  and by external users of SOAuth, for instance middleware for use with
  FastAPI and starlette applications. This layer is found in `soauth/toolkit`.
  This builds heavily on top of the API layer (but via network requests) and the
  core layer.
- The app layer, which presents the management frontend to users. This is
  a FastAPI server and Jinja2 templates, found in `soauth/app`. This builds
  on top of the toolkit and API layers.

Included are a somewhat comprehensive set of tests for the service layer down.
These can be run with `pytest`.

Getting set up
--------------

SOAuth can be installed in editable mode, and provides an optional `dev` set
of dependencies for use.

```
uv pip install -e ".[dev]"
```
Included in the dev dependencies is the `ruff` formatter. We use both formatting
and `fix` layer of this; before checking in code:
```
ruff format
ruff check --fix
```
To run the SOAuth development server, you will need to have 
[Testcontainers Desktop](https://testcontainers.com/desktop/) installed. This allows
for the test postgres database to be brought up and down. To run the development
server, you will need to have a set of GitHub credentials set as environment 
variables or otherwise passed through to the `pydantic_settings` model.
```
soauth run dev
```
Brings up a postgres container and runs both servers. You can reach them at
```
http://localhost:8000
http://localhost:8001
```
for the API server and management interface respectively. API docs are available
at
```
http://localhost:8000/docs
```
but require you to be logged in to an administrator account. It is strongly
recommended that you set the environment variable:
```
SOAUTH_CREATE_ADMIN_USERS='["jborrow"]'
```
to contain your own username. By default the example server creates another app
and user for you to play around with.

For code API docs (e.g. whatever you get from the docstrings), you can run
```
pdoc --docformat=numpy soauth
```
on the command line to bring up the documentation server.


Mocks
-----

SOAuth comes with some mocks for starlette and FastAPI middleware. This can allow
you to test unit test your application. 
```python
from soauth.toolkit.fastapi import mock_global_setup
from fastapi import FastAPI

app = mock_global_setup(
    app=FastAPI(),
    grants=["best", "grant", "ever!"]
)
```
On your request, this will set:
```python
request.user

SOUser(
    is_authenticated=True,
    display_name="test_user",
    user_id=UUID("00000000-0000-0000-0000-000000000001"),
    full_name="Test User",
    email="test@test.com",
    groups={"test_user"}
)

request.auth.scopes

["best", "grant", "ever!"]
```
To use this alongside the test client,
```python
from fastapi.testclient import TestClient
from fastapi import Request
from starlette.authentication import requires

@app.get("/")
@requires("best")
def home(request: Request):
    return {"hello": request.user}

client = TestClient(app)
print(client.get("/").content)
```
which returns:
```json
{
  "hello": {
    "is_authenticated": true,
    "display_name": "test_user",
    "user_id": "00000000-0000-0000-0000-000000000001",
    "full_name": "Test User",
    "email": "test@test.com",
    "groups": [
      "test_user"
    ]
  }
}
```