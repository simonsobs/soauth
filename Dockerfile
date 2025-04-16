FROM python:3.12

COPY ./soauth /packages/soauth
COPY pyproject.toml /packages/pyproject.toml
WORKDIR /packages

RUN pip install --no-cache-dir --editable .
RUN pip install --no-cache-dir --upgrade "psycopg[binary,pool]"
RUN pip install --no-cache-dir --upgrade "uvicorn"

WORKDIR /

CMD ["soauth", "run", "prod"]