from types import SimpleNamespace

from app.core.db_errors import (
    translate_database_error,
)


class FakeDatabaseError(Exception):
    def __init__(
        self,
        pgcode,
        constraint_name=None,
    ):
        super().__init__()

        self.pgcode = pgcode

        self.diag = SimpleNamespace(
            constraint_name=constraint_name
        )


def make_error(
    pgcode,
    constraint=None,
):

    return FakeDatabaseError(
        pgcode=pgcode,
        constraint_name=constraint,
    )


def test_unique_violation_translation():

    exc = make_error(
        "23505",
        "uq_active_commitment_per_po_line_supplier",
    )

    translated = translate_database_error(exc)

    assert translated is not None
    assert translated.status_code == 409
    assert translated.error_code == "RESOURCE_CONFLICT"
    assert "active commitment" in translated.message


def test_foreign_key_violation_translation():

    exc = make_error(
        "23503"
    )

    translated = translate_database_error(exc)

    assert translated is not None
    assert translated.status_code == 409
    assert translated.error_code == "INVALID_RELATIONSHIP"


def test_check_violation_translation():

    exc = make_error(
        "23514"
    )

    translated = translate_database_error(exc)

    assert translated is not None
    assert translated.status_code == 409
    assert translated.error_code == "BUSINESS_RULE_VIOLATION"


def test_not_null_violation_translation():

    exc = make_error(
        "23502"
    )

    translated = translate_database_error(exc)

    assert translated is not None
    assert translated.status_code == 400
    assert translated.error_code == "REQUIRED_FIELD_MISSING"


def test_serialization_failure_translation():

    exc = make_error(
        "40001"
    )

    translated = translate_database_error(exc)

    assert translated is not None
    assert translated.status_code == 409
    assert translated.error_code == "CONCURRENT_OPERATION"


def test_deadlock_translation():

    exc = make_error(
        "40P01"
    )

    translated = translate_database_error(exc)

    assert translated is not None
    assert translated.status_code == 409
    assert translated.error_code == "CONCURRENT_OPERATION"


def test_unknown_database_error_returns_none():

    exc = make_error(
        "99999"
    )

    translated = translate_database_error(exc)

    assert translated is None