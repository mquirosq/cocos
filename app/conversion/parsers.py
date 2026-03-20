from conversion.models import FileGene, Gene, FileUpload
from django.db import transaction
from django.shortcuts import render
import os

# --- Registry for parsers ---
PARSERS = {}

def register_parser(name, extensions=None):
    """
    Decorator to register a parser instance under `name`.
    """
    def decorator(cls):
        PARSERS[name] = cls()
        return cls
    return decorator

def get_parser(name):
    return PARSERS.get(name)

# --- Main parsing function ---
def parse_file(parser, data, file, user=None, options=None):
    """
    Detect parser from `filename` extension and parse.
    Raises `RuntimeError` if no parser matches the extension.
    """
    parser = get_parser(parser)
    if not parser:
        raise RuntimeError(f'No parser registered for parser: {parser}')
    return parser.parse(data, file, user=user, options=options)

# --- Base Parser, extend this for specific file types or parsing ---
class BaseParser():
    def parse(self, data, file, user=None, options=None):
        """Parse data and persist results.

        `options` is a dict for parser-specific flags (e.g. {'complete_version': True}).
        Must return `FileUpload` or a Django response on error.
        """
        raise NotImplementedError


# --- Example parser for Bakta JSON feature files ---
@register_parser('bakta_json')
class BaktaJsonParser(BaseParser):
    
    def parse(self, data, file, user=None, options=None):
        """Parse a Bakta JSON feature file and create FileUpload, Gene, and FileGene entries.

        Reads `complete_version` from `options` (defaults to False).
        """
        complete_version = False if options is None else bool(options.get('complete_version', False))
        
        with transaction.atomic():
            file_upload = FileUpload.objects.create(file=file, user=user)
            features = data.get('features', [])
            try:
                for gene in features:
                    gene_name = gene.get('gene')
                    gene_db_xrefs = gene.get('db_xrefs')
                    gene_product = gene.get('product')
                    identifiers = []
                    if gene_db_xrefs:
                        for xref in gene_db_xrefs:
                            identifiers.append(xref)
                    if gene_product:
                        identifiers.append(gene_product)
                    if gene_name:
                        identifiers.append(gene_name)

                    identifiers = {ident.strip() for ident in identifiers if ident.strip()}
                    gene_obj = None
                    if identifiers:
                        # Get a gene with any of the identifiers, or create a new one
                        gene_obj = Gene.objects.search_identifiers(identifiers).first()
                        if not gene_obj:
                            gene_obj = Gene.objects.create()

                        gene_obj.add_identifiers(identifiers)

                    # Get expert type
                    expert_field = gene.get('expert')[0] if gene.get('expert') else None
                    expert_type = expert_field.get('type') if expert_field else 'unknown'

                    if gene_obj:
                        file_gene = FileGene.objects.create(
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
                try:
                    file_upload.file.delete()
                except Exception:
                    pass
                file_upload.delete()
                transaction.set_rollback(True)
                return render(None, 'featureParser/parse_feature_file.html', {'messages': [f'Error parsing features: {str(e)}']})

            return file_upload
