import re
import os
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

# GENE AND RELATED MODELS
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
    """Through model linking File and Gene with expert info"""
    file = models.ForeignKey('File', on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)
    expert = models.CharField(max_length=255)
    start = models.IntegerField(null=True, blank=True)
    stop = models.IntegerField(null=True, blank=True)
    nt = models.TextField(null=True, blank=True)
    aa = models.TextField(null=True, blank=True)

    def clean(self):
        if self.file and self.file.file_type != File.FileType.JSON:
            raise ValidationError({'file': 'Genes can only be linked to JSON files.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.file} - {self.gene} ({self.expert})"
    class Meta:
        db_table = 'model_filegene'


# FILE AND CONVERSION TASK MODELS

def get_file_upload_path(instance, filename):
    user_id = instance.user_id or 'unknown'
    file_type = instance.file_type or 'unknown'
    safe_name = os.path.basename(filename)
    return f"uploads/persistent/user_{user_id}/{file_type}/{safe_name}"

class File(models.Model):
    """File in the system"""
    class FileType(models.TextChoices):
        FASTQ = 'fastq', 'FASTQ'
        FASTA = 'fasta', 'FASTA'
        JSON = 'json', 'JSON'
        CSV = 'csv', 'CSV'

    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to=get_file_upload_path)
    file_type = models.CharField(max_length=50, choices=FileType.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='files')
    genes = models.ManyToManyField('Gene', related_name='files', blank=True, through='FileGene')

    def __str__(self):
        return f"File created at {self.created_at} by {self.user.username} ({self.file.name})"
    class Meta:
        db_table = 'model_file'

class ProcessGroup(models.Model):
    """Grouping of conversion tasks under a name"""
    name = models.CharField(max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='process_groups')

    def __str__(self):
        return self.name

class ConversionTask(models.Model):
    """A conversion task representing a bioinformatics process"""

    class TaskStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    class TaskType(models.TextChoices):
        ANNOTATION = 'annotation', 'Annotation'
        FROM_JSON = 'from_json', 'JSON Processing'
        ASSEMBLY_ONT = 'assembly_ont', 'ONT Assembly'
        ASSEMBLY_ILLUMINA = 'assembly_illumina', 'Illumina Assembly'
        ASSEMBLY_ONT_ANNOTATED = 'assembly_ont_annotated', 'ONT Assembly with Annotation'
        ASSEMBLY_ILLUMINA_ANNOTATED = 'assembly_illumina_annotated', 'Illumina Assembly with Annotation'
        PREDICTION = 'prediction', 'Prediction'
    
    # Allow blank so we can create a pending task before an external job id exists.
    external_job_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=50, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    process = models.ForeignKey(ProcessGroup, on_delete=models.PROTECT, related_name='conversion_tasks')
    input_files = models.ManyToManyField(File, related_name='input_conversion_tasks', blank=True)
    output_files = models.ManyToManyField(File, related_name='output_conversion_tasks', blank=True)
    task_type = models.CharField(max_length=50, choices=TaskType.choices)

    # Model-level validation
    def clean(self):
        # Check that external_job_id is not null when status is not 'pending'
        if not self.external_job_id and self.status != self.TaskStatus.PENDING and self.status != self.TaskStatus.FAILED and self.task_type not in [self.TaskType.FROM_JSON, self.TaskType.PREDICTION]:
            raise ValidationError({'external_job_id': 'external_job_id can be null only when status is "pending" or "failed".'})

    # Ensure model validation runs on save
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ConversionTask(external_job_id={self.external_job_id}, status={self.status}, task_type={self.task_type})"
    class Meta:
        db_table = 'converter_conversiontask'
