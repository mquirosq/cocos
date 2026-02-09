from django.db import models
from django.core.exceptions import ValidationError

# TODO: Right now pending is useless
class ConversionTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    TYPE_CHOICES = [
        ('annotation', 'Annotation'),
        ('sequencing_ont', 'ONT Sequencing'),
        ('sequencing_illumina', 'Illumina Sequencing'),
    ]
    
    # Future: add user association
    external_job_id = models.CharField(max_length=100, unique=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    input_path = models.CharField(max_length=255)
    task_type = models.CharField(max_length=50, choices=TYPE_CHOICES)

    # Model-level validation
    def clean(self):
        # Check that external_job_id is not null when status is not 'pending'
        if not self.external_job_id and self.status != 'pending':
            raise ValidationError({'external_job_id': 'external_job_id can be null only when status is "pending".'})

    # Ensure model validation runs on save
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ConversionTask(external_job_id={self.external_job_id}, status={self.status}, task_type={self.task_type})"
