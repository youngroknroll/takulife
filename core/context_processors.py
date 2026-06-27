def project_name(request):
    """Inject the product name into every template context.

    Keeps views from each hardcoding ``"project_name"`` in their render context.
    """
    return {"project_name": "takulife"}
