from typing import Any, Dict

import yaml  # type: ignore[import-untyped]

from daylib.day_concrete_components import Task, DataArtifact
from daylib.day_cost_components import ArtifactType, TaskType


class PipelineFactory:
    """
    Factory class to create tasks and their associated artifacts from a YAML configuration file.
    """

    def __init__(self, config_path: str):
        """
        Initialize the PipelineFactory with the path to a configuration YAML file.
        """
        self.config_path = config_path

    def load_config(self) -> Dict[Any, Any]:
        """
        Load the configuration YAML file into a dictionary.
        """
        with open(self.config_path, "r") as file:
            result: Dict[Any, Any] = yaml.safe_load(file)
            return result

    def create_artifact(self, artifact_config: dict) -> DataArtifact:
        """
        Create a DataArtifact object from its configuration dictionary.
        """
        return DataArtifact(
            name=artifact_config["name"],
            description=artifact_config["description"],
            artifact_type=ArtifactType(artifact_config["type"]),
            size_per_x_cov=artifact_config["size_per_x_cov"],
            keep=artifact_config["keep"]
        )

    def create_task(self, task_config: dict) -> Task:
        """
        Create a Task object and add its associated artifacts.
        """
        task = Task(
            name=task_config["name"],
            description=task_config["description"],
            task_type=TaskType(task_config["type"]),
            vcpu_min_per_x_cov=task_config["vcpu_min_per_x_cov"]
        )
        for artifact_config in task_config.get("artifacts", []):
            artifact = self.create_artifact(artifact_config)
            task.artifacts.append(artifact)
        return task

    def create_pipeline(self) -> list:
        """
        Create a list of Task objects by parsing the YAML configuration.
        """
        config = self.load_config()
        return [self.create_task(task) for task in config.get("tasks", [])]
