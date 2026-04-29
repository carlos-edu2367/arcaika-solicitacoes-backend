# Arcaika — API de Ordens de Serviço

Backend em **Python / FastAPI** para gerenciamento de solicitações e ordens de serviço em empresas de engenharia. Permite que usuários de unidades criem OS com anexos, acompanhem status e recebam atualizações, enquanto admins gerenciam o ciclo completo de atendimento.

---

## Sumário

- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Stack](#stack)
- [Estrutura de diretórios](#estrutura-de-diretórios)
- [Configuração e ambiente](#configuração-e-ambiente)
- [Rodando o projeto](#rodando-o-projeto)
- [Endpoints principais](#endpoints-principais)
- [Autenticação e roles](#autenticação-e-roles)
- [Upload de anexos](#upload-de-anexos)
- [Background jobs](#background-jobs)

---

## Funcionalidades

### Usuários (`/user`)
- Login unificado para `users` globais e `local_users`
- Registro de usuários admin e cliente
- Criação de `local_users` vinculados a uma unidade (por admin)
- Troca de senha

### Locais (`/requests/local`)
- Criação de unidades com cidade e estado (por admin)
- Listagem por cidade/estado e busca por ID

### Solicitações / OS (`/requests`, `/local_user/solicitacoes`)
- Criação de OS com nome, e-mail, telefone, descrição, prioridade e anexos
- Listagem paginada por local, status ou ID
- Workflow de status: `criado → em_andamento → concluido` (transições só por admin)
- Edição de OS em status `criado` (só pelo `local_user` dono)
- Soft-delete de OS em status `criado` (só pelo `local_user` dono)
- Upload de múltiplos anexos (imagens, vídeos, PDF — até 10 MB cada)

### Notificações
- E-mail automático para admins na criação de cada OS

---

## Arquitetura

O projeto segue uma arquitetura em camadas inspirada em Clean Architecture / DDD:

```
┌─────────────────────────────────────────────────┐
│                   Infra Layer                   │
│  FastAPI routes · SQLAlchemy repos · RQ worker  │
│       Supabase storage · Email provider         │
├─────────────────────────────────────────────────┤
│               Application Layer                 │
│   Services · DTOs (Pydantic) · Repo interfaces  │
├─────────────────────────────────────────────────┤
│                 Domain Layer                    │
│    Entities · Enums · Erros de domínio          │
└─────────────────────────────────────────────────┘
```

**Camadas:**

| Camada | Diretório | Responsabilidade |
|---|---|---|
| Domain | `domain/entities/` | Entidades puras, enums (`Roles`, `Status`, `Prioridade`), erros de domínio |
| Application | `application/services/`, `dtos/`, `providers/` | Lógica de negócio, DTOs Pydantic, interfaces abstratas de repositório |
| Infra | `infra/` | Implementações concretas: DB (SQLAlchemy async), rotas FastAPI, workers RQ, providers de hash/token/storage/email |

**Decisões arquiteturais:**
- Repositórios definidos como abstrações no domínio e implementados na infra, injetados via `Depends`
- Unit of Work (UoW) para controle de transações
- Sequence no PostgreSQL para `ordem_servico` única e sequencial
- Worker Docker separado para processar uploads pesados sem bloquear a API

---

## Stack

| Categoria | Tecnologia |
|---|---|
| Framework | FastAPI 0.109 + Uvicorn |
| Banco de dados | PostgreSQL (async via asyncpg + SQLAlchemy 2.0) |
| Fila / Cache | Redis + RQ (Redis Queue) |
| Armazenamento | Supabase Storage |
| Autenticação | JWT (python-jose) + Argon2 (passlib) |
| Rate limiting | fastapi-limiter |
| Containerização | Docker Compose (3 serviços: redis, api, worker) |
| Validação | Pydantic 2.x |

---

## Estrutura de diretórios

```
arcaika/
├── domain/
│   └── entities/          # User, Local, Solicitacao, LocalUser, AnexoSolicitacao
├── application/
│   ├── services/          # SolicitacaoService, UserService, etc.
│   ├── dtos/              # Schemas Pydantic de entrada e saída
│   └── providers/         # Interfaces: UserRepo, StorageProvider, EmailProvider
├── infra/
│   ├── db/                # Models SQLAlchemy + to_domain() mappers
│   ├── web/               # Rotas FastAPI (/user, /requests, /local_user)
│   ├── workers/           # Jobs RQ para processamento de anexos
│   └── providers/         # Implementações: hash, token, Supabase, SMTP
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Configuração e ambiente

Copie o arquivo de exemplo e preencha as variáveis:

```bash
cp .env.example .env
```

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | URL de conexão PostgreSQL async (`postgresql+asyncpg://...`) |
| `REDIS_URL` | URL do Redis (`redis://localhost:6379`) |
| `SECRET_KEY` | Chave secreta para JWT |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | Service role key do Supabase |
| `SUPABASE_BUCKET` | Nome do bucket para armazenar anexos |
| `SMTP_HOST` | Servidor SMTP para envio de e-mails |
| `SMTP_USER` | Usuário SMTP |
| `SMTP_PASSWORD` | Senha SMTP |
| `ADMIN_EMAIL` | E-mail de destino para notificações de novas OS |

---

## Rodando o projeto

### Com Docker Compose (recomendado)

```bash
# Subir todos os serviços (redis, api, worker)
docker compose up --build

# Apenas em background
docker compose up -d --build
```

Os 3 serviços sobem automaticamente:
- `redis` — cache e fila de jobs
- `api` — FastAPI na porta `8000`
- `worker` — consumer RQ para processamento de anexos

### Localmente (sem Docker)

```bash
# Instalar dependências
pip install -r requirements.txt

# Subir o Redis separadamente
redis-server

# Iniciar a API
uvicorn infra.web.main:app --reload

# Em outro terminal, iniciar o worker
rq worker upload_anexos --url redis://localhost:6379
```

A API estará disponível em `http://localhost:8000`.  
Documentação interativa: `http://localhost:8000/docs`

---

## Endpoints principais

### Autenticação
| Método | Rota | Descrição | Role |
|---|---|---|---|
| `POST` | `/user/login` | Login (user ou local_user) | Público |
| `POST` | `/user/register` | Registrar user admin/cliente | Admin |
| `POST` | `/user/local_user` | Criar local_user vinculado a local | Admin |
| `PATCH` | `/user/password` | Troca de senha | Autenticado |

### Locais
| Método | Rota | Descrição | Role |
|---|---|---|---|
| `POST` | `/requests/local` | Criar local/unidade | Admin |
| `GET` | `/requests/local` | Listar locais (filtro cidade/estado) | Autenticado |
| `GET` | `/requests/local/{id}` | Buscar local por ID | Autenticado |

### Solicitações
| Método | Rota | Descrição | Role |
|---|---|---|---|
| `POST` | `/local_user/solicitacoes` | Criar OS com anexos | Local User |
| `GET` | `/requests` | Listar OS (paginado, filtros) | Admin / Cliente |
| `GET` | `/requests/{id}` | Detalhe da OS | Autenticado |
| `PATCH` | `/requests/{id}/status` | Atualizar status da OS | Admin |
| `PUT` | `/local_user/solicitacoes/{id}` | Editar OS em status `criado` | Local User |
| `DELETE` | `/local_user/solicitacoes/{id}` | Soft-delete OS em status `criado` | Local User |

---

## Autenticação e roles

O sistema usa **JWT** com três roles distintos:

| Role | Descrição | Permissões principais |
|---|---|---|
| `ADMIN` | Administrador global | Tudo — incluindo mudar status de OS e criar usuários |
| `CLIENTE` | Usuário cliente | Visualizar OS do seu local |
| `LOCAL_USER` | Usuário de unidade | Criar, editar e deletar próprias OS (só em status `criado`) |

O token é retornado no login e deve ser enviado no header:

```
Authorization: Bearer <token>
```

Rate limiting está ativo nos endpoints de autenticação e upload para proteger contra abuso.

---

## Upload de anexos

- Formatos aceitos: imagens (JPEG, PNG, WebP), vídeos (MP4, MOV) e PDF
- Tamanho máximo por arquivo: **10 MB**
- Múltiplos arquivos por OS
- Cada anexo tem uma classe: `cliente` ou `admin`

O upload é feito junto à criação da OS via `multipart/form-data`. O processamento é **assíncrono** — os arquivos são salvos temporariamente e enfileirados para o worker processar.

---

## Background jobs

O worker RQ consome a fila `upload_anexos` e executa:

1. Lê o arquivo temporário salvo pela API
2. Envia para o Supabase Storage
3. Atualiza o registro `AnexoSolicitacao` no banco com a URL final
4. Remove o arquivo temporário

Isso garante que a criação da OS responde imediatamente ao usuário, sem aguardar o upload completar.

```
API ──► salva temp + enfileira job ──► responde 201
                                          │
Worker ◄── consome fila ◄────────────────┘
Worker ──► Supabase Storage + atualiza DB
```
