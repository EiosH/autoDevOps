# This is a base class for agents

class BaseAgent:
    def execute(self, task):
        raise NotImplementedError('This method should be overridden by subclass')