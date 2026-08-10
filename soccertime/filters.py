from django.contrib import admin
from django.db.models import Value
from django.db.models.functions import StrIndex, Substr


class LinkSchemeFilter(admin.SimpleListFilter):
    title = "Scheme"
    parameter_name = "link_scheme"

    def lookups(self, request, model_admin):
        """The distinct schemes in use, resolved by the database.

        This used to read every link into Python to parse it, and returned the results
        from a set, which left the dropdown in an order that changed between processes.
        Rows whose link carries no scheme yield an empty string here — `StrIndex` returns
        0 when the separator is absent — and are dropped.
        """
        schemes = (
            model_admin.model.objects.exclude(link__isnull=True)
            .exclude(link="")
            .annotate(scheme=Substr("link", 1, StrIndex("link", Value("://")) - 1))
            .exclude(scheme="")
            .values_list("scheme", flat=True)
            .distinct()
            .order_by("scheme")
        )
        return [(scheme, scheme) for scheme in schemes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(link__startswith=f"{self.value()}://")
        return queryset
