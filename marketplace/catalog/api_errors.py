from rest_framework import status
from rest_framework.response import Response


def catalog_not_found(message: str = "Product not found"):
    return Response({"code": "NOT_FOUND", "message": message}, status=status.HTTP_404_NOT_FOUND)


def map_b2b_error(exc):
    if exc.status_code == 404:
        return catalog_not_found()
    if exc.status_code == 400:
        return Response(
            {"code": "VALIDATION_ERROR", "message": "Bad request"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if exc.status_code in (401, 403):
        return Response(
            {"code": "FORBIDDEN", "message": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if exc.status_code == 503:
        return Response(
            {"code": "ERROR", "message": "Catalog service unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(
        {"code": "ERROR", "message": "Catalog service error"},
        status=status.HTTP_502_BAD_GATEWAY,
    )
