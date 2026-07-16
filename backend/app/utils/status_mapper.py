# backend/app/utils/status_mapper.py

def map_feasibility_status(feasible, shortfall):
    if feasible:
        return "FEASIBLE"

    if shortfall > 0:
        return "SHORTFALL"

    return "UNFULFILLABLE"

def map_time_status(on_time):
    if on_time:
        return "ON_TRACK"

    return "TIME_RISK"

def map_reliability_status(score):
    if score >= 80:
        return "RELIABLE"

    if score >= 60:
        return "MODERATE"

    return "HIGH_RISK"

def map_supplier_risk(score):
    if score >= 80:
        return "LOW"

    if score >= 60:
        return "MODERATE"

    if score >= 40:
        return "HIGH"

    return "CRITICAL"


VERIFIED_DELIVERY_STATUSES = [
    "VERIFIED",
    "PARTIAL"
]

CHAIN_FAILURE_STATUSES = [
    "SHORTFALL",
    "UNFULFILLABLE",
    "TIME_RISK",
    "FAILED"
]