---
description: "Use when writing or editing the manual, CHANGELOG, release notes, user-facing docs, commit messages, PR titles or descriptions in the KeyTune project."
name: "Writing Guide"
---
# KeyTune Writing Guide

How to write the manual, changelog, release notes and commits. One rule underneath everything: **write for the person reading, with what they need to know, in the order they need it.** The rest follows from that.

| Type | Language | Reader |
| --- | --- | --- |
| Manual (`docs/manual.md`), changelog (`CHANGELOG.md`), release notes, UI text | Portuguese (source language; translations come from the catalog, see `i18n.instructions.md`) | People using KeyTune, often with a screen reader |
| Commits, PRs, issues, code comments | English | People maintaining the project |

Examples of manual and changelog text below stay in Portuguese because that is what ships.

## 1. Sound human

Text that "sounds like AI" is vague, padded and predictable. The fix is to be specific and short.

**Tone: objective, but written for a person.** Short does not mean curt. Write the way you would explain it to a colleague sitting next to you: a connecting phrase ("agora dá para...", "então você pode continuar ouvindo", "vale aceitar") is fine when it carries information or gives the text a natural rhythm. Put the reason next to the rule ("é o que permite converter a qualidade"), so the reader can decide. A bare list of facts reads cold; a padded paragraph reads fake. Aim between the two.

**Do**
- Say what happens, using the real name of the thing: "`Ctrl+E` abre o explorador de pastas", not "an improved navigation experience".
- Use plain verbs: *usar*, not *utilizar* or *alavancar*; *mudar*, not *promover uma transformação*.
- Vary sentence length. A short sentence after a long one helps the ear, and screen reader users read with their ears.
- State the limit or exception when there is one ("no máximo 200 itens", "transmissões ao vivo não são baixadas"). It is usually what the reader wants most.
- Talk to the reader ("você") in the active voice: "O KeyTune pergunta a pasta", not "A pasta é solicitada".

**Avoid**
- Empty openers: "No cenário atual...", "É importante ressaltar que...", "Vale destacar...".
- Sales adjectives: *robusto, poderoso, incrível, perfeito, fluido, intuitivo, de ponta, completo*. If it is true, show the fact.
- The "not just X, it's Y" mold and the reflexive triple ("rápido, simples e seguro").
- Closers that repeat what was just said ("Em resumo...", "Com isso, você...").
- An em dash in every sentence and bold on every line. Bold is for interface item names, nothing else.
- Emoji, exclamation marks, "agora você pode" on everything.
- Promises the code does not keep. Check in the app before writing.

**Quick test.** Reread and ask, sentence by sentence: "does this tell the reader something they did not know or need to be reminded of?" If not, cut it. Then read it aloud; if you would not say it that way to a colleague, rewrite it.

| Instead of | Write |
| --- | --- |
| Foi implementada uma funcionalidade robusta de download | `Ctrl+Shift+B` baixa músicas e vídeos do YouTube |
| Melhorias de desempenho em diversas áreas | O explorador não trava mais ao abrir pastas de rede fora do ar |
| Agora você pode converter seus arquivos com facilidade | `Ctrl+Shift+K` converte áudio e vídeo entre formatos |
| Corrigido um problema que afetava alguns usuários | Corrigido: `Ctrl+V` não reconhecia arquivos copiados com `Ctrl+C` |

## 2. Manual

The manual is for lookup, not for reading cover to cover. Whoever opens it wants to do one thing right now.

- **One section, one task.** Title it with what the person wants to do ("Baixar uma playlist do YouTube"), not with the internal feature name.
- **What it is first, steps second.** One or two sentences of context at most.
- **Numbered steps, one verb each.** One action per step. The condition comes before the action: "Se a pasta não existir, escolha outra."
- **Shortcut first, menu second**, always both: "Pressione `Ctrl+Shift+B` (ou **Arquivo > Baixar do YouTube**)." KeyTune is keyboard-first; readers should find the shortcut without hunting.
- **Say what the reader will hear or see** at the end when it helps confirm the result: "O KeyTune anuncia o resumo com o que deu certo e o que falhou."
- **Interface names exactly as on screen**, in bold, same spelling. When the UI text changes, the manual changes in the same commit.
- **Tables for shortcuts**, lists for options, paragraphs for explanation. No long block of text in the middle of a procedure.
- **Troubleshooting** as "symptom, cause, what to do".
- **No history patches.** The manual describes the app as it is now. "It used to work like this" belongs in the changelog.
- **Think of the screen reader:** no "click here", no "as shown above", no information carried only by color, image or position. Headings in order, no skipped levels.

Section template:

```markdown
### Baixar músicas e vídeos do YouTube

Você pode salvar no computador uma música ou um vídeo que encontrou na aba KeyTube, em áudio ou em vídeo.

1. Selecione o item na lista.
2. Pressione `Ctrl+Shift+B` (ou use **Arquivo > Baixar do YouTube**).
3. Escolha áudio ou vídeo, a qualidade e a pasta, e confirme.

O download acontece em segundo plano e o KeyTune avisa quando termina, então você pode continuar ouvindo ou usando o player. Se a qualidade que você escolheu não existir, ele baixa na original e informa. Para saber o andamento ou cancelar, pressione `Ctrl+Shift+B` de novo durante o download.

Se o KeyTune avisar que não encontrou o FFmpeg, vale aceitar o download dele: é o que permite converter a qualidade. Se você recusar, o arquivo ainda é baixado, só que na qualidade original.
```

## 3. Changelog

Format: [Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/). The changelog is for humans: it answers "what changes for me if I update?"

**Structure** (already used in `CHANGELOG.md`)
- A `## [Não lançado]` section on top, newest versions first, dates as `YYYY-MM-DD`.
- Groups: **Adicionado**, **Alterado**, **Obsoleto**, **Removido**, **Corrigido**, **Segurança**. Only the ones that have entries.
- One entry per change the user notices. Internal refactors, tests and CI stay out unless they change something visible.

**Writing each entry**
- Start with what the user sees or does, not what the code does.
- Short bold name, colon, and one to three sentences: what changed, how to use it (shortcut or menu) and the relevant limit.
- **Adicionado**: what the feature does and where it is. **Alterado**: give the old and the new behavior, because people used to the old one need to know what moved. **Removido**: say what to use instead. **Corrigido**: describe the symptom the person saw, not the internal cause.
- Breaking changes (a shortcut that moved, a setting that vanished) go under **Alterado** or **Removido**, and the sentence says what to do.
- An entry that runs too long is probably two entries. If it passes about five lines, split it or move the detail to the manual.

**Examples**

```markdown
### Adicionado

- **Explorador de pastas**: agora dá para navegar pelas pastas do computador sem sair do KeyTune. Pressione `Ctrl+E` e uma lista com as pastas e os arquivos de mídia aparece ao lado das abas. `Enter` entra na pasta ou toca o arquivo, e `Shift+Enter` adiciona à playlist sem interromper o que está tocando.
- **Download do YouTube**: `Ctrl+Shift+B` baixa músicas e vídeos do YouTube e do YouTube Music para o seu computador. Se já existir um arquivo com o mesmo nome na pasta, ele é mantido, e transmissões ao vivo não podem ser baixadas.

### Alterado

- **Abrir e colar ficaram iguais**: `Ctrl+O` e `Ctrl+V` agora põem a mídia na playlist atual e já tocam. Antes, `Ctrl+O` trocava a playlist inteira pelos arquivos escolhidos. Se você prefere uma lista separada, abra uma com `Ctrl+T` e abra ou cole nela.

### Corrigido

- **Colar arquivos copiados**: `Ctrl+V` não reconhecia arquivos copiados com `Ctrl+C` e respondia que a área de transferência estava vazia. Agora funciona.
```

**GitHub release notes** are that version's `CHANGELOG.md` section, copied. The update dialog shows this text, so it has to make sense on its own. See `update-release.instructions.md` for the flow.

## 4. Commits, PRs and issues (English)

Format: [Conventional Commits](https://www.conventionalcommits.org/) plus the classic Git message rules.

```
<type>(<scope>): <summary>

<body: what and why, wrapped at 72 columns>

<footer: BREAKING CHANGE, Closes #123>
```

**Subject line**
- Imperative mood, lowercase, no trailing period: `add folder explorer`, not `added` or `adds`. Tip: complete "If applied, this commit will ___".
- 50 characters as a goal, 72 as the ceiling.
- Say what changes for the project, not what you did: `fix paste of files copied in Explorer`, not `fix bug`.

**Types**: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`. Use `feat` and `fix` only for changes the user notices.

**Scopes** (already in the history): `ui`, `youtube`, `radio`, `library`, `playback`, `update`, `i18n`, `docs`. Reuse before inventing.

**Body**: optional, but use it when the *why* is not obvious. Explain the motivation, the decision and what was left out. The *how* is in the diff. One change, one commit; if the subject needs an "and", it is probably two commits.

**Footer**: `BREAKING CHANGE: <what breaks and what to do>` or `!` after the type (`feat(ui)!:`). References: `Closes #123`.

**Examples**

```
feat(youtube): add channel and artist navigation in search results

Right arrow opens a channel, artist, album or playlist in the same
list. Backspace returns to the previous list.
```

```
fix(playlist): accept files copied in Windows Explorer on paste

Ctrl+V only read text from the clipboard and reported it as empty
after Ctrl+C on a playlist item.
```

```
refactor(frames): split the commands mixin into focused sub-mixins
```

```
docs: document the folder explorer shortcuts in the manual
```

**Avoid**: `fix stuff`, `update code`, `WIP`, `address review comments`, one-word messages, and subjects that only repeat a file name.

**PRs**: title like a good commit subject. Short description with *what changed*, *why* and *how to test* (shortcuts and flows to walk through with a screen reader). No filler.

## 5. Checklist before publishing

- [ ] Does the text say something specific (shortcut, menu, limit) instead of praising the feature?
- [ ] Does it read like a person explaining, not a bare list of facts and not a padded pitch?
- [ ] Do interface names match the screen?
- [ ] Does each manual step hold one action, and can it be followed with the keyboard alone?
- [ ] Does the changelog entry say what changes for the user, and what to do if something broke?
- [ ] Are new strings wrapped in `_()` and the catalog updated (`python scripts/i18n.py extract` then `compile`)?
- [ ] Is the commit in English, imperative, with type and scope?

## Sources

- [Keep a Changelog](https://keepachangelog.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Google developer documentation style guide](https://developers.google.com/style)
- [Semantic Versioning](https://semver.org/)
