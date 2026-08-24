# Plugins do KeyTune 2

O KeyTune 2 possui uma API pública baseada em capacidades, descoberta por manifesto, gerenciamento acessível, pacotes verificáveis e um marketplace que pode ser mantido inteiramente por pull requests no GitHub.

## Criando um plugin

Um pacote `.ktplugin` é um ZIP com `keytune-plugin.json` na raiz:

```json
{
  "id": "org.exemplo.meu-plugin",
  "name": "Meu plugin",
  "version": "1.0.0",
  "api_version": "2.0",
  "minimum_keytune_version": "2.0.0",
  "entrypoint": "plugin:Plugin",
  "author": "Exemplo",
  "description": "Uma integração de exemplo.",
  "license": "MIT",
  "isolation": "process",
  "permissions": ["playback.read", "notifications"]
}
```

O objeto indicado por `entrypoint` recebe a API no construtor. Pode implementar `on_start()`, `on_event(nome, dados)` e `on_stop()`. A API estável 2.x fornece estado/controle de reprodução, acesso às playlists já carregadas, biblioteca inteligente, YouTube Music, resolução pelo yt-dlp, análise AutoDJ, rede, armazenamento de configurações, notificações e contribuições de menu, aba e tela. Cada chamada exige a permissão correspondente.

Um exemplo instalável e mantido junto ao player está em `examples/plugins/now-playing`. Compacte o conteúdo da pasta — não a pasta externa — para gerar um `.ktplugin`.

```python
class Plugin:
    def __init__(self, api):
        self.api = api

    def on_start(self):
        state = self.api.playback_state()
        playlists = self.api.playlists()
        self.api.add_menu_action("announce", "Anunciar faixa", self.announce)

    def announce(self):
        state = self.api.playback_state()
        self.api.notify(state.get("media_path") or "Nada em reprodução")
```

No modo `process`, `add_menu_action` aceita o mesmo callback da API normal; o host guarda apenas o id e envia `ui.action` ao worker, que executa o callback dentro do processo isolado. Sem callback, o plugin pode tratar `on_event("ui.action", {"id": ...})`. Fábricas wxPython de abas/telas são exclusivas do modo `in_process`.

Plugins com telas ricas podem optar por `in_process`; só esse modo recebe fábricas wxPython para abas e telas. Ele tem o mesmo acesso ao computador que o KeyTune. O modo padrão `process` impede que uma falha derrube o player, mas **não é uma sandbox de segurança do sistema operacional**. Permissões controlam a API do KeyTune e informam o usuário; elas não tornam código Python não confiável seguro.

## Permissões

As permissões disponíveis são `playback.read`, `playback.control`, `library.read`, `library.write`, `youtube_music.read`, `youtube_music.write`, `yt_dlp`, `autodj.analyze`, `network`, `filesystem.read`, `filesystem.write`, `clipboard`, `notifications`, `ui.menu`, `ui.tab`, `ui.view` e `settings`. Uma atualização que pedir novas permissões fica sem elas até nova aprovação explícita.

## Referência da API 2.0

| Método | Permissão | Resultado |
| --- | --- | --- |
| `playback_state()` | `playback.read` | mídia, posição, volume, velocidade, pitch e estado |
| `playback(action)` | `playback.control` | executa `play_pause`, `stop`, `next` ou `previous` |
| `playlists()` / `active_playlist()` | `library.read` | abas carregadas, itens, rótulos e seleção atual |
| `library_search(query, limit)` | `library.read` | registros da biblioteca inteligente |
| `add_to_playlist(paths, playlist_index=...)` | `library.write` | quantidade adicionada |
| `youtube_music_account()` | `youtube_music.read` | conexão e nome da conta, nunca cookies |
| `youtube_music_search(query, scope=...)` | `youtube_music.read` | resultados normalizados do serviço do player |
| `youtube_music_playlists(limit=...)` | `youtube_music.read` | playlists da conta conectada |
| `youtube_music_playlist(id)` | `youtube_music.read` | conteúdo normalizado de uma playlist |
| `youtube_music_rate`, `youtube_music_create_playlist`, `youtube_music_add_tracks` | `youtube_music.write` | alterações explícitas na conta conectada |
| `resolve_media(path)` | `yt_dlp` | URL reproduzível e metadados; cabeçalhos/cookies não são expostos |
| `yt_dlp_info(path, ...)` | `yt_dlp` | metadados, formatos ou entradas de playlist extraídos pelo yt-dlp gerenciado |
| `yt_dlp_download(path, destino, ...)` | `yt_dlp` + `filesystem.write` | caminhos finais dos arquivos baixados |
| `analyze_media(path)` | `autodj.analyze` | BPM, grade de batidas, confiança, energia e tonalidade |
| `request(...)` | `network` | resposta HTTP limitada a 2 MB |
| `get_setting` / `set_setting` | `settings` | JSON privado e atômico por plugin |
| `notify(message)` | `notifications` | anúncio pelo mecanismo acessível do KeyTune |
| `add_menu_action`, `add_tab`, `add_view` | `ui.*` | contribuição de interface |

Chamadas são síncronas. Plugins `in_process` não devem executar rede, yt-dlp ou análise na thread da interface; use uma thread de trabalho e devolva atualizações de UI pela integração do wxPython. Plugins isolados já fazem RPC a partir do processo separado. Valores retornados são objetos JSON e não expõem instâncias internas mutáveis do player.

Eventos estáveis iniciais são `playback.media_changed` (caminho, título, artista e índice da playlist), `tab.changed` (índice) e `ui.action` (id de uma ação registrada por plugin isolado). O `on_start()` ocorre depois da restauração da sessão, portanto as playlists consultadas nesse ponto já correspondem à interface carregada.

### Biblioteca carregada e YouTube Music

`playlists()` consulta exatamente as playlists e pastas abertas no momento, inclusive itens e rótulos visíveis. `library_search()` usa o banco da Biblioteca inteligente e devolve uma lista vazia quando ela está desativada. A API de YouTube Music reutiliza a sessão e os serviços do KeyTune: o plugin nunca recebe cookies, arquivos de autenticação ou cabeçalhos sensíveis. Avaliar mídia, criar playlists e adicionar faixas exigem a permissão de escrita separada `youtube_music.write`.

### yt-dlp e AutoDJ online

O KeyTune distribui e gerencia o **executável oficial do yt-dlp**, não mantém necessariamente o pacote Python `yt_dlp` importado dentro do processo. Por isso a API não entrega o objeto interno `YoutubeDL`: isso acoplaria plugins a uma dependência opcional e permitiria contornar a validação de opções. Em vez disso, `yt_dlp_info()` e `yt_dlp_download()` são fachadas estáveis sobre o mesmo executável, cookies protegidos e runtimes JavaScript já usados pelo player.

Um plugin downloader pode, portanto, reutilizar o yt-dlp nativo do KeyTune sem empacotar outra cópia:

```python
info = api.yt_dlp_info("https://www.youtube.com/watch?v=...")
files = api.yt_dlp_download(
    "https://www.youtube.com/watch?v=...",
    r"C:\Users\usuario\Videos",
    format_selector="best[ext=mp4]/best",
)
```

Downloads exigem simultaneamente `yt_dlp` e `filesystem.write`. A API aceita seletor de formato, modelo de nome sem componentes de pasta, playlist e limite de itens; argumentos de linha de comando arbitrários não são aceitos. O seletor padrão prefere um MP4 progressivo para não depender de um `ffmpeg.exe` externo. Seletores que combinam vídeo e áudio separados só funcionarão quando um executável FFmpeg compatível estiver disponível.

`resolve_media()` continua sendo a opção apropriada quando o plugin só precisa de uma URL reproduzível. `analyze_media()` aceita arquivo local, URL ou referência do YouTube Music. Para conteúdo online, o KeyTune resolve a mídia, encaminha internamente os cabeçalhos necessários, baixa no máximo 120 MB para uma pasta temporária, decodifica os formatos do YouTube com os codecs FFmpeg empacotados pelo **PyAV** e analisa com **librosa 0.11**. O resultado remoto fica sete dias no cache; o arquivo temporário é removido imediatamente. A análise é limitada aos primeiros 15 minutos para manter uso previsível de memória e CPU.

O librosa fornece rastreamento de batidas, envelope de ataques, RMS e cromagrama. PyAV evita depender de um `ffmpeg.exe` externo e oferece wheels para o build do Windows. Se um formato ainda não puder ser decodificado, a análise falha de modo isolado e a reprodução comum continua funcionando.

## Marketplace no GitHub

O repositório comunitário `keytune-plugins` mantém `catalog.json` com `schema_version: 1` e uma lista `plugins`. Cada entrada contém `id`, `name`, `version`, `description`, `author`, `homepage`, `download_url` HTTPS, `sha256` e `verified`. Autores:

1. publicam o `.ktplugin` em uma GitHub Release;
2. calculam SHA-256 do arquivo final;
3. abrem uma pull request adicionando/atualizando uma entrada;
4. passam pela validação automática de schema, ids únicos, HTTPS, checksum, manifesto e compatibilidade;
5. recebem o selo `verified` somente após revisão humana da procedência.

O cliente baixa o catálogo fora da thread da interface, limita seu tamanho, exige HTTPS, limita pacotes e arquivos extraídos, bloqueia *zip slip*, confere SHA-256 e instala transacionalmente. Novos plugins permanecem desativados até o usuário revisar e aprovar todas as permissões.

## Compatibilidade

O primeiro número de `api_version` é a fronteira incompatível. Como a plataforma ainda está na mesma pull request e não houve uma API 2.0 publicada, estes métodos fazem parte diretamente do contrato 2.0 — não existe um bump artificial para 2.1. Depois da primeira publicação, novos métodos e eventos em versões menores serão aditivos. APIs só serão removidas em uma versão principal, após aviso de depreciação. Plugins devem ignorar eventos e campos desconhecidos. Dados privados ficam em uma pasta por id e nunca devem depender da estrutura interna do player.

## Diagnóstico e distribuição

Falhas são registradas separadamente em `plugin-logs/<id>.log`. O pacote instalado fica em `plugins/<id>` e o estado/consentimento em `plugins/registry.json`. Não inclua segredos no manifesto ou pacote. Releases devem ser imutáveis: publique uma nova versão em vez de substituir um arquivo já catalogado.
