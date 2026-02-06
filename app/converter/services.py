import requests
import os
from .models import AnnotationTask

BASE = os.getenv("ANNOTATION_BASE", "http://localhost:8000")

def get_job_status(job_id):
    response = requests.get(f"{BASE}/jobs/{job_id}")
    response.raise_for_status()
    status = response.json()["status"]
    return status, response.status_code

def perform_bakta_annotation_from_job(job_id):
    response = requests.post(f"{BASE}/annotation/bakta/existing/{job_id}?threads=4")
    response.raise_for_status()
    return response.json()

def download_bakta_json_result(job_id):
    response = requests.get(f"{BASE}/annotation/{job_id}/download?format=json")
    response.raise_for_status()
    return response.json()

# TODO: Check commented code
def annotate_from_fasta(fasta_content):
    resp = requests.post(
        f"{BASE}/annotation/bakta/upload?threads=4",
        files={"assembly": ("sequences.fasta", fasta_content, "application/octet-stream")},
        timeout=30,
    )
    
    if resp.status_code == 503:
        print("Received 503 Server Busy response")
        return resp.json()
    
    # resp.raise_for_status()
    return resp.json()