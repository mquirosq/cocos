from django.apps import AppConfig
import importlib
from pathlib import Path

class InputparserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inputParser'
    
    def ready(self):
        """Import model implementation modules so `@register_model` decorators run.

        Strategy:
        - Walk `ai_models/` under the app directory and find all `.py` files.
        - For each file, construct the dotted module name relative to the project package.
        - Attempt a normal import. If it fails, skip that module.
        """

        base = Path(__file__).resolve().parents[1] / 'ai_models'
        if not base.exists():
            return

        for py in base.rglob('*.py'):
            if py.name == '__init__.py':
                continue

            # Build the dotted module name relative to the project package.
            rel = py.relative_to(base)
            parts = list(rel.with_suffix('').parts)
            module_name = 'ai_models.' + '.'.join(parts)

            # Try to import the module. If it fails, skip and continue.
            try:
                importlib.import_module(module_name)
            except Exception:
                continue