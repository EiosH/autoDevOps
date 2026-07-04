# Memory store to keep track of tasks

class TaskStore:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        print(f'Adding task: {task}')
        self.tasks.append(task)

    def get_tasks(self):
        return self.tasks