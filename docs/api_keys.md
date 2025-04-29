API Keys
========

Applications registered with SOAuth automatically qualify for 'login' session management,
which we outlined in the instructions on [creating an app](create.md). Many applications
also require the ability for users to generate 'API keys' that can be used to authenticate
against applications programatically.

SOAuth provides this functionality through the 'keys' sub-menu. Users can request
API keys, which are shown once and only once. These API keys are long strings that must
be protected.

The API Key Flow
----------------

API keys use the exact same access mechanism as the tokens used for web applications.
The key that is returned from the management interface is actually a refresh token, which
must be exchanged with the identity server for an access token before access to the
protected resources can be granted. Additionally, it's important to remember that
SOAuth implements 'refresh token rotation' - every time you get a new access token,
the refresh token is also replaced. The process works as follows:

1. A user retrieves an initial API key (refresh token A) from the management interface.
2. The user exchanges refresh token A for access token B and refresh token B via
   a post endpoint _at the identity service_.
3. The user makes use of the access token to access protected resources via the
   destination API, sending the token as a cookie or as a 'Authorization: Bearer
   {token}' header. The user must then either:
   - Manage the lifecycle of the access token themselves. Once access token B
     expires, they must exchange refresh token B for access token C and refresh
     token C, and continue on. This will involve handling 401 errors or careful
     timing of the age of the access token (its expiry time was provided by
     the identity service during the exchange).
   - Continually monitor the refresh token cookie as it comes back from the
     API endpoint. If it has changed, it must be serialized such that when the
     user's script or session ends, the correct refresh token is stored. Attempting
     to authenticate with refresh token A once token B, or token C, and so forth
     have been emitted by the indentity server will fail.

We provide functionality for managing this lifecycle within SOAuth itself. It is critical
to realise that API keys can only be used by a single client at a time; that should hopefully
be clear as a consequence of the refresh token rotation. You can generate as many 'parallel'
API keys you like from the management interface at this time.

Creating an API Key
-------------------

Creating an API key is simple, and can be handled through the web interface. Again, remember
that _after you first use this key, it will be invalidated_, and as such you either need
to manage its lifecycle yourself or use the built-in SOAuth tools.
![Navigation to the key creation/removal screen](key_create_1.png)
Then, click the 'create key' button on the appropriate tab:
![Create a new key](key_create_2.png)
Finally, you should copy the key out and make use of it.
![Copy out your key](key_create_3.png)


Revoking an API Key
-------------------

The list of all of your keys on the keys page, which can be navigated to from the management
interface home:
![Navigation to the key creation/removal screen](key_create_1.png)
To delete a key, you simply click on the 'Delete Key' button:
![Key deletion](key_revoke.png)
The next time this _refresh_ key is used, it will not work. Note that any _access tokens_
(i.e. currently active sessions) will remain value until they expire.

Using an API Key
----------------

In practice, you will need to communicate with both your destination application
and the identity server to use an API key. Here, we'll assume you are trying to
connect to an application `https://application.org` and using an identity server
at `https://soauth.org`. To fufill this flow:

First, `POST` your API key to `https://soauth.org/exchange` with structure
`{"refresh_token": API_KEY}`.

The response will be structured as:
```json
{
  "access_token": "ajdksalksd....",
  "access_token_expires": "2021-02-20:00:32:22Z",
  "refresh_token": "ASHKjHILhlasdfa....",
  "refresh_token_expires": "2021-08-20:00:32:22Z",
}
```
where `refresh_token` replaces your current API key.

To authenticate against the destination authentication provider, you can 
either set `access_token: "ajdksalksd...."` as a cookie, or provide the
`Bearer` `Authorization` header, as `Authorization: Bearer ajdksalksd...`
(or in python, `headers={"Authorization": "Bearer ajdksalksd..."}`).

Unless you include the `refresh_token` with your requests (not supported
when using headers), you are responsible for managing its lifecycle yourself.
You will need to again `POST` the new `refresh_token` to gain a new `access_token`
when it expires. API Keys/refresh tokens are typically valid for six months
after first being emitted.


HTTPX Integration
-----------------

We provide integration with the [httpx](https://www.python-httpx.org) client providing
a native authentication provider that is threadsafe. This works by internally managing the
authentication key lifecycle and serializing your refresh keys to disk. There is
additional documentation associated with the authentication object itself, but it is
worth knowing that it works with both `httpx.Client` _and_ `httpx.AsyncClient`.

To begin, register your API key with the SOAuth client:
```
soauth register {tag_name} {api_key}
```
For example:
```
soauth register hippo AHKSAJFH8a9ihknj89ahdsfias0d9fjoinJS...
```
The 'tag' is how you will refer to the API key in your script. By default, we
serialize keys to `~/.config/soauth/{tag_name}`, where we store both access
and refresh (API) tokens.

To use the authentication provider (`soauth.toolkit.client.SOAuth`) in a python script:
```python
import httpx
from soauth.toolkit.client import SOAuth

TOKEN_TAG = "hippo"

client = httpx.Client(
    base_url="https://hippo.simonsobs.org",
    auth=SOAuth(TOKEN_TAG)
)

client.post("/whatever")
```
Note that it is not generally safe to use these keys from multiple processes at once.

**Next**: [hosting SOAuth](hosting.md)