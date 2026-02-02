from django.shortcuts import render
from converter.models import AnnotationTask

def home(request):
    return render(request, 'home/home.html')

# TODO: Remove, only for testing purposes
def delete_all_tasks(request):
    AnnotationTask.objects.all().delete()
    return render(request, 'home/home.html', {'message': 'All tasks deleted.'})
