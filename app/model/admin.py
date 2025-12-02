from django.contrib import admin

from model.models import FileUpload, Gene, FileGene
@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'uploaded_at', 'file')
    search_fields = ('file',)
@admin.register(Gene)
class GeneAdmin(admin.ModelAdmin):
    list_display = ('id', 'identifiers')
    search_fields = ('identifiers',)
@admin.register(FileGene)
class FileGeneAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_upload', 'gene', 'expert')
    search_fields = ('expert', 'gene__identifiers', 'file_upload__file')
    
