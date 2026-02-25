from uuid import UUID

class Local():
    def __init__(self, nome: str, cidade: str, estado: str, id: UUID = None):
        self.nome = nome
        self.cidade = cidade
        self.estado = estado
        self.id = id

    