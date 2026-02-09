from django.contrib import admin

# Register your models here.

from .models import ConversionTask
@admin.register(ConversionTask)
class ConversionTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'external_job_id', 'status', 'created_at', 'updated_at')
    search_fields = ('external_job_id', 'status')
