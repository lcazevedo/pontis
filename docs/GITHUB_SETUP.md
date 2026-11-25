# Guia de Publicação e Configuração no GitHub (Parte 13)

Este guia reúne os passos manuais na sua conta do GitHub para publicar o repositório **Pontis**, ativar a proteção da branch `main` e confirmar a primeira execução do CI.

---

## 1. Criar o repositório no GitHub

1. Acesse <https://github.com/new>.
2. Defina:
   - **Owner:** `lcazevedo`
   - **Repository name:** `pontis`
   - **Visibility:** `Public` (necessário para GitHub Actions gratuito ilimitado e para o botão *Sponsor* público).
3. **Não marque** *Add a README*, *.gitignore* nem *Choose a license* (o repositório local já possui tudo configurado).
4. Clique em **Create repository**.

---

## 2. Conectar o repositório local e enviar (`push`)

No diretório do projeto:

```bash
git remote add origin git@github.com:lcazevedo/pontis.git
# (ou via HTTPS: https://github.com/lcazevedo/pontis.git)

git branch -M main
git push -u origin main
```

---

## 3. Confirmar a execução do CI

1. Abra a aba **Actions** no repositório `github.com/lcazevedo/pontis`.
2. O workflow **CI** (`ci.yml`) será disparado automaticamente pelo `push` na branch `main` com 3 jobs:
   - `Quality (ruff & mypy)`
   - `Tests (pytest)`
   - `Build AppImage (Linux x86_64)` (gera e testa o AppImage em `ubuntu-22.04` e publica o artefato para download por 14 dias).
3. Aguarde todos os jobs ficarem verdes (`✓`).

---

## 4. Proteger a branch `main`

Depois que o primeiro **CI** concluir (para os nomes dos *status checks* aparecerem na busca do GitHub):

1. Acesse **Settings → Branches** (ou **Settings → Rules → Rulesets**).
2. Clique em **Add branch protection rule** (ou **New branch ruleset**) para `main`:
   - **Require a pull request before merging** (recomendado caso receba contribuições externas).
   - **Require status checks to pass before merging**:
     - Marque **Require branches to be up to date before merging**.
     - Adicione os 3 checks obrigatórios:
       - `Quality (ruff & mypy)`
       - `Tests (pytest)`
       - `Build AppImage (Linux x86_64)`
   - **Do not allow bypassing the above settings** (opcional para conta solo; se preferir poder fazer hotfix rápido como mantenedor, pode deixar desmarcado).
   - Bloqueie **force pushes** e **deletions**.
3. Salve a regra.

---

## 5. Ativar o botão Sponsor e checar templates

1. Vá em **Settings → General → Features** e confirme que **Sponsorships** está marcado (ele lê automaticamente o arquivo `.github/FUNDING.yml`, configurado com GitHub Sponsors e Ko-fi).
2. Abra **Issues → New issue** para conferir os formulários de **Bug report**, **Feature request** e os links de **Security** / **FAQ**.

---

## 6. Releases por tag (usado na Parte 14)

Quando chegar a hora de publicar uma versão (por exemplo `v1.0.0`):

1. Garanta que `pontis.__version__` em `src/pontis/__init__.py` e `pyproject.toml` seja `1.0.0`.
2. Crie e envie a tag:
   ```bash
   git tag -a v1.0.0 -m "Pontis v1.0.0"
   git push origin v1.0.0
   ```
3. O workflow **Release** (`.github/workflows/release.yml`) validará a versão, rodará toda a suíte de qualidade, compilará o AppImage em `ubuntu-22.04` e publicará o **GitHub Release** com `Pontis-1.0.0-x86_64.AppImage` e `.sha256` anexados automaticamente.
