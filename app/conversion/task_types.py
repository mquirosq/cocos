from .models import ConversionTask


ASSEMBLY_TYPES = {
    ConversionTask.TaskType.ASSEMBLY_ILLUMINA,
    ConversionTask.TaskType.ASSEMBLY_ONT,
    ConversionTask.TaskType.ASSEMBLY_ILLUMINA_ANNOTATED,
    ConversionTask.TaskType.ASSEMBLY_ONT_ANNOTATED,
}

ANNOTATED_TYPES = {
    ConversionTask.TaskType.ASSEMBLY_ILLUMINA_ANNOTATED,
    ConversionTask.TaskType.ASSEMBLY_ONT_ANNOTATED,
    ConversionTask.TaskType.ANNOTATION,
}

ASSEMBLY_AND_ANNOTATION_TYPES = {
    ConversionTask.TaskType.ASSEMBLY_ILLUMINA_ANNOTATED,
    ConversionTask.TaskType.ASSEMBLY_ONT_ANNOTATED,
}