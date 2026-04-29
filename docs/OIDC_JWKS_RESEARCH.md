# OIDC And JWKS Research

Sources:

- OpenID Connect Discovery 1.0: <https://openid.net/specs/openid-connect-discovery-1_0.html>
- RFC 7517 JSON Web Key: <https://www.rfc-editor.org/rfc/rfc7517>

## Implementation Notes

- OpenID Provider metadata exposes `jwks_uri`, which clients use to fetch signing keys.
- JWKS keys can use `kid` to select the correct key for a JWT header.
- Praetor supports `PRAETOR_JWT_JWKS_URI` directly or `PRAETOR_OIDC_DISCOVERY_URL` when the issuer should advertise the JWKS endpoint.
- Praetor currently verifies RS256 tokens through RSA public keys built from JWK `n` and `e`, then applies issuer, audience, expiry, not-before, and RBAC role checks.
- HS256 remains available only as the local/simple JWT mode when no JWKS or discovery URL is configured.
