from django.shortcuts import render
import json
from .parser import parse_bakta_json

def parse_feature_file(request):
    """View to handle feature file parsing"""
    if request.method == 'POST':
        complete_version = request.POST.get('complete') == 'on'
        try:
            data = json.load(request.FILES.get('feature_file'))
        except json.JSONDecodeError:
            return render(None, 'featureParser/parse_feature_file.html', {'messages': ['Error decoding JSON file!']})
            
        file_upload = parse_bakta_json(data, request.FILES.get('feature_file'), complete_version)
        return render(request, 'featureParser/parse_feature_file.html', {'messages': ['File parsed successfully!'], 'file_upload': file_upload})
    return render(request, 'featureParser/parse_feature_file.html')