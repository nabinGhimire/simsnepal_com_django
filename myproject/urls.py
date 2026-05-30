from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from frontend.sitemaps import FrontendSitemap

sitemaps = {
    'frontend': FrontendSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('panel/', include('panel.urls')),
    path('', include('frontend.urls')),
    path('', include('sso.urls')),
    path('webview/', include('webview.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('llms.txt', TemplateView.as_view(template_name="frontend/llms.txt", content_type="text/plain")),
    path('robots.txt', TemplateView.as_view(template_name="frontend/llms.txt", content_type="text/plain")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
