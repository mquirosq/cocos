from django.shortcuts import render
import json
from model.models import FileGene, Gene, FileUpload
from django.db import transaction

def parse_feature_file(request):
    if request.method == 'POST':
        file_upload = parse_bakta_json(request.FILES.get('feature_file'))
        return render(request, 'featureParser/parse_feature_file.html', {'messages': ['File parsed successfully!'], 'file_upload': file_upload})
    return render(request, 'featureParser/parse_feature_file.html')


def parse_bakta_json(file):
    try:
        data = json.load(file)
    except json.JSONDecodeError:
        return render('featureParser/parse_feature_file.html', {'messages': ['Error decoding JSON file!']})
    
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

                identifiers = [ident.strip() for ident in identifiers if ident.strip()]
                if identifiers:
                    # Get a gene with any of the identifiers, or create a new one
                    gene_obj = Gene.objects.search_identifiers(identifiers).first()
                    if not gene_obj:
                        gene_obj = Gene.objects.create()
                    
                    gene_obj.add_identifiers(identifiers)

                # Get expert type
                expert_field = gene.get('expert')[0] if gene.get('expert') else None
                expert_type = expert_field.get('type') if expert_field else 'unknown'


                FileGene.objects.create(
                    file_upload=file_upload,
                    gene=gene_obj,
                    expert=expert_type
                )

                file_upload.genes.add(gene_obj)

        except Exception as e:
            file_upload.file.delete()
            file_upload.delete()
            transaction.set_rollback(True)
            return render(None, 'featureParser/parse_feature_file.html', {'messages': [f'Error parsing features: {str(e)}']})

        return file_upload