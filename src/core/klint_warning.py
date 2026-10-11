"""The warning klint raises when it carries on after ignoring something."""


class KlintWarning(UserWarning):
    """Something in the rules or settings was ignored; the run continues."""
