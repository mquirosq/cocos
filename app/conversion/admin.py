from django.contrib import admin

from conversion.models import FileUpload, Gene, FileGene, ConversionTask

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

@admin.register(ConversionTask)
class ConversionTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'external_job_id', 'status', 'created_at', 'updated_at')
    search_fields = ('external_job_id', 'status')
