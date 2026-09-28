from django.contrib import admin

from .models import PredictionTask

@admin.register(PredictionTask)
class PredictionTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'created_at', 'updated_at', 'selected_models', 'selected_antibiotics', 'data')
    search_fields = ('status',)
