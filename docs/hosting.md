Hosting SOAuth
==============

Requirements
------------

SOAuth requires a database to persist data between sessions. Additional important
(but small) data is also stored on disk (see configuration). The database can either
be a SQLite database, or a PostgreSQL database (we strongly recommend PostgreSQL).
Wherever possible, asynchronous database calls are used.

To configure the database, the following environment variables are used:

- `SOAUTH_DATABASE_TYPE`, taking the value "sqlite" OR "postgres"
- `SOAUTH_DATABASE_USER`, the database user or unset for sqlite
- `SOAUTH_DATABASE_PASSWORD`, the database password or unset for sqlite
- `SOAUTH_DATABASE_PORT`, the database port or unset for sqlite
- `SOAUTH_DATABASE_HOST`, the database host or unset for sqlite
- `SOAUTH_DATABASE_DB`, the database to use or file for sqlite

On first startup, the server will create all necessary tables and schemas.
You can run the server with `SOAUTH_DATABASE_ECHO="yes"` for debugging purposes.

Management & API Servers
------------------------

To host a production instance of SOAuth, you can use the Docker container.
SOAuth is made up of two components: the base API layer, and a _separate server_
that runs the management interface. The API runs on port 8000, and the management
interface runs on port 8001.

The recommended way of hosting this is through a reverse proxy. This also allows
the proxy server to handle SSL certificates.

An example nginx config would look like (note that this configuration does not 
explicitly handle SSL certificates):

```
server {
    location / {
        root /ssl/www;
        autoindex on;
        proxy_pass http://soauth:8000/;
    }

    location /management/ {
        proxy_pass http://soauth:8001/;
    }

    location = / {
        return 301 /management/;
    }
}
```

If you are unable to run inside a docker container, you may use the `soauth run prod`
command which runs the two servers in this configuration.

Configuration
-------------

There are many possible configuration variables for SOAuth. Here we will only discuss
those relevant to running a production server.

### Security

These variables set security-based parameters. It is best to leave them as defaults,
unless you have a strong reason for changing them.

- `SOAUTH_KEY_PAIR_TYPE="Ed25519"`, the key pair type to use. Only the default is supported
- `SOAUTH_KEY_PASSWORD="CHANGEME"`, the key password to use, rendering a database leak of keys less useful
- `SOAUTH_REFRESH_KEY_EXPIRY=1.572e+7`, the expiry time of refresh keys. Default: 26 weeks
- `SOAUTH_ACCESS_KEY_EXPIRY=08:00:00`, the expiry time of access keys. Default is 8 hours
- `SOAUTH_STALE_LOGIN_EXPIRY=00:30:00`, how long users have to complete a login. Default is 30 minutes
- `SOAUTH_LOGIN_RECORD_LENGTH=1.21e+6`, how long to keep a record of user logins. Default is 2 weeks

### Hostnames

These are the hostnames that your server will be seen by from the outside world.
They are used for redirects, and for internal configuration.

- `SOAUTH_HOSTNAME=http://localhost:8000`, the address of your running API server, e.g. `https://soauth.org`
- `SOAUTH_MANAGEMENT_PATH=/management`, where to host the management interface
- `SOAUTH_MANAGEMENT_HOSTNAME=http://localhost:8001`, the management hostname, usually the same as `SOAUTH_HOSTNAME`

### GitHub

To authenticate with GitHub, you will need to produce an [OAuth2 app](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).
You should set the redirect URL to `{SOAUTH_HOSTNAME}/github`.

- `SOAUTH_GITHUB_CLIENT_ID`, the client ID
- `SOAUTH_GITHUB_CLIENT_SECRET`, the client secret
- `SOAUTH_REDIRECT_URI`, whatever you told GitHub to redirect to
- `SOAUTH_GITHUB_ORGANIZATION_CHECKS`, a list of strings for github orgs to
   check against. If users are part of these organizations, they will be given
   grants with the same value as the organization name. For example, setting
   this to `["simonsobs"]` will check against membership in the `simonsobs`
   organization and add `simonsobs` to the list of grants for member users.

### Storage

As part of allowing users to authenticate from the management interface, SOAuth
needs to store an internal set of app credentials. These are stored in files,
with the names given below. This data **must be persisted**, so it is recommended
to mount a volume.

- `SOAUTH_APP_ID_FILENAME`, where to store the app id, suggest `/data/app_id`
- `SOAUTH_CLIENT_SECRET_FILENAME`, where to store the client secret, suggest `/data/client_secret`
- `SOAUTH_PUBLIC_KEY_FILENAME`, where to store the public_key, suggest `/data/public_key`


Example
-------

Imagine we are running on a kubernetes cluster, and want to host our
SOAuth server at `soauth.org`. We will need three containers:

- `nginxinc/nginx-unprivileged:latest` or `nginx:latest`
- `postgres:latest`
- `soauth` (e.g. `jborrow/soauth:0.1.0`; this is probably wildly out of date by the time you
  are reading this)

They should be networked together. Nginx should serve the management interface at
`soauth.org/management` and the API at `soauth.org`. `postgres` should have a
database created called `soauth` (`su postgresql; createdb soauth`). The following
configuration could then be set:

```
SOAUTH_GITHUB_CLIENT_ID=asdf78gkbjdsfas
SOAUTH_GITHUB_CLIENT_SECRET=f30b159a1b27a958044ccc63ffd717e
SOAUTH_GITHUB_REDIRECT_URI=https://soauth.org/github
SOAUTH_GITHUB_ORGANIZATION_CHECKS='["simonsobs"]'

SOAUTH_APP_ID_FILENAME=/data/app_id
SOAUTH_CLIENT_SECRET_FILENAME=/data/client_secret
SOAUTH_PUBLIC_KEY_FILENAME=/data/public_key

SOAUTH_HOSTNAME=https://soauth.org
SOAUTH_MANAGEMENT_HOSTNAME=https://soauth.org

SOAUTH_DATABASE_TYPE=postgres
SOAUTH_DATABASE_USER=postgres
SOAUTH_DATABASE_PASSWORD=alls67itauksgdf67u6asdf
SOAUTH_DATABASE_PORT=5432
SOAUTH_DATABASE_HOST=postgres
SOAUTH_DATABASE_DB=soauth
```

Before running the container for the first time, it would be wise to mount a
persistent volume at `/data` with read/write permissions for the user running
the `soauth` server, for the local data to be stored.

**Next**: [developing SOAuth](developing.md)