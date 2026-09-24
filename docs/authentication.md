# Authentication

Authentication verifies the identity of a user or service.

Passwords should never be stored in plaintext. They should be protected
using a password hashing algorithm such as Argon2id.

After successful authentication, an application may issue an access token
that represents the authenticated user.

Access tokens should have an expiration time and should not be logged.
