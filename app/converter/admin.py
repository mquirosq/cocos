from django.contrib import admin

# Register your models here.

from .models import AnnotationTask
@admin.register(AnnotationTask)
class AnnotationTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'external_job_id', 'status', 'created_at', 'updated_at')
    search_fields = ('external_job_id', 'status')
