from urllib.parse import urlparse

from django.contrib import admin


class LinkSchemeFilter(admin.SimpleListFilter):
    title = "Scheme"
    parameter_name = "link_scheme"

    def lookups(self, request, model_admin):
        schemes = set()
        for url in model_admin.model.objects.values_list("link", flat=True):
            if url:
                scheme = urlparse(url).scheme
                if scheme:
                    schemes.add(scheme)

        return [(scheme, scheme.lower()) for scheme in schemes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(link__startswith=f"{self.value()}://")
        return queryset
