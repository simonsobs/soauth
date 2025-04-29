SOAuth
======

<img src="../soauth/app/apple-touch-icon.png" width="128px" />

Looking for API Docs? Run `pdoc --docformat=numpy soauth` on the command line. We do not
maintain a hosted copy of the documentation at this time. Full developer documentation for
the API is available at `/docs` on the main server.

Statement of Need
-----------------

SOAuth is the Simons Observatory Authentication Framework. It is designed to wrap around
the GitHub authentication API, to serve several goals:

1. Provide access to proprietary data products based upon membership of the `simonsobs`
   GitHub organization.
2. Allow for public logins to SO services.
3. Allow for broad, fine-grained, permission setting for individual users.
4. Reduce code duplication for the various FastAPI-powered applications we maintain.

Table of Contents
-----------------

- [Authentication Flow](introduction.md)
- [Creating an App](create.md)
- [Sample App](sample.md)
- [API Keys](api_keys.md)
- [Hosting SOAuth](hosting.md)
- [Developing SOAuth](developing.md)