Introduction
============

SOAuth attemps to be compatible with the OAuth2 specification. As such, authentication
occurrs through a series of steps:

1. Authentication is initialized through a redirection to an authorization page.
2. Once credentials have been validated, the user is redirected back to the original app,
   but to a specific endpoint that takes a 'code' that can be exchanged on the backend.
3. This 'code' is exchanged by the backend for an authentication token, giving access
   to the service. This token can be transformed into one providing access to the app.
4. The frontend for the app stores this token and passes it with each request for
   re-validation.