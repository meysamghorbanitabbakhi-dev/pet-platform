from app.main import create_app


def test_k9_1_customer_routes_are_in_checked_application_contract() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/v1/me/context" in paths
    assert "/api/v1/pet-life/households/{household_id}/pets" in paths
    assert "/api/v1/catalog/offers/{offer_id}" in paths
    assert "/api/v1/orders/{order_id}" in paths
    assert "/api/v1/orders/{order_id}/pet-plan" in paths


def test_k9_1_public_offer_contract_hides_supplier_identity_and_storage_paths() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    properties = schemas["OfferDetailResponse"]["properties"]
    assert "supplier_country_code" in properties
    assert "supplier_id" not in properties
    assert "supplier_name" not in properties
    media_properties = schemas["ProductMediaResponse"]["properties"]
    assert "public_reference" in media_properties
    assert "filesystem_path" not in media_properties
