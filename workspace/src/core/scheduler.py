# Scheduler class to manage tasks

from .agents.base import BaseAgent


class Scheduler:
    def __init__(self):
        self.agents = [DevAgent()]

    def run_task(self, task):
        for agent in self.agents:
            agent.execute(task)