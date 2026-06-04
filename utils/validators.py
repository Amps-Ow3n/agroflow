def normalize(text: str) -> str:
    return text.strip().lower()

VALID_CROPS = {"maize", "beans", "rice", "cassava", "sorghum"}

def validate_crop(crop):
    crop = crop.lower().strip()
    if crop not in VALID_CROPS:
        raise HTTPException(status_code=400, detail="Unsupported crop")
    return crop

def validate_quantity(qty):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

def validate_date_range(start, end):
    if start > end:
        raise HTTPException(status_code=400, detail="Invalid date range")

def validate_zone(zone):
    if not zone or len(zone) < 2:
        raise HTTPException(status_code=400, detail="Invalid zone")
    