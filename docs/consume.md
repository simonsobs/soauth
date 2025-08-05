Consumer Mode
=============

To enable easy integration with other services, we provide a 'consumer' version of the
server that can accept POST requests with access tokens to validate them. This allows
for 'external server' authentication (with e.g.
[nginx](https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-subrequest-authentication/)).

To run the `soauth` server in consumer mode, you can use the same docker container as
normal. However, you'll need to change the command that is run to:
```
soauth run consume
```
This server runs on port 8002 and does two main things:

1. Handles the callback loop with the main `soauth` server
2. Hosts an endpoint, `/introspect`, that takes the cookies in the request and 
   returns a 200 code if the tokens are good, and a 401 if they are bad.

Using with Nginx
----------------

The most common use case for this kind of authentication is with another web service.
Nginx, for instance, can proxy all requests via the auth server to check if they
have valid tokens in them, configured as follows:
```
# 'Private' webpages hosted behind soauth.

# Reverse proxy to the 'consumer' service
location /auth/ {
  proxy_pass http://soauth:8002/;
}

# Handle the tokens.
location = /auth/introspect {
  proxy_pass http://soauth:8002/introspect;
  proxy_method POST;
}

# When we 401 in /private, we want to redirect to login
location @error401 {
  return 302 https://identity.simonsobservatory.org/login/$YOUR_UUID;
}

# The 'private' web pages hosted behind soauth
location /private/ {
  root /private;
  # This sends each request via /auth/introspect to make sure they have valid cookies.
  auth_request /auth/introspect;
  proxy_intercept_errors on;
  error_page 401 = @error401;
}

# We get redirected to the root of the auth after login.
location = /auth {
  return 302 /private/;
}
```
There are a few things here to note.

1. We host the `soauth` service at `/auth/*`. 
2. All requests to `/auth/introspect` are handled as POST requests (by default
   Nginx makes these requests as GET requests).
3. We set up a redirect on a 401 error directly to the login page for `soauth`.
4. We host as set of webpages at `/private/`, and add the `auth_request` directive.
5. When users are redirected by the auth service to its root, we send them instead
   to the root of the private service.