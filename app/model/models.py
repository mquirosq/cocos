import re
from django.db import models

class FileUpload(models.Model):
    """File that has been uploaded"""
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='uploads/')
    genes = models.ManyToManyField('Gene', related_name='files', blank=True, through='FileGene')

    def __str__(self):
        return f"File uploaded at {self.uploaded_at}"

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
    
    
class FileGene(models.Model):
    """Through model linking FileUpload and Gene with expert info"""
    file_upload = models.ForeignKey(FileUpload, on_delete=models.CASCADE)
    gene = models.ForeignKey(Gene, on_delete=models.CASCADE)
    expert = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.file_upload} - {self.gene} ({self.expert})"
