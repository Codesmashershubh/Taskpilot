from abc import ABC, abstractmethod

from app.models import EmailMessage


class EmailSource(ABC):
    """
    Contract every email backend must satisfy. Note there is deliberately
    no `send()` method anywhere in this interface — creating a draft is the
    only write action available, so the agent is structurally incapable of
    sending mail on the user's behalf no matter what an LLM plans to do.
    """

    name: str = "base"

    @abstractmethod
    async def list_new_emails(self, label: str) -> list[EmailMessage]:
        """Return emails under `label` that haven't been processed yet."""
        raise NotImplementedError

    @abstractmethod
    async def create_draft(self, thread_id: str, to: str, subject: str, body: str) -> str:
        """Create a Gmail DRAFT (never sends). Returns a draft id."""
        raise NotImplementedError
