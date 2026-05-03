import re
import os
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


def _infer_file_type(filename):
    ext = os.path.splitext((filename or '').lower())[1]
    if ext in {'.fa', '.fasta', '.fna', '.ffn', '.faa', '.frn'}:
        return 'fasta'
    if ext in {'.json'}:
        return 'json'
    return 'other'


def file_upload_path(instance, filename):
    user_id = instance.user_id or 'unknown'
    file_type = _infer_file_type(filename)
    safe_name = os.path.basename(filename)
    return f"uploads/persistent/user_{user_id}/{file_type}/{safe_name}"

class FileUpload(models.Model):
    """File that has been uploaded"""
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to=file_upload_path)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='uploaded_files')
    genes = models.ManyToManyField('Gene', related_name='files', blank=True, through='FileGene')

    def __str__(self):
        return f"File uploaded at {self.uploaded_at}"
    class Meta:
        db_table = 'model_fileupload'

class GeneQuerySet(models.QuerySet):
    """Custom QuerySet for Gene model"""
    def search_identifiers(self, identifiers):
        """Search for genes containing any of the identifiers (case insensitive)"""
        queries = models.Q()
        for identifier in identifiers:
            esc = re.escape(identifier.strip())
            pattern = rf'(^|,\s*){esc}($|,)'
            queries |= models.Q(identifiers__iregex=pattern)
        return self.filter(queries)
    
class Gene(models.Model):
    """Gene with multiple identifiers"""
    identifiers = models.TextField()

    objects = GeneQuerySet.as_manager()

    def identifiers_list(self):
        """Return list of identifiers"""
        return [s.strip() for s in (self.identifiers or '').split(',') if s.strip()]

    def add_identifier(self, identifier):
        """Add an identifier if not already present"""
        identifier = identifier.strip()
        identifier_list = self.identifiers_list()
       
        if identifier not in identifier_list:
            identifier_list.append(identifier)
            self.identifiers = ', '.join(identifier_list)
            self.save(update_fields=['identifiers'])

    def add_identifiers(self, identifiers):
        """Add multiple identifiers if not already present"""
        for identifier in identifiers:
            self.add_identifier(identifier)

    def __str__(self):
        return self.identifiers
    class Meta:
        db_table = 'model_gene'
    
    
class FileGene(models.Model):
    """Through model linking FileUpload and Gene with expert info"""
    file_upload = models.ForeignKey(FileUpload, on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)
    expert = models.CharField(max_length=255)
    start = models.IntegerField(null=True, blank=True)
    stop = models.IntegerField(null=True, blank=True)
    nt = models.TextField(null=True, blank=True)
    aa = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.file_upload} - {self.gene} ({self.expert})"
    class Meta:
        db_table = 'model_filegene'

class ConversionTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    TYPE_CHOICES = [
        ('annotation', 'Annotation'),
        ('from_json', 'From JSON'),
        ('assembly_ont', 'ONT Assembly'),
        ('assembly_illumina', 'Illumina Assembly'),
        ('assembly_ont_annotated', 'ONT Assembly with Annotation'),
        ('assembly_illumina_annotated', 'Illumina Assembly with Annotation'),
    ]
    
    # Allow blank so we can create a pending task before an external job id exists.
    external_job_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    process_name = models.CharField(max_length=255, blank=True, default='')
    input_path = models.CharField(max_length=255)
    task_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='conversion_tasks')
    previous_task = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_tasks',
    )

    # Model-level validation
    def clean(self):
        # Check that external_job_id is not null when status is not 'pending'
        if not self.external_job_id and self.status != 'pending' and self.task_type != 'from_json':
            raise ValidationError({'external_job_id': 'external_job_id can be null only when status is "pending".'})

        if self.previous_task and self.task_type != 'annotation':
            raise ValidationError({'previous_task': 'Only annotation tasks can have a previous_task.'})

        if self.previous_task and self.previous_task.task_type not in {'assembly_illumina', 'assembly_ont'}:
            raise ValidationError({'previous_task': 'previous_task must be assembly_illumina or assembly_ont.'})

        if self.previous_task and self.user_id and self.previous_task.user_id != self.user_id:
            raise ValidationError({'previous_task': 'previous_task must belong to the same user.'})

    # Ensure model validation runs on save
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ConversionTask(external_job_id={self.external_job_id}, status={self.status}, task_type={self.task_type})"
    class Meta:
        db_table = 'converter_conversiontask'
