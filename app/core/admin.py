from django.contrib import admin

from core.models import Gene, FileGene, File, ProcessGroup


@admin.register(Gene)
class GeneAdmin(admin.ModelAdmin):
    list_display = ('id', 'identifiers')
    search_fields = ('identifiers',)

@admin.register(FileGene)
class FileGeneAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'gene', 'expert')
    search_fields = ('expert', 'gene__identifiers', 'file__file')

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'file', 'file_type', 'user')
    search_fields = ('file',)

@admin.register(ProcessGroup)
class ProcessGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
