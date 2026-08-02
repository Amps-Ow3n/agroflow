def calculate_remaining_capacity(
    available,
    committed
):

    remaining = max(
        available - committed,
        0
    )

    shortfall = max(
        committed - available,
        0
    )


    utilization = (
        round(
            (committed / available) * 100,
            2
        )
        if available > 0
        else 0
    )


    return {

        "available": available,

        "committed": committed,

        "remaining": remaining,

        "shortfall": shortfall,

        "utilization": utilization
    }