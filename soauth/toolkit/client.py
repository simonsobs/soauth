"""
An API client for SOAuth, wraps around httpx.
"""

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from hashlib import md5
from pathlib import Path
from typing import Any

import httpx
from httpx._types import QueryParamTypes, RequestContent, RequestData, RequestFiles
from pydantic import BaseModel


class TokenData(BaseModel):
    access_token: str | None = None
    refresh_token: str
    access_token_expires: datetime | None = None
    refresh_token_expires: datetime | None = None


class SOAuth(httpx.Auth):
    """
    An authentication provider for httpx, providing threadsafe authentication access.
    """

    token_data: TokenData | None = None
    serialization_directory: Path
    identity_server: str
    token_tag: str

    def __init__(
        self,
        token_tag: str,
        *,
        api_key: str | None = None,
        serialization_directory: Path | None = None,
        identity_server: str | None = None,
    ):
        """
        Create the SOAuth httpx provider. Requires a 'token tag' that uniquely identifies this token
        on your system.

        Parameters
        ----------
        token_tag: str
            Required tag for this service, associated with the API key. Allows for (de)serialization
            of the keys to a file to enable storage between sessions. Example values would be `hippo`,
            `lightserve`, or whatever you like!
        api_key: str | None, optional
            The API key when using it in the first instance. If not provided, we will de-serialize your
            key from the `token_tag` (see example and documentation).
        serialization_directory: Path | None, optional
            The serialization directory for keys. If not provided, we use `~/.config/soauth`.
        identity_server: str | None, optional
            Which identity server to use, if not provided we use the default.

        Example
        -------
        The usage of `SOAuth` differs between first use and subsequent uses.

        First use:
        ```python
        import httpx
        from soauth.toolkit.client import SOAuth

        TOKEN_TAG = "hippo"
        API_KEY = "ashSDFo98hoaisdfsd..."

        client = httpx.Client(
            base_url="https://hippo.simonsobservatory.org",
            auth=SOAuth(
                TOKEN_TAG,
                api_key=API_KEY
            )
        )

        client.post("/whatever")
        ```
        Here, we have to specify the API key. Generally, we recommend doing this in an interactive
        shell before moving on to scripts that simply reference everything via the tag. After the
        first use, your original API key will expire, and as such running this again will not work.
        For subsequent uses, you should do:
        ```python
        import httpx
        from soauth.toolkit.client import SOAuth

        TOKEN_TAG = "hippo"

        client = httpx.Client(
            base_url="https://hippo.simonsobservatory.org",
            auth=SOAuth(TOKEN_TAG)
        )

        client.post("/whatever")
        ```
        Which will de-serialize the keys from the appropriate file.
        """
        if api_key is not None:
            self.token_data = TokenData(refresh_token=api_key)

        if serialization_directory is None:
            serialization_directory = Path.home() / ".config/soauth"

        if identity_server is None:
            identity_server = (
                "https://ingress.simonsobs-identity.production.svc.spin.nersc.org"
            )

        self.identity_server = identity_server
        self.serialization_directory = serialization_directory
        self.token_tag = token_tag

        self._sync_lock = threading.RLock()
        self._async_lock = asyncio.Lock()

    def sync_exchange_with_identity_server(self, refresh_token: str):
        url = f"{self.identity_server}/exchange"

        response = httpx.post(url, json={"refresh_token": refresh_token})

        if response.status_code != 200:
            raise ValueError(
                f"Failed to exchange token: {response.status_code} {response.text}"
            )

        self.token_data = TokenData.model_validate_json(response.content)
        self.serialize_tokens(token_data=self.token_data)

        return

    @property
    def filename(self):
        if not self.serialization_directory.exists():
            self.serialization_directory.mkdir(exist_ok=True, parents=True)
        return self.serialization_directory / self.token_tag

    def serialize_tokens(self, token_data: TokenData) -> Path:
        """
        Serializes the access tokens to disk.
        """

        with open(self.filename, "w") as handle:
            handle.write(token_data.model_dump_json())

        self.filename.chmod(0o600)

        return self.filename

    def deserialize_tokens(self) -> TokenData:
        """
        Reads the token data from file but does not do any code exchange.
        """

        with open(self.filename, "r") as handle:
            self.token_data = TokenData.model_validate_json(handle.read())

        return self.token_data

    def sync_get_token(self):
        with self._sync_lock:
            if self.token_data is None:
                self.deserialize_tokens()

            if self.token_data.access_token is None or (
                self.token_data.access_token_expires - datetime.now(tz=timezone.utc)
            ) < timedelta(minutes=5):
                self.sync_exchange_with_identity_server(
                    refresh_token=self.token_data.refresh_token
                )

            return self.token_data.access_token

    def sync_auth_flow(self, request):
        token = self.sync_get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    async def async_exchange_with_identity_server(self, refresh_token: str):
        url = f"{self.identity_server}/exchange"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"refresh_token": refresh_token})

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to exchange token: {response.status_code} {response.text}"
                )

        self.token_data = TokenData.model_validate_json(response.content)
        self.serialize_tokens(token_data=self.token_data)

        return

    async def async_get_token(self):
        async with self._async_lock:
            if self.token_data is None:
                # This must mean that we need to deserialize
                with open(self.filename, "r") as handle:
                    self.token_data = TokenData.Model_validate_json(handle.read())

            if self.token_data.access_token is None or (
                self.token_data.access_token_expires - datetime.now(tz=timezone.utc)
            ) < timedelta(minutes=5):
                await self.async_exchange_with_identity_server(
                    refresh_token=self.token_data.refresh_token
                )

            return self.token_data.access_token

    async def async_auth_flow(self, request):
        token = await self.async_get_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request


class SOAuthClient:
    """
    A non-threadsafe API client for SOAuth services. Making parallel requests with
    `threading` or `multiprocessing` is not supported.
    """

    def __init__(self, base_url: str, api_key: str | None = None):
        """
        Create a (non-threadsafe) SO Auth client. Do not use this even from
        multiple scripts at once!

        Parameters
        ----------
        base_url: str
            The URL for the API itself. If the API docs are hosted at
            mywebsite.org/favourites/best/docs, this would be
            mywebsite.org/favourites/best. All API calls will be made
            relative to this URL.

        api_key: str | None, optional
            The 'new' API key to use. If this is None, we assume that you
            have serialized the API key at ~/.config/soauth/$HASH where $HASH
            is the hash of the base_url.
        """

        self.base_url, self.base_url_hash = self._validate_base_url(base_url=base_url)
        self._initial_client_creation(api_key=api_key)
        return

    def _validate_base_url(self, base_url: str) -> tuple[str, str]:
        """
        Validates the base URL and returns its hash. Makes sure it does
        not end with a slash.
        """

        base_url = base_url if base_url[-1] != "/" else base_url[:-1]

        return (
            base_url,
            md5(base_url.encode("utf-8"), usedforsecurity=False).hexdigest(),
        )

    def _create_client(self, token_data: TokenData) -> httpx.Client:
        """
        Create the httpx internal client.
        """

        self._client = httpx.Client(
            base_url=self.base_url,
            cookies={
                "access_token": token_data.access_token,
                # CRITICAL: Do not include the refresh token; this client manages
                # its lifecycle. We _do not_ want the server to change it under
                # us!
            },
        )

        return self._client

    def _exchange_with_identity_server(self, refresh_token: str):
        """
        Exchange the refresh token with the identity server. Sets the token_data,
        and serializes it to the key file. If `self._client` is set, updates the cookies.
        """

        global _IDENTITY_SERVER

        url = f"{_IDENTITY_SERVER}/exchange"

        response = httpx.post(url, json={"refresh_token": refresh_token})

        if response.status_code != 200:
            raise ValueError(
                f"Failed to exchange token: {response.status_code} {response.text}"
            )

        self.token_data = TokenData.model_validate_json(response.content)
        self._serialize_tokens(token_data=self.token_data)
        self._create_client(token_data=self.token_data)

        return

    def _filename(self) -> Path:
        global _SERIALIZATION_DIRECTORY
        _SERIALIZATION_DIRECTORY.mkdir(parents=True, exist_ok=True)
        filename = _SERIALIZATION_DIRECTORY / self.base_url_hash
        return filename

    def _deserialize_tokens(self) -> TokenData:
        """
        Reads the token data from file but does not do any code exchange.
        """

        filename = self._filename()

        with open(filename, "r") as handle:
            self.token_data = TokenData.model_validate_json(handle.read())

        return self.token_data

    def _serialize_tokens(self, token_data: TokenData) -> Path:
        """
        Serializes the access tokens to disk.
        """

        filename = self._filename()

        with open(filename, "w") as handle:
            handle.write(token_data.model_dump_json())

        filename.chmod(0o600)

        return filename

    def _valid_token_data(self) -> TokenData:
        """
        Checks if token_data is valid. If it is, returns it; otherwise, performs
        the code exchange.
        """

        if (
            self.token_data.access_token_expires - datetime.now(tz=timezone.utc)
        ) < timedelta(minutes=5):
            # TODO: handle expiry of stuff!
            self._exchange_with_identity_server(
                refresh_token=self.token_data.refresh_token
            )

        return self.token_data

    def _validate_api_key(self, api_key: str | None = None) -> TokenData:
        """
        Either refresh the API key and access tokens from file or perform an exchange
        with the server. If api_key is None, we read from file.
        """

        if api_key is not None:
            self._exchange_with_identity_server(refresh_token=api_key)
            return self.token_data

        self._deserialize_tokens()

        return self._valid_token_data()

    def _initial_client_creation(self, api_key: str | None = None):
        """
        Use the provided kwargs to this object to create the initial client.
        """

        self._create_client(token_data=self._validate_api_key(api_key=api_key))

        return self._client

    def put(
        self,
        url: str,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: Any | None = None,
        params: QueryParamTypes | None = None,
        **kwargs,
    ):
        return self._client.put(
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            **kwargs,
        )

    def get(self, url: str, *, params: QueryParamTypes | None = None, **kwargs):
        return self._client.get(url=url, params=params, **kwargs)

    def post(
        self,
        url: str,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: Any | None = None,
        params: QueryParamTypes | None = None,
        **kwargs,
    ):
        return self._client.post(
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            **kwargs,
        )

    def delete(self, url: str, *, params: QueryParamTypes | None = None, **kwargs):
        return self._client.delete(url=url, params=params, **kwargs)
