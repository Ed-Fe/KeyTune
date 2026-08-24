# KeyTune 2.0.0 — Plataforma extensível

O KeyTune 2 transforma o player acessível em uma plataforma extensível. Esta versão adiciona um sistema completo de plugins com API pública 2.0, permissões explícitas, gerenciador acessível, isolamento de falhas, instalação verificada e um marketplace mantido pela comunidade por pull requests no GitHub.

## Destaques

- Manifestos estritos e compatibilidade versionada.
- Permissões apresentadas antes da ativação, com plugins desativados por padrão.
- API para reprodução, biblioteca, rede, configurações, notificações, menus, abas e telas.
- Processo separado por padrão e logs de diagnóstico por plugin.
- Pacotes `.ktplugin` verificados por SHA-256, com instalação transacional e proteção contra caminhos inseguros.
- Marketplace remoto em JSON, downloads HTTPS e fluxo de revisão comunitária.
- AutoDJ com análise de BPM/batidas/energia, cache, perfis e planejamento conservador de transições.
- Guia público para autores e mantenedores do catálogo.

> O isolamento em processo evita que a falha de um plugin derrube o player, mas não é uma sandbox do sistema operacional. Instale somente plugins de autores em quem você confia.
