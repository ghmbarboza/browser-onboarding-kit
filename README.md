# Browser Onboarding Kit

[![Check](https://github.com/ghmbarboza/browser-onboarding-kit/actions/workflows/check.yml/badge.svg)](https://github.com/ghmbarboza/browser-onboarding-kit/actions/workflows/check.yml)

Pacote white label para executar onboarding de plataformas autorizadas
com Claude Code e Claude in Chrome: aproveitar logins, alternar entre a
plataforma e os serviços necessários, configurar integrações e validar.

Instala contexto persistente no escopo do usuário. A autorização cobre
as tarefas que cada usuário indicar; a instalação não concede acesso a
contas ou permissões adicionais. O pacote não altera regras internas do
Claude. O [guia do Chrome](https://support.claude.com/en/articles/12902446-claude-in-chrome-permissions-guide)
lista criar contas como ação proibida, mesmo com permissões. Se a extensão
bloquear uma etapa, o agente pede somente a intervenção necessária e retoma.

## Instalar

Requer Python 3.10+, Git, Claude Code e a extensão Claude in Chrome instalada
e conectada. O instalador usa somente a biblioteca padrão do Python. macOS
e Linux são os ambientes suportados pelo instalador; a integração real
depende dos ambientes aceitos pelo Claude. Windows nativo não foi validado.

```bash
git clone https://github.com/ghmbarboza/browser-onboarding-kit.git
cd browser-onboarding-kit
python3 install.py
python3 install.py --check
```

Reinicie/retome o Code depois da instalação. Em `/chrome`, confira a conexão
e habilite “Enabled by default” se quiser Chrome também nas sessões comuns.
Essa configuração é feita pela interface oficial; o instalador não edita
preferências privadas da extensão.

Abra uma sessão na pasta do seu projeto:

```bash
~/.local/bin/onboarding-studio /caminho/do/projeto
```

Para retomar:

```bash
~/.local/bin/onboarding-studio /caminho/do/projeto --continue
```

Se `~/.local/bin` estiver no PATH, basta `onboarding-studio`. Sem pasta, o
launcher usa a pasta atual. Ele recusa iniciar na home ou na raiz e passa
`--chrome` e o contexto atualizado. Nas versões que oferecem
`--system-prompt-snapshot`, desativa a reutilização do snapshot para que a
retomada receba as instruções atuais.

Envie o objetivo, a URL e as contas autorizadas usando
[session-brief.md](examples/session-brief.md). A skill pode ser chamada como
`/browser-onboarding`, além de ser selecionada automaticamente pelo Code.

## O que fica instalado

| Local padrão | Conteúdo |
| --- | --- |
| `~/.claude/CLAUDE.md` | Bloco delimitado com o protocolo global |
| `~/.claude/settings.json` | Hooks SessionStart e UserPromptSubmit |
| `~/.claude/skills/browser-onboarding/SKILL.md` | Procedimento completo |
| `~/.claude/browser-onboarding-kit/` | Contexto, hook, launcher e manifesto |
| `~/.local/bin/onboarding-studio` | Comando que ativa Claude in Chrome |
| `~/.claude/backups/browser-onboarding-kit/` | Backups locais privados dos arquivos alterados |

O contexto retorna ao iniciar, retomar, limpar/compactar e a cada prompt.
O hook não lê prompts, cofres ou páginas, não faz chamadas de rede e não
aprova ferramentas. As instruções locais têm a prioridade normal do Code.
Hooks desabilitados pelo usuário ou políticas administradas continuam
valendo. `--bare` e `--safe-mode` desativam parte dessas camadas.

O instalador preserva MCPs, modos de permissão, outros hooks e texto global.
Valida os arquivos antes de escrever, cria backups privados e tenta reverter
as escritas se ocorrer uma falha. Não instala dependências, não coleta
telemetria e não modifica a extensão. Não usa `sudo`.

Ele respeita `CLAUDE_CONFIG_DIR`; também aceita `--config-dir` e `--bin-dir`.
Arquivos de destino que sejam symlinks ou arquivos gerenciados editados
manualmente precisam ser resolvidos antes de atualizar. Faça a instalação
com sessões do Code ociosas para evitar edição concorrente de settings.

## Chrome integrado e painel lateral

Quando Code controla o Chrome, as instruções desta sessão orientam o agente
que chama as ferramentas da extensão. O painel lateral independente tem
outro contexto: cole [sidebar-instructions.md](chrome/sidebar-instructions.md)
ao iniciar a conversa ali. O instalador não injeta conteúdo silenciosamente
nesse painel. Veja a [anatomia e diagnóstico](docs/claude-in-chrome.md).

## Atualizar e remover

```bash
git pull --ff-only
python3 install.py
python3 install.py --check
```

A reinstalação não duplica os hooks. Para remover, execute no clone:

```bash
python3 install.py --uninstall
```

Use os mesmos diretórios personalizados da instalação. A remoção preserva
alterações externas aos blocos e hooks do pacote e mantém arquivos
gerenciados que tenham sido editados, informando seus caminhos. Backups
locais são mantidos; não os publique, pois podem conter configurações privadas.
Para suspender somente o contexto do hook em uma sessão, use
`BROWSER_ONBOARDING_OFF=1 claude`; o bloco global e a skill continuam instalados.

## Verificar o pacote

```bash
python3 -m unittest discover -s tests -v
```

Os testes usam diretórios temporários: verificam preservação de settings,
instalação repetida, remoção, falhas e entrega de contexto. Não criam contas
nem usam credenciais reais. Um teste de conexão com Chrome não demonstra
que um onboarding real foi concluído.

Código e textos próprios sob MIT. Nenhum código proprietário da extensão
é redistribuído. Você pode adaptar o nome, idioma e instruções para sua
distribuição. Não há caminhos, contas ou credenciais do autor no runtime.

Fontes oficiais: [hooks](https://code.claude.com/docs/en/hooks),
[skills](https://code.claude.com/docs/en/skills),
[integração Chrome](https://code.claude.com/docs/en/chrome).
