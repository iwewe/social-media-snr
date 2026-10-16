from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Beranda sementara. Wajib login lewat LoginRequiredMiddleware. UI nyata: WP-0.5."""
    return render(request, "investigations/home.html")
