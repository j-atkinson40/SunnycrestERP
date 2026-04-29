"""Email provider abstraction — Phase W-4b Layer 1 §3.26.15.6.

Per BRIDGEABLE_MASTER §3.26.15.6, every email account connects through
a provider implementation that conforms to the ``EmailProvider`` ABC.
Step 1 ships the ABC + 4 stub implementations:

    GmailAPIProvider             — Google Workspace / Gmail OAuth
    MicrosoftGraphProvider       — Microsoft 365 OAuth
    IMAPProvider                 — generic IMAP+SMTP fallback
    TransactionalSendOnlyProvider — wraps existing DeliveryService for
                                     state-changes-generate-communications
                                     (§3.26.15.17) outbound-only flows

Stubs implement the ABC contract but raise ``NotImplementedError`` for
operations that require real provider integration (initial sync, real
outbound, etc). Step 2 wires real OAuth + sync infrastructure on top.

The native-transport implementation alluded to in §3.26.15.1 lands as
a 5th provider (``NativeProvider``) without disturbing this contract,
when SMTP/IMAP/POP3 + DKIM/SPF/DMARC + deliverability infrastructure
matures per the integrate-now-make-native-later framework.
"""

from app.services.email.providers.base import (
    EmailProvider,
    PROVIDER_REGISTRY,
    get_provider_class,
    register_provider,
)
from app.services.email.providers.gmail import GmailAPIProvider
from app.services.email.providers.imap import IMAPProvider
from app.services.email.providers.msgraph import MicrosoftGraphProvider
from app.services.email.providers.transactional import TransactionalSendOnlyProvider

# Side-effect registration: importing this package registers all
# 4 stub providers into PROVIDER_REGISTRY.
register_provider("gmail", GmailAPIProvider)
register_provider("msgraph", MicrosoftGraphProvider)
register_provider("imap", IMAPProvider)
register_provider("transactional", TransactionalSendOnlyProvider)

__all__ = [
    "EmailProvider",
    "PROVIDER_REGISTRY",
    "get_provider_class",
    "register_provider",
    "GmailAPIProvider",
    "MicrosoftGraphProvider",
    "IMAPProvider",
    "TransactionalSendOnlyProvider",
]
