from django.contrib import admin

from conversion.models import File, Gene, FileGene, ConversionTask

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'file', 'file_type', 'user')
    search_fields = ('file',)

@admin.register(Gene)
class GeneAdmin(admin.ModelAdmin):
    list_display = ('id', 'identifiers')
    search_fields = ('identifiers',)

@admin.register(FileGene)
class FileGeneAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'gene', 'expert')
    search_fields = ('expert', 'gene__identifiers', 'file__file')

@admin.register(ConversionTask)
class ConversionTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'external_job_id', 'status', 'created_at', 'updated_at')
    search_fields = ('external_job_id', 'status')
