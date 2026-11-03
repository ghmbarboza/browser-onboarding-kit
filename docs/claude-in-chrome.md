# Anatomia do Claude in Chrome

Análise em 2026-11-02. Fonte local: pacote distribuído da extensão, versão
1.0.104, Manifest V3. Os hashes e sinais reproduzíveis estão em
[extension-static-report.json](extension-static-report.json). Nenhum bundle,
cookie, token, conversa ou dado do perfil foi incluído no repositório.

## Camadas que participam de uma tarefa

| Camada | Função | O que o pacote configura |
| --- | --- | --- |
| Instruções do usuário | Define contas, objetivo, destinos e autorização | Modelo de escopo e autorização explícita |
| Claude Code | Carrega memória, skills e hooks | Bloco global, skill, SessionStart e UserPromptSubmit |
| Inicialização do CLI | Habilita ferramentas e contexto de sessão | Launcher com `--chrome` e prompt adicional |
| Conexão nativa | Liga o processo local à extensão | Diagnóstico; não troca ou modifica o host |
| Permissões da extensão | Decide acesso a sites e ações que exigem aprovação | Orientação via `/chrome`; nenhuma alteração oculta |
| Painel lateral | Tem sua própria conversa e contexto | Texto para colar nessa conversa |
| Modelo e serviços | Podem aplicar regras e limites adicionais | Registro correto da causa observada e retomada |

O agente do Claude Code usa as ferramentas da extensão dentro da mesma
sessão. Isso permite aplicar o contexto instalado às ações dele no Chrome.
Uma conversa iniciada no painel lateral é outra sessão: os hooks locais do
Code não são uma instalação global dentro da extensão. Use o
[contexto para o painel](../chrome/sidebar-instructions.md) nessa conversa.
[Integração oficial](https://code.claude.com/docs/en/chrome).

## O que a inspeção local mostrou

- O manifesto declara `nativeMessaging`, `debugger`, `scripting`, `tabs`,
  `tabGroups`, `storage` e acesso a hosts. Essas são capacidades do pacote;
  não comprovam consentimento por site nem conexão ativa.
- O service worker contém integração por native messaging. O emparelhamento
  com Code/Desktop faz parte da ponte; um launcher não substitui essa ponte.
- Há referências a modos de permissão em componentes distintos, incluindo
  a ponte e o fluxo MCP. Ter o CLI em bypass não demonstra que uma aprovação
  ou restrição da extensão foi removida.
- O painel contém configuração de prompts, um campo `userSystemPrompt` e
  referências a configuração remota. Existem também textos de interface
  relacionados a prompt personalizado. Isso é evidência estática, sem
  confirmação de disponibilidade dessa opção na interface do usuário.
- O esquema de políticas gerenciadas do pacote contém `blockedUrlPatterns`
  e `forceLoginOrgUUID`. Não foi encontrada nesse esquema uma chave para
  liberar criação de contas ou substituir regras internas.
- O painel inclui aviso sobre ações como criar contas. Um texto no bundle
  não revela sozinho como a decisão é aplicada pelo modelo ou servidor.

Não inferimos que exista um botão de “aceitar tudo” a partir de nomes de
variáveis. Esta inspeção não capturou requisições autenticadas nem prompts
remotos. Não houve mudança de arquivos assinados, flags internos ou dados
de armazenamento da extensão.

## Limite confirmado pela documentação

O guia oficial lista criação de contas entre ações proibidas,
independentemente das permissões. Instruções que explicitam a autorização
do usuário não alteram essa proibição. Modos de aprovação e regras do
produto são camadas distintas.
[Guia de permissões](https://support.claude.com/en/articles/12902446-claude-in-chrome-permissions-guide).

O contexto deste pacote combate recusas genéricas por ambiguidade de
autorização: esclarece intenção, origem da conta, destino da credencial e
resultado esperado. Não afirma revogar restrições do provedor. Quando uma
ação continua bloqueada, o fluxo preserva a etapa e solicita somente a
intervenção necessária, retomando após confirmação.

## Diagnóstico de uma recusa

1. Verifique `/chrome`: integração habilitada, extensão instalada e navegador
   correto. Use autenticação compatível no Code. A documentação informa
   que API key/token de `setup-token` não habilitam a integração.
2. Diferencie uma resposta do modelo de uma chamada que foi efetivamente
   negada. Registre a ação e o erro mínimo, sem dados de credencial.
3. Confira permissão do site pela interface da extensão. Não conclua que
   `bypassPermissions` no Code configura acesso ao domínio no Chrome.
4. Se faltar login, use sessão existente ou autenticação suportada. Não
   leia cookies ou senhas para tentar reconstruir a sessão em outro browser.
5. Se a ferramenta/produto não permitir a etapa, registre o bloqueio uma vez,
   preserve o progresso e retome após a ação humana necessária. Não repita
   indefinidamente uma ação negada.

Um teste de `tabs_context_mcp` comprova comunicação com a extensão. Não
comprova acesso a todos os sites, capacidade de criar contas ou sucesso
de transferência de chaves. O pacote distingue essas verificações.

## Reproduzir a análise

Localize o diretório da versão instalada pelo gerenciador de extensões do
seu navegador. Passe somente o diretório que contém `manifest.json`:

```bash
python3 scripts/inspect_extension.py '/caminho/da/extensao/versao' > report.local.json
```

O script só lê manifesto, esquema gerenciado e bundles em `assets/*.js`.
O relatório contém metadados, contagens e hashes, sem trechos de código ou
caminhos absolutos. Refaça a análise ao atualizar a extensão; nomes dos
bundles e decisões do serviço podem mudar entre versões.
