from rest_framework.response import Response


def error_response(detail, status_code):
    return Response({"detail": detail}, status=status_code)


def field_error_response(field, message, status_code=400):
    return Response({field: [message]}, status=status_code)
