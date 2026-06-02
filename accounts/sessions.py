"""JWT session revocation (refresh-token blacklisting).

simplejwt records an ``OutstandingToken`` for every refresh token minted while
the ``token_blacklist`` app is installed. Blacklisting them all immediately
stops any further refreshes for that user — so after a password reset (or, later,
a forced sign-out) a stolen session dies once its short-lived access token
expires.
"""

from __future__ import annotations

from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def revoke_all_refresh_tokens(user) -> int:
    """Blacklist every outstanding refresh token for ``user``. Returns the count."""
    revoked = 0
    for outstanding in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=outstanding)
        if created:
            revoked += 1
    return revoked
