# daylib/concrete_components.py

from daylib.day_cost_components import AbstractArtifact, AbstractTask

class DataArtifact(AbstractArtifact):
    def calculate_storage_cost(self, genome_coverage: float, storage_rate: float) -> float:
        return self.size_per_x_cov * genome_coverage * storage_rate if self.keep else 0.0


class Task(AbstractTask):
    def calculate_task_cost(self, genome_coverage: float, vcpu_cost_per_min: float) -> float:
        return self.vcpu_min_per_x_cov * genome_coverage * vcpu_cost_per_min
