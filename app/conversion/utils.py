
import os
from django.utils.text import get_valid_filename
import uuid

def upload_file(file, upload_dir='uploads/fasta'):
    if not file:
        raise ValueError("No file provided for upload.")
    
    # Read the file content
    file_bytes = file.read()
    
    # Uploads file, creating dir and avoiding collisions
    upload_dir = os.path.join(upload_dir)
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = get_valid_filename(file.name) # Makes filename safe
    dest_path = os.path.join(upload_dir, safe_name)
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(safe_name)
        dest_path = os.path.join(upload_dir, f"{base}_{uuid.uuid4().hex}{ext}")

    # Upload the file
    with open(dest_path, 'wb') as f:
        f.write(file_bytes)

    return dest_path
