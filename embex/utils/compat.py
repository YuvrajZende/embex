"""
Compatibility shim for chromadb on Python 3.14+.

Python 3.14 broke ``pydantic.v1``'s type inference that chromadb's
Settings model depends on.  This module patches it before chromadb
is first imported.

**Usage**: ``from embex.utils.compat import chromadb``
"""

from __future__ import annotations

import sys

if sys.version_info >= (3, 14):
    # Patch pydantic.v1 field type resolution BEFORE chromadb imports it.
    # The issue: pydantic v1's ModelField._type_analysis() uses
    # typing.get_type_hints() which breaks on Python 3.14 for
    # some annotation styles.  We patch the FieldInfo resolution.
    try:
        import pydantic.v1.fields as _pv1_fields

        _OrigModelField = _pv1_fields.ModelField

        _orig_init = _OrigModelField.__init__

        def _patched_init(self, *args, **kwargs):
            try:
                _orig_init(self, *args, **kwargs)
            except (_pv1_fields.errors_.ConfigError, Exception) as exc:
                # If type inference fails, default to Any
                if "unable to infer type" in str(exc):
                    import typing
                    kwargs.setdefault("type_", typing.Any)
                    kwargs.setdefault("class_validators", {})
                    kwargs.setdefault("model_config", type('Config', (), {'arbitrary_types_allowed': True}))
                    # Set minimal attributes
                    self.name = kwargs.get("name", "unknown")
                    self.type_ = typing.Any
                    self.outer_type_ = typing.Any
                    self.class_validators = {}
                    self.default = kwargs.get("default", None)
                    self.default_factory = kwargs.get("default_factory", None)
                    self.required = False
                    self.model_config = kwargs.get("model_config", type('Config', (), {}))
                    self.field_info = kwargs.get("field_info", _pv1_fields.FieldInfo())
                    self.allow_none = True
                    self.validate_always = False
                    self.sub_fields = None
                    self.sub_fields_mapping = None
                    self.key_field = None
                    self.validators = {}
                    self.pre_validators = None
                    self.post_validators = None
                    self.parse_json = False
                    self.shape = 1
                    self.alias = self.name
                    self.has_alias = False
                    self.discriminator_key = None
                    self.discriminator_alias = None
                else:
                    raise

        _OrigModelField.__init__ = _patched_init
    except Exception:
        pass

import chromadb  # noqa: E402

__all__ = ["chromadb"]
