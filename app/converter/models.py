from django.db import models

# Create your models here.

class AnnotationTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Future: add user association
    external_job_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    input_path = models.CharField(max_length=255)
    output_path = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"AnnotationTask(external_job_id={self.external_job_id}, status={self.status})"
