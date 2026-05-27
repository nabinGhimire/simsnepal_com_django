from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class FrontendSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['home', 'features', 'pricing', 'faq', 'about', 'contact']

    def location(self, item):
        return reverse(item)
