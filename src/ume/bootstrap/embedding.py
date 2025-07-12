from importlib import import_module
from typing import Callable, Any, Tuple, Type, Optional

__all__ = ["load_embedding"]

def load_embedding(
    package: str, register_listener: Callable[[Any], None]
) -> Tuple[Callable[[str], list[float]], Optional[Type[Any]], Optional[Callable[..., Any]]]:
    """Return generate_embedding and optionally register OntologyListener."""
    try:
        embedding_mod = import_module(f"{package}.embedding")
        generate_embedding = embedding_mod.generate_embedding
        ontology_mod = import_module(f"{package}.ontology")
        OntologyListener = ontology_mod.OntologyListener
        configure_ontology_graph = ontology_mod.configure_ontology_graph
        listener = OntologyListener()
        register_listener(listener)
        return generate_embedding, OntologyListener, configure_ontology_graph
    except Exception:
        def generate_embedding(_: str) -> list[float]:
            raise ImportError(
                "sentence-transformers is required to generate embeddings"
            )
        return generate_embedding, None, None
