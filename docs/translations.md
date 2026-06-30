# Traduzindo o KeyTune

O KeyTune usa o sistema de tradução padrão do Python (GNU `gettext`). O idioma
em que o código é escrito — **Português (Brasil)** — é o *idioma-fonte*: cada
texto visível ao usuário aparece em Português dentro do código, e as traduções
para outros idiomas ficam em catálogos separados, sob `locale/`.

Isso significa que **você não precisa mexer no código** para adicionar um idioma:
basta criar um catálogo de tradução.

## Estrutura

```
locale/
  keytune.pot                      # modelo com todos os textos do programa
  en/LC_MESSAGES/keytune.po        # tradução para inglês (texto editável)
  en/LC_MESSAGES/keytune.mo        # versão compilada que o app carrega
```

- `.pot` — modelo gerado a partir do código. Não traduza este arquivo; use-o
  como base para criar um novo idioma.
- `.po` — o arquivo que você edita, com cada `msgid` (texto-fonte em Português)
  e seu `msgstr` (sua tradução).
- `.mo` — versão binária compilada do `.po`. É o que o aplicativo lê em tempo de
  execução, então **precisa ser recompilada** sempre que o `.po` muda.

## Adicionando um novo idioma

1. Registre o idioma em `src/player/i18n.py`, no dicionário `SUPPORTED_LANGUAGES`
   (código do idioma → nome nativo). Use códigos como `en`, `es`, `fr`, `pt_BR`.
2. Atualize o modelo a partir do código atual:

   ```
   python scripts/i18n.py extract
   ```

3. Copie `locale/keytune.pot` para `locale/<idioma>/LC_MESSAGES/keytune.po` e
   traduza cada `msgstr`. Deixe `msgstr ""` em branco para os textos que ainda
   não traduziu — o app cai de volta no Português automaticamente.
4. Compile os catálogos:

   ```
   python scripts/i18n.py compile
   ```

5. Abra o KeyTune, vá em *Configurações > Preferências > Geral > Idioma* e
   escolha o novo idioma (a mudança vale na próxima abertura do app).

## Dicas para traduzir

- **Aceleradores de menu** (`&`): o `&` marca a tecla de atalho do menu
  (ex.: `&Arquivo` → Alt+A). Mantenha um `&` na sua tradução, de preferência em
  uma letra única dentro de cada menu.
- **Atalhos após tabulação** (`\t`): em textos como `Salvar\tCtrl+S`, a parte
  após o `\t` é o atalho exibido. **Não traduza nem altere** o atalho.
- **Marcadores `{...}`**: textos como `Sobre o {app}` ou `Página {current} de
  {total}` contêm campos preenchidos pelo programa. Mantenha os nomes entre
  chaves exatamente como estão; só reordene se fizer sentido no seu idioma.
- **Quebras de linha** (`\n`): preserve as quebras de linha do texto-fonte.

## Manual, créditos e instalador

- **Manual**: crie `docs/manual.<idioma>.md` (ex.: `docs/manual.en.md`). O build
  o renderiza para `manual.<idioma>.html` e o app abre essa versão quando o
  idioma correspondente está ativo, caindo de volta no manual em Português se a
  tradução não existir.
- **Créditos**: as listas de bibliotecas e contribuidores são neutras; só os
  títulos são traduzidos. Adicione o idioma em `CREDITS_STRINGS`, em
  `scripts/generate_credits.py`, e gere com
  `python scripts/generate_credits.py --language <idioma>`.
- **Instalador**: adicione o idioma em `[Languages]` e traduza as entradas de
  `[CustomMessages]` em `installer/keytune.iss` (os textos do assistente vêm
  prontos dos arquivos `.isl` do Inno Setup).

## Ferramenta `scripts/i18n.py`

Não depende de `xgettext`/`msgfmt` instalados — é Python puro:

- `python scripts/i18n.py extract` — varre `src/` e reescreve
  `locale/keytune.pot`.
- `python scripts/i18n.py compile` — compila todos os `locale/**/keytune.po` em
  `.mo`. O build de release também roda isso automaticamente.
