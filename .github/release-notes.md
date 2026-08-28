# KeyTune 2.0.0 — Plataforma extensível

O KeyTune 2 transforma o player acessível em uma plataforma extensível. Esta versão adiciona um sistema completo de plugins com API pública 2.0, permissões explícitas, gerenciador acessível, isolamento de falhas, instalação verificada e um marketplace mantido pela comunidade por pull requests no GitHub.

## Destaques

- Manifestos estritos e compatibilidade versionada.
- Confirmação de instalação com dados do plugin, permissões e modo de isolamento antes de instalar e ativar.
- API para reprodução, biblioteca, rede, arquivos de texto, área de transferência, configurações, notificações, menus, abas e telas; autenticação da conta é opcional e exige permissão própria.
- Processo separado por padrão, ambiente sem segredos, timeout de inicialização e logs de diagnóstico, preservando acesso normal às bibliotecas Python.
- Pacotes `.ktplugin` verificados por SHA-256, com instalação transacional e proteção contra caminhos inseguros.
- Marketplace remoto em JSON, downloads HTTPS e fluxo de revisão comunitária.
- AutoDJ ativável pelo menu e pelas preferências, com seleção entre até seis opções mesmo em playlists novas, análise de downbeat, frases de quatro compassos, mudanças de seção, energia local, loudness e tonalidade maior/menor, além de sincronização com correção de fase, troca progressiva de graves/EQ e corte na batida planejada.
- Sessões AutoDJ em uma aba dinâmica separada, com planejamento de várias faixas, cinco músicas preparadas à frente, restauração da fila, prevenção de provável choque vocal e compensação conservadora de loudness.
- A aba AutoDJ agora informa o que está sendo analisado, marca o estado das faixas e oferece controles para trocar ou recalcular a sequência, adicionar músicas e pausar a preparação.
- As informações do AutoDJ agora são lidas pelo NVDA no foco normal e explicam BPM, confiança, ajuste de tempo e o motivo de qualquer transição comum.
- `Ctrl+V` abre links de playlist do YouTube Music diretamente, a primeira faixa inicia de forma explícita e a automação de EQ do AutoDJ não reconstrói mais os filtros durante a transição.
- Guia público para autores e mantenedores do catálogo.

> O processo separado evita que uma falha comum derrube o player, mas o plugin continua tendo acesso normal ao computador e não fica em uma sandbox de segurança. Instale somente plugins de autores em quem você confia.
