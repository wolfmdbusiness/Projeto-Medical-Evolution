from __future__ import annotations

from templates.uti_hospitalis_v1 import DEFAULT_TEMPLATE, UTIHospitalisV1


class UnknownTemplateProfileError(Exception):
    """Raised when `meta.template_profile_id` names a profile that has no
    registered template (Milestone 1.1, item 6: the id must stop being
    decorative)."""

    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        super().__init__(f"Template profile desconhecido: '{profile_id}'")


class TemplateProfileMismatchError(Exception):
    """Raised when an explicit template is passed to the renderer but does
    not match the profile the state itself requests."""

    def __init__(self, requested_id: str, template_id: str):
        self.requested_id = requested_id
        self.template_id = template_id
        super().__init__(
            f"state.meta.template_profile_id='{requested_id}' é incompatível "
            f"com o template fornecido ('{template_id}')"
        )


_REGISTRY: dict[str, UTIHospitalisV1] = {
    DEFAULT_TEMPLATE.template_profile_id: DEFAULT_TEMPLATE,
}


def get_template_profile(profile_id: str) -> UTIHospitalisV1:
    """Simple, explicit profile_id -> template lookup.

    Intentionally not a plugin architecture: there is exactly one profile
    today, and this keeps the resolution mechanism a one-line dict lookup
    that fails loudly on an unknown id instead of a registry framework.
    """

    try:
        return _REGISTRY[profile_id]
    except KeyError:
        raise UnknownTemplateProfileError(profile_id) from None
