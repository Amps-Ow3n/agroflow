# backend/app/utils/normalizers.py

def normalize_actor_type(actor_type: str):
    return actor_type.strip().lower()


def normalize_product(product: str):
    return product.strip().lower()


def normalize_location(location: str):
    return location.strip().lower()