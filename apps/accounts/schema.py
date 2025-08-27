from drf_spectacular.extensions import OpenApiAuthenticationExtension
from .authentication import CookieJWTAuthentication


class CookieJWTAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = CookieJWTAuthentication
    name = 'cookieAuth'  # This is the name that will appear in the OpenAPI schema

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'cookie',
            'name': 'access_token',  # The name of the cookie
            'description': 'JWT authentication with HttpOnly cookies',
        }
