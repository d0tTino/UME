import numpy as np

class IndexFlatL2:
    def __init__(self, dim: int) -> None:
        self.d = dim
        self.vectors: np.ndarray = np.empty((0, dim), dtype="float32")

    def add(self, arr: np.ndarray) -> None:
        self.vectors = np.vstack([self.vectors, arr])

    def search(self, arr: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        if self.vectors.size == 0:
            return np.empty((arr.shape[0], k)), np.full((arr.shape[0], k), -1)
        diff = self.vectors[None, :, :] - arr[:, None, :]
        dist = np.sum(diff ** 2, axis=2)
        idx = np.argsort(dist, axis=1)[:, :k]
        dists = np.take_along_axis(dist, idx, axis=1)
        return dists, idx

    @property
    def ntotal(self) -> int:
        return self.vectors.shape[0]

class StandardGpuResources:
    def __init__(self) -> None:
        self.temp_memory: int | None = None

    def setTempMemory(self, value: int) -> None:  # noqa: N802
        self.temp_memory = value

def index_cpu_to_gpu(res: StandardGpuResources, device: int, index: IndexFlatL2) -> IndexFlatL2:
    return index

def index_gpu_to_cpu(index: IndexFlatL2) -> IndexFlatL2:
    return index

def write_index(index: IndexFlatL2, path: str) -> None:
    with open(path, "wb") as f:
        np.save(f, index.vectors)

def read_index(path: str) -> IndexFlatL2:
    with open(path, "rb") as f:
        data = np.load(f)
    index = IndexFlatL2(data.shape[1])
    index.vectors = data
    return index


