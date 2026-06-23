from skills.base import BaseSkill


class SkillNotFoundError(Exception):
    pass


class SkillRegistry:
    def __init__(self) -> None:
        self.skills: list[BaseSkill] = []

    def register(self, skill: BaseSkill) -> None:
        self.skills.append(skill)

    def get(self, name: str) -> BaseSkill:
        for skill in self.skills:
            if skill.spec.name == name:
                return skill
        raise SkillNotFoundError(f"Skill with name '{name}' not found.")

    def list_skills(self):
        return [skill.spec for skill in self.skills]
