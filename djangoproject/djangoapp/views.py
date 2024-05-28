from django.http import HttpResponse

def response_200(request):
    return HttpResponse(status=200)

def hello_world(request):
    return HttpResponse("Hello, World!")

def home(request):
    return HttpResponse("Home")