"""Which half of the store the current request belongs to.

Two values, "machinery" and "materials", the same pair store-api uses on products,
promotions, hero slides and QR codes. The answer decides the header mark, the nav
links, the footer's brand column, which hero carousel is fetched and which shop's
deals the promo banner advertises - so every part of the shell asks the same question
and has to get the same answer.

Its own module for one reason: app.py works it out from `request.endpoint`, and a
handful of *views* know better than the endpoint does. A promotion page is the case
that forces it - /promotions/12 is one URL that serves a machinery bundle or a
materials one depending on the row behind it, and the routing table cannot see the
row. So a view sets an override and app.py reads it, which app.py cannot offer
directly: it imports the blueprints, so anything they imported back from it would be a
circular import (the same reasoning that put site_cache.py in its own file).

The override lives on `g`, i.e. it is scoped to one request and never leaks into the
next one.
"""
from flask import g, session

# Every value either half of this module may return. Anything else is a bug, not a
# third shop.
SECTIONS = ("machinery", "materials")

DEFAULT_SECTION = "machinery"

# Session key holding the last shop the visitor was actually in. Written by app.py,
# which owns the endpoint map that decides what "in" means; named here so that a view
# wanting the answer doesn't have to reach into app.py for the string (it can't -
# app.py imports the blueprints).
SESSION_KEY = "site_section"

_OVERRIDE_KEY = "_site_section_override"


def override(section):
    """Declare, from inside a view, which shop this request is really in.

    Wins over the endpoint map in app.py for the rest of the request. Ignored when
    handed something that isn't one of SECTIONS, so a value read straight off a
    store-api row can be passed in without the caller checking first.

    Call it BEFORE render_template: the sitewide globals (hero slides, active
    promotions, footer brands) are lazy and resolve during rendering, which is what
    makes a view-level override work at all.
    """
    if section in SECTIONS:
        setattr(g, _OVERRIDE_KEY, section)


def current_override():
    """The override this request set, or None. Read by app.py's _request_section."""
    return getattr(g, _OVERRIDE_KEY, None)


def remembered():
    """The shop the visitor was last in, or None if they haven't picked one yet.

    For pages that belong to BOTH shops - About, Contact, sign-in - this is the only
    thing that says which one the visitor came from, since their endpoint doesn't.
    Views that offer a link into a catalogue read it so the link stays in the shop
    the shopper is standing in.
    """
    return session.get(SESSION_KEY)
