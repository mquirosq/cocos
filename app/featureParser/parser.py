
from model.models import FileGene, Gene, FileUpload
from django.db import transaction
from django.shortcuts import render

# TODO: Aplicar patrón de diseño para tener múltiples parsers según el tipo de archivo
def parse_bakta_json(data, file, complete_version=False):
    """Parse a Bakta JSON feature file and create FileUpload, Gene, and FileGene entries"""

    with transaction.atomic():
        file_upload = FileUpload.objects.create(file=file)
        features = data.get('features', [])
        try:
            for gene in features:
                gene_name = gene.get('gene', [])
                gene_db_xrefs = gene.get('db_xref', [])
                gene_product = gene.get('product', [])
                identifiers = []
                if gene_db_xrefs:
                    identifiers.extend(gene_db_xrefs.split(','))
                if gene_product:
                    identifiers.append(gene_product)
                if gene_name:
                    identifiers.append(gene_name)

                identifiers = {ident.strip() for ident in identifiers if ident.strip()}
                if identifiers:
                    # Get a gene with any of the identifiers, or create a new one
                    gene_obj = Gene.objects.search_identifiers(identifiers).first()
                    if not gene_obj:
                        gene_obj = Gene.objects.create()
                    
                    gene_obj.add_identifiers(identifiers)

                # Get expert type
                expert_field = gene.get('expert')[0] if gene.get('expert') else None
                expert_type = expert_field.get('type') if expert_field else 'unknown'

                file_gene =FileGene.objects.create(
                    file_upload=file_upload,
                    gene=gene_obj,
                    expert=expert_type
                )
                
                if complete_version:
                    file_gene.start = gene.get('start')
                    file_gene.stop = gene.get('stop')
                    file_gene.nt = gene.get('nt')
                    file_gene.aa = gene.get('aa')
                    file_gene.save(update_fields=['start', 'stop', 'nt', 'aa'])

                file_upload.genes.add(gene_obj)

        except Exception as e:
            file_upload.file.delete()
            file_upload.delete()
            transaction.set_rollback(True)
            return render(None, 'featureParser/parse_feature_file.html', {'messages': [f'Error parsing features: {str(e)}']})

        return file_upload