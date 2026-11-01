import pytest

from app.services.ai_analysis_service import _format_user_error


@pytest.mark.parametrize(
    "error_detail",
    [
        "Object not found",
        "StorageApiError: object not found",
        "Failed to download document",
    ],
)
def test_storage_errors_have_a_clear_user_message(error_detail):
    assert _format_user_error(error_detail) == (
        "Unable to retrieve document from cloud storage. Please try again."
    )
