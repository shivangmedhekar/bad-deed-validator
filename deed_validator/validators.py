"""Validation logic for deed data."""

from __future__ import annotations

import logging

from .exceptions import AmountMismatchError, DateOrderError, DeedValidationError
from .models import DeedData
from .utils import words_to_int

logger = logging.getLogger(__name__)


class DeedValidator:
    """Runs sanity-check rules against a :class:`DeedData` instance."""

    def validate(self, deed: DeedData) -> None:
        """Raise :class:`DeedValidationError` if any rule fails.

        All rules are evaluated so that **every** problem is reported in a
        single error message.
        """
        errors: list[DeedValidationError] = []
        logger.info("Running sanity checks")

        self._check_date_order(deed, errors)
        self._check_amount_match(deed, errors)

        if errors:
            msgs = "\n - " + "\n - ".join(str(e) for e in errors)
            raise DeedValidationError(f"Sanity checks failed:{msgs}")

        logger.info("All sanity checks passed")

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    @staticmethod
    def _check_date_order(
        deed: DeedData,
        errors: list[DeedValidationError],
    ) -> None:
        if deed.date_recorded < deed.date_signed:
            errors.append(
                DateOrderError(
                    f"Invalid dates: recorded {deed.date_recorded.isoformat()} "
                    f"is before signed {deed.date_signed.isoformat()}."
                )
            )

    @staticmethod
    def _check_amount_match(
        deed: DeedData,
        errors: list[DeedValidationError],
    ) -> None:
        try:
            words_value = words_to_int(deed.amount_words)
        except ValueError as e:
            errors.append(AmountMismatchError(f"Could not parse amount words: {e}"))
            return

        if words_value != deed.amount_numeric:
            errors.append(
                AmountMismatchError(
                    f"Amount mismatch: numeric={deed.amount_numeric:,} "
                    f"vs words={words_value:,} (from '{deed.amount_words}')."
                )
            )

