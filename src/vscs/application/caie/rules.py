"""Category knowledge, style language, and exclusions used by CAIE."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.domain.assets import AssetCategory


@dataclass(frozen=True, slots=True)
class CategoryPromptRule:
    classification: str
    functional_language: str
    environment_language: str
    required_anchors: tuple[str, ...]
    negative_terms: tuple[str, ...]


STYLE_PROFILES: dict[str, str] = {
    "grounded_cinematic": (
        "Grounded, physically plausible design; premium streaming television production quality; "
        "realistic materials; physically accurate lighting; restrained visual effects; coherent scale; "
        "functional engineering; cinematic HDR; subtle film grain; no fantasy styling."
    ),
    "neutral_reference": (
        "Clean production reference presentation, neutral composition, clear readable silhouette, even lighting, "
        "accurate materials, minimal background distraction, high detail."
    ),
}


CATEGORY_RULES: dict[AssetCategory, CategoryPromptRule] = {
    AssetCategory.SHIP: CategoryPromptRule(
        classification="an orbital spacecraft operating in vacuum, not a terrestrial maritime vessel",
        functional_language="Show a purpose-built spacecraft whose hull, propulsion, docking systems and external machinery clearly express its production role.",
        environment_language="Place it in space, an orbital dock, starport, shipyard, planetary orbit or deep-space operating environment.",
        required_anchors=("spacecraft", "vacuum", "orbital"),
        negative_terms=("terrestrial tugboat", "harbour tug", "boat", "ocean", "sea", "water", "mast", "sails", "rigging", "anchor", "lifebuoy", "tyre fenders", "maritime funnel"),
    ),
    AssetCategory.VEHICLE: CategoryPromptRule(
        classification="a technologically coherent production vehicle, not an unrelated contemporary consumer vehicle",
        functional_language="Make its mobility system, crew access, structure and intended operating role immediately legible and functional.",
        environment_language="Place it in the environment where it is canonically operated.",
        required_anchors=("vehicle", "functional"),
        negative_terms=("toy vehicle", "generic sports car", "unrelated modern traffic"),
    ),
    AssetCategory.CHARACTER: CategoryPromptRule(
        classification="a single canonical production character reference",
        functional_language="Preserve age, body proportions, facial identity, hair, wardrobe and role-specific details; show one person only.",
        environment_language="Use a neutral studio reference setting unless the CAP explicitly requires an environmental portrait.",
        required_anchors=("canonical production character", "one person"),
        negative_terms=("multiple people", "duplicate person", "extra limbs", "extra fingers", "malformed hands", "cropped head", "identity drift"),
    ),
    AssetCategory.LOCATION: CategoryPromptRule(
        classification="a canonical production location with a coherent architectural and spatial identity",
        functional_language="Show circulation, scale, materials, structural logic and the location's production purpose clearly.",
        environment_language="Use a wide establishing composition that makes the location readable for future scene continuity.",
        required_anchors=("location", "architectural", "spatial"),
        negative_terms=("impossible architecture", "floating building parts", "generic fantasy palace"),
    ),
    AssetCategory.ENVIRONMENT: CategoryPromptRule(
        classification="a canonical natural or constructed production environment",
        functional_language="Define terrain, atmosphere, climate, scale, material character and navigable spatial layers.",
        environment_language="Use an establishing composition suitable for production continuity and later scene matching.",
        required_anchors=("environment", "scale"),
        negative_terms=("miniature diorama", "abstract background", "generic fantasy landscape"),
    ),
    AssetCategory.PLANET: CategoryPromptRule(
        classification="a planetary-scale world, not a small landscape or decorative sphere",
        functional_language="Show recognisable planetary geology, atmosphere, hydrology, cloud systems and continental-scale features where applicable.",
        environment_language="Use an orbital view or high-altitude view that communicates true planetary scale.",
        required_anchors=("planetary", "orbital view", "planetary scale"),
        negative_terms=("small floating island", "glass marble", "fantasy globe", "flat landscape only"),
    ),
    AssetCategory.PROP: CategoryPromptRule(
        classification="a single canonical production prop",
        functional_language="Show its form, materials, controls, wear state, scale cues and intended use with an unobstructed silhouette.",
        environment_language="Use a clean neutral production reference setting unless operational context is essential.",
        required_anchors=("canonical production prop", "production reference"),
        negative_terms=("multiple unrelated objects", "cluttered table", "product advertisement"),
    ),
    AssetCategory.TECHNOLOGY: CategoryPromptRule(
        classification="a physically coherent engineered technology asset",
        functional_language="Communicate how the device is constructed and operated through restrained, plausible interfaces and visible functional engineering logic.",
        environment_language="Present it as a clean production reference or in its correct operational installation.",
        required_anchors=("engineered technology", "functional"),
        negative_terms=("magic device", "excessive holograms", "floating interface", "neon circuitry everywhere"),
    ),
    AssetCategory.UNIFORM: CategoryPromptRule(
        classification="a canonical production costume and uniform reference",
        functional_language="Show the complete garment, rank or role identifiers, construction, closures, materials, trim and practical fit consistently.",
        environment_language="Use a neutral full body studio presentation on one wearer or a clean garment display.",
        required_anchors=("uniform reference", "full body"),
        negative_terms=("fashion runway", "multiple outfits", "cropped garment", "fantasy armour"),
    ),
    AssetCategory.EFFECT: CategoryPromptRule(
        classification="a controlled production visual effect reference",
        functional_language="Show the effect's source, physical interaction, scale, colour behaviour and environmental influence without obscuring its structure.",
        environment_language="Use a simple context that makes the effect readable and repeatable.",
        required_anchors=("visual effect reference", "controlled"),
        negative_terms=("uncontrolled explosion", "abstract colour cloud", "fantasy magic"),
    ),
}


DEFAULT_RULE = CategoryPromptRule(
    classification="a single canonical production asset",
    functional_language="Present the asset clearly, consistently and without unrelated objects.",
    environment_language="Use an appropriate production reference composition with coherent scale and lighting.",
    required_anchors=("canonical production asset",),
    negative_terms=("unrelated objects", "ambiguous subject"),
)


GLOBAL_NEGATIVE_TERMS = (
    "caption", "title card", "labels", "specification panel", "readable text", "letters", "numbers",
    "watermark", "logo", "UI overlay", "interface frame", "border", "poster layout", "infographic",
    "malformed typography", "low resolution", "blur", "duplicate objects", "distorted geometry",
    "cartoon", "anime", "illustration", "painterly", "AI artefacts",
)
