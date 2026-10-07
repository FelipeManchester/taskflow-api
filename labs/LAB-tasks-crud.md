# Lab: CRUD de tasks

Rotas de tasks aninhadas em `/projects/{project_id}/tasks`.

O lab está completo quando todos os testes de `tests/test_tasks.py` passarem.

## Regras

- `tests/test_tasks.py` é a especificação. Não edite: faça os testes passarem.
- `tests/conftest.py` é a infraestrutura dos testes (banco separado, cliente HTTP, usuários logados). Não precisa mexer.
- Se um teste parecer contraditório com as user stories, avise antes de forçar o código a passar nele.

## Preparação (uma vez só)

1. Criar o banco de testes. Os testes apagam e recriam as tabelas a cada execução, então nunca podem rodar no banco de desenvolvimento:

   ```bash
   docker compose exec db createdb -U app taskflow_test
   ```

2. Adicionar ao final do `pyproject.toml`:

   ```toml
   [tool.pytest.ini_options]
   pythonpath = ["."]
   testpaths = ["tests"]
   ```

3. Colocar `conftest.py` e `test_tasks.py` numa pasta `tests/` na raiz do projeto, ao lado de `app/`.

4. Rodar `uv run pytest` uma vez. Quase tudo vai aparecer como **FAILED**, e isso é o esperado. O que **não** pode aparecer é **ERROR**: ele indica problema na infraestrutura (banco de teste não criado, import quebrado), e precisa ser resolvido antes de começar.

## User stories

### US1: criar task

`POST /projects/{project_id}/tasks` cria uma task no projeto e responde **201** com o `TaskRead`.

- Sem `status` e `priority`, os defaults são `todo` e `medium`.
- O `project_id` vem da URL. Se o JSON trouxer um `project_id`, ele é ignorado.

### US2: autenticação e dono do projeto

- Todas as rotas de tasks exigem login: **401** sem token.
- Se o projeto não existe ou é de outro usuário: **404**.

### US3: validação

- `title` com 1 a 200 caracteres.
- `status`, `priority` e `due_date` inválidos: **422**.
- `description` com até **5000** caracteres.
- `assignee_id` que não corresponde a um usuário existente: **422** com `detail` igual a `"Assignee not found"`.

### US4: listar

`GET /projects/{project_id}/tasks` devolve só as tasks daquele projeto, ordenadas por `id`. Projeto sem tasks devolve `[]`.

### US5: buscar uma task

`GET /projects/{project_id}/tasks/{task_id}` devolve a task.

- Task inexistente: **404**.
- Task que existe, mas pertence a **outro projeto**: **404**, mesmo que os dois projetos sejam do mesmo usuário.

### US6: editar

`PATCH /projects/{project_id}/tasks/{task_id}` altera só os campos enviados.

- `title`, `status` e `priority` não aceitam `null`: **422**.
- `description`, `due_date` e `assignee_id` aceitam `null`, que limpa o campo.
- O `updated_at` da resposta precisa ser mais recente que o anterior.
- `assignee_id` segue a mesma regra da US3.

### US7: remover

`DELETE /projects/{project_id}/tasks/{task_id}` responde **204** sem body. Depois disso, a task dá **404**.

### US8: cascata

Apagar um projeto apaga as tasks dele.

## Passo a passo

Cada passo termina com um comando de teste. Só avance quando os testes daquele passo estiverem verdes.

### Passo 0: mover o `ProjectDep`

**Arquivos:** `app/routers/projects.py` e `app/dependencies.py`

O router de tasks vai precisar do `ProjectDep`, e um router não deve importar de outro (risco de import circular). Por isso ele vai para o arquivo compartilhado.

1. Recorte o `get_project_or_404` e o `ProjectDep` do `projects.py` e cole no `dependencies.py`, abaixo do `CurrentUserDep`.
2. No `dependencies.py`, ajuste os imports: agora ele precisa do model `Project`.
3. No `projects.py`, importe o `ProjectDep` do `dependencies.py` e remova os imports que deixaram de ser usados.

**Confira:** o servidor sobe (`uv run fastapi dev app/main.py`) e as rotas de projetos continuam funcionando no `/docs`.

### Passo 1: o esqueleto do router

**Arquivos:** `app/routers/tasks.py` e `app/main.py`

1. Crie o router com `prefix="/projects/{project_id}/tasks"` e `tags=["tasks"]`.
   - O nome do parâmetro na URL precisa ser exatamente `project_id`: é por ele que o `get_project_or_404` recebe o valor.
2. Registre o router no `main.py` com `include_router`.

**Confira:** a seção **tasks** aparece no `/docs` (ainda vazia).

### Passo 2: criar task (US1 e US2)

**Arquivo:** `app/routers/tasks.py`

Escreva a rota `POST ""`. Ela precisa receber:

- o body, com o schema de criação de task;
- o projeto, com o `ProjectDep`. Ele já resolve o 401 e o 404 da US2 sozinho;
- a session, com o `SessionDep`.

E fazer:

1. Montar um `Task` a partir do body, com o `project_id` vindo do **projeto**, não do body.
2. `add`, `commit` e `refresh`.
3. Devolver a task com `status_code` 201 e `response_model` de leitura.

É muito parecido com o `create_project`.

**Teste:**

```bash
uv run pytest -k "create_task and not assignee and not rejects" -v
```

Devem passar 5 testes.

### Passo 3: validação (US3)

**Arquivos:** `app/schemas.py` e `app/routers/tasks.py`

1. **Limite da descrição:** no `schemas.py`, a `description` do `TaskCreate` e do `TaskUpdate` ganha `max_length=5000`. Use o `Field(default=None, ...)`.
2. **Responsável inexistente:** no `tasks.py`, antes de criar a task, se o `assignee_id` vier preenchido, confira se o usuário existe com `session.get(User, ...)`. Se não existir, lance um `HTTPException` 422 com `detail="Assignee not found"`.
   - Escreva essa checagem como uma **função auxiliar** no próprio `tasks.py` (recebendo a session e o `assignee_id`), porque o `PATCH` vai precisar dela também.

**Teste:**

```bash
uv run pytest -k "rejects_invalid_payload or 5000_chars or create_task_with_existing_assignee or create_task_with_nonexistent_assignee" -v
```

Devem passar 10 testes (o primeiro é parametrizado e conta como 7).

### Passo 4: listar (US4)

**Arquivo:** `app/routers/tasks.py`

Escreva a rota `GET ""`. Ela recebe o projeto e a session, e faz um `select(Task)` filtrando pelo `project_id` do projeto, ordenado por `id`. É parecida com o `list_projects`, sem a paginação.

**Teste:**

```bash
uv run pytest -k "list or require_authentication" -v
```

Devem passar 4 testes. O `require_authentication` entra aqui porque ele testa o `POST` e o `GET` de listagem.

### Passo 5: buscar uma task (US5)

**Arquivo:** `app/routers/tasks.py`

1. Crie uma dependency `get_task_or_404`, no mesmo espírito do `get_project_or_404`. Ela recebe:
   - o `task_id` (vem da URL);
   - o projeto, pelo `ProjectDep`;
   - a session.

   E lança 404 se a task não existir **ou** se o `project_id` dela for diferente do `id` do projeto. Essa segunda condição é o que fecha o caso "task de outro projeto".

2. Crie o alias `TaskDep`, como o `ProjectDep`.
3. Escreva a rota `GET "/{task_id}"`, que só devolve a task.

O `TaskDep` pode ficar no próprio `tasks.py`, porque só esse router usa.

**Teste:**

```bash
uv run pytest -k "get_task or get_nonexistent" -v
```

Devem passar 4 testes.

### Passo 6: editar (US6)

**Arquivo:** `app/routers/tasks.py`

Escreva a rota `PATCH "/{task_id}"`. Ela recebe o body de edição, a task (`TaskDep`) e a session.

1. Pegue só os campos enviados com `model_dump(exclude_unset=True)`.
2. Se o `assignee_id` estiver entre eles **e** não for `None`, use a função auxiliar do passo 3. (`None` é permitido: significa tirar o responsável.)
3. Aplique os campos com `setattr`, como no `update_project`.
4. `commit` e devolva a task.

Rode os testes **antes** de seguir para o item 5. Um deles deve falhar com 500.

5. Leia o erro do `test_patch_bumps_updated_at` e resolva. Dica: quem calcula o novo `updated_at` é o banco, e o objeto em memória não sabe o valor novo.

**Teste:**

```bash
uv run pytest -k "patch" -v
```

Devem passar 9 testes (um deles é parametrizado e conta como 3).

### Passo 7: remover (US7 e US8)

**Arquivo:** `app/routers/tasks.py`

Escreva a rota `DELETE "/{task_id}"`, com `status_code` 204. Ela recebe a task e a session, remove a task e faz o `commit`. É igual ao `delete_project`.

A US8 (cascata) não exige código novo: ela testa o `ondelete="CASCADE"` e o `passive_deletes=True` que você já colocou no model.

**Teste:**

```bash
uv run pytest -k "delete" -v
```

Devem passar 3 testes.

### Passo 8: a suíte inteira

```bash
uv run pytest -v
```

Todos verdes. Depois, rode o Ruff:

```bash
uv run ruff check
uv run ruff format
```

## Rodando os testes

```bash
uv run pytest              # todos
uv run pytest -x           # para no primeiro que falhar
uv run pytest -k "create"  # só os que têm "create" no nome
uv run pytest -v           # mostra o nome de cada teste
```

Quando um teste falha, o pytest mostra a linha do `assert` e os valores comparados. Leia de baixo para cima, como os tracebacks.

## Entrega

Quando todos ficarem verdes, mandar para revisão:

1. a saída do `uv run pytest -v`;
2. o `app/routers/tasks.py`;
3. o trecho do `dependencies.py` com o `get_project_or_404`.
