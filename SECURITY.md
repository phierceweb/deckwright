# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately through GitHub's [private vulnerability reporting][gh-pvr]:
the repository's **Security** tab → **Report a vulnerability**. If that tab is
not available to you, email <oss@phierceweb.com> instead.

Include the affected version, a description of the issue, and steps to
reproduce. You can expect an initial acknowledgement within a few days.

[gh-pvr]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability

## Supported versions

deckwright is pre-1.0 and under active development. Security fixes land in the
latest tagged release; there is no long-term-support branch yet. Pin to a
tagged release and upgrade promptly when a fix ships.

## Scope

deckwright is a CLI/library, not a deployed service. What follows is what a deck spec,
a theme, and a `.pptx` you were sent can each actually do.

### A deck spec carries the authority of a script

A `.deck.yaml` is data, but building one is not a read-only act:

- **It reads local files you name.** `image:` and `document:` take paths, and the
  build opens them.
- **It executes Python you name.** `extends:` points at a module that is imported and
  run before any placement is validated — building someone else's `.deck.yaml` runs
  their code on your machine.
- **It writes wherever `out:` points**, including outside the working directory —
  `out: ../../out/review/Review v1.pptx` is the documented idiom, so the path is
  deliberately unconstrained.
- **A `document:` slide runs its markdown in a real browser.** The markdown is
  rendered to HTML with raw HTML passed through unfiltered, and that HTML is
  screenshotted in local headless Chrome. Any remote `<img>`, stylesheet or font it
  names **is fetched** — so building a deck can produce outbound network requests, to
  any host, from your machine. What that HTML may *not* do is bounded by a content
  policy, below.

Treat a spec you did not write exactly as you would treat a script from the same
source. There is no sandboxed or offline build mode.

### What card HTML may do

The markdown behind a `document:` card is usually not yours — a vendored README, a
file from a colleague, a doc in a repo you cloned — and its raw HTML reaches the
browser unfiltered. The card is a `file://` document, so a `file://` URL inside it
would otherwise resolve: an `<iframe src="file:///…">` renders that file into the PNG
that gets embedded in the deck, at any opacity, and looking at the slide need not show
it. Every rendered card therefore carries a content policy that denies everything not
named:

- **No frames, objects or embeds at all** — this is what closes local-file reads.
- **No script**, except the height probe deckwright itself appends, allowed by hash.
- **Images and fonts** may load from `data:`, `https:` and `http:` — not from `file:`.
- **Inline CSS only.**

The policy is applied where HTML meets the browser (`services/htmlshot.py`), so it
covers every card, not just markdown ones. It bounds the *content* of a card; it does
not make an untrusted spec safe — `extends:` still executes Python, and that is what
the section above means.

### The browser sandbox

Chrome runs **sandboxed by default**. `DECKWRIGHT_CHROME_NO_SANDBOX=1` passes
`--no-sandbox`, which is implied when running as root because the sandbox cannot
work there. Switch it off only where the HTML being rendered is as trusted as a
script you would run — in a container that denies unprivileged user namespaces,
for example. A build that fails for want of a sandbox names the variable.

### Templates and decks from other people

`conform`, `qa`, `inspect` and `diff` all read a `.pptx` that came from somewhere
else — the documented `conform` workflow is someone handing you a brand template.
Those packages are zipped XML, and deckwright parses every part with entity expansion
and network access refused (`deckwright.utils.xml`, gated by
`tests/test_xml_safety.py`); python-pptx does the same for the parts it owns. A
malformed or hostile package is reported as a finding rather than trusted.

What is **not** bounded: a package whose parts decompress to far more than they
weigh will use memory in proportion. Treat an untrusted `.pptx` as untrusted input
of unknown size.

### External tools

Rendering shells out to local LibreOffice and Poppler; HTML cards go through local
Chrome/Chromium. Every binary is resolved from a `DECKWRIGHT_*` setting or a well-known
install path, invoked as an argument list — never through a shell, and never
downloaded.

### Network

`deckwright glyphs sync` is the only command that itself opens a socket: it re-vendors
the icon set by `git clone`-ing google/material-design-icons over HTTPS into a
temporary directory. It is a release-time command, never run by building, rendering or
QA, and `bin/setup` only falls back to it when the committed bundle fails its hash
check.

That is separate from the browser, which will fetch whatever the HTML you asked it
to render refers to — see the deck-spec section above. No credentials or secrets are
involved in either path.
