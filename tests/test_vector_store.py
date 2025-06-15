import numpy as np
import pytest

faiss = pytest.importorskip("faiss")


def _has_gpu_support() -> bool:
    """Return True if FAISS was compiled with GPU support and a GPU is available."""
    return hasattr(faiss, "StandardGpuResources") and getattr(faiss, "get_num_gpus", lambda: 0)() > 0


@pytest.mark.skipif(not _has_gpu_support(), reason="FAISS GPU libraries are unavailable")
def test_add_and_query_gpu_index() -> None:
    """Verify basic add/query operations on a small FAISS GPU index."""
    dimension = 4
    data = np.random.random((10, dimension)).astype("float32")
    cpu_index = faiss.IndexFlatL2(dimension)
    res = faiss.StandardGpuResources()
    index = faiss.index_cpu_to_gpu(res, 0, cpu_index)

    index.add(data)
    _, indices = index.search(data, 1)

    assert np.all(indices.ravel() == np.arange(10))
