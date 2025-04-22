A Sample App
============

To assist in understanding the authorization flow through a 'real' application, here
we'll walk you through a sample FastAPI app. To get set up with the keys you
will need (to save as secrets or environment variables), you will need to follow
the [app registration/creation instructions](create.md).

First, you will need to read in the details so they can be used in your app:
```python
import os
APP_ID = os.environ["APP_ID"]
BASE_URL = os.environ["BASE_URL"]
AUTHENTICATION_SERVICE_URL = os.environ["APPLICATION_SERVICE_URL"]
PUBLIC_KEY = os.environ["PUBLIC_KEY"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
# Note that SOAuth always uses this as a key pair type, so you can probably
# get away with hardcoding it.
KEY_PAIR_TYPE = "Ed25519"
```
Here we use the `os` module to read in environment variables. For a larger app,
you will want to consider something like
[pydantic_settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/),
which provides validation and default options out of the box.

Next, we'll want to set up our FastAPI app and apply the `global_setup`
function:
```python
from fastapi import FastAPI
from soauth.toolkit.fastapi import global_setup

app = global_setup(
    FastAPI(),
    app_base_url=BASE_URL,
    authentication_base_url=AUTHENTICATION_SERVICE_URL,
    app_id=APP_ID,
    client_secret=CLIENT_SECRET,
    public_key=PUBLIC_KEY,
    key_pair_type=KEY_PAIR_TYPE,
)
```
This is all we need to do to protect our application. You may want to
add exception handlers (which we won't cover here, see
[the bottom section](create.md) in the app creation documentation) for
things like 401 authorization errors.

Now, let's add a way for users to login (and get access tokens and refresh
keys):
```python
from fastapi import Request
from fastapi.responses import HTMLResponse

@app.get("/")
async def homepage(request: Request):
  if request.user.is_authenticated:
    return HTMLResponse(
      "You are logged in. "
      "<a href='proprietary'>Prop check</a> "
      f"<a href='logout'>Logout</a>"
    )
  else:
    return HTMLResponse(f"<a href='{request.app.login_url}' referrerpolicy='no-referrer-when-downgrade'>Login</a>")
```
When users are first presented with this page they have
`request.user.is_authenticated` set to `False` and as such see the login link.
When they are logged in, they see the ability to log out (which goes to the `/logout`
endpoint; you can also use `request.app.logout_url`) and to go to another
endpoint, `proprietary`:
```python
from starlette.authentication import requires

@app.get("/proprietary")
@requires("simonsobs")
async def prop(request: Request):
  return HTMLResponse(
    "You have the 'simonsobs' auth credential. "
    f"All your credentials: {request.auth.scopes}"
  )
```
The proprietary endpoint uses the `starlette` `requires` decorator which states
that `simonsobs` must be in the user's `request.auth.scopes`. You can check this
list yourself if you need, like in a template where you want to render something
different depending on available scopes.


Full App
--------

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from soauth.toolkit.fastapi import global_setup
from starlette.authentication import requires
import os

APP_ID = os.environ["APP_ID"]
BASE_URL = os.environ["BASE_URL"]
AUTHENTICATION_SERVICE_URL = os.environ["APPLICATION_SERVICE_URL"]
PUBLIC_KEY = os.environ["PUBLIC_KEY"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
KEY_PAIR_TYPE = "Ed25519"


app = global_setup(
    FastAPI(),
    app_base_url=BASE_URL,
    authentication_base_url=AUTHENTICATION_SERVICE_URL,
    app_id=APP_ID,
    client_secret=CLIENT_SECRET,
    public_key=PUBLIC_KEY,
    key_pair_type=KEY_PAIR_TYPE,
)


@app.get("/")
async def homepage(request: Request):
  if request.user.is_authenticated:
    return HTMLResponse(
      "You are logged in. "
      "<a href='proprietary'>Prop check</a> "
      f"<a href='logout'>Logout</a>"
    )
  else:
    return HTMLResponse(f"<a href='{request.app.login_url}' referrerpolicy='no-referrer-when-downgrade'>Login</a>")
  

@app.get("/proprietary")
@requires("simonsobs")
async def prop(request: Request):
  return HTMLResponse(
    "You have the 'simonsobs' auth credential. "
    f"All your credentials: {request.auth.scopes}"
  )
```

**Next**: [hosting SOAuth](hosting.md)