from rest_framework.pagination import PageNumberPagination


class FlexiblePagination(PageNumberPagination):
    """
    Default page_size=20, but clients can override with ?page_size=N.
    Max allowed: 2000 (to support full admin lists).
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 2000