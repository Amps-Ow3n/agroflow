from app.engines.support.multi_source_match_engine import (
    build_fulfillment_plan as build_plan
)


def build_fulfillment_plan(cursor, commitment):
    """
    Core matching contract.

    Takes a commitment and returns
    allocation plan across sources.
    """

    return build_plan(cursor, commitment)