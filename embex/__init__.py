"""Embex — Local-first memory layer for AI agents."""

# Apply Python 3.14 compatibility patch for chromadb/pydantic.v1
# MUST run before any module imports chromadb.
import sys as _sys
import warnings

# Suppress Pydantic V1 compatibility warning
warnings.filterwarnings("ignore", message=".*Pydantic V1 functionality.*")

if _sys.version_info >= (3, 14):
    try:
        import pydantic.v1.fields as _pv1_fields

        _orig_init = _pv1_fields.ModelField.__init__

        def _patched_field_init(self, *args, **kwargs):
            try:
                _orig_init(self, *args, **kwargs)
            except Exception as exc:
                if "unable to infer type" in str(exc):
                    import typing
                    self.name = kwargs.get("name", "unknown")
                    self.type_ = typing.Any
                    self.outer_type_ = typing.Any
                    self.class_validators = {}
                    self.default = kwargs.get("default", None)
                    self.default_factory = kwargs.get("default_factory", None)
                    self.required = False
                    self.model_config = kwargs.get(
                        "model_config", type("Config", (), {})
                    )
                    self.field_info = kwargs.get(
                        "field_info", _pv1_fields.FieldInfo()
                    )
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

        _pv1_fields.ModelField.__init__ = _patched_field_init
    except Exception:
        pass

