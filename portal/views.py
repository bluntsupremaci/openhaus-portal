from django.shortcuts import render, HttpResponse

def index(request):
    # TODO: Replace with real dashboard logic later
    return HttpResponse("<h1>Welcome to OpenHaus Portal</h1>")
    # or better:
    # return render(request, 'portal/index.html', {})