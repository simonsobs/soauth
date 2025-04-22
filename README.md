SOAuth
======

[![Test and Format](https://github.com/simonsobs/soauth/actions/workflows/pytest.yml/badge.svg)](https://github.com/simonsobs/soauth/actions/workflows/pytest.yml)

SOAuth is the Simons Observatory Authentication Framework. It is designed to wrap around
the GitHub authentication API, to serve several goals:

1. Provide access to proprietary data products based upon membership of the `simonsobs`
   GitHub organization.
2. Allow for public logins to SO services.
3. Allow for broad, fine-grained, permission setting for individual users.
4. Reduce code duplication for the various FastAPI-powered applications we maintain.

Documentation is available in [docs/](docs/README.md).
