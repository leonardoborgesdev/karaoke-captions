---
name: legenda-karaoke-reels
description: Como funciona e como replicar em outro PC o sistema de legenda estilo karaokê (palavra atual destacada em cor, fonte Archivo Black, 2 linhas centralizadas) usado nos reels do canal de repositórios GitHub. Use quando o usuário pedir pra mexer na legenda, trocar cor de destaque, trocar fonte, ou montar esse mesmo pipeline em outra máquina.
---

# Legenda karaokê para reels (destaque de palavra por palavra)

Sistema usado nos vídeos do canal de reels de repositórios GitHub (@borges.devv e afins):
uma legenda que aparece centralizada, quebrada em até 2 linhas, com a palavra que está
sendo falada naquele instante destacada em cor diferente das outras — efeito "karaokê".

Isso é gerado como um arquivo `.ass` (Advanced SubStation Alpha) e queimado no vídeo
via filtro `ass=` do ffmpeg (libass). Não é legenda "de player" (.srt) — fica
embutida no vídeo final, pixel a pixel.

## Peças do sistema

1. **Transcrição com timestamp por palavra** — `faster-whisper`, modelo `base`
   (NUNCA usar `small` no Windows/CPU, trava minutos), `word_timestamps=True`,
   `vad_filter=True`. Cada palavra sai com `start`/`end` em segundos.

2. **Fonte** — Archivo Black (Google Fonts, licença OFL), porque no Linux/VPS não
   existe Arial Black. Baixar direto de:
   `https://raw.githubusercontent.com/google/fonts/main/ofl/archivoblack/ArchivoBlack-Regular.ttf`
   e instalar em `/usr/share/fonts/truetype/custom/` + `fc-cache -f` (Linux) ou
   instalar normalmente no Windows (clicar duas vezes no .ttf → Instalar).

3. **Geração do `.ass`** — função `build_ass(words, out_path)` (em `pipeline_remoto.py`):
   - Agrupa as palavras em blocos ("chunks") de até 6 palavras, ou fecha o bloco
     antes se bater pontuação (`.`, `,`, `!`, `?`) e já tiver 3+ palavras.
   - Se o bloco tem mais de 4 palavras, quebra em 2 linhas (`\N`) na metade.
   - Pra cada palavra do bloco, gera uma linha `Dialogue` separada, com
     `start`/`end` = o tempo daquela palavra específica. Nessa linha, TODAS as
     palavras do bloco aparecem, mas só a palavra da vez fica na cor de destaque
     (as outras ficam brancas) — isso cria a ilusão de "andar" a cor palavra por
     palavra conforme a fala avança.
   - Posição fixa: `\pos(540,1345)` (centro horizontal da tela 1080px, ~70% da
     altura numa tela 1920px vertical).

4. **Estilo ASS** (cabeçalho do arquivo):
   ```
   Style: Cap,Archivo Black,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,50,1
   ```
   Campos relevantes: fonte `Archivo Black`, tamanho `72`, cor primária branca
   (`&H00FFFFFF`), contorno preto (`Outline=4`), sombra (`Shadow=3`),
   `Alignment=5` (centralizado), `BorderStyle=1`.

5. **Cor de destaque** — hoje fixa em roxo `&H00EA3393` (variável `PURPLE` no
   código). Formato ASS de cor é `&HAABBGGRR` (alpha-blue-green-red, ordem
   INVERTIDA do RGB normal, sem `#`). Pra trocar a cor, converte o hex RGB
   desejado (`#RRGGBB`) pra esse formato: pega os bytes e inverte a ordem,
   prefixa com `&H00`. Ex: roxo `#EA3393` vira `&H00EA3393`... só que como
   BGR, na real fica `&H00` + `BB` + `GG` + `RR` = `93` `33` `EA` →
   `&H0093 33EA`. **Cuidado**: sempre inverter R e B, é o erro mais comum.

6. **Composição final** — o filtro `ass={ass_path}` é aplicado por ÚLTIMO na
   cadeia do `filter_complex`, depois de todos os overlays (círculo do avatar,
   corte em tela cheia, borda), garantindo que a legenda sempre fique por cima
   de tudo.

## Como replicar em outro PC do zero

1. Instalar `ffmpeg` com suporte a `libass` (build padrão já vem com isso na
   maioria dos casos — testar com `ffmpeg -filters | grep ass`).
2. Instalar Python 3.10+ e `pip install faster-whisper`.
3. Baixar e instalar a fonte Archivo Black (link acima).
4. Copiar a função `build_ass()` de `pipeline_remoto.py` neste repositório.
5. Fluxo mínimo pra testar isolado:
   ```python
   from faster_whisper import WhisperModel
   model = WhisperModel("base", device="cpu", compute_type="int8")
   segments, _ = model.transcribe("audio.wav", language="pt", word_timestamps=True, vad_filter=True)
   words = [{"word": w.word.strip(), "start": w.start, "end": w.end} for seg in segments for w in seg.words]
   build_ass(words, "captions.ass")
   # depois:
   # ffmpeg -i video.mp4 -vf "ass=captions.ass" -c:a copy saida.mp4
   ```

## Erros comuns (já caímos nesses)

- **`\N` de quebra de linha em Python**: nunca escrever `\N` literal numa string
  Python normal — `\N{...}` é sintaxe de escape Unicode e quebra. Usar
  `chr(92) + "N"` pra montar o backslash na mão.
- **Cor errada**: lembrar que ASS usa BGR, não RGB. Testar sempre num trecho
  curto antes de rodar o vídeo inteiro.
- **Fonte não aplica**: se a fonte não estiver instalada no sistema (não só na
  pasta do projeto), o `ass=` filter cai silenciosamente pra uma fonte padrão
  feia sem avisar erro nenhum. Sempre confirmar com `fc-list | grep -i archivo`
  (Linux) que a fonte está de fato instalada no SO.
- **Legenda em cima de tudo**: se aplicar o filtro `ass=` antes de outros
  overlays (círculo, avatar em tela cheia), a legenda fica escondida atrás
  deles. Sempre aplicar por último na cadeia.
