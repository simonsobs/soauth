SOAuth
======

Web authentication for Simons Observatory services, backed by a centralized
authentiation server using OAuth2-like authentication patterns.

We focus on:

- Centralizing access control over proprietary data via the GitHub service
  (membership of specific organizations grants certain priviliges and group
  membership).
- A simple development experience.
- Use of a fully decentralized model (JWTs).

The main purpose of the Simons Observatory Authentication Service is to provide
significant SO-owned user information in the payload of the JWT.

Authentication Flow
-------------------

The authentication flow in Simons Observatory applications works as follows:

-  The creator of the application registers an 'App' with the service. Each
   'App' has a unique set of authentication keys that provide access to the
   entire cookie scope. For instance, all services hosted under a single
   domain would have a single scope (e.g. if you have services running under
   a reverse proxy, they would share the same 'App'), and hence should share
   keys.
-  A not logged in user is redirected to webauth.simonsobs.org (where a copy
   of this service is running).
-  The user is presented with a GitHub login interface, where they are asked
   to authenticate with their GitHub account. This provides us access to their
   information (username, email, organization membership). This login flow
   takes place on GitHub servers.
-  The user is redirected back to webauth.simonsobs.org, where their refresh
   and access tokens are generated to provide access to the protected resources
   under the original 'App'.
-  The user is then redirected back to the original application, where the
   access and refresh token may be set as cookies or otherwise used.

Access tokens are extremely pirivalged items. They alone provide access to
protectex resources. As such, they should be secured (e.g. through the use
of httpOnly cookies), and have short lifetimes.

To avoid users having to re-authenticate every few minutes, we also provide
a refresh token. Refresh tokens can be used to get a new access token,
which is entirely handled by the backend.

a) With each request, the user sends _both_ the access token and refresh
   token. If the acccess token is expired, the backend attempts to get
   a new one from the authentication service.
b) The backend uses the refresh token (on the user's behalf) to retrieve
   a new access and, critically, a new refresh token (with an unaltered
   expiry date).
c) The new access token is used to access the protected resource.
d) The new access and refresh token are provided to the client.

If any client tries to use an old refresh token to access resources, all
refresh tokens for that user and application are expired. They will be
forced to log in again through the GitHub interface.

Repository Contents
-------------------

This repository contains a number of components. First, it contains the
main server and database ORM for storing the authentication information.
Second, it contains pydantic models for authenticated users, such that
their contents can easily be deserialized. Finally, it contains
authentication wrappers for FastAPI services.

Core Endpoints
--------------

This server epxoses several core endpoints:

- `/login/{app_id}` - This allows users to be redirected to GitHub to authenticate
  and get a fresh refresh and authentication token.
- `/github` - This is used by GitHub as a callback URL. Your GitHub redirect URI
  should be pointed at this endpoint.
- `/exchange` - This allows for the refresh token to be exhanged for a new refresh
  token and access token.
- `/logout` - This invalidates your local refresh token andaccess token, as well as
  deleting the refresh token on the server so it can no longer be used.

OAuth2 Compatibility
--------------------

Not sure?
