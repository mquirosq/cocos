from django.db import models
from django.core.exceptions import ValidationError

from core.models import File, ProcessGroup, TaskStatus

class PredictionTask(models.Model):
    """A prediction task representing a model prediction process"""

    status = models.CharField(max_length=50, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    process = models.ForeignKey(ProcessGroup, on_delete=models.PROTECT, related_name='prediction_tasks')
    output_csv = models.ForeignKey('core.File', on_delete=models.PROTECT, null=True, blank=True, related_name='prediction_output_csv')

    selected_models = models.JSONField(default=list)
    selected_antibiotics = models.JSONField(default=list)
    data = models.JSONField(default=list, blank=True, null=True)

    # Model-level validation
    def clean(self):
        if self.output_csv and self.output_csv.file_type != File.FileType.CSV:
            raise ValidationError({'output_csv': 'Output CSV must be a CSV file.'})

    # Ensure model validation runs on save
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)