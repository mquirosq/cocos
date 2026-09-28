from .models import ConversionTask


ASSEMBLY_TYPES = {
    ConversionTask.ConversionTaskType.ASSEMBLY_ILLUMINA,
    ConversionTask.ConversionTaskType.ASSEMBLY_ONT,
    ConversionTask.ConversionTaskType.ASSEMBLY_ILLUMINA_ANNOTATED,
    ConversionTask.ConversionTaskType.ASSEMBLY_ONT_ANNOTATED,
}

ANNOTATED_TYPES = {
    ConversionTask.ConversionTaskType.ASSEMBLY_ILLUMINA_ANNOTATED,
    ConversionTask.ConversionTaskType.ASSEMBLY_ONT_ANNOTATED,
    ConversionTask.ConversionTaskType.ANNOTATION,
}

ASSEMBLY_AND_ANNOTATION_TYPES = {
    ConversionTask.ConversionTaskType.ASSEMBLY_ILLUMINA_ANNOTATED,
    ConversionTask.ConversionTaskType.ASSEMBLY_ONT_ANNOTATED,
}