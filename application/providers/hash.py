from abc import ABC, abstractmethod

class HashProvider(ABC):
    @abstractmethod
    def hash(self, text: str) -> str:
        pass

    @abstractmethod
    def verify(self, hashed: str, text: str) -> bool:
        pass

