How to contribute
=================

There are many ways to contribute to SOAuth:

1. Through opening issues in [our tracker](https://github.com/simonsobs/soauth/issues).
2. By contributing [pull requests](https://github.com/simonsobs/soauth/pulls).
3. By sending feedback to the maintainers on Slack.

Issues
------

We are happy to field issues from users of SOAuth, through the GitHub
[issue tracker](https://github.com/simonsobs/soauth/issues). When creating an
issue, please state:

- Whether you are using the production instance of SOAuth or a development one, and:
    - The UTC time at which you experienced the issue (if production)
    - A trace of the logs from the server (if development)
- How to reproduce the issue
- A link to your code that uses SOAuth as a provider

Code Contributions
------------------

Because of the nature of SOAuth, we are currently only open to direct code
contributions from members of the Simons Observatory Data Delivery team. If you
are interested, please reach out to Josh Borrow on Slack. Unfortunately we are
not able to accept contributions from non-SO members at this time.

When making code contributions, please make sure that:

- Your code is formatted and linted with ruff (`ruff format; ruff check --fix`)
- New features include documentation along with code
- You have read the [developer docs](docs/developing.md)