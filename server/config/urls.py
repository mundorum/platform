from django.contrib import admin
from django.urls import include, path

import noid_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('accounts.urls')),
    path('noid/', include(noid_urls)),
    path('vp/', include('vp_studio.urls')),
    # Legacy: noid's API lived at /api/ before the server was shared. Kept
    # for one release so an editor tab opened before the deploy keeps
    # working; remove once nothing calls /api/ any more.
    path('api/', include(noid_urls.api_patterns)),
    path('', include('portal.urls')),
]
