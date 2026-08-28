"""How a listing is cut into pages.

Twenty-five to a page, which is what every listing on the site paginates by, so a client
walking the API sees the same slices a visitor does. The ceiling is what stops one request
from rendering the whole table: the events listing joins six tables per row, and the
production database holds tens of thousands of them.
"""

from rest_framework.pagination import PageNumberPagination


class Pages(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
