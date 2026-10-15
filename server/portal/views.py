from pathlib import Path

from django.http import FileResponse, HttpResponseRedirect

PAGE = Path(__file__).resolve().parent / 'page' / 'index.html'


def portal_page(request):
    # Before the server was shared, noid lived at "/" and its share links
    # were /?scene=<id>&view=true — forward those to noid so they keep working.
    if 'scene' in request.GET:
        return HttpResponseRedirect(f'/noid/?{request.GET.urlencode()}')
    return FileResponse(open(PAGE, 'rb'), content_type='text/html; charset=utf-8')
