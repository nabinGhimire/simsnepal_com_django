from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def calendar(request):
    """Nepali Academic Patro — placeholder until the full calendar is built."""
    return render(request, "panel/coming_soon.html")
