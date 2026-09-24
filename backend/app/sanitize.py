"""
Email content is untrusted input (anyone who can email the watched label
can inject content), so it's worth normalizing before it enters the
system. But it's important to sanitize for the actual context this data
is used in:

- The backend never renders email content into a server-side HTML
  template, and the JSON API is not an HTML-rendering context, so there
  is no stored-XSS vector on the backend side.
- The React frontend renders all email content as plain text nodes
  (JSX auto-escapes), and no component uses dangerouslySetInnerHTML, so
  there's no XSS vector there either.

Given that, HTML-escaping (turning `<` into `&lt;`) on the backend would
be pure downside: it doesn't stop anything React wasn't already stopping,
and it corrupts legitimate content containing `<`/`>` — most obviously a
"From" header like `Jane Doe <jane@example.com>`, which would otherwise
literally display the escaped entities to the user. So instead this
module does what's actually useful for untrusted external text: strip
control/non-printable characters (defends against terminal/log injection
and rendering glitches) and cap length (defends against a hostile sender
blowing up storage or LLM prompt size).

If this codebase ever grows a path that renders email content into raw
HTML (a server-side template, an email digest, etc.), escape at THAT
render boundary, not here.
"""
import unicodedata


def sanitize_text(value: str, max_len: int = 20000) -> str:
    if not value:
        return ""
    truncated = value[:max_len]
    # Keep normal whitespace (space, tab, newline); drop other control chars.
    cleaned = "".join(
        ch for ch in truncated if ch in ("\n", "\t") or unicodedata.category(ch) != "Cc"
    )
    return cleaned.strip()


def extract_email_address(raw_sender: str) -> str:
    """Pull the bare address out of a raw 'Name <addr@example.com>' header."""
    if not raw_sender:
        return ""
    if "<" in raw_sender and ">" in raw_sender:
        return raw_sender.split("<", 1)[1].split(">", 1)[0].strip()
    return raw_sender.strip()
