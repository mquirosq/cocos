import time
from app.converter import services
from pathlib import Path

# 1) Health quick check
print("Health:", __import__("requests").get("http://127.0.0.1:8000/health").json())

# 2) Upload FASTA to start annotation (reads file and posts)
fasta_path = Path(__file__).resolve().parents[2] / "example_files" / "ATCC25922.fasta"
if not fasta_path.exists():
    raise SystemExit(f"FASTA not found: {fasta_path}")
with open(fasta_path, "rb") as f:
    fasta = f.read()

resp = services.annotate_from_fasta(fasta)
print("Annotate response:", resp)

# If response contains job_id, poll status until annotated or failed
job_id = resp.get("job_id")
if job_id:
    for _ in range(10000): # max ~5 hours
        st, msg = services.get_job_status(job_id)
        print("Status:", st)
        if st == "annotated" or (isinstance(st, dict) and st.get("status") == "annotated"):
            break
        if st == "failed":
            print("Reason for failure:", msg if msg else "Unknown")
            raise SystemExit("Annotation failed")
        time.sleep(2)
    # Try download JSON
    try:
        j = services.download_bakta_json_result(job_id)
        print("Downloaded JSON keys:", list(j.keys()) if isinstance(j, dict) else type(j))
    except Exception as e:
        print("Download failed:", e)
else:
    print("No job_id returned; response:", resp)