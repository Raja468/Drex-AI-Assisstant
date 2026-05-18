from abc import ABC, abstractmethod

class BaseAIClient(ABC):
    
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def generate(self, prompt: str, context: dict = None) -> str:
        pass