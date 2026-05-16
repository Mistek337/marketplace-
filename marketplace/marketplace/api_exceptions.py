from rest_framework.views import exception_handler as drf_exception_handler


def _as_error_message(data) -> str:
    if isinstance(data, dict):
        if "message" in data:
            return str(data["message"])
        detail = data.get("detail")
        if detail is not None:
            return str(detail)
    if isinstance(data, list) and data:
        return str(data[0])
    return "Request failed"


def openapi_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and "code" in data and "message" in data:
        return response

    status_code = response.status_code
    message = _as_error_message(data)
    code_by_status = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
    }
    response.data = {
        "code": code_by_status.get(status_code, "ERROR"),
        "message": message,
    }
    return response
