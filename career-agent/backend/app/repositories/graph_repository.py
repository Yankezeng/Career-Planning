from abc import ABC, abstractmethod


class GraphRepository(ABC):
    @abstractmethod
    def get_job_relations(self, job_id: int):
        raise NotImplementedError

    @abstractmethod
    def find_transfer_path(self, source_job_id: int, target_job_id: int):
        raise NotImplementedError
